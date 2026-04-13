"""
Executor — thin wrapper that calls the active provider and parses JSON.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.agent.schemas import build_extraction_prompt
from backend.config import get_settings

log = logging.getLogger(__name__)


def _strip_fences(text: str) -> str:
    if text.strip().startswith("```"):
        lines = text.strip().splitlines()
        return "\n".join(l for l in lines if not l.startswith("```")).strip()
    return text.strip()


def run_extraction(
    file_path: str,
    doc_type: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Synchronous extraction. Safe to call from a thread pool.

    Args:
        file_path : absolute path to the PDF
        doc_type  : optional hint for schema-guided extraction
        provider  : "llamaparse" | "openai" | "gemini" | "anthropic"
        model     : optional model override
    """
    from backend.agent.providers import run_with_provider

    settings = get_settings()
    active_provider = provider or settings.active_provider
    system_prompt = build_extraction_prompt(doc_type)

    raw_output = run_with_provider(
        file_path, system_prompt, active_provider, model
    )
    raw_output = _strip_fences(raw_output)

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as exc:
        log.error("Provider %s returned non-JSON: %s", active_provider, raw_output[:300])
        return {
            "doc_type": doc_type or "unknown",
            "page_count": 0,
            "extracted_at": "",
            "fields": {},
            "tables": [],
            "entities": {"persons": [], "orgs": [], "dates": [], "amounts": []},
            "summary": f"Extraction failed ({active_provider}) — model did not return valid JSON.",
            "errors": [{"field": "output", "reason": str(exc)}],
        }
