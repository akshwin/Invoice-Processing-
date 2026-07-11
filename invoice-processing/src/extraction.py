"""Stage 1 — Extraction & Normalization (BRD Section 5, 9).

NOTE — deviation from BRD Section 9 tech stack: the BRD specifies the Claude API
(Anthropic) for structured extraction. This build uses Groq's API (Llama 3.3 70B /
Llama 4 Scout) instead, at the candidate's explicit request. See README "Deviations
from the BRD" for the full note. The architecture is unchanged — forced tool-use
constrained to a JSON schema, exactly as BRD Section 9 describes for the Claude-based
design.

NOTE — deviation from BRD Section 3.2: the BRD scopes OCR for scanned/image invoices
out of the build. This build actually handles them: when a PDF has no machine-readable
text layer, pages are rendered to images (PyMuPDF, no external OCR binary needed) and
read by a vision-capable model (Llama 4 Scout) using the exact same forced-tool-use
schema as the text path — a multimodal read, not a traditional Tesseract-style OCR
step. See README for the full note on this scope addition.
"""
import base64
import json
import os
import re
from typing import Optional

import fitz  # PyMuPDF
import pdfplumber
from dotenv import load_dotenv
from groq import Groq

from .llm_utils import call_with_retry
from .schemas import ExtractedInvoice

load_dotenv()

TEXT_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client


class ExtractionFailedError(Exception):
    """Raised only when a PDF genuinely can't be read by either the text path or the
    image/vision fallback — e.g. a corrupt file or a PDF with zero pages."""


def _pdf_text_or_none(pdf_path: str) -> Optional[str]:
    """Returns extracted text, or None if the PDF has no usable machine-readable text
    (e.g. a scanned/image-based invoice) — signals the caller to fall back to vision."""
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    alnum_chars = len(re.findall(r"[A-Za-z0-9]", text))
    return text if alnum_chars >= 10 else None


def _render_pdf_pages_to_png(pdf_path: str, dpi: int = 150) -> list[bytes]:
    doc = fitz.open(pdf_path)
    try:
        return [page.get_pixmap(dpi=dpi).tobytes("png") for page in doc]
    finally:
        doc.close()


EXTRACTION_SYSTEM_PROMPT = """You are an invoice data extraction assistant for an accounts payable system.

Call the extract_invoice tool with the fields you find in the invoice you're given (as text, or as
one or more page images if it's a scanned document). Rules:
- Only extract a field's value if it is explicitly present on the invoice. If a field is not stated,
  return null for it — never guess, infer, compute, or fill in a plausible value.
- In particular, do NOT calculate "total" from subtotal + tax if no total is printed on the invoice.
  Extract totals, subtotals, and tax only when they appear as explicit values.
- invoice_date must be normalized to ISO 8601 (YYYY-MM-DD) if present, regardless of the format
  printed on the invoice (e.g. "May 12, 2026" or "05/12/2026" both become "2026-05-12").
- po_reference is whatever PO number the invoice states explicitly — whether it's clearly labeled
  ("PO Reference: PO-10234") or mentioned in a sentence ("per our purchase order PO-10234 dated...")
  — or null if no PO number appears anywhere.
- A discount is a line item with a negative amount — extract it as-is, don't drop or net it out.
- If there are multiple tax lines (e.g. state tax + local tax), sum them into the single `tax` field.
- If the invoice spans multiple pages, treat it as one document — line items may continue across
  pages, but there is one subtotal/tax/total for the whole invoice (usually on the last page).
- Use extraction_confidence_notes to flag anything ambiguous (e.g. "vendor name appears abbreviated",
  "scanned image was low-resolution in places"), or leave it as an empty string if extraction was
  unambiguous.
"""

_EXTRACT_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_invoice",
        "description": "Record the structured fields extracted from an invoice.",
        "parameters": {
            "type": "object",
            "properties": {
                "invoice_number": {"type": ["string", "null"]},
                "invoice_date": {"type": ["string", "null"], "description": "ISO 8601 date, e.g. 2026-05-12"},
                "vendor_name": {"type": ["string", "null"]},
                "po_reference": {"type": ["string", "null"]},
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": ["number", "null"]},
                            "unit_price": {"type": ["number", "null"]},
                            "amount": {"type": ["number", "null"]},
                        },
                        "required": ["description"],
                    },
                },
                "subtotal": {"type": ["number", "null"]},
                "tax": {"type": ["number", "null"]},
                "total": {"type": ["number", "null"]},
                "extraction_confidence_notes": {"type": "string"},
            },
            "required": [
                "invoice_number",
                "invoice_date",
                "vendor_name",
                "po_reference",
                "line_items",
                "subtotal",
                "tax",
                "total",
                "extraction_confidence_notes",
            ],
        },
    },
}


def _run_extraction(model: str, user_content) -> ExtractedInvoice:
    client = _get_client()

    def _call():
        return client.chat.completions.create(
            model=model,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            tools=[_EXTRACT_TOOL],
            tool_choice={"type": "function", "function": {"name": "extract_invoice"}},
        )

    response = call_with_retry(_call)
    tool_call = response.choices[0].message.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    return ExtractedInvoice.model_validate(args)


def extract_invoice(pdf_path: str) -> tuple[ExtractedInvoice, str]:
    """Returns (extracted_invoice, method) where method is "text" or "vision".

    Tries direct text extraction first (fast, cheap, exact). Falls back to rendering
    every page as an image and reading it with a vision-capable model only when the
    PDF has no usable text layer at all — e.g. a scanned invoice. Both paths share the
    same forced-tool-use extraction schema, so downstream code doesn't care which one
    ran.
    """
    try:
        text = _pdf_text_or_none(pdf_path)
    except Exception as e:
        raise ExtractionFailedError(f"Could not open or read PDF: {e}") from e

    if text is not None:
        invoice = _run_extraction(TEXT_MODEL, f"Extract the invoice fields from this text:\n\n{text}")
        return invoice, "text"

    try:
        images = _render_pdf_pages_to_png(pdf_path)
    except Exception as e:
        raise ExtractionFailedError(f"Could not render PDF pages as images: {e}") from e

    if not images:
        raise ExtractionFailedError("PDF has no pages.")

    content = [
        {
            "type": "text",
            "text": "This invoice has no machine-readable text layer (it's scanned/image-based). "
            "Extract the invoice fields from the page image(s) below.",
        }
    ]
    for png_bytes in images:
        b64 = base64.b64encode(png_bytes).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    invoice = _run_extraction(VISION_MODEL, content)
    return invoice, "vision"
