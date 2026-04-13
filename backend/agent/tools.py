"""
Layer 2 — PDF reader @tool.
Primary parser  : PyMuPDF (fitz)  — fast, handles native/text PDFs.
Fallback parser : pdfplumber      — better table detection.
OCR fallback    : pytesseract     — for scanned / image-only PDFs.
Returns a dict with pages, tables, and chunked text ready for the LLM.
"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pages_via_pymupdf(pdf_path: str) -> tuple[list[str], int]:
    """Extract per-page text with PyMuPDF. Returns (pages, page_count)."""
    import fitz  # PyMuPDF

    pages: list[str] = []
    doc = fitz.open(pdf_path)
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()
    return pages, len(pages)


def _is_scanned(pages: list[str]) -> bool:
    """Heuristic: if >80 % of pages have fewer than 30 chars, treat as scanned."""
    if not pages:
        return True
    sparse = sum(1 for p in pages if len(p.strip()) < 30)
    return (sparse / len(pages)) > 0.8


def _ocr_pages(pdf_path: str) -> list[str]:
    """OCR every page via pytesseract. Used only for scanned PDFs."""
    import fitz
    import pytesseract
    from PIL import Image

    doc = fitz.open(pdf_path)
    pages: list[str] = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        pages.append(pytesseract.image_to_string(img))
    doc.close()
    return pages


def _tables_via_pdfplumber(pdf_path: str) -> list[dict[str, Any]]:
    """Extract tables using pdfplumber. Returns list of {page, name, rows}."""
    import pdfplumber

    result: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            for t_idx, raw_table in enumerate(page.extract_tables()):
                if not raw_table or len(raw_table) < 2:
                    continue
                header = [str(h).strip() if h else f"col_{i}"
                          for i, h in enumerate(raw_table[0])]
                rows = [
                    {header[i]: (cell.strip() if cell else None)
                     for i, cell in enumerate(row)}
                    for row in raw_table[1:]
                ]
                result.append({
                    "page": page_num,
                    "name": f"table_p{page_num}_{t_idx + 1}",
                    "rows": rows,
                })
    return result


def _chunk_text(pages: list[str], chunk_size: int = 3000) -> list[str]:
    """Split concatenated page text into chunks the LLM can digest."""
    full_text = "\n\n".join(pages)
    return [full_text[i:i + chunk_size]
            for i in range(0, len(full_text), chunk_size)]


# ---------------------------------------------------------------------------
# LangChain @tool
# ---------------------------------------------------------------------------

@tool
def pdf_reader(file_path: str) -> str:
    """
    Read a PDF file and return its content as a JSON string.

    Uses PyMuPDF as the primary parser. Falls back to pytesseract OCR
    for scanned / image-only documents. Tables are always extracted with
    pdfplumber for the best accuracy.

    Args:
        file_path: Absolute path to the PDF file on disk.

    Returns:
        JSON string with keys:
          - page_count  : total number of pages
          - pages       : list of per-page text strings
          - chunks      : text split into ~3000-char segments for the LLM
          - tables      : list of {page, name, rows} table objects
          - ocr_used    : bool — whether OCR fallback was triggered
          - errors      : list of error strings encountered during parsing
    """
    errors: list[str] = []
    ocr_used = False

    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})
    if path.suffix.lower() != ".pdf":
        return json.dumps({"error": f"Not a PDF file: {file_path}"})

    # --- Primary: PyMuPDF text extraction ---
    try:
        pages, page_count = _pages_via_pymupdf(file_path)
    except Exception as exc:
        errors.append(f"PyMuPDF failed: {exc}")
        pages, page_count = [], 0

    # --- OCR fallback for scanned documents ---
    if _is_scanned(pages):
        log.info("Scanned PDF detected — falling back to pytesseract OCR.")
        try:
            pages = _ocr_pages(file_path)
            page_count = len(pages)
            ocr_used = True
        except Exception as exc:
            errors.append(f"OCR failed: {exc}")

    # --- Table extraction: always pdfplumber ---
    try:
        tables = _tables_via_pdfplumber(file_path)
    except Exception as exc:
        errors.append(f"pdfplumber table extraction failed: {exc}")
        tables = []

    return json.dumps({
        "page_count": page_count,
        "pages": pages,
        "chunks": _chunk_text(pages),
        "tables": tables,
        "ocr_used": ocr_used,
        "errors": errors,
    }, ensure_ascii=False)
