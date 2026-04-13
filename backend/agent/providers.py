"""
Multi-provider abstraction.
Each provider implements run_loop → str (raw model output / JSON).
APIclaw tools are optionally injected alongside pdf_reader so the LLM
can enrich extracted data with live Amazon intelligence.

Supported LLM providers: openai | gemini | anthropic
Enrichment layer       : apiclaw (Amazon data tools)
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared PDF reader tool (called by all providers)
# ---------------------------------------------------------------------------

def call_pdf_reader(file_path: str) -> str:
    """
    Parse a PDF and return its text, tables, and metadata as a JSON string.
    Used by OpenAI / Gemini / Anthropic tool-call loops.

    Parser priority:
      1. PyMuPDF  (local, fast)
      2. pytesseract OCR (fallback for scanned/image-only PDFs)

    Tables are always extracted with pdfplumber.
    Note: when LlamaParse is the selected provider the PDF is parsed
    by run_llamaparse() directly — this function is not called in that path.
    """
    import io
    from pathlib import Path

    errors: list[str] = []
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    llama_text: str | None = None

    # ── 2. PyMuPDF fallback ──────────────────────────────────────────────
    pages: list[str] = []
    if not llama_text:
        try:
            import fitz
            doc = fitz.open(file_path)
            for page in doc:
                pages.append(page.get_text("text"))
            doc.close()
        except Exception as exc:
            errors.append(f"PyMuPDF: {exc}")

        # ── 3. OCR fallback (sparse / scanned PDFs) ──────────────────────
        sparse = sum(1 for p in pages if len(p.strip()) < 30)
        if pages and (sparse / len(pages)) > 0.8:
            try:
                import fitz
                import pytesseract
                from PIL import Image
                doc = fitz.open(file_path)
                pages = []
                for page in doc:
                    pix = page.get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    pages.append(pytesseract.image_to_string(img))
                doc.close()
                log.info("OCR fallback used for %s", file_path)
            except Exception as exc:
                errors.append(f"OCR: {exc}")

    # ── 4. Table extraction (pdfplumber, always runs) ────────────────────
    tables: list[dict] = []
    page_count: int = len(pages)
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            for p_num, page in enumerate(pdf.pages, 1):
                for t_idx, raw in enumerate(page.extract_tables()):
                    if not raw or len(raw) < 2:
                        continue
                    header = [str(h).strip() if h else f"col_{i}"
                              for i, h in enumerate(raw[0])]
                    rows = [{header[i]: (c.strip() if c else None)
                             for i, c in enumerate(row)} for row in raw[1:]]
                    tables.append({"page": p_num, "name": f"table_p{p_num}_{t_idx+1}", "rows": rows})
    except Exception as exc:
        errors.append(f"pdfplumber: {exc}")

    full_text = llama_text if llama_text else "\n\n".join(pages)
    parser_used = "llamaparse" if llama_text else ("ocr" if pages else "pymupdf")

    return json.dumps({
        "parser": parser_used,
        "page_count": page_count,
        "full_text": full_text[:12000],
        "table_data": tables,
        "errors": errors,
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# LlamaParse provider  (no LLM — parses directly and builds the envelope)
# ---------------------------------------------------------------------------

def _parse_markdown_tables(text: str) -> list[dict]:
    """
    Extract pipe-delimited markdown tables from text.
    Returns a list of {"name": "table_N", "columns": [...], "rows": [...]} dicts.
    """
    import re

    tables: list[dict] = []
    lines = text.splitlines()
    i = 0
    table_num = 0

    while i < len(lines):
        line = lines[i].strip()

        # A header row must contain at least one pipe character
        if "|" not in line:
            i += 1
            continue

        # Next line must be a separator row  (|---|---|  or  | :---: |)
        if i + 1 >= len(lines):
            i += 1
            continue
        sep = lines[i + 1].strip()
        if not sep.startswith("|") or not re.fullmatch(r"[\|\-\s:]+", sep):
            i += 1
            continue

        # Parse headers — skip blank / all-dash cells (they're separators)
        raw_headers = [h.strip() for h in line.strip("|").split("|")]
        headers = [
            (h if h and not re.fullmatch(r"[\-\s:]+", h) else f"col_{j}")
            for j, h in enumerate(raw_headers)
        ]
        n_cols = len(headers)
        i += 2  # skip header row + separator row

        rows: list[dict] = []
        while i < len(lines):
            row_line = lines[i].strip()
            if "|" not in row_line:
                break
            cells = [c.strip() for c in row_line.strip("|").split("|")]
            # Pad or trim to match header count
            while len(cells) < n_cols:
                cells.append("")
            cells = cells[:n_cols]
            rows.append({headers[j]: cells[j] for j in range(n_cols)})
            i += 1

        if rows:
            table_num += 1
            tables.append({
                "name": f"table_{table_num}",
                "columns": headers,
                "rows": rows,
            })

    return tables


def run_llamaparse(file_path: str, result_type: str, api_key: str) -> str:
    """
    Parse a PDF with LlamaParse and return the standard extraction envelope.

    result_type: "markdown" (preserves tables/headers) | "text" (plain)
    No LLM API key required — LlamaParse handles the full parse step.
    """
    import datetime

    if result_type not in ("markdown", "text"):
        result_type = "markdown"

    try:
        from llama_parse import LlamaParse

        parser = LlamaParse(
            api_key=api_key,
            result_type=result_type,
            verbose=False,
            language="en",
        )
        documents = parser.load_data(file_path)
        full_text = "\n\n".join(doc.text for doc in documents if doc.text)
    except Exception as exc:
        log.error("LlamaParse failed: %s", exc)
        return json.dumps({
            "doc_type": "unknown",
            "page_count": 0,
            "extracted_at": datetime.datetime.utcnow().isoformat() + "Z",
            "fields": {},
            "tables": [],
            "entities": {"persons": [], "orgs": [], "dates": [], "amounts": []},
            "summary": f"LlamaParse error: {exc}",
            "errors": [{"field": "parse", "reason": str(exc)}],
        })

    # Parse structured tables from the markdown output (primary source)
    tables = _parse_markdown_tables(full_text)
    log.info("Extracted %d tables from LlamaParse markdown", len(tables))

    # Get page count from pdfplumber (lightweight — no table extraction needed)
    page_count = 0
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
    except Exception as exc:
        log.warning("pdfplumber page count failed: %s", exc)

    envelope = {
        "doc_type": "document",
        "page_count": page_count,
        "extracted_at": datetime.datetime.utcnow().isoformat() + "Z",
        "fields": {},
        "table_data": tables,
        "entities": {"persons": [], "orgs": [], "dates": [], "amounts": []},
        "summary": full_text[:600].strip(),
        "full_text": full_text,
        "parser": f"llamaparse/{result_type}",
        "errors": [],
    }
    return json.dumps(envelope, ensure_ascii=False)


# ---------------------------------------------------------------------------
# LiteParse provider  (local, no API key — Node.js CLI under the hood)
# ---------------------------------------------------------------------------

def run_liteparse(file_path: str) -> str:
    """
    Parse a PDF with LiteParse (local, no API key) and return the
    standard extraction envelope.

    Uses spatial-layout-preserving text output.  Markdown tables are
    extracted first; pdfplumber is used as a fallback for tables and
    always for page count.
    """
    import datetime

    errors: list[str] = []

    try:
        from backend.agent.lite_parser import parse_with_liteparse_full

        full_text, pages_data = parse_with_liteparse_full(file_path)
        if not full_text and not pages_data:
            raise RuntimeError("LiteParse returned no output")

    except Exception as exc:
        log.error("LiteParse provider failed: %s", exc)
        return json.dumps({
            "doc_type": "unknown",
            "page_count": 0,
            "extracted_at": datetime.datetime.utcnow().isoformat() + "Z",
            "fields": {},
            "table_data": [],
            "entities": {"persons": [], "orgs": [], "dates": [], "amounts": []},
            "summary": f"LiteParse error: {exc}",
            "parser": "liteparse",
            "errors": [{"field": "parse", "reason": str(exc)}],
        })

    # Try markdown table extraction from the spatial text first
    tables = _parse_markdown_tables(full_text)

    # pdfplumber: page count + table fallback when liteparse text has no pipe tables
    page_count = 0
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            if not tables:
                for p_num, page in enumerate(pdf.pages, 1):
                    for t_idx, raw in enumerate(page.extract_tables()):
                        if not raw or len(raw) < 2:
                            continue
                        header = [
                            str(h).strip() if h else f"col_{i}"
                            for i, h in enumerate(raw[0])
                        ]
                        rows = [
                            {header[i]: (c.strip() if c else None)
                             for i, c in enumerate(row)}
                            for row in raw[1:]
                        ]
                        tables.append({
                            "name": f"table_p{p_num}_{t_idx + 1}",
                            "columns": header,
                            "rows": rows,
                        })
    except Exception as exc:
        errors.append(f"pdfplumber: {exc}")

    log.info("LiteParse: %d pages, %d tables, %d chars", page_count, len(tables), len(full_text))

    envelope = {
        "doc_type": "document",
        "page_count": page_count,
        "extracted_at": datetime.datetime.utcnow().isoformat() + "Z",
        "fields": {},
        "table_data": tables,
        "entities": {"persons": [], "orgs": [], "dates": [], "amounts": []},
        "summary": full_text[:600].strip(),
        "full_text": full_text,
        "pages": pages_data,
        "parser": "liteparse",
        "errors": errors,
    }
    return json.dumps(envelope, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Unified tool dispatcher (pdf_reader + apiclaw)
# ---------------------------------------------------------------------------

def _dispatch_tool(name: str, args: dict, file_path: str) -> str:
    if name == "pdf_reader":
        return call_pdf_reader(args.get("file_path", file_path))
    return json.dumps({"error": f"Unknown tool: {name}"})


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

PDF_TOOL_OPENAI = {
    "type": "function",
    "function": {
        "name": "pdf_reader",
        "description": "Read a PDF file and return its full text, tables, and metadata. Always call this first.",
        "parameters": {
            "type": "object",
            "properties": {"file_path": {"type": "string"}},
            "required": ["file_path"],
        },
    },
}


def run_openai(
    file_path: str, system_prompt: str, model: str, api_key: str,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    tools = [PDF_TOOL_OPENAI]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"Extract all structured data from the PDF at path: {file_path}. "
            "Start by calling pdf_reader to read the file."
        )},
    ]

    for _ in range(8):
        response = client.chat.completions.create(
            model=model, messages=messages, tools=tools,
            tool_choice="auto", temperature=0, max_tokens=4096,
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            return msg.content or "{}"

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = _dispatch_tool(tc.function.name, args, file_path)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return "{}"


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------

def run_gemini(
    file_path: str, system_prompt: str, model: str, api_key: str,
) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    pdf_decl = types.FunctionDeclaration(
        name="pdf_reader",
        description="Read a PDF file and return its full text, tables, and metadata.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={"file_path": types.Schema(type=types.Type.STRING)},
            required=["file_path"],
        ),
    )
    tools_list: list[types.Tool] = [types.Tool(function_declarations=[pdf_decl])]

    config = types.GenerateContentConfig(
        system_instruction=system_prompt, tools=tools_list,
        temperature=0, max_output_tokens=4096,
    )
    contents: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=(
        f"Extract all structured data from the PDF at path: {file_path}. "
        "Start by calling pdf_reader to read the file."
    ))])]

    for _ in range(8):
        response = client.models.generate_content(model=model, contents=contents, config=config)
        candidate = response.candidates[0]
        contents.append(types.Content(role="model", parts=candidate.content.parts))

        tool_calls = [p for p in candidate.content.parts if p.function_call]
        if not tool_calls:
            return "\n".join(p.text for p in candidate.content.parts if p.text)

        tool_results = []
        for part in tool_calls:
            fc = part.function_call
            result = _dispatch_tool(fc.name, dict(fc.args), file_path)
            tool_results.append(types.Part(function_response=types.FunctionResponse(
                name=fc.name, response={"result": result}
            )))
        contents.append(types.Content(role="user", parts=tool_results))

    return "{}"


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

PDF_TOOL_ANTHROPIC = {
    "name": "pdf_reader",
    "description": "Read a PDF file and return its full text, tables, and metadata. Always call this first.",
    "input_schema": {
        "type": "object",
        "properties": {"file_path": {"type": "string"}},
        "required": ["file_path"],
    },
}


def run_anthropic(
    file_path: str, system_prompt: str, model: str, api_key: str,
) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    tools = [PDF_TOOL_ANTHROPIC]

    messages = [{"role": "user", "content": (
        f"Extract all structured data from the PDF at path: {file_path}. "
        "Start by calling pdf_reader to read the file."
    )}]

    for _ in range(8):
        response = client.messages.create(
            model=model, max_tokens=4096, system=system_prompt,
            tools=tools, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            return "\n".join(b.text for b in response.content if hasattr(b, "text"))

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = _dispatch_tool(block.name, block.input, file_path)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return "{}"


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def run_with_provider(
    file_path: str,
    system_prompt: str,
    provider: str,
    model: str | None = None,
) -> str:
    from backend.config import get_settings
    settings = get_settings()

    # ── LlamaParse: cloud parser, no LLM loop ────────────────────────────
    if provider == "llamaparse":
        result_type = model if model in ("markdown", "text") else "markdown"
        log.info("Provider=llamaparse result_type=%s", result_type)
        return run_llamaparse(file_path, result_type, settings.llama_cloud_api_key)

    # ── LiteParse: local parser, no API key ──────────────────────────────
    if provider == "liteparse":
        log.info("Provider=liteparse")
        return run_liteparse(file_path)

    if not model:
        model = {"openai": settings.openai_model,
                 "gemini": settings.gemini_model,
                 "anthropic": settings.anthropic_model}.get(provider, settings.openai_model)

    log.info("Provider=%s model=%s", provider, model)

    if provider == "openai":
        return run_openai(file_path, system_prompt, model, settings.openai_api_key)
    elif provider == "gemini":
        return run_gemini(file_path, system_prompt, model, settings.google_api_key)
    elif provider == "anthropic":
        return run_anthropic(file_path, system_prompt, model, settings.anthropic_api_key)
    else:
        raise ValueError(f"Unknown provider: {provider}")
