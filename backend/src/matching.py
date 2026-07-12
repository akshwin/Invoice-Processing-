"""Stage 2 — PO Matching (BRD Section 6, 9). Deterministic — no LLM call."""
import csv
from dataclasses import dataclass
from typing import Optional

from .schemas import ExtractedInvoice


@dataclass
class PurchaseOrder:
    po_number: str
    vendor_name: str
    po_amount: float
    po_date: str
    status: str


@dataclass
class MatchResult:
    matched_po: Optional[PurchaseOrder]
    match_method: str  # "po_number" | "vendor_and_amount" | "no_match"
    notes: str


def load_po_dataset(csv_path: str) -> list[PurchaseOrder]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            PurchaseOrder(
                po_number=row["po_number"].strip(),
                vendor_name=row["vendor_name"].strip(),
                po_amount=float(row["po_amount"]),
                po_date=row["po_date"].strip(),
                status=row["status"].strip().lower(),
            )
            for row in reader
        ]


def _vendor_names_match(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    return a == b or a in b or b in a


def match_invoice_to_po(invoice: ExtractedInvoice, pos: list[PurchaseOrder]) -> MatchResult:
    if invoice.po_reference:
        for po in pos:
            if po.po_number.strip().lower() == invoice.po_reference.strip().lower():
                return MatchResult(
                    matched_po=po,
                    match_method="po_number",
                    notes=f"Matched by explicit PO reference '{invoice.po_reference}' on the invoice.",
                )
        return MatchResult(
            matched_po=None,
            match_method="no_match",
            notes=f"Invoice states PO reference '{invoice.po_reference}', but no PO with that number exists in the PO dataset.",
        )

    if not invoice.vendor_name:
        return MatchResult(
            matched_po=None,
            match_method="no_match",
            notes="Invoice has no PO reference and no vendor name to match against.",
        )

    candidates = [po for po in pos if _vendor_names_match(po.vendor_name, invoice.vendor_name)]

    if not candidates:
        return MatchResult(
            matched_po=None,
            match_method="no_match",
            notes=f"No PO found for vendor '{invoice.vendor_name}' (no explicit PO reference on the invoice).",
        )

    if len(candidates) == 1:
        return MatchResult(
            matched_po=candidates[0],
            match_method="vendor_and_amount",
            notes=f"Matched by vendor name '{invoice.vendor_name}' (only one open PO for this vendor).",
        )

    if invoice.total is None:
        return MatchResult(
            matched_po=None,
            match_method="no_match",
            notes=f"Multiple POs found for vendor '{invoice.vendor_name}' and invoice has no total to disambiguate by amount proximity.",
        )

    best = min(candidates, key=lambda po: abs(po.po_amount - invoice.total))
    return MatchResult(
        matched_po=best,
        match_method="vendor_and_amount",
        notes=f"Matched by vendor name '{invoice.vendor_name}' and closest amount proximity (PO amount {best.po_amount} vs invoice total {invoice.total}).",
    )
