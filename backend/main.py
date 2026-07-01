import io
import os
import uuid
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from agent import send_message  # noqa: E402 — must import after load_dotenv populates env vars
from scraping import COMPANIES, fetch_pdf_bytes, find_pdf_links, sanitize_filename

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

app = FastAPI(title="Mining AI Analyst")


@app.get("/health")
def health():
    supabase.table("companies").select("id").limit(1).execute()
    return {"status": "ok", "supabase_connected": True}


@app.get("/companies")
def list_companies():
    return list(COMPANIES.keys())


@app.get("/companies/{company_name}/documents")
def get_documents(company_name: str):
    if company_name not in COMPANIES:
        raise HTTPException(status_code=404, detail="Unknown company")
    return find_pdf_links(company_name)


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


class ChatRequest(BaseModel):
    message: str
    documents: dict[str, str] = {}  # only needed on the first message of a conversation
    session_id: str | None = None


@app.post("/chat")
def chat(payload: ChatRequest):
    reply, session_id = send_message(payload.message, payload.documents, payload.session_id)
    return {"reply": reply, "session_id": session_id}


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent / "static", html=True), name="static")
