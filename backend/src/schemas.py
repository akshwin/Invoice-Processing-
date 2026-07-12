"""Pydantic schemas per BRD Section 8.1 (invoice) and 8.3 (decision output)."""
from typing import Optional
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None


class ExtractedInvoice(BaseModel):
    """BRD 8.1 — structured extraction target. Missing fields must be null, never guessed."""
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None  # ISO 8601
    vendor_name: Optional[str] = None
    po_reference: Optional[str] = None
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    extraction_confidence_notes: str = ""


class DecisionOutput(BaseModel):
    """BRD 8.3 — final decision record."""
    invoice_number: Optional[str]
    vendor_name: Optional[str]
    matched_po: Optional[str]
    decision: str  # APPROVE | FLAG_FOR_REVIEW | REJECT
    reasoning: str
    rules_triggered: list[str]
    timestamp: str
    run_id: str
