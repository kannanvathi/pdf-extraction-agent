"""
Layer 4 — Motor async MongoDB repository.
SHA-256 deduplication prevents re-extracting the same PDF.
Indexes optimised for user history queries and doc_type filtering.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

from backend.config import get_settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Index definitions
# ---------------------------------------------------------------------------

INDEXES: list[IndexModel] = [
    IndexModel([("file_hash", ASCENDING)], unique=True, name="unique_file_hash"),
    IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_history"),
    IndexModel([("doc_type", ASCENDING), ("created_at", DESCENDING)], name="type_filter"),
    IndexModel([("created_at", DESCENDING)], name="recency"),
]


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class ExtractionRepository:
    """All database interactions for PDF extraction results."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db["extractions"]

    # --- Lifecycle ---

    async def ensure_indexes(self) -> None:
        """Create indexes if they don't exist. Safe to call on every startup."""
        await self._col.create_indexes(INDEXES)
        log.info("MongoDB indexes ensured on 'extractions' collection.")

    # --- 1. Save / upsert an extraction result ---

    async def save_extraction(
        self,
        file_path: str,
        envelope: dict[str, Any],
        user_id: str | None = None,
        job_id: str | None = None,
    ) -> str:
        """
        Persist an extraction envelope.  Returns the document _id as a string.
        If a document with the same SHA-256 hash already exists the existing
        _id is returned without touching the database (deduplication).
        """
        file_hash = _sha256(file_path)
        existing = await self._col.find_one({"file_hash": file_hash}, {"_id": 1, "pages": 1})
        if existing:
            has_pages = bool(existing.get("pages"))
            envelope_has_pages = bool(envelope.get("pages"))
            if has_pages or not envelope_has_pages:
                # Cache is up-to-date — skip re-insert
                log.info("Duplicate PDF detected (hash %s). Skipping re-insert.", file_hash[:12])
                return str(existing["_id"])
            # Cached doc is stale (missing spatial data) — update it in-place
            log.info("Updating stale cached doc %s with pages data.", str(existing["_id"])[:12])
            update_fields = _sanitize({k: v for k, v in envelope.items()
                                       if k not in ("file_hash", "file_name", "created_at")})
            await self._col.update_one(
                {"_id": existing["_id"]},
                {"$set": update_fields},
            )
            return str(existing["_id"])

        lr_doc_id = f"lr-doc-{uuid.uuid4().hex[:7]}"
        doc = _sanitize({
            "lr_doc_id":  lr_doc_id,
            "file_hash":  file_hash,
            "file_name":  Path(file_path).name,
            "user_id":    user_id,
            "job_id":     job_id,
            "created_at": datetime.now(timezone.utc),
            **envelope,
        })
        result = await self._col.insert_one(doc)
        return str(result.inserted_id)

    # --- 2. Fetch a single result by MongoDB _id ---

    async def get_by_id(self, doc_id: str) -> dict[str, Any] | None:
        """Return one extraction document by its _id string, or None."""
        from bson import ObjectId

        try:
            oid = ObjectId(doc_id)
        except Exception:
            return None
        doc = await self._col.find_one({"_id": oid})
        return _serialize(doc) if doc else None

    # --- 3. Check / fetch by SHA-256 hash (dedup lookup) ---

    async def get_by_hash(self, file_path: str) -> dict[str, Any] | None:
        """
        Return a cached extraction if the same file (by SHA-256) was already
        processed. Callers can skip the agent entirely on a cache hit.
        """
        file_hash = _sha256(file_path)
        doc = await self._col.find_one({"file_hash": file_hash})
        return _serialize(doc) if doc else None

    # --- 4. Paginated user history ---

    async def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return the most-recent extractions for a given user, newest first."""
        cursor = (
            self._col.find({"user_id": user_id})
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return [_serialize(doc) async for doc in cursor]

    # --- 5. List all documents (dashboard) ---

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return all extractions newest-first, projecting out heavy fields."""
        projection = {
            "full_text": 0,
            "pages": 0,
            "table_data": 0,
            "entities": 0,
            "fields": 0,
        }
        cursor = (
            self._col.find({}, projection)
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return [_serialize(doc) async for doc in cursor]

    # --- 6. Save structured claim rows (keeps raw data intact) ---

    async def save_claims(
        self,
        doc_id: str,
        claim_id_column: str,
        claim_rows: list[dict],
    ) -> bool:
        """
        Upsert claim_rows into an existing extraction document.
        Raw fields (full_text, pages, table_data …) are untouched.
        Returns True if a document was matched and updated.
        """
        from bson import ObjectId

        try:
            oid = ObjectId(doc_id)
        except Exception:
            return False

        update = _sanitize({
            "claim_id_column": claim_id_column,
            "claim_rows":      claim_rows,
        })
        result = await self._col.update_one({"_id": oid}, {"$set": update})
        return result.matched_count > 0

    # --- 7. Filter by document type ---

    async def list_by_type(
        self,
        doc_type: str,
        skip: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return extractions filtered by doc_type (invoice / contract / …)."""
        cursor = (
            self._col.find({"doc_type": doc_type})
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return [_serialize(doc) async for doc in cursor]


# ---------------------------------------------------------------------------
# Database connection factory  (call once at app startup)
# ---------------------------------------------------------------------------

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> ExtractionRepository:
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_url)
    _db = _client[settings.mongodb_db]
    repo = ExtractionRepository(_db)
    await repo.ensure_indexes()
    return repo


async def close_db() -> None:
    if _client:
        _client.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sanitize(obj: Any) -> Any:
    """
    Recursively strip NULL bytes (\\x00) from all string keys and values.
    MongoDB rejects documents whose key names contain the NULL byte.
    """
    if isinstance(obj, dict):
        return {k.replace("\x00", ""): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(item) for item in obj]
    if isinstance(obj, str):
        return obj.replace("\x00", "")
    return obj


def _serialize(doc: dict) -> dict:
    """Convert ObjectId → str and datetime → ISO string for JSON output."""
    from bson import ObjectId

    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v

    # Backfill lr_doc_id for legacy documents that predate the field
    if "lr_doc_id" not in out:
        raw_id = str(out.get("_id", ""))
        out["lr_doc_id"] = f"lr-doc-{raw_id[:7]}" if len(raw_id) >= 7 else "lr-doc-legacy"

    return out
