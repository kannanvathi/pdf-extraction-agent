"""
LiteParse — local document parsing via the LlamaIndex LiteParse library.

Runs entirely on-device (Node.js CLI under the hood), no API key required.
Preserves spatial layout as a grid that LLMs understand natively.

Requirements:
    npm install -g @llamaindex/liteparse   # Node.js CLI (once)
    pip install liteparse                  # Python wrapper
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def liteparse_available() -> bool:
    """Return True if the liteparse package and CLI are both accessible."""
    try:
        from liteparse import LiteParse  # noqa: F401
        return True
    except ImportError:
        return False


def parse_with_liteparse(file_path: str, ocr_enabled: bool = True) -> str | None:
    """
    Parse a document with LiteParse and return the full text.

    Returns None on failure so callers can fall back gracefully.

    Args:
        file_path   : absolute path to the PDF (or DOCX/XLSX/image)
        ocr_enabled : enable Tesseract OCR for scanned pages (default True)
    """
    if not Path(file_path).exists():
        log.error("LiteParse: file not found: %s", file_path)
        return None

    try:
        from liteparse import LiteParse

        parser = LiteParse()
        result = parser.parse(file_path, ocr_enabled=ocr_enabled)
        text = result.text or ""
        log.info(
            "LiteParse parsed %s — %d pages, %d chars",
            Path(file_path).name,
            result.num_pages,
            len(text),
        )
        return text

    except Exception as exc:
        log.error("LiteParse failed for %s: %s", file_path, exc)
        return None


def parse_with_liteparse_full(
    file_path: str, ocr_enabled: bool = True
) -> tuple[str, list[dict]]:
    """
    Parse a document with LiteParse and return full text + per-page spatial data.

    Returns:
        (text, pages_data) where pages_data is a list of dicts with shape:
        {
            pageNum: int,
            width: float,
            height: float,
            textItems: [{text, x, y, width, height, confidence, fontName, fontSize}],
            boundingBoxes: [{x1, y1, x2, y2}]
        }

    On failure returns ("", []).
    """
    if not Path(file_path).exists():
        log.error("LiteParse: file not found: %s", file_path)
        return "", []

    try:
        from liteparse import LiteParse

        parser = LiteParse()
        result = parser.parse(file_path, ocr_enabled=ocr_enabled)
        text = result.text or ""

        pages_data: list[dict] = []
        for page in result.pages:
            text_items = []
            for item in getattr(page, "textItems", []):
                text_items.append({
                    "text":       getattr(item, "text", ""),
                    "x":          getattr(item, "x", 0),
                    "y":          getattr(item, "y", 0),
                    "width":      getattr(item, "width", 0),
                    "height":     getattr(item, "height", 0),
                    "confidence": getattr(item, "confidence", None),
                    "fontName":   getattr(item, "fontName", None),
                    "fontSize":   getattr(item, "fontSize", None),
                })

            bounding_boxes = []
            for bb in getattr(page, "boundingBoxes", []):
                bounding_boxes.append({
                    "x1": getattr(bb, "x1", 0),
                    "y1": getattr(bb, "y1", 0),
                    "x2": getattr(bb, "x2", 0),
                    "y2": getattr(bb, "y2", 0),
                })

            pages_data.append({
                "pageNum":      getattr(page, "pageNum", 0),
                "width":        getattr(page, "width", 0),
                "height":       getattr(page, "height", 0),
                "textItems":    text_items,
                "boundingBoxes": bounding_boxes,
            })

        log.info(
            "LiteParse (full) parsed %s — %d pages, %d chars",
            Path(file_path).name,
            result.num_pages,
            len(text),
        )
        return text, pages_data

    except Exception as exc:
        log.error("LiteParse (full) failed for %s: %s", file_path, exc)
        return "", []
