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
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

from agent import generate_overview, send_message, send_message_with_overview, _filter_docs, detect_company_intent  # noqa: E402
from extractor import run_extraction
from scraping import COMPANIES, fetch_pdf_bytes, find_pdf_links, sanitize_filename, discover_company, identify_company_from_url, discover_news_release_pdfs

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
    completed = [r["company_name"] for r in (rows.data or [])]
    # Prepend actively-running companies so they appear in the sidebar during analysis
    active = [name for name in active_jobs_by_company if name not in completed]
    return active + completed


@app.get("/companies/{company_name}/overview")
def get_cached_overview(company_name: str):
    from urllib.parse import unquote
    row = supabase.table("company_overviews").select("*").eq("company_name", company_name).limit(1).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="No cached report")
    data = row.data[0]
    # Compute which URLs were actually selected (fed to Gemini) by re-running the filter
    source_urls = data.get("source_urls") or []
    pdf_docs = {}
    for url in source_urls:
        raw = unquote(url.split("/")[-1])  # keep query string so SEDAR ids stay unique
        label = raw[:-4] if raw.lower().endswith(".pdf") else raw
        if label:
            pdf_docs[label] = url
    data["selected_urls"] = source_urls
    return data


@app.get("/companies/{company_name}/documents")
def get_documents(company_name: str):
    if company_name not in COMPANIES and company_name not in dynamic_companies:
        raise HTTPException(status_code=404, detail="Unknown company")
    return find_pdf_links(company_name, dynamic_companies)


def _company_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")


def _list_all_storage_paths(prefix: str) -> list[str]:
    """Recursively list all file paths under a storage prefix."""
    paths = []
    items = supabase.storage.from_("documents").list(prefix) or []
    for item in items:
        full = f"{prefix}/{item['name']}"
        if item.get("id") is None:  # folder (no id)
            paths.extend(_list_all_storage_paths(full))
        else:
            paths.append(full)
    return paths


@app.post("/companies/{company_name}/documents/upload")
async def upload_documents(company_name: str, files: List[UploadFile] = File(...)):
    slug = _company_slug(company_name)
    folder = f"{slug}/main"

    # Wipe only the main folder — timeline docs are untouched
    existing_paths = _list_all_storage_paths(folder)
    if existing_paths:
        supabase.storage.from_("documents").remove(existing_paths)
        print(f"  [Upload] Deleted {len(existing_paths)} existing files from {folder}/")

    uploaded = {}
    for file in files:
        content = await file.read()
        basename = file.filename.split("/")[-1].split("\\")[-1]
        storage_path = f"{folder}/{basename}"
        supabase.storage.from_("documents").upload(
            storage_path,
            content,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        url = supabase.storage.from_("documents").get_public_url(storage_path)
        label = basename[:-4] if basename.lower().endswith(".pdf") else basename
        uploaded[label] = url
        print(f"  [Upload] Stored {basename} → {url}")
    return {"documents": uploaded}


@app.post("/companies/{company_name}/timeline/upload")
async def upload_timeline_documents(company_name: str, files: List[UploadFile] = File(...)):
    slug = _company_slug(company_name)
    folder = f"{slug}/timeline"
    uploaded = {}
    for file in files:
        content = await file.read()
        # Strip any folder prefix the browser adds (e.g. "Time line/filename.pdf" → "filename.pdf")
        basename = file.filename.split("/")[-1].split("\\")[-1]
        storage_path = f"{folder}/{basename}"
        supabase.storage.from_("documents").upload(
            storage_path,
            content,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        url = supabase.storage.from_("documents").get_public_url(storage_path)
        label = basename[:-4] if basename.lower().endswith(".pdf") else basename
        uploaded[label] = url
        print(f"  [Timeline Upload] Stored {basename} → {url}")
    return {"documents": uploaded}


AIF_PROMPT = """Extract insider ownership data from this Annual Information Form (AIF). Return ONLY a JSON object with these exact fields:
{
  "period": "AIF 2024",
  "period_end_date": "2024-12-31",
  "cash": null,
  "cash_currency": null,
  "financial_liabilities": null,
  "shares_outstanding": null,
  "exploration_spend": null,
  "quarterly_ga": null,
  "insider_ownership_pct": null,
  "ceo_total_compensation": null
}
Rules:
- insider_ownership_pct: total percentage of shares held or controlled by ALL directors and officers combined. Look for a table of insider holdings with a total row or stated percentage. Sum all individual director/officer rows if no total is given.
- period: "AIF YYYY" where YYYY is the fiscal year the AIF covers (e.g. "AIF 2024")
- period_end_date: YYYY-12-31 for the fiscal year end
- ceo_total_compensation: always null — this document type does not disclose it.
- All other fields must be null.
Return ONLY the JSON, no other text."""


MIC_PROMPT = """Extract CEO compensation data from this Management Information Circular (MIC) / proxy statement. Return ONLY a JSON object with these exact fields:
{
  "period": "AGM 2024",
  "period_end_date": "2024-06-30",
  "cash": null,
  "cash_currency": null,
  "financial_liabilities": null,
  "shares_outstanding": null,
  "exploration_spend": null,
  "quarterly_ga": null,
  "insider_ownership_pct": null,
  "ceo_total_compensation": null
}
Rules:
- ceo_total_compensation: the CEO's TOTAL annual compensation for the most recent fiscal year shown in the Summary Compensation Table — sum of base salary, bonus, share-based awards (RSUs/PSUs), option-based awards, pension value, and all other compensation. Use the stated Total if given, otherwise sum the components. Express as a plain number in THOUSANDS of the stated currency (e.g. C$450,000 → 450).
- period: "AGM YYYY" where YYYY is the year of the annual meeting / most recent fiscal year covered
- period_end_date: YYYY-06-30 unless a more specific date is evident
- All other fields must be null.
Return ONLY the JSON, no other text."""


TIMELINE_PROMPT = """Extract financial data from this financial statement. Return ONLY a JSON object with these exact fields:
{
  "period": "Q1 2024",
  "period_end_date": "2024-03-31",
  "cash": 7.7,
  "cash_currency": "C$",
  "financial_liabilities": 38.2,
  "shares_outstanding": 918.4,
  "exploration_spend": 3.1,
  "quarterly_ga": 2.0
}
Rules:
- period: quarter + year (e.g. Q1 2024, Q2 2024, Q3 2024, Q4 2024)
- period_end_date: ISO date YYYY-MM-DD (the balance sheet date)
- cash: cash and cash equivalents only, at the balance sheet date, in millions
- cash_currency: C$ or US$
- financial_liabilities: ALL financial liabilities at the balance sheet date, in millions. Include: notes payable, secured notes, debentures, convertible notes, Silver Stream derivative liability, royalty/stream derivative liabilities, lease obligations, option liabilities. Do NOT include trade payables or accrued liabilities. Sum all qualifying items. Use 0 only if there are genuinely no financial liabilities.
- shares_outstanding: common shares issued and outstanding at the balance sheet date (period-end count, NOT weighted average used in EPS), in millions
- exploration_spend: cash spent on mineral property acquisition, exploration and evaluation, or development activities, in millions. Source: cash flow statement INVESTING ACTIVITIES section only (look for "mineral property expenditures", "acquisition of mineral properties", "exploration and evaluation expenditures"). Do NOT use the income statement "exploration and evaluation" expense line — that is a different, much smaller number. The cash flow statement may show cumulative year-to-date figures: determine how many quarters the statement covers from its header ("three months" = 1 quarter, "six months" = 2 quarters, "nine months" = 3 quarters, "year ended" = 4 quarters), then divide the cumulative figure by the number of quarters to get a per-quarter average. Always a positive number.
- quarterly_ga: general and administrative / corporate costs for the QUARTER (three months), in millions. Use the "three months ended" column from the income statement if available. For annual statements divide the annual figure by 4. Always a positive number.
- insider_ownership_pct: ONLY extract this from a Management Information Circular (MIC) or proxy circular. It is the total percentage of shares held or controlled by ALL directors and officers combined. Look for a table showing insider holdings and a total row or stated percentage. For financial statements (FS, MD&A, AIF), leave this null.
- Use null for any value not found. Return ONLY the JSON, no other text."""


timeline_jobs: dict[str, dict] = {}


def run_timeline_job(job_id: str, slug: str, pdf_paths: list):
    import json as _json
    job = timeline_jobs[job_id]
    folder = f"{slug}/timeline"
    key = os.environ["GEMINI_API_KEY"]
    results = []

    for i, storage_path in enumerate(pdf_paths):
        if job.get("status") == "cancelled":
            return

        clean_name = storage_path.split("/")[-1]
        job["current"] = i + 1
        job["label"] = clean_name

        url = supabase.storage.from_("documents").get_public_url(storage_path)

        period_hint, date_hint = None, None
        is_mic = bool(re.search(r"circular|proxy|\bmic\b", clean_name, re.IGNORECASE))
        m = re.search(r"(Q[1-4])[-_](\d{4})", clean_name, re.IGNORECASE)
        if m:
            q, yr = m.group(1).upper(), m.group(2)
            period_hint = f"{q} {yr}"
            month = {"Q1": "03", "Q2": "06", "Q3": "09", "Q4": "12"}[q]
            last_day = {"Q1": "31", "Q2": "30", "Q3": "30", "Q4": "31"}[q]
            date_hint = f"{yr}-{month}-{last_day}"
        elif is_mic:
            yr_m = re.search(r"(\d{4})", clean_name)
            if yr_m:
                yr = yr_m.group(1)
                period_hint = f"AGM {yr}"
                date_hint = f"{yr}-06-30"

        try:
            from agent import _extract_text
            pdf_bytes = fetch_pdf_bytes(url)
            text = _extract_text(pdf_bytes)
            hint_note = f"\nNOTE: This file is named '{clean_name}'. The period is {period_hint} and the balance sheet date is {date_hint}. Use these if the document is ambiguous.\n" if period_hint else ""
            resp = http.post(
                f"{GEMINI_URL}?key={key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"role": "user", "parts": [{"text": f"{TIMELINE_PROMPT}{hint_note}\n\n{text[:60000]}"}]}],
                    "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
                },
                timeout=120,
            )
            resp.raise_for_status()
            extracted = _json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
            if period_hint:
                extracted["period"] = period_hint
                extracted["period_end_date"] = date_hint
            extracted["filename"] = clean_name
            results.append(extracted)
        except Exception as e:
            results.append({"filename": clean_name, "period": period_hint, "period_end_date": date_hint, "error": str(e)})

    results.sort(key=lambda x: x.get("period_end_date") or "")

    results_bytes = _json.dumps(results).encode()
    try:
        supabase.storage.from_("documents").remove([f"{folder}/results.json"])
    except Exception:
        pass
    supabase.storage.from_("documents").upload(
        f"{folder}/results.json", results_bytes,
        file_options={"content-type": "application/json", "upsert": "true"},
    )
    job["status"] = "done"
    job["data"] = results


@app.post("/companies/{company_name}/timeline/analyze")
def analyze_timeline(company_name: str, background_tasks: BackgroundTasks):
    slug = _company_slug(company_name)
    folder = f"{slug}/timeline"

    all_paths = _list_all_storage_paths(folder)
    pdf_paths = sorted([p for p in all_paths if p.lower().endswith(".pdf")])

    if not pdf_paths:
        raise HTTPException(status_code=404, detail="No timeline documents found. Please upload first.")

    job_id = str(uuid.uuid4())
    timeline_jobs[job_id] = {"status": "running", "current": 0, "total": len(pdf_paths), "label": "Starting..."}
    background_tasks.add_task(run_timeline_job, job_id, slug, pdf_paths)
    return {"job_id": job_id, "total": len(pdf_paths)}


@app.get("/companies/{company_name}/timeline/jobs/{job_id}")
def get_timeline_job(job_id: str):
    job = timeline_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/companies/{company_name}/timeline/jobs/{job_id}/cancel")
def cancel_timeline_job(job_id: str):
    job = timeline_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job["status"] = "cancelled"
    return {"status": "cancelled"}


@app.get("/companies/{company_name}/timeline/files")
def get_timeline_files(company_name: str):
    slug = _company_slug(company_name)
    folder = f"{slug}/timeline"
    all_paths = _list_all_storage_paths(folder)
    names = [p.split("/")[-1] for p in all_paths if p.lower().endswith(".pdf")]
    return {"files": sorted(names)}


@app.delete("/companies/{company_name}/timeline")
def delete_timeline(company_name: str):
    slug = _company_slug(company_name)
    folder = f"{slug}/timeline"
    all_paths = _list_all_storage_paths(folder)
    if all_paths:
        supabase.storage.from_("documents").remove(all_paths)
    return {"deleted": len(all_paths)}


@app.get("/companies/{company_name}/timeline/data")
def get_timeline_data(company_name: str):
    slug = _company_slug(company_name)
    url = supabase.storage.from_("documents").get_public_url(f"{slug}/timeline/results.json")
    try:
        resp = http.get(url, timeout=10)
        resp.raise_for_status()
        return {"data": resp.json()}
    except Exception:
        raise HTTPException(status_code=404, detail="No timeline data yet. Click Analyze.")


insider_ownership_jobs: dict[str, dict] = {}


def run_insider_ownership_job(job_id: str, slug: str, pdf_paths: list):
    import json as _json
    job = insider_ownership_jobs[job_id]
    folder = f"{slug}/insider-ownership"
    key = os.environ["GEMINI_API_KEY"]
    results = []

    for i, storage_path in enumerate(pdf_paths):
        if job.get("status") == "cancelled":
            return

        clean_name = storage_path.split("/")[-1]
        job["current"] = i + 1
        job["label"] = clean_name

        url = supabase.storage.from_("documents").get_public_url(storage_path)
        is_mic = bool(re.search(r"circular|proxy|\bmic\b", clean_name, re.IGNORECASE))

        period_hint, date_hint = None, None
        yr_m = re.search(r"(\d{4})", clean_name)
        if yr_m:
            yr = yr_m.group(1)
            if is_mic:
                period_hint = f"AGM {yr}"
                date_hint = f"{yr}-06-30"
            else:
                period_hint = f"AIF {yr}"
                date_hint = f"{yr}-12-31"

        prompt = MIC_PROMPT if is_mic else AIF_PROMPT
        # AIFs and MICs are large (100+ pages); the relevant disclosure is usually near
        # the end, well past a fixed truncation point, so locate it instead of guessing.
        section_patterns = (
            [r"summary compensation table", r"executive compensation"]
            if is_mic
            else [r"ownership of securities", r"directors and (?:executive officers|officers) as a group"]
        )

        try:
            from agent import _extract_text
            pdf_bytes = fetch_pdf_bytes(url)
            text = _extract_text(pdf_bytes)
            section_match = None
            for pattern in section_patterns:
                section_match = re.search(pattern, text, re.IGNORECASE)
                if section_match:
                    break
            if section_match:
                start = max(0, section_match.start() - 1000)
                excerpt = text[start:start + 10000]
            else:
                excerpt = text[:60000]
            hint_note = f"\nNOTE: This file is named '{clean_name}'. The period is {period_hint} and the balance sheet date is {date_hint}. Use these if the document is ambiguous.\n" if period_hint else ""
            resp = http.post(
                f"{GEMINI_URL}?key={key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"role": "user", "parts": [{"text": f"{prompt}{hint_note}\n\n{excerpt}"}]}],
                    "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
                },
                timeout=120,
            )
            resp.raise_for_status()
            extracted = _json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
            if period_hint:
                extracted["period"] = period_hint
                extracted["period_end_date"] = date_hint
            extracted["filename"] = clean_name
            results.append(extracted)
        except Exception as e:
            results.append({"filename": clean_name, "period": period_hint, "period_end_date": date_hint, "error": str(e)})

    results.sort(key=lambda x: x.get("period_end_date") or "")

    results_bytes = _json.dumps(results).encode()
    try:
        supabase.storage.from_("documents").remove([f"{folder}/results.json"])
    except Exception:
        pass
    supabase.storage.from_("documents").upload(
        f"{folder}/results.json", results_bytes,
        file_options={"content-type": "application/json", "upsert": "true"},
    )
    job["status"] = "done"
    job["data"] = results


@app.post("/companies/{company_name}/insider-ownership/upload")
async def upload_insider_ownership_documents(company_name: str, files: List[UploadFile] = File(...)):
    slug = _company_slug(company_name)
    folder = f"{slug}/insider-ownership"
    uploaded = {}
    for file in files:
        content = await file.read()
        basename = file.filename.split("/")[-1].split("\\")[-1]
        storage_path = f"{folder}/{basename}"
        supabase.storage.from_("documents").upload(
            storage_path,
            content,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        url = supabase.storage.from_("documents").get_public_url(storage_path)
        label = basename[:-4] if basename.lower().endswith(".pdf") else basename
        uploaded[label] = url
        print(f"  [Insider Ownership Upload] Stored {basename} → {url}")
    return {"documents": uploaded}


@app.post("/companies/{company_name}/insider-ownership/analyze")
def analyze_insider_ownership(company_name: str, background_tasks: BackgroundTasks):
    slug = _company_slug(company_name)
    folder = f"{slug}/insider-ownership"

    all_paths = _list_all_storage_paths(folder)
    pdf_paths = sorted([p for p in all_paths if p.lower().endswith(".pdf")])

    if not pdf_paths:
        raise HTTPException(status_code=404, detail="No insider ownership documents found. Please upload first.")

    job_id = str(uuid.uuid4())
    insider_ownership_jobs[job_id] = {"status": "running", "current": 0, "total": len(pdf_paths), "label": "Starting..."}
    background_tasks.add_task(run_insider_ownership_job, job_id, slug, pdf_paths)
    return {"job_id": job_id, "total": len(pdf_paths)}


@app.get("/companies/{company_name}/insider-ownership/jobs/{job_id}")
def get_insider_ownership_job(job_id: str):
    job = insider_ownership_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/companies/{company_name}/insider-ownership/jobs/{job_id}/cancel")
def cancel_insider_ownership_job(job_id: str):
    job = insider_ownership_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job["status"] = "cancelled"
    return {"status": "cancelled"}


@app.get("/companies/{company_name}/insider-ownership/files")
def get_insider_ownership_files(company_name: str):
    slug = _company_slug(company_name)
    folder = f"{slug}/insider-ownership"
    all_paths = _list_all_storage_paths(folder)
    names = [p.split("/")[-1] for p in all_paths if p.lower().endswith(".pdf")]
    return {"files": sorted(names)}


@app.delete("/companies/{company_name}/insider-ownership")
def delete_insider_ownership(company_name: str):
    slug = _company_slug(company_name)
    folder = f"{slug}/insider-ownership"
    all_paths = _list_all_storage_paths(folder)
    if all_paths:
        supabase.storage.from_("documents").remove(all_paths)
    return {"deleted": len(all_paths)}


@app.get("/companies/{company_name}/insider-ownership/data")
def get_insider_ownership_data(company_name: str):
    slug = _company_slug(company_name)
    url = supabase.storage.from_("documents").get_public_url(f"{slug}/insider-ownership/results.json")
    try:
        resp = http.get(url, timeout=10)
        resp.raise_for_status()
        return {"data": resp.json()}
    except Exception:
        raise HTTPException(status_code=404, detail="No insider ownership data yet. Click Analyze.")


@app.get("/companies/{company_name}/documents/uploaded")
def get_uploaded_documents(company_name: str):
    slug = _company_slug(company_name)
    try:
        all_paths = _list_all_storage_paths(f"{slug}/main")
        docs = {}
        for path in all_paths:
            if not path.lower().endswith(".pdf"):
                continue
            name = path.split("/")[-1]
            label = name[:-4]
            url = supabase.storage.from_("documents").get_public_url(path)
            docs[label] = url
        return {"documents": docs}
    except Exception as e:
        print(f"  [Upload] list error: {e}")
        return {"documents": {}}


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
active_jobs_by_company: dict[str, str] = {}  # company_name -> job_id for running jobs
dynamic_companies: dict[str, dict] = {}  # populated at runtime via chat intent


def _save_overview(company_name: str, overview_md: str, current_urls: list[str]):
    now = datetime.now(timezone.utc).isoformat()
    company_url = dynamic_companies.get(company_name, {}).get("base_url") or None
    existing = supabase.table("company_overviews").select("id").eq("company_name", company_name).limit(1).execute()
    if existing.data:
        update_data = {"overview_markdown": overview_md, "source_urls": current_urls, "generated_at": now}
        if company_url:
            update_data["company_url"] = company_url
        supabase.table("company_overviews").update(update_data).eq("company_name", company_name).execute()
    else:
        insert_data = {"company_name": company_name, "overview_markdown": overview_md, "source_urls": current_urls}
        if company_url:
            insert_data["company_url"] = company_url
        supabase.table("company_overviews").insert(insert_data).execute()


def run_overview_job(job_id: str, company_name: str, pdf_docs: dict, current_urls: list[str], skip_filter: bool = False):
    job = overview_jobs[job_id]

    def on_progress(info: dict):
        job.update(info)

    try:
        if job.get("status") == "cancelled":
            return

        # news PDF discovery disabled — news comes from Gemini web access
        # job["label"] = "Fetching recent press releases..."
        # news_pdfs = discover_news_release_pdfs(company_name, dynamic_companies)
        # added = 0
        # for label, url in news_pdfs.items():
        #     if url not in pdf_docs.values():
        #         pdf_docs[label] = url
        #         added += 1
        # if added:
        #     job["pdfs"] = list(pdf_docs.keys())
        #     job["pdf_urls"] = dict(pdf_docs)
        #     job["total"] = len(pdf_docs)
        #     print(f"  [News PDFs] Added {added} press releases for {company_name}")

        if job.get("status") == "cancelled":
            return

        overview_md = generate_overview(company_name, pdf_docs, on_progress, dynamic_companies, skip_filter=skip_filter)
        _save_overview(company_name, overview_md, current_urls)
        job["label"] = "Extracting structured facts..."
        null_report = run_extraction(company_name, pdf_docs)
        job["null_report"] = null_report
        job["status"] = "done"
        job["overview_markdown"] = overview_md
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
    finally:
        active_jobs_by_company.pop(company_name, None)


@app.post("/companies/{company_name}/overview/start")
def start_overview(company_name: str, background_tasks: BackgroundTasks, force: bool = False):
    # Read uploaded docs from Supabase Storage — main folder only, never timeline
    slug = _company_slug(company_name)
    all_paths = _list_all_storage_paths(f"{slug}/main")
    pdf_docs = {}
    for path in all_paths:
        if not path.lower().endswith(".pdf"):
            continue
        name = path.split("/")[-1]
        label = name[:-4]
        url = supabase.storage.from_("documents").get_public_url(path)
        pdf_docs[label] = url

    if not pdf_docs:
        raise HTTPException(status_code=404, detail="No uploaded documents found. Please upload documents first.")

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
    active_jobs_by_company[company_name] = job_id
    background_tasks.add_task(run_overview_job, job_id, company_name, pdf_docs, current_urls)
    return {"job_id": job_id, "pdfs": pdf_list, "selected_pdfs": selected_pdfs, "pdf_urls": pdf_docs, "cached": False}


class ManualDocsRequest(BaseModel):
    docs: dict[str, str]  # label -> url
    company_url: str | None = None  # optional: registers unknown company for news/website scraping


@app.post("/companies/{company_name}/overview/start-manual")
def start_overview_manual(company_name: str, body: ManualDocsRequest, background_tasks: BackgroundTasks):
    pdf_docs = {label: url for label, url in body.docs.items() if url.strip()}

    # Ensure company has a base_url in dynamic_companies for news PDF discovery.
    # Priority: explicit company_url → Supabase saved url → leave empty.
    existing = dynamic_companies.get(company_name, {})
    if not existing.get("base_url"):
        base_url = body.company_url.rstrip("/") if body.company_url else None
        if not base_url:
            row = supabase.table("company_overviews").select("company_url").eq("company_name", company_name).limit(1).execute()
            if row.data and row.data[0].get("company_url"):
                base_url = row.data[0]["company_url"]
        if base_url:
            dynamic_companies[company_name] = {
                **existing,
                "base_url": base_url,
                "investor_pages": existing.get("investor_pages", []),
                "about_pages": existing.get("about_pages", []),
                "news_page": existing.get("news_page", "/news/"),
            }
    current_urls = sorted(pdf_docs.values())
    pdf_list = list(pdf_docs.keys())
    job_id = str(uuid.uuid4())
    overview_jobs[job_id] = {
        "status": "running", "step": "reading", "label": "Starting...",
        "current": 0, "total": len(pdf_docs),
        "pdfs": pdf_list, "selected_pdfs": pdf_list, "pdf_urls": pdf_docs,
    }
    active_jobs_by_company[company_name] = job_id
    background_tasks.add_task(run_overview_job, job_id, company_name, pdf_docs, current_urls, True)
    return {"job_id": job_id, "pdfs": pdf_list, "selected_pdfs": pdf_list, "pdf_urls": pdf_docs}


class MarkdownUpdateRequest(BaseModel):
    overview_markdown: str

@app.patch("/companies/{company_name}/overview/markdown")
def update_overview_markdown(company_name: str, body: MarkdownUpdateRequest):
    existing = supabase.table("company_overviews").select("id").eq("company_name", company_name).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="No report found")
    supabase.table("company_overviews").update({"overview_markdown": body.overview_markdown}).eq("company_name", company_name).execute()
    return {"updated": company_name}


@app.delete("/companies/{company_name}/overview")
def delete_overview(company_name: str):
    supabase.table("company_overviews").delete().eq("company_name", company_name).execute()
    active_jobs_by_company.pop(company_name, None)
    dynamic_companies.pop(company_name, None)
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
    supabase.table("company_overviews").delete().eq("company_name", company_name).execute()
    active_jobs_by_company.pop(company_name, None)
    # Keep dynamic_companies entry so base_url is available for immediate regeneration
    return {"archived_as": archived_name, "source_urls": existing.get("source_urls", [])}


@app.get("/companies/{company_name}/active-job")
def get_active_job(company_name: str):
    job_id = active_jobs_by_company.get(company_name)
    if not job_id:
        raise HTTPException(status_code=404, detail="No active job")
    return {"job_id": job_id}


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
                # Unknown company, no URL — send to upload panel so user can provide URL + docs
                encoded = company_name.replace(" ", "%20")
                reply = (
                    f"I found **{company_name}**. Please upload the company's documents to generate a report.\n\n"
                    f"[Open upload panel →](/companies/{encoded})"
                )
                return {"reply": reply, "session_id": payload.session_id, "company": company_name, "upload": True}
            # Register placeholder with provided URL
            dynamic_companies[company_name] = {"base_url": provided_url.rstrip("/"), "investor_pages": [], "about_pages": [], "news_page": "/news/"}

        # No cache — redirect to upload panel (user provides docs manually)
        encoded = company_name.replace(" ", "%20")
        reply = (
            f"I found **{company_name}**. Please upload the relevant documents to generate a full report.\n\n"
            f"[Open upload panel →](/companies/{encoded})"
        )
        return {"reply": reply, "session_id": payload.session_id, "company": company_name, "upload": True}

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
