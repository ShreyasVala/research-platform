# api/main.py
# The FastAPI web server — exposes HTTP endpoints so anything
# can interact with your research system.
#
# When running, visit http://localhost:8000/docs in your browser
# for an interactive page to test every endpoint without any frontend.

import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from config import get_settings
from agents.supervisor import SupervisorAgent
from agents.memory import MemoryManager
from tools.storage import save_upload_bytes, safe_filename
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
settings.ensure_dirs()   # creates uploads/, reports/, state/ on startup

app = FastAPI(
    title="Multi-Agent Research Platform",
    description="AI research system with parallel worker agents and MCP tools",
    version="1.0.0",
)

# CORS = allows a web browser on a different port to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

supervisor = SupervisorAgent()
memory = MemoryManager()


# Pydantic models define the shape of JSON requests and responses
# FastAPI uses these to validate data automatically
class ResearchRequest(BaseModel):
    query: str
    document_name: str | None = None   # optional document to analyse


class ResearchResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ── Endpoints ─────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Check the server is running. Shows current LLM config."""
    return {
        "status": "ok",
        "llm_provider": "openai",
        "supervisor_model": settings.supervisor_model,
        "worker_model": settings.worker_model,
        "storage_backend": settings.storage_backend,
    }


@app.post("/research", response_model=ResearchResponse)
async def start_research(req: ResearchRequest):
    """
    Start a new research job.
    Returns immediately with a job_id.
    Poll /status/{job_id} to check progress.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if len(req.query) > 2000:
        raise HTTPException(status_code=400, detail="Query too long (max 2000 chars).")

    job_id = await supervisor.run_research(req.query, req.document_name)
    return ResearchResponse(
        job_id=job_id,
        status="planning",
        message=f"Research started. Poll /status/{job_id} for updates.",
    )


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Check the current status of a research job."""
    state = await memory.load(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id": state.job_id,
        "status": state.status,
        "query": state.query,
        "tasks_planned": len(state.plan),
        "workers_completed": len(state.worker_results),
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "error": state.error or None,
    }


@app.get("/report/{job_id}")
async def get_report(job_id: str):
    """Get the finished research report. Returns 202 if still running."""
    state = await memory.load(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found.")
    if state.status != "done":
        raise HTTPException(
            status_code=202,
            detail=f"Report not ready yet. Current status: {state.status}",
        )
    return {
        "job_id": state.job_id,
        "query": state.query,
        "report": state.final_report,
        "report_location": getattr(state, "report_location", "") or None,
        "worker_count": len(state.worker_results),
    }


@app.get("/jobs")
async def list_jobs():
    """List all research jobs and their current status."""
    return {"jobs": await memory.list_jobs()}


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF or text file to include in a research job."""
    allowed = {".pdf", ".txt", ".md", ".csv"}
    name = safe_filename(file.filename)
    if name is None:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    suffix = Path(name).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {allowed}",
        )

    content = await file.read()
    try:
        saved = await asyncio.to_thread(save_upload_bytes, name, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "filename": saved["filename"],
        "size_kb": saved["size_kb"],
        "storage": saved["storage"],
        "message": (
            f"Uploaded successfully. "
            f"Use document_name='{saved['filename']}' in your /research request."
        ),
    }
