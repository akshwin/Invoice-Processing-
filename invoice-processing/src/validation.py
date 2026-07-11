"""Stage 3 — Validation (BRD Section 6.1). Plain Python, deterministic, unit-testable.

Rules run in order (BRD Section 6 flowchart) — each can short-circuit the ones below it:
BR-1 (PO match) -> BR-2 (required fields) -> BR-3 (duplicate) -> BR-4/BR-5 (amount tolerance).
"""
from dataclasses import dataclass
from typing import Optional

from .matching import MatchResult, PurchaseOrder
from .schemas import ExtractedInvoice

# BR-4 default threshold (BRD 6.1): "configurable — expose as constants, not magic numbers"
AMOUNT_TOLERANCE_PERCENT = 0.02
AMOUNT_TOLERANCE_FLAT = 50.0


@dataclass
class RuleOutcome:
    rule_id: str
    passed: bool
    message: str


def check_po_matched(match: MatchResult) -> RuleOutcome:
    """BR-1: Invoice must match to exactly one PO."""
    if match.matched_po is None:
        return RuleOutcome("BR-1", False, f"No matching PO found. {match.notes}")
    return RuleOutcome("BR-1", True, match.notes)


def check_required_fields(invoice: ExtractedInvoice) -> RuleOutcome:
    """BR-2: invoice_number, total, and vendor_name must all be present."""
    missing = []
    if not invoice.invoice_number:
        missing.append("invoice number")
    if invoice.total is None:
        missing.append("total")
    if not invoice.vendor_name:
        missing.append("vendor name")

    if missing:
        return RuleOutcome("BR-2", False, f"Missing critical field(s): {', '.join(missing)}.")
    return RuleOutcome("BR-2", True, "Invoice number, total, and vendor name are all present.")


def check_duplicate(invoice: ExtractedInvoice, history: list[dict]) -> RuleOutcome:
    """BR-3: same vendor + invoice number + amount seen before => duplicate."""
    for past in history:
        if (
            past.get("vendor_name") == invoice.vendor_name
            and past.get("invoice_number") == invoice.invoice_number
            and past.get("total") == invoice.total
        ):
            return RuleOutcome(
                "BR-3",
                False,
                f"An invoice with the same vendor, invoice number ('{invoice.invoice_number}'), "
                f"and amount has already been processed.",
            )
    return RuleOutcome("BR-3", True, "No prior invoice found with the same vendor, number, and amount.")


def compute_remaining_po_balance(po: PurchaseOrder, history: list[dict]) -> float:
    """BR-5 helper: PO amount minus totals of previously APPROVED invoices matched to this PO."""
    consumed = sum(
        past["total"]
        for past in history
        if past.get("matched_po") == po.po_number and past.get("decision") == "APPROVE" and past.get("total") is not None
    )
    return po.po_amount - consumed


def check_amount_tolerance(
    invoice: ExtractedInvoice, po: PurchaseOrder, history: list[dict]
) -> RuleOutcome:
    """BR-4 (with BR-5 partial-balance adjustment): invoice total must be within tolerance
    of the matched PO amount — or of the PO's remaining balance, if it's been partially
    consumed by earlier approved invoices."""
    remaining_balance = compute_remaining_po_balance(po, history)
    is_partial = remaining_balance < po.po_amount

    reference_amount = remaining_balance if is_partial else po.po_amount
    tolerance = max(reference_amount * AMOUNT_TOLERANCE_PERCENT, AMOUNT_TOLERANCE_FLAT)
    delta = invoice.total - reference_amount

    if abs(delta) <= tolerance:
        return RuleOutcome(
            "BR-4",
            True,
            f"Invoice total ({invoice.total}) is within tolerance of the reference amount ({reference_amount}).",
        )

    rule_id = "BR-5" if is_partial else "BR-4"
    reference_label = "remaining PO balance" if is_partial else "PO amount"
    return RuleOutcome(
        rule_id,
        False,
        f"Invoice total is {invoice.total}, {reference_label} is {reference_amount}, "
        f"a difference of {delta:+.2f} — outside the tolerance of ±{tolerance:.2f}.",
    )


@dataclass
class ValidationResult:
    outcomes: list[RuleOutcome]
    failed_outcome: Optional[RuleOutcome]  # the rule that short-circuited, if any


def run_validation(
    invoice: ExtractedInvoice, match: MatchResult, history: list[dict]
) -> ValidationResult:
    outcomes = []

    br1 = check_po_matched(match)
    outcomes.append(br1)
    if not br1.passed:
        return ValidationResult(outcomes, br1)

    br2 = check_required_fields(invoice)
    outcomes.append(br2)
    if not br2.passed:
        return ValidationResult(outcomes, br2)

    br3 = check_duplicate(invoice, history)
    outcomes.append(br3)
    if not br3.passed:
        return ValidationResult(outcomes, br3)

    br4 = check_amount_tolerance(invoice, match.matched_po, history)
    outcomes.append(br4)
    if not br4.passed:
        return ValidationResult(outcomes, br4)

    return ValidationResult(outcomes, None)
