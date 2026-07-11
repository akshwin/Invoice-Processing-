import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.matching import PurchaseOrder, match_invoice_to_po
from src.schemas import ExtractedInvoice

POS = [
    PurchaseOrder("PO-10234", "Bluebird Supplies Inc.", 4500.00, "2026-05-01", "open"),
    PurchaseOrder("PO-10237", "Northgate Industrial Parts", 1200.00, "2026-05-05", "open"),
    PurchaseOrder("PO-99999", "Acme Corp", 100.0, "2026-01-01", "open"),
    PurchaseOrder("PO-88888", "Acme Corp", 500.0, "2026-01-02", "open"),
]


def test_match_by_explicit_po_number():
    invoice = ExtractedInvoice(vendor_name="Bluebird Supplies Inc.", po_reference="PO-10234", total=4500.0)
    result = match_invoice_to_po(invoice, POS)
    assert result.matched_po.po_number == "PO-10234"
    assert result.match_method == "po_number"


def test_explicit_po_number_not_found_is_no_match():
    invoice = ExtractedInvoice(vendor_name="Bluebird Supplies Inc.", po_reference="PO-00000", total=4500.0)
    result = match_invoice_to_po(invoice, POS)
    assert result.matched_po is None
    assert result.match_method == "no_match"


def test_match_by_vendor_when_no_po_reference():
    invoice = ExtractedInvoice(vendor_name="Northgate Industrial Parts", po_reference=None, total=1200.0)
    result = match_invoice_to_po(invoice, POS)
    assert result.matched_po.po_number == "PO-10237"
    assert result.match_method == "vendor_and_amount"


def test_match_by_vendor_and_amount_proximity_when_multiple_candidates():
    invoice = ExtractedInvoice(vendor_name="Acme Corp", po_reference=None, total=110.0)
    result = match_invoice_to_po(invoice, POS)
    assert result.matched_po.po_number == "PO-99999"


def test_no_match_for_unknown_vendor():
    invoice = ExtractedInvoice(vendor_name="Nobody Inc.", po_reference=None, total=100.0)
    result = match_invoice_to_po(invoice, POS)
    assert result.matched_po is None
