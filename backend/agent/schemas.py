"""
Layer 3 — Pydantic domain schemas + schema-guided extraction factory.
Import any schema and pass it to `build_extraction_prompt()` to get a
runtime-injected system prompt that maps PDF content to exact field names.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Base envelope (mirrors the agent's JSON output)
# ---------------------------------------------------------------------------

class ExtractionEnvelope(BaseModel):
    doc_type: str
    page_count: int
    extracted_at: str
    fields: dict
    table_data: list[dict]
    entities: dict
    summary: str
    errors: list[dict]


# ---------------------------------------------------------------------------
# Domain schemas — one per document type
# ---------------------------------------------------------------------------

class InvoiceSchema(BaseModel):
    """Fields the agent must extract from an invoice."""
    invoice_number: Optional[str] = Field(None, description="Unique invoice identifier")
    invoice_date: Optional[str] = Field(None, description="Date invoice was issued (ISO 8601)")
    due_date: Optional[str] = Field(None, description="Payment due date (ISO 8601)")
    vendor_name: Optional[str] = Field(None, description="Name of the issuing vendor/supplier")
    vendor_address: Optional[str] = Field(None, description="Full address of the vendor")
    vendor_tax_id: Optional[str] = Field(None, description="VAT / GST / EIN of the vendor")
    client_name: Optional[str] = Field(None, description="Name of the billed client")
    client_address: Optional[str] = Field(None, description="Full address of the client")
    subtotal: Optional[float] = Field(None, description="Pre-tax total amount as float")
    tax_amount: Optional[float] = Field(None, description="Total tax amount as float")
    discount: Optional[float] = Field(None, description="Discount applied as float")
    total_amount: Optional[float] = Field(None, description="Final payable amount as float")
    currency: Optional[str] = Field(None, description="ISO 4217 currency code e.g. USD")
    payment_terms: Optional[str] = Field(None, description="e.g. Net 30, Due on receipt")
    purchase_order: Optional[str] = Field(None, description="PO number if referenced")
    bank_details: Optional[str] = Field(None, description="Bank / payment instructions")


class ContractSchema(BaseModel):
    """Fields the agent must extract from a contract or agreement."""
    contract_title: Optional[str] = Field(None, description="Title or type of the contract")
    contract_date: Optional[str] = Field(None, description="Date the contract was signed (ISO 8601)")
    effective_date: Optional[str] = Field(None, description="Date the contract takes effect (ISO 8601)")
    expiry_date: Optional[str] = Field(None, description="Termination or expiry date (ISO 8601)")
    parties: Optional[list[str]] = Field(None, description="Full legal names of all signing parties")
    governing_law: Optional[str] = Field(None, description="Jurisdiction / governing law clause")
    contract_value: Optional[float] = Field(None, description="Total contract value as float")
    payment_schedule: Optional[str] = Field(None, description="Payment milestone summary")
    termination_clause: Optional[str] = Field(None, description="Summary of termination conditions")
    confidentiality: Optional[bool] = Field(None, description="True if an NDA / confidentiality clause exists")
    arbitration_clause: Optional[bool] = Field(None, description="True if arbitration clause present")
    renewal_terms: Optional[str] = Field(None, description="Auto-renewal or extension terms")


class ResumeSchema(BaseModel):
    """Fields the agent must extract from a resume / CV."""
    full_name: Optional[str] = Field(None, description="Candidate's full name")
    email: Optional[str] = Field(None, description="Primary email address")
    phone: Optional[str] = Field(None, description="Primary phone number")
    location: Optional[str] = Field(None, description="City, State / Country")
    linkedin: Optional[str] = Field(None, description="LinkedIn profile URL")
    summary: Optional[str] = Field(None, description="Professional summary or objective")
    skills: Optional[list[str]] = Field(None, description="List of technical and soft skills")
    education: Optional[list[dict]] = Field(None, description="List of {degree, institution, year}")
    experience: Optional[list[dict]] = Field(None, description="List of {title, company, start, end, description}")
    certifications: Optional[list[str]] = Field(None, description="List of certifications")
    languages: Optional[list[str]] = Field(None, description="Spoken/written languages")
    total_years_experience: Optional[float] = Field(None, description="Computed total years of experience")


class ReportSchema(BaseModel):
    """Fields the agent must extract from a business or technical report."""
    report_title: Optional[str] = Field(None, description="Title of the report")
    report_date: Optional[str] = Field(None, description="Publication date (ISO 8601)")
    authors: Optional[list[str]] = Field(None, description="Author names")
    organization: Optional[str] = Field(None, description="Issuing organization")
    executive_summary: Optional[str] = Field(None, description="Executive summary or abstract")
    key_findings: Optional[list[str]] = Field(None, description="Bullet-point key findings")
    recommendations: Optional[list[str]] = Field(None, description="Recommendations listed")
    period_covered: Optional[str] = Field(None, description="Reporting period e.g. Q1 2024")


class FormSchema(BaseModel):
    """Generic form — extracts all labeled field-value pairs."""
    form_title: Optional[str] = Field(None, description="Title or name of the form")
    form_id: Optional[str] = Field(None, description="Form ID or reference number")
    submission_date: Optional[str] = Field(None, description="Date form was submitted (ISO 8601)")
    submitter_name: Optional[str] = Field(None, description="Name of the person who filled the form")
    form_fields: Optional[dict] = Field(None, description="All labeled field-value pairs as a dict")


# ---------------------------------------------------------------------------
# Schema registry
# ---------------------------------------------------------------------------

SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "invoice":  InvoiceSchema,
    "contract": ContractSchema,
    "resume":   ResumeSchema,
    "report":   ReportSchema,
    "form":     FormSchema,
}


def get_schema_for_type(doc_type: str) -> type[BaseModel] | None:
    return SCHEMA_REGISTRY.get(doc_type.lower())


def build_extraction_prompt(doc_type: str | None = None) -> str:
    """
    Return the system prompt to inject into the AgentExecutor.
    If doc_type is supplied and has a registered schema, injects the
    Pydantic JSON Schema for schema-guided extraction (Layer 3).
    Falls back to the generic system prompt if no schema is registered.
    """
    from backend.agent.prompts import build_system_prompt

    if doc_type:
        model_cls = get_schema_for_type(doc_type)
        if model_cls:
            return build_system_prompt(model_cls.model_json_schema())

    return build_system_prompt()
