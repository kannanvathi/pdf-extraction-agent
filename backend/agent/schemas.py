"""
Layer 3 — Pydantic schemas for loss run insurance document extraction.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Loss Run — claim row
# ---------------------------------------------------------------------------

class LossRunClaim(BaseModel):
    """A single claim record extracted from a loss run report."""
    period_index: Optional[int] = Field(None, description="0-based index into policy_periods list")
    claim_number: Optional[str] = Field(None, description="Unique claim identifier assigned by the carrier")
    date_of_loss: Optional[str] = Field(None, description="Date the loss/incident occurred (ISO 8601)")
    date_reported: Optional[str] = Field(None, description="Date the claim was reported to the carrier (ISO 8601)")
    date_closed: Optional[str] = Field(None, description="Date the claim was closed (ISO 8601), null if open")
    claimant_name: Optional[str] = Field(None, description="Name of the claimant or injured party")
    type_of_loss: Optional[str] = Field(None, description="Cause or type of loss (e.g. Slip & Fall, Auto Collision)")
    description: Optional[str] = Field(None, description="Brief description of the incident or claim")
    status: Optional[str] = Field(None, description="Claim status: open | closed | reopened")
    paid_indemnity: Optional[float] = Field(None, description="Indemnity/compensation payments made to date")
    paid_expense: Optional[float] = Field(None, description="Allocated loss adjustment expense paid")
    total_paid: Optional[float] = Field(None, description="Total payments made (indemnity + expense)")
    outstanding_reserve: Optional[float] = Field(None, description="Outstanding reserve / case reserve remaining")
    total_incurred: Optional[float] = Field(None, description="Total incurred = total_paid + outstanding_reserve")
    subrogation: Optional[float] = Field(None, description="Subrogation or recovery amount received")
    litigation: Optional[bool] = Field(None, description="True if the claim is in litigation")


# ---------------------------------------------------------------------------
# Loss Run — policy period summary
# ---------------------------------------------------------------------------

class PolicyPeriod(BaseModel):
    """Aggregate statistics for one policy year within a loss run."""
    period_index: Optional[int] = Field(None, description="0-based index (0 = most recent)")
    period_start: Optional[str] = Field(None, description="Policy period start date (ISO 8601)")
    period_end: Optional[str] = Field(None, description="Policy period end date (ISO 8601)")
    policy_number: Optional[str] = Field(None, description="Policy number for this specific period")
    total_claims: Optional[int] = Field(None, description="Total number of claims in this period")
    open_claims: Optional[int] = Field(None, description="Number of open/pending claims")
    closed_claims: Optional[int] = Field(None, description="Number of closed claims")
    total_paid: Optional[float] = Field(None, description="Total paid losses + expenses for this period")
    total_reserve: Optional[float] = Field(None, description="Total outstanding reserves for this period")
    total_incurred: Optional[float] = Field(None, description="Total incurred for this period")


# ---------------------------------------------------------------------------
# Loss Run — policy header
# ---------------------------------------------------------------------------

class PolicyInfo(BaseModel):
    """Header-level policy information from the loss run report."""
    insured_name: Optional[str] = Field(None, description="Full legal name of the insured")
    policy_number: Optional[str] = Field(None, description="Primary policy number")
    policy_period_start: Optional[str] = Field(None, description="Start of the most recent policy period (ISO 8601)")
    policy_period_end: Optional[str] = Field(None, description="End of the most recent policy period (ISO 8601)")
    line_of_business: Optional[str] = Field(None, description="Line of business: GL | WC | Auto | Property | Umbrella | Package | Other")
    insurer_name: Optional[str] = Field(None, description="Name of the insurance carrier/company")
    producer_name: Optional[str] = Field(None, description="Producer, broker, or agent name")
    account_number: Optional[str] = Field(None, description="Account or risk number")
    report_date: Optional[str] = Field(None, description="Date this loss run report was generated (ISO 8601)")
    state: Optional[str] = Field(None, description="2-letter US state code where the policy is domiciled")


# ---------------------------------------------------------------------------
# Loss Run — document-level summary
# ---------------------------------------------------------------------------

class LossRunSummary(BaseModel):
    """Aggregate totals across ALL policy periods in the document."""
    total_claims: Optional[int] = Field(None, description="Total claim count across all periods")
    open_claims: Optional[int] = Field(None, description="Total open claims across all periods")
    closed_claims: Optional[int] = Field(None, description="Total closed claims across all periods")
    total_paid: Optional[float] = Field(None, description="Total paid across all periods")
    total_reserve: Optional[float] = Field(None, description="Total outstanding reserves across all periods")
    total_incurred: Optional[float] = Field(None, description="Total incurred across all periods")
    loss_ratio_note: Optional[str] = Field(None, description="Any loss ratio or commentary present in the document")


# ---------------------------------------------------------------------------
# Loss Run — full extraction envelope
# ---------------------------------------------------------------------------

class LossRunSchema(BaseModel):
    """Complete structured extraction of a Loss Run insurance document."""
    doc_type: str = Field("lossrun", description="Always 'lossrun'")
    page_count: Optional[int] = Field(None, description="Total pages in the document")
    extracted_at: Optional[str] = Field(None, description="UTC datetime of extraction (ISO 8601)")
    policy_info: Optional[PolicyInfo] = Field(None, description="Policy header information")
    policy_periods: Optional[list[PolicyPeriod]] = Field(None, description="One entry per policy year")
    claims: Optional[list[LossRunClaim]] = Field(None, description="All individual claim records")
    summary: Optional[LossRunSummary] = Field(None, description="Aggregate totals across all periods")
    full_text: Optional[str] = Field(None, description="Raw extracted text from the document")
    errors: Optional[list[dict]] = Field(None, description="Fields that could not be extracted")


# ---------------------------------------------------------------------------
# Schema registry (kept for backwards-compatibility with executor)
# ---------------------------------------------------------------------------

SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "lossrun": LossRunSchema,
}


def get_schema_for_type(doc_type: str) -> type[BaseModel] | None:
    return SCHEMA_REGISTRY.get(doc_type.lower())


def build_extraction_prompt(doc_type: str | None = None) -> str:
    """Always returns the loss run system prompt."""
    from backend.agent.prompts import build_system_prompt
    return build_system_prompt()
