import base64
import io
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests as http

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

from agent import generate_overview, send_message, send_message_with_overview, _filter_docs, detect_company_intent  # noqa: E402
from scraping import COMPANIES, fetch_pdf_bytes, find_pdf_links, sanitize_filename, discover_company, identify_company_from_url

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

app = FastAPI(title="Mining AI Analyst")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    supabase.table("companies").select("id").limit(1).execute()
    return {"status": "ok", "supabase_connected": True}


@app.get("/companies")
def list_companies():
    return list({**COMPANIES, **dynamic_companies}.keys())


@app.get("/analyzed-companies")
def analyzed_companies():
    rows = supabase.table("company_overviews").select("company_name, generated_at").order("generated_at", desc=True).execute()
    return [r["company_name"] for r in (rows.data or [])]


@app.get("/companies/{company_name}/overview")
def get_cached_overview(company_name: str):
    row = supabase.table("company_overviews").select("*").eq("company_name", company_name).limit(1).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="No cached report")
    return row.data[0]


@app.get("/companies/{company_name}/documents")
def get_documents(company_name: str):
    if company_name not in COMPANIES and company_name not in dynamic_companies:
        raise HTTPException(status_code=404, detail="Unknown company")
    return find_pdf_links(company_name, dynamic_companies)


class DownloadRequest(BaseModel):
    documents: dict[str, str]  # label -> url


# In-memory job tracking — fine for a single local dev server, not for
# multi-worker/production deployment (state wouldn't be shared).
download_jobs: dict[str, dict] = {}


def run_download_job(job_id: str, company_name: str, documents: dict[str, str]):
    job = download_jobs[job_id]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for label, url in documents.items():
            try:
                pdf_bytes = fetch_pdf_bytes(url)
                zf.writestr(f"{sanitize_filename(label)}.pdf", pdf_bytes)
            except Exception:
                pass
            job["completed"] += 1
    buffer.seek(0)
    job["zip_bytes"] = buffer.getvalue()
    job["zip_name"] = sanitize_filename(company_name) + ".zip"
    job["status"] = "done"


@app.post("/companies/{company_name}/documents/download/start")
def start_download(company_name: str, payload: DownloadRequest, background_tasks: BackgroundTasks):
    if company_name not in COMPANIES:
        raise HTTPException(status_code=404, detail="Unknown company")
    if not payload.documents:
        raise HTTPException(status_code=400, detail="No documents selected")

    job_id = str(uuid.uuid4())
    download_jobs[job_id] = {"total": len(payload.documents), "completed": 0, "status": "running"}
    background_tasks.add_task(run_download_job, job_id, company_name, payload.documents)
    return {"job_id": job_id}


@app.get("/jobs/{job_id}/status")
def job_status(job_id: str):
    job = download_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    return {"completed": job["completed"], "total": job["total"], "status": job["status"]}


@app.get("/jobs/{job_id}/download")
def job_download(job_id: str):
    job = download_jobs.get(job_id)
    if job is None or job["status"] != "done":
        raise HTTPException(status_code=404, detail="Job not ready")
    return StreamingResponse(
        io.BytesIO(job["zip_bytes"]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{job["zip_name"]}"'},
    )


overview_jobs: dict[str, dict] = {}
dynamic_companies: dict[str, dict] = {}  # populated at runtime via chat intent


def _save_overview(company_name: str, overview_md: str, current_urls: list[str]):
    now = datetime.now(timezone.utc).isoformat()
    existing = supabase.table("company_overviews").select("id").eq("company_name", company_name).limit(1).execute()
    if existing.data:
        supabase.table("company_overviews").update({
            "overview_markdown": overview_md,
            "source_urls": current_urls,
            "generated_at": now,
        }).eq("company_name", company_name).execute()
    else:
        supabase.table("company_overviews").insert({
            "company_name": company_name,
            "overview_markdown": overview_md,
            "source_urls": current_urls,
        }).execute()


def run_overview_job(job_id: str, company_name: str, pdf_docs: dict, current_urls: list[str], crawl_url: str | None = None):
    job = overview_jobs[job_id]

    def on_progress(info: dict):
        job.update(info)

    try:
        if crawl_url:
            job["label"] = "Crawling investor pages..."
            discovered = discover_company(company_name, base_url=crawl_url)
            if discovered:
                dynamic_companies[company_name] = discovered
                result = find_pdf_links(company_name, dynamic_companies)
                pdf_docs = result["documents"]
                current_urls = sorted(pdf_docs.values())
                job["pdfs"] = list(pdf_docs.keys())
                job["pdf_urls"] = dict(pdf_docs)
                job["total"] = len(pdf_docs)
            else:
                job["status"] = "error"
                job["error"] = "Could not find investor documents for this company."
                return

        if job.get("status") == "cancelled":
            return

        overview_md = generate_overview(company_name, pdf_docs, on_progress, dynamic_companies)
        _save_overview(company_name, overview_md, current_urls)
        job["status"] = "done"
        job["overview_markdown"] = overview_md
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


@app.post("/companies/{company_name}/overview/start")
def start_overview(company_name: str, background_tasks: BackgroundTasks, force: bool = False):
    from urllib.parse import urlparse

    # Determine if a fresh crawl is needed (dynamic company not in memory)
    needs_crawl = False
    crawl_url = None
    if company_name not in COMPANIES:
        company_info = dynamic_companies.get(company_name, {})
        if not company_info.get("investor_pages"):
            # Server restarted or placeholder — recover base_url from Supabase source_urls
            crawl_url = company_info.get("base_url")
            if not crawl_url:
                cached = supabase.table("company_overviews").select("source_urls").eq("company_name", company_name).limit(1).execute()
                if cached.data and cached.data[0].get("source_urls"):
                    first_url = cached.data[0]["source_urls"][0]
                    p = urlparse(first_url)
                    crawl_url = f"{p.scheme}://{p.netloc}"
                else:
                    raise HTTPException(status_code=404, detail="Unknown company — paste the URL in chat to analyze")
            dynamic_companies[company_name] = {"base_url": crawl_url, "investor_pages": [], "about_pages": [], "news_page": "/news/"}
            needs_crawl = True

    if needs_crawl:
        pdf_docs, current_urls, pdf_list, selected_pdfs = {}, [], [], []
    else:
        result = find_pdf_links(company_name, dynamic_companies)
        pdf_docs = result["documents"]
        current_urls = sorted(pdf_docs.values())
        pdf_list = list(pdf_docs.keys())
        selected_pdfs = list(_filter_docs(pdf_docs).keys())

        if not force:
            existing = supabase.table("company_overviews").select("*").eq("company_name", company_name).limit(1).execute()
            if existing.data and sorted(existing.data[0]["source_urls"]) == current_urls:
                return {
                    "cached": True,
                    "overview_markdown": existing.data[0]["overview_markdown"],
                    "pdfs": pdf_list,
                    "selected_pdfs": selected_pdfs,
                }

    job_id = str(uuid.uuid4())
    overview_jobs[job_id] = {
        "status": "running",
        "step": "reading",
        "label": "Starting...",
        "current": 0,
        "total": len(pdf_docs),
        "pdfs": pdf_list,
        "selected_pdfs": selected_pdfs,
        "pdf_urls": pdf_docs,
    }
    background_tasks.add_task(run_overview_job, job_id, company_name, pdf_docs, current_urls, crawl_url)
    return {"job_id": job_id, "pdfs": pdf_list, "selected_pdfs": selected_pdfs, "pdf_urls": pdf_docs, "cached": False}


@app.delete("/companies/{company_name}/overview")
def delete_overview(company_name: str):
    supabase.table("company_overviews").delete().eq("company_name", company_name).execute()
    return {"deleted": company_name}


@app.post("/companies/{company_name}/overview/archive")
def archive_overview(company_name: str):
    row = supabase.table("company_overviews").select("*").eq("company_name", company_name).limit(1).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="No report found to archive")
    existing = row.data[0]
    # Find next available archive number
    base = f"_{company_name} [archived"
    all_names = [r["company_name"] for r in supabase.table("company_overviews").select("company_name").like("company_name", f"{base}%").execute().data or []]
    # Extract existing numbers: [archived] = 1, [archived 2] = 2, etc.
    used = set()
    for n in all_names:
        suffix = n[len(base):]  # e.g. "]" or " 2]"
        if suffix == "]":
            used.add(1)
        elif suffix.startswith(" ") and suffix.endswith("]"):
            try:
                used.add(int(suffix[1:-1]))
            except ValueError:
                pass
    num = 1
    while num in used:
        num += 1
    archived_name = f"_{company_name} [archived]" if num == 1 else f"_{company_name} [archived {num}]"
    supabase.table("company_overviews").insert({
        "company_name": archived_name,
        "overview_markdown": existing["overview_markdown"],
        "source_urls": existing["source_urls"],
        "generated_at": existing["generated_at"],
    }).execute()
    return {"archived_as": archived_name}


@app.get("/overview-jobs/{job_id}")
def get_overview_job(job_id: str):
    job = overview_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/overview-jobs/{job_id}/cancel")
def cancel_overview_job(job_id: str):
    job = overview_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "running":
        job["status"] = "cancelled"
    return {"status": job["status"]}


class ChatRequest(BaseModel):
    message: str
    documents: dict[str, str] = {}  # only needed on the first message of a conversation
    session_id: str | None = None


_URL_RE = re.compile(r"https?://[^\s]+")


@app.post("/chat")
def chat(payload: ChatRequest, background_tasks: BackgroundTasks):
    # Extract URL if present
    url_match = _URL_RE.search(payload.message)
    provided_url = url_match.group(0).rstrip(".,)/\\ ") if url_match else None

    # Check if user wants to analyze a specific company
    try:
        company_name = detect_company_intent(payload.message)
    except Exception:
        company_name = None

    # URL provided but no company name detected — identify from URL
    if not company_name and provided_url:
        company_name = identify_company_from_url(provided_url)

    if company_name:

        # Check cache by exact name first, then fall back to domain match if a URL was provided
        cached_data = supabase.table("company_overviews").select("*").eq("company_name", company_name).limit(1).execute().data
        if not cached_data and provided_url:
            domain = re.sub(r"https?://(?:www\.)?", "", provided_url).split("/")[0]
            all_rows = supabase.table("company_overviews").select("*").not_.like("company_name", "_%").execute().data or []
            for row in all_rows:
                if any(domain in u for u in (row.get("source_urls") or [])):
                    cached_data = [row]
                    company_name = row["company_name"]
                    break

        if cached_data:
            overview_md = cached_row.data[0]["overview_markdown"]
            generated_at = cached_row.data[0]["generated_at"][:10]  # date only
            reply, session_id = send_message_with_overview(payload.message, overview_md, company_name, payload.session_id)
            encoded = company_name.replace(" ", "%20")
            return {
                "reply": reply,
                "session_id": session_id,
                "company": company_name,
                "cached": True,
                "report_url": f"/companies/{encoded}",
                "generated_at": generated_at,
            }

        all_companies = {**COMPANIES, **dynamic_companies}
        if company_name not in all_companies:
            if not provided_url:
                reply = f"I couldn't find investor information for **{company_name}**. Please paste the company's investor relations URL."
                return {"reply": reply, "session_id": payload.session_id}
            # Register a placeholder so the job can start immediately
            dynamic_companies[company_name] = {"base_url": provided_url.rstrip("/"), "investor_pages": [], "about_pages": [], "news_page": "/news/"}
            all_companies = {**COMPANIES, **dynamic_companies}

        # No cache — start overview job in background (crawl happens inside the job)
        company_info = all_companies[company_name]
        base_url = company_info.get("base_url", provided_url or "")
        needs_crawl = not company_info.get("investor_pages") and provided_url
        if needs_crawl:
            pdf_docs = {}
            current_urls = []
            selected_pdfs = []
        else:
            result = find_pdf_links(company_name, dynamic_companies)
            pdf_docs = result["documents"]
            current_urls = sorted(pdf_docs.values())
            selected_pdfs = list(_filter_docs(pdf_docs).keys())
        job_id = str(uuid.uuid4())
        overview_jobs[job_id] = {
            "status": "running", "step": "reading", "label": "Starting...",
            "current": 0, "total": len(pdf_docs), "pdfs": list(pdf_docs.keys()),
            "selected_pdfs": selected_pdfs, "pdf_urls": dict(pdf_docs),
        }
        background_tasks.add_task(run_overview_job, job_id, company_name, pdf_docs, current_urls, provided_url if needs_crawl else None)
        encoded = company_name.replace(" ", "%20")
        reply = (
            f"Starting analysis of **{company_name}**. "
            f"Website: {base_url}\n\n"
            f"Found {len(pdf_docs)} documents ({len(selected_pdfs)} selected for analysis). "
            f"This will take 3-4 minutes.\n\n"
            f"[View live progress here](/companies/{encoded}?job={job_id})"
        )
        return {"reply": reply, "session_id": payload.session_id, "job_id": job_id, "company": company_name}

    try:
        reply, session_id = send_message(payload.message, payload.documents, payload.session_id)
    except Exception as e:
        msg = str(e)
        if "503" in msg or "502" in msg:
            reply = "The AI service is temporarily unavailable (Gemini 503). Please try again in a moment."
        elif "timed out" in msg.lower() or "timeout" in msg.lower():
            reply = "The request timed out. Please try again."
        else:
            reply = f"Something went wrong: {msg}"
        return {"reply": reply, "session_id": payload.session_id}
    return {"reply": reply, "session_id": session_id}


chart_jobs: dict[str, dict] = {}
chart_cache: dict[str, list] = {}  # company_name → extracted chart list


def _is_pie_or_bar_chart(img_bytes: bytes) -> bool:
    """Ask Gemini vision whether a page image contains a pie or bar chart."""
    key = os.environ["GEMINI_API_KEY"]
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(img_bytes).decode()}},
                {"text": "Does this page contain a pie chart or bar chart? Answer only 'yes' or 'no'."},
            ],
        }]
    }
    try:
        resp = http.post(
            GEMINI_URL,
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if not resp.ok:
            return False
        answer = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
        return answer.startswith("yes")
    except Exception:
        return False


def run_chart_job(job_id: str, company_name: str, source_urls: list):
    import fitz

    # Only scan presentation-like PDFs — filter by path OR filename keywords
    _PRES_KEYWORDS = ("presentation", "deck", "corporate", "investor", "conference", "fact-sheet", "factsheet", "merger")
    def _is_presentation(url: str) -> bool:
        lower = url.lower()
        return "/presentations/" in lower or any(kw in lower for kw in _PRES_KEYWORDS)
    presentation_urls = [u for u in source_urls if _is_presentation(u)]

    job = chart_jobs[job_id]
    charts = []
    job["total"] = len(presentation_urls)

    for i, url in enumerate(presentation_urls):
        raw_name = url.split("/")[-1].split("?")[0].replace(".pdf", "")
        job["current"] = i + 1
        job["label"] = raw_name
        try:
            pdf_bytes = fetch_pdf_bytes(url)
            fitz_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_num in range(len(fitz_doc)):
                pix = fitz_doc[page_num].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                img_bytes = pix.tobytes("png")
                if _is_pie_or_bar_chart(img_bytes):
                    charts.append({
                        "document": raw_name,
                        "page": page_num + 1,
                        "image": base64.b64encode(img_bytes).decode(),
                    })
            fitz_doc.close()
        except Exception as e:
            print(f"Chart extraction error for {url}: {e}")

    chart_cache[company_name] = charts
    job["status"] = "done"
    job["charts"] = charts


@app.post("/companies/{company_name}/charts/start")
def start_chart_extraction(company_name: str, background_tasks: BackgroundTasks):
    if company_name in chart_cache:
        return {"cached": True, "charts": chart_cache[company_name]}
    row = supabase.table("company_overviews").select("source_urls").eq("company_name", company_name).limit(1).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="No report found for this company")
    job_id = str(uuid.uuid4())
    chart_jobs[job_id] = {"status": "running", "current": 0, "total": 0, "label": "Starting..."}
    unique_urls = list(dict.fromkeys(row.data[0]["source_urls"]))
    background_tasks.add_task(run_chart_job, job_id, company_name, unique_urls)
    return {"cached": False, "job_id": job_id}


@app.get("/companies/{company_name}/charts/jobs/{job_id}")
def get_chart_job(job_id: str):
    job = chart_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent / "static", html=True), name="static")
