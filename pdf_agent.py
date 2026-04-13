"""
PDF Data Extraction Agent
Extracts structured data from PDFs using pdfplumber + Gemini API.
"""

import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# PDF text + table extraction (pdfplumber)
# ---------------------------------------------------------------------------

def extract_raw(pdf_path: str) -> dict:
    """Extract raw text, tables, and page count from a PDF file."""
    pages_text = []
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages_text.append(text)

            for table in page.extract_tables():
                if table:
                    all_tables.append({"page": page_num, "data": table})

    return {
        "page_count": page_count,
        "full_text": "\n\n".join(pages_text),
        "raw_tables": all_tables,
    }


# ---------------------------------------------------------------------------
# Gemini-powered structured extraction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an intelligent PDF data extraction agent.

Your job is to analyze PDF text content and extracted table data, then return ONLY a valid JSON object.

Strict rules:
- Never invent or infer values. Extract only what is explicitly present in the text.
- If a field is not found, set its value to null.
- Normalize all dates to ISO 8601 (YYYY-MM-DD).
- Normalize all monetary values to numeric floats (strip currency symbols).
- Tables must be arrays of objects with consistent keys per row (use first row as header if present).
- Add a "confidence" key (0.0–1.0) per extracted field if uncertain.
- No markdown, no explanation, no preamble — raw JSON only.

Output envelope:
{
  "doc_type": "invoice|contract|resume|report|form|unknown",
  "page_count": <integer>,
  "extracted_at": "<ISO 8601 datetime>",
  "fields": { "<key>": "<value>" },
  "tables": [ { "name": "<table name or inferred label>", "rows": [ {…} ] } ],
  "entities": {
    "persons": [],
    "orgs": [],
    "dates": [],
    "amounts": []
  },
  "summary": "<2-sentence plain English summary>",
  "errors": [ { "field": "<field>", "reason": "<reason>" } ]
}"""


def build_user_message(raw: dict) -> str:
    tables_json = json.dumps(raw["raw_tables"], indent=2) if raw["raw_tables"] else "[]"
    extracted_at = datetime.now(timezone.utc).isoformat()

    return f"""PAGE COUNT: {raw["page_count"]}
EXTRACTED AT: {extracted_at}

--- FULL TEXT ---
{raw["full_text"]}

--- RAW TABLES (pdfplumber output) ---
{tables_json}

Now extract all structured data and return the JSON envelope. Set extracted_at to "{extracted_at}"."""


def extract_with_gemini(raw: dict) -> dict:
    """Send raw PDF content to Gemini and get structured JSON back."""
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=build_user_message(raw),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0,
            max_output_tokens=4096,
        ),
    )
    response_text = response.text.strip()

    # Strip accidental markdown fences
    if response_text.startswith("```"):
        lines = response_text.splitlines()
        response_text = "\n".join(
            line for line in lines if not line.startswith("```")
        ).strip()

    return json.loads(response_text)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_pdf(pdf_path: str) -> dict:
    path = Path(pdf_path)
    if not path.exists():
        return {
            "doc_type": "unknown",
            "page_count": 0,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "fields": {},
            "tables": [],
            "entities": {"persons": [], "orgs": [], "dates": [], "amounts": []},
            "summary": "File not found.",
            "errors": [{"field": "file", "reason": f"Path does not exist: {pdf_path}"}],
        }

    raw = extract_raw(str(path))
    result = extract_with_gemini(raw)
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 pdf_agent.py <path/to/file.pdf>", file=sys.stderr)
        sys.exit(1)

    output = process_pdf(sys.argv[1])
    print(json.dumps(output, indent=2))
