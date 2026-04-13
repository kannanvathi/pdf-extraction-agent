"""
LlamaParse — cloud PDF parsing via LlamaIndex.

Used as a high-quality alternative to PyMuPDF when the API key is configured.
Falls back to the local PyMuPDF stack if LlamaParse is unavailable or fails.

Usage:
    from backend.agent.llama_parser import parse_pdf_text
    text = parse_pdf_text("/path/to/file.pdf")
"""

from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)


def parse_pdf_text(file_path: str) -> str | None:
    """
    Parse a PDF with LlamaParse and return the combined markdown text.

    Returns None if LlamaParse is not configured or fails, so the caller
    can fall back to PyMuPDF.
    """
    from backend.config import get_settings
    settings = get_settings()

    if not settings.llama_cloud_api_key:
        return None

    try:
        from llama_parse import LlamaParse

        parser = LlamaParse(
            api_key=settings.llama_cloud_api_key,
            result_type="markdown",       # preserves headers, tables, lists
            verbose=False,
            language="en",
        )
        documents = parser.load_data(file_path)
        if not documents:
            log.warning("LlamaParse returned no documents for %s", file_path)
            return None

        return "\n\n".join(doc.text for doc in documents if doc.text)

    except Exception as exc:
        log.warning("LlamaParse failed for %s: %s", file_path, exc)
        return None


def llama_parse_available() -> bool:
    """Return True if llama-parse is installed and the API key is set."""
    from backend.config import get_settings
    settings = get_settings()
    if not settings.llama_cloud_api_key:
        return False
    try:
        import llama_parse  # noqa: F401
        return True
    except ImportError:
        return False
