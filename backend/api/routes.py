"""
FastAPI routes — no Celery/Redis required for local dev.
Extraction runs in a thread-pool background task.
SSE progress is delivered via per-job asyncio.Queue.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import AsyncIterator

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from backend.config import get_settings, PROVIDER_REGISTRY
from backend.db.repository import ExtractionRepository

router = APIRouter()

_executor = ThreadPoolExecutor(max_workers=4)
_job_queues: dict[str, asyncio.Queue] = {}


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_repo(request: Request) -> ExtractionRepository:
    return request.app.state.repo


# ---------------------------------------------------------------------------
# Background extraction coroutine
# ---------------------------------------------------------------------------

async def _run_extraction(
    job_id: str,
    file_path: str,
    user_id: str | None,
    doc_type: str | None,
    provider: str,
    model: str | None,
    queue: asyncio.Queue,
    repo: ExtractionRepository,
) -> None:
    async def emit(event: str, data: dict) -> None:
        await queue.put({"event": event, "data": data})

    await emit("started", {
        "job_id": job_id,
        "file": Path(file_path).name,
        "provider": provider,
        "model": model,
    })
    await emit("step", {"step": 1, "message": "Parsing PDF with PyMuPDF …"})

    try:
        from backend.agent.executor import run_extraction

        loop = asyncio.get_event_loop()
        await emit("step", {"step": 2, "message": f"Running {provider.upper()} extraction agent …"})

        envelope = await loop.run_in_executor(
            _executor,
            partial(run_extraction, file_path, doc_type, provider, model),
        )

        await emit("step", {"step": 3, "message": "Saving result to MongoDB …"})
        doc_id = await repo.save_extraction(file_path, envelope, user_id, job_id)
        envelope["_id"] = doc_id
        envelope["provider"] = provider
        envelope["model"] = model

        await emit("result", {"job_id": job_id, "doc_id": doc_id, "envelope": envelope})

    except Exception as exc:
        await emit("error", {"job_id": job_id, "reason": str(exc)})

    finally:
        await asyncio.sleep(30)
        _job_queues.pop(job_id, None)


# ---------------------------------------------------------------------------
# GET /providers  — list available providers + active one
# ---------------------------------------------------------------------------

@router.get("/providers", summary="List available AI providers")
async def list_providers():
    settings = get_settings()
    providers = []
    key_map = {
        "llamaparse": settings.llama_cloud_api_key,
        "openai":     settings.openai_api_key,
        "gemini":     settings.google_api_key,
        "anthropic":  settings.anthropic_api_key,
    }

    # Local providers (no API key) — check package availability at runtime
    def _local_available(provider_id: str) -> bool:
        if provider_id == "liteparse":
            from backend.agent.lite_parser import liteparse_available
            return liteparse_available()
        return False

    for key, info in PROVIDER_REGISTRY.items():
        if info.get("local"):
            available = _local_available(key)
        else:
            available = bool(key_map.get(key, ""))
        providers.append({
            "id":        key,
            "label":     info["label"],
            "models":    info["models"],
            "color":     info["color"],
            "available": available,
            "active":    key == settings.active_provider,
        })
    return {
        "active": settings.active_provider,
        "providers": providers,
    }


# ---------------------------------------------------------------------------
# POST /extract  — upload + queue
# ---------------------------------------------------------------------------

@router.post("/extract", summary="Upload a PDF and start extraction")
async def extract_pdf(
    request: Request,
    file: UploadFile = File(..., description="PDF file to extract"),
    user_id: str | None = Form(None),
    doc_type: str | None = Form(None, description="invoice|contract|resume|report|form"),
    provider: str | None = Form(None, description="llamaparse|openai|gemini|anthropic"),
    model: str | None = Form(None, description="Model override e.g. gpt-4o or markdown/text for llamaparse"),
):
    settings = get_settings()
    active_provider = provider or settings.active_provider
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    if active_provider not in PROVIDER_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {active_provider}")

    job_id = str(uuid.uuid4())
    dest = upload_dir / f"{job_id}_{file.filename}"

    async with aiofiles.open(dest, "wb") as f:
        while chunk := await file.read(65536):
            await f.write(chunk)

    repo: ExtractionRepository = request.app.state.repo
    cached = await repo.get_by_hash(str(dest))
    # Only use cache if it contains spatial page data when provider needs it.
    # Liteparse results without 'pages' are stale (stored before that field existed).
    cache_valid = (
        cached is not None
        and not (active_provider == "liteparse" and not cached.get("pages"))
    )
    if cache_valid:
        return {
            "job_id": job_id,
            "status": "cached",
            "message": "Identical PDF was previously processed.",
            "result": cached,
        }

    queue: asyncio.Queue = asyncio.Queue()
    _job_queues[job_id] = queue

    asyncio.create_task(
        _run_extraction(job_id, str(dest), user_id, doc_type,
                        active_provider, model, queue, repo)
    )

    return {
        "job_id":       job_id,
        "status":       "queued",
        "provider":     active_provider,
        "stream_url":   f"/api/v1/jobs/{job_id}/stream",
    }


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/stream  — SSE
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}/stream", summary="Stream extraction progress via SSE")
async def stream_job(job_id: str):
    async def event_generator() -> AsyncIterator[str]:
        queue = _job_queues.get(job_id)
        if queue is None:
            yield f"event: error\ndata: {json.dumps({'reason': 'Job not found or already expired'})}\n\n"
            return

        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15)
            except (asyncio.TimeoutError, TimeoutError):
                yield ": heartbeat\n\n"
                continue

            yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
            if item["event"] in ("result", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# GET /documents  — dashboard list (all docs, no heavy fields)
# ---------------------------------------------------------------------------

@router.get("/documents", summary="List all extraction documents (dashboard)")
async def list_documents(
    skip:  int = Query(0,  ge=0),
    limit: int = Query(50, ge=1, le=200),
    repo:  ExtractionRepository = Depends(get_repo),
):
    docs = await repo.list_all(skip=skip, limit=limit)
    return {"skip": skip, "limit": limit, "total": len(docs), "results": docs}


# ---------------------------------------------------------------------------
# GET /pdf/{doc_id}  — serve the original PDF file
# ---------------------------------------------------------------------------

@router.get("/pdf/{doc_id}", summary="Serve the original PDF file for a document")
async def serve_pdf(
    doc_id: str,
    repo:   ExtractionRepository = Depends(get_repo),
):
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    file_name = doc.get("file_name")
    if not file_name:
        raise HTTPException(status_code=404, detail="File name not recorded.")
    settings   = get_settings()
    file_path  = Path(settings.upload_dir) / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="PDF file no longer on server.")
    # Strip job-id prefix for the download filename
    display = file_name.split("_", 1)[-1] if "_" in file_name else file_name
    return FileResponse(
        str(file_path),
        media_type="application/pdf",
        filename=display,
        headers={"Cache-Control": "max-age=3600"},
    )


# ---------------------------------------------------------------------------
# PATCH /extractions/{doc_id}/claims  — save structured claim rows
# ---------------------------------------------------------------------------

class ClaimsPayload(BaseModel):
    claim_id_column:     str         # display label of the chosen column
    claim_id_col_idx:    int         # 0-based index in the spatial grid
    rows: list[dict]                 # [{claim_id, row_index, data: {col: val}}]


@router.patch("/extractions/{doc_id}/claims", summary="Save claim-keyed rows to a document")
async def save_claims(
    doc_id:  str,
    payload: ClaimsPayload,
    repo:    ExtractionRepository = Depends(get_repo),
):
    ok = await repo.save_claims(doc_id, payload.claim_id_column, payload.rows)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {
        "ok":          True,
        "doc_id":      doc_id,
        "claim_count": len(payload.rows),
        "column":      payload.claim_id_column,
    }


# ---------------------------------------------------------------------------
# GET /history/{user_id}
# ---------------------------------------------------------------------------

@router.get("/history/{user_id}", summary="Paginated extraction history for a user")
async def user_history(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    repo: ExtractionRepository = Depends(get_repo),
):
    docs = await repo.list_by_user(user_id, skip=skip, limit=limit)
    return {"user_id": user_id, "skip": skip, "limit": limit, "results": docs}


# ---------------------------------------------------------------------------
# GET /extractions/{id}
# ---------------------------------------------------------------------------

@router.get("/extractions/{doc_id}", summary="Fetch a single extraction result")
async def get_extraction(
    doc_id: str,
    repo: ExtractionRepository = Depends(get_repo),
):
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Extraction not found.")
    return doc


# ---------------------------------------------------------------------------
# GET /extractions/type/{doc_type}
# ---------------------------------------------------------------------------

@router.get("/extractions/type/{doc_type}", summary="Filter extractions by document type")
async def list_by_type(
    doc_type: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    repo: ExtractionRepository = Depends(get_repo),
):
    docs = await repo.list_by_type(doc_type, skip=skip, limit=limit)
    return {"doc_type": doc_type, "skip": skip, "limit": limit, "results": docs}
