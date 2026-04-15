"""
Executor — calls the active provider, normalizes the loss run envelope.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.agent.schemas import build_extraction_prompt
from backend.config import get_settings

log = logging.getLogger(__name__)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        return "\n".join(l for l in lines if not l.startswith("```")).strip()
    return text


def _normalize_envelope(raw: dict) -> dict:
    """
    Ensure the envelope always has the standard loss run shape.
    Fills missing top-level keys so downstream code never KeyErrors.
    Also promotes flat 'fields' output (from LLM providers) into policy_info
    when the model returns the old generic envelope format.
    """
    # Force doc_type
    raw.setdefault("doc_type", "lossrun")
    raw["doc_type"] = "lossrun"

    # Ensure required keys exist
    raw.setdefault("policy_info", {})
    raw.setdefault("policy_periods", [])
    raw.setdefault("claims", [])
    raw.setdefault("errors", [])

    # Normalize summary — accept both dict and missing
    if "summary" not in raw or not isinstance(raw.get("summary"), dict):
        raw["summary"] = {}

    summary = raw["summary"]
    # Compute open/closed counts from claims if not provided
    claims = raw.get("claims") or []
    if claims and summary.get("total_claims") is None:
        summary["total_claims"] = len(claims)
        summary["open_claims"] = sum(1 for c in claims if str(c.get("status", "")).lower() == "open")
        summary["closed_claims"] = sum(1 for c in claims if str(c.get("status", "")).lower() == "closed")

    # Compute financial totals from claims if not provided
    if claims and summary.get("total_incurred") is None:
        incurred = [c.get("total_incurred") for c in claims if c.get("total_incurred") is not None]
        paid = [c.get("total_paid") for c in claims if c.get("total_paid") is not None]
        reserve = [c.get("outstanding_reserve") for c in claims if c.get("outstanding_reserve") is not None]
        if incurred:
            summary["total_incurred"] = round(sum(incurred), 2)
        if paid:
            summary["total_paid"] = round(sum(paid), 2)
        if reserve:
            summary["total_reserve"] = round(sum(reserve), 2)

    # If LLM returned old-style generic envelope, migrate 'fields' → 'policy_info'
    if raw.get("fields") and not any(raw["policy_info"].values() if raw["policy_info"] else []):
        fields = raw["fields"]
        mapping = {
            "insured_name": ["insured_name", "insured", "named_insured"],
            "policy_number": ["policy_number", "policy_no", "policy_num"],
            "insurer_name": ["insurer_name", "carrier", "insurance_company"],
            "line_of_business": ["line_of_business", "lob", "coverage_type"],
            "report_date": ["report_date", "date_of_report", "run_date"],
        }
        for target, sources in mapping.items():
            for src in sources:
                if src in fields and fields[src]:
                    raw["policy_info"][target] = fields[src]
                    break

    return raw


def run_extraction(
    file_path: str,
    doc_type: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Synchronous loss run extraction. Safe to call from a thread pool.
    doc_type is always forced to 'lossrun'.
    """
    from backend.agent.providers import run_with_provider

    settings = get_settings()
    active_provider = provider or settings.active_provider
    system_prompt = build_extraction_prompt("lossrun")

    raw_output = run_with_provider(
        file_path, system_prompt, active_provider, model
    )
    raw_output = _strip_fences(raw_output)

    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        log.error("Provider %s returned non-JSON: %s", active_provider, raw_output[:300])
        parsed = {
            "doc_type": "lossrun",
            "page_count": 0,
            "extracted_at": "",
            "policy_info": {},
            "policy_periods": [],
            "claims": [],
            "summary": {},
            "errors": [{"field": "output", "reason": str(exc)}],
        }

    return _normalize_envelope(parsed)
