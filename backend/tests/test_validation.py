import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.matching import MatchResult, PurchaseOrder
from src.schemas import ExtractedInvoice
from src.validation import (
    AMOUNT_TOLERANCE_FLAT,
    AMOUNT_TOLERANCE_PERCENT,
    check_amount_tolerance,
    check_duplicate,
    check_po_matched,
    check_required_fields,
    run_validation,
)

PO = PurchaseOrder("PO-10234", "Bluebird Supplies Inc.", 4500.00, "2026-05-01", "open")


def test_br1_fails_when_no_match():
    match = MatchResult(matched_po=None, match_method="no_match", notes="none found")
    outcome = check_po_matched(match)
    assert not outcome.passed
    assert outcome.rule_id == "BR-1"


def test_br2_fails_when_total_missing():
    invoice = ExtractedInvoice(invoice_number="INV-1", vendor_name="Bluebird Supplies Inc.", total=None)
    outcome = check_required_fields(invoice)
    assert not outcome.passed
    assert "total" in outcome.message


def test_br2_passes_when_all_present():
    invoice = ExtractedInvoice(invoice_number="INV-1", vendor_name="Bluebird Supplies Inc.", total=100.0)
    outcome = check_required_fields(invoice)
    assert outcome.passed


def test_br3_detects_duplicate():
    invoice = ExtractedInvoice(invoice_number="INV-1", vendor_name="Bluebird Supplies Inc.", total=100.0)
    history = [{"vendor_name": "Bluebird Supplies Inc.", "invoice_number": "INV-1", "total": 100.0}]
    outcome = check_duplicate(invoice, history)
    assert not outcome.passed


def test_br3_no_duplicate_when_amount_differs():
    invoice = ExtractedInvoice(invoice_number="INV-1", vendor_name="Bluebird Supplies Inc.", total=100.0)
    history = [{"vendor_name": "Bluebird Supplies Inc.", "invoice_number": "INV-1", "total": 999.0}]
    outcome = check_duplicate(invoice, history)
    assert outcome.passed


def test_br4_passes_within_tolerance():
    invoice = ExtractedInvoice(total=4520.0)  # delta $20, within $50 flat tolerance
    outcome = check_amount_tolerance(invoice, PO, [])
    assert outcome.passed


def test_br4_fails_outside_tolerance():
    invoice = ExtractedInvoice(total=5200.0)  # delta $700, way outside tolerance
    outcome = check_amount_tolerance(invoice, PO, [])
    assert not outcome.passed
    assert outcome.rule_id == "BR-4"


def test_br5_uses_remaining_balance_for_partial_po():
    invoice = ExtractedInvoice(total=2000.0)
    history = [{"matched_po": "PO-10234", "decision": "APPROVE", "total": 2500.0}]
    # remaining balance = 4500 - 2500 = 2000 -> exact match, should pass as BR-5 context
    outcome = check_amount_tolerance(invoice, PO, history)
    assert outcome.passed


def test_br5_flags_not_rejects_when_partial_balance_mismatch():
    invoice = ExtractedInvoice(total=3000.0)
    history = [{"matched_po": "PO-10234", "decision": "APPROVE", "total": 2500.0}]
    # remaining balance = 2000, invoice wants 3000 -> mismatch, should be BR-5 (flag, not reject)
    outcome = check_amount_tolerance(invoice, PO, history)
    assert not outcome.passed
    assert outcome.rule_id == "BR-5"


def test_full_validation_happy_path():
    invoice = ExtractedInvoice(invoice_number="INV-1", vendor_name="Bluebird Supplies Inc.", total=4500.0)
    match = MatchResult(matched_po=PO, match_method="po_number", notes="matched")
    result = run_validation(invoice, match, [])
    assert result.failed_outcome is None


def test_full_validation_ec1_amount_mismatch():
    invoice = ExtractedInvoice(invoice_number="INV-1", vendor_name="Bluebird Supplies Inc.", total=6200.0)
    match = MatchResult(matched_po=PO, match_method="po_number", notes="matched")
    result = run_validation(invoice, match, [])
    assert result.failed_outcome.rule_id == "BR-4"


def test_full_validation_ec2_missing_total():
    invoice = ExtractedInvoice(invoice_number="INV-1", vendor_name="Bluebird Supplies Inc.", total=None)
    match = MatchResult(matched_po=PO, match_method="po_number", notes="matched")
    result = run_validation(invoice, match, [])
    assert result.failed_outcome.rule_id == "BR-2"


def test_tolerance_constants_are_named_not_magic():
    assert AMOUNT_TOLERANCE_PERCENT == 0.02
    assert AMOUNT_TOLERANCE_FLAT == 50.0
