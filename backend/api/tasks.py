"""
Celery tasks — production-grade async PDF processing.
Progress events are published to a Redis channel so the SSE endpoint
can stream them to the browser in real time.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import redis
from celery import Celery
from celery.utils.log import get_task_logger

from backend.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Celery app
# ---------------------------------------------------------------------------

celery_app = Celery(
    "pdf_agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,     # one task at a time per worker
    task_acks_late=True,              # ack only after task completes
)

log: logging.Logger = get_task_logger(__name__)

# ---------------------------------------------------------------------------
# Redis pub/sub channel helpers
# ---------------------------------------------------------------------------

def _channel(job_id: str) -> str:
    return f"pdf_job:{job_id}"


def _publish(r: redis.Redis, job_id: str, event: str, data: dict) -> None:
    payload = json.dumps({"event": event, "data": data, "ts": datetime.now(timezone.utc).isoformat()})
    r.publish(_channel(job_id), payload)


# ---------------------------------------------------------------------------
# Main extraction task
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="tasks.extract_pdf", max_retries=2)
def extract_pdf_task(
    self,
    job_id: str,
    file_path: str,
    user_id: str | None,
    doc_type: str | None,
) -> dict:
    """
    Run the LangChain agent extraction pipeline.
    Publishes progress/result events to Redis for SSE consumers.
    Returns the final extraction envelope dict.
    """
    r = redis.from_url(settings.redis_url, decode_responses=True)

    try:
        _publish(r, job_id, "started", {"job_id": job_id, "file": os.path.basename(file_path)})
        self.update_state(state="PROGRESS", meta={"step": "reading_pdf"})

        # ---- Import here to avoid cold-import overhead in workers ----
        from backend.agent.executor import run_extraction
        from backend.db.repository import ExtractionRepository
        import asyncio
        import motor.motor_asyncio

        _publish(r, job_id, "step", {"step": 1, "message": "Parsing PDF with PyMuPDF / OCR …"})
        self.update_state(state="PROGRESS", meta={"step": "agent_running"})

        envelope = run_extraction(file_path, doc_type)

        _publish(r, job_id, "step", {"step": 2, "message": "Saving to MongoDB …"})

        # Persist asynchronously
        async def _save():
            client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_url)
            db = client[settings.mongodb_db]
            repo = ExtractionRepository(db)
            await repo.ensure_indexes()
            doc_id = await repo.save_extraction(file_path, envelope, user_id, job_id)
            client.close()
            return doc_id

        doc_id = asyncio.run(_save())
        envelope["_id"] = doc_id

        _publish(r, job_id, "result", {"job_id": job_id, "doc_id": doc_id, "envelope": envelope})
        return envelope

    except Exception as exc:
        log.exception("extract_pdf_task failed for job %s", job_id)
        _publish(r, job_id, "error", {"job_id": job_id, "reason": str(exc)})
        raise self.retry(exc=exc, countdown=10)
    finally:
        r.close()
