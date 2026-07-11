# AI-Powered Invoice Processing System

Takes an invoice PDF, extracts its data, matches it to a purchase order, validates it against
business rules, and produces a decision — **Approve / Flag for Review / Reject** — with a
plain-English explanation. Built for the Zamp AI Solutions Associate case study (PS-1).

Spec: `BRD Document.pdf` (Business Requirements Document, single source of truth for this build).

## Setup

```bash
cd invoice-processing
pip install -r requirements.txt
```

Create a `.env` file in this directory (see `.env.example`):

```
GROQ_API_KEY=your-key-here
```

Get a key at [console.groq.com](https://console.groq.com).

## Run

Test data (PO dataset + 13 invoice PDFs) is already generated in `data/`. To regenerate it from
scratch:

```bash
python scripts/generate_test_data.py
```

Run the full pipeline against every test invoice from the command line (no UI):

```bash
python scripts/run_cli.py
```

Launch the app:

```bash
streamlit run app.py
```

Two tabs: **Run** (upload a PDF, watch the 4 pipeline stages execute live, see the decision) and
**Dashboard** (history of every run, filterable by decision, click a row for full detail).

**Demo tip:** `run_history/history.json` reflects genuine runs only — it is never hand-seeded with
fake data. It ships pre-populated with one clean, live-verified run of all 13 test invoices. If you
re-upload the *same* invoice PDF a second time, BR-3 (duplicate detection) will correctly catch it
and Reject it — that's real duplicate-detection working, not a bug; reset the log first
(`echo [] > run_history/history.json`) if you want to re-demo the original Approve/Flag outcome.

Groq's free tier caps daily tokens per model at the organization level (not per API key) — if you
rehearse heavily right before your interview, do a quick sanity check
(`python -c "..."` a single small chat completion) beforehand so you're not caught out mid-demo.

## Tests

```bash
python -m pytest tests/ -v
```

18 unit tests cover PO matching (explicit PO number, vendor+amount proximity, no-match) and all
five business rules (BR-1 through BR-5, including the partial-PO-balance case) — deterministic,
no API calls required.

## Scope

**In scope** (BRD Section 3.1): PDF upload → full pipeline run; structured extraction (vendor,
invoice number, date, line items, subtotal, tax, total, PO reference); PO matching against a CSV
dataset; validation against BR-1 through BR-5; a decision with plain-English reasoning; a live
stage-by-stage run view; a dashboard of run history; the two P0 edge cases (EC-1 amount mismatch,
EC-2 missing critical field) built and demoed end-to-end.

**Out of scope** (BRD Section 3.2, deliberate for the build window): fuzzy/phonetic vendor-name
matching — exact/substring matching only; multi-user auth; integration with a real accounting
system — PO data is a fabricated CSV; editing extracted data through the UI. Of the three P1 edge
cases the BRD defers, two are actually implemented anyway (see "Beyond the BRD" below):
**EC-3 (scanned invoices)** and **duplicate detection (BR-3)**. Only **EC-4 (PO-splitting across
multiple invoices)** remains unbuilt — the validation/decision architecture is structured so it's
one function away (see Extensibility below), but no shipped test invoice exercises it.

### Beyond the BRD — complex and scanned invoices

The BRD's own test-data spec (Section 8.4) only calls for clean, simple happy-path invoices plus
EC-1/EC-2. Real vendor invoices are messier — and specifically, real scans are never a single clean
rasterized page — so the test set now includes **four scanned/image variants, two messy text-based
invoices, and one invoice built in a wholly different format from every other test case**, all
live-verified end-to-end:

- **Clean scanned invoice, zero machine-readable text** (`INV-7188_summit_EC3_scanned.pdf`) — the
  BRD explicitly scopes OCR out (Section 3.2), but it turned out to be straightforward to handle
  *without* a traditional OCR engine: when `pdfplumber` finds no usable text layer, the PDF's pages
  are rendered to images (PyMuPDF — no external OCR binary needed) and read by a vision-capable
  model (Llama 4 Scout via Groq) using the *exact same* forced-tool-use extraction schema as the
  text path. This is a real, deliberate scope addition beyond BRD Section 3.2 — flag it as such if
  asked, rather than presenting it as if the BRD always required it.
- **Skewed scan** (`INV-9110_cascade_scanned_skewed.pdf`) — rotated ~3.5° with a white fill behind
  it (Pillow), simulating a page that wasn't perfectly aligned on a scanner bed or in a phone
  camera frame. The vision model reads it correctly despite the tilt.
- **Low-quality/noisy scan** (`INV-9225_ironclad_scanned_lowquality.pdf`) — rendered at low DPI,
  Gaussian-blurred, given pixel noise, then round-tripped through a low-quality JPEG re-encode
  (quality 45) to bake in real compression artifacts before being embedded back as a PDF —
  simulating a cheap scanner or a photo taken in bad lighting.
- **Multi-page scanned invoice** (`INV-9340_pinnacle_scanned_multipage.pdf`) — 40 line items across
  two image-only pages with zero text anywhere; the vision path is handed both page images in one
  call and correctly sums the total across both.
- **A genuine multi-page *text* invoice** (`INV-7742_riverside_complex_multipage.pdf`) — 30 line
  items that force reportlab's table to split across two pages; extraction correctly sums the full
  amount across both pages via the normal text path.
- **A messier single-page text invoice** (`INV-8850_harborpoint_complex_discount_tax.pdf`) — a
  discount line item (negative amount), two separate tax lines (state + local, which the extraction
  prompt sums into one `tax` field), a non-ISO date ("June 3, 2026"), and a PO reference embedded in
  a sentence rather than a labeled field.
- **A wholly different invoice format** (`INV-ZCS-0442_zenith_freeform_format.pdf`) — built from
  scratch with no shared code path with any other test invoice, specifically to answer "what if a
  vendor's invoice looks nothing like the others": no line-item table at all (plain bullet-style
  text lines), different field vocabulary throughout (`Invoice Ref` / `Client` / `Issued` /
  `Related PO` / `Amount Due` instead of `Invoice #` / `Bill To` / `Date` / `PO Reference` /
  `TOTAL DUE`), a DD/MM/YYYY date ("22/05/2026"), and `USD 123.45` currency notation instead of
  `$123.45`. Extraction handled every one of these correctly on the first live run — normalized the
  date correctly (not day/month-swapped), found the total under a label it had never seen before,
  and parsed the bullet lines into structured line items despite there being no table to anchor on.
  This is the strongest evidence that extraction generalizes by *reading*, not by matching a
  template — see "Key engineering decisions" for why that's the point of using an LLM here at all.

All seven are generated reproducibly by `scripts/generate_test_data.py` (the three degraded scans
use Pillow + numpy for the rotation/noise/blur/JPEG-artifact effects, still deterministic via a
seeded RNG), matched against new PO rows (`PO-10240`, `PO-10242` through `PO-10247`). All thirteen
test invoices — the original six plus these seven — were run through the full pipeline in one
clean batch and produced correct decisions; see `run_history/history.json` for the live record.

**Also found and fixed while stress-testing this:** Groq's hosted Llama models occasionally
produce a malformed function-call generation that gets rejected as `tool_use_failed`, and free-tier
rate limits are easy to trip when firing several invoices back-to-back (as a batch test does — a
real single-invoice UI session, paced by human clicks, is far less likely to hit this). Both
`extraction.py` and `decision.py` now retry through `src/llm_utils.py` (rate-limit-aware backoff,
one retry on `tool_use_failed`) rather than surfacing a transient hiccup as a hard failure — a
direct, tested improvement to the BRD's "graceful failure" reliability requirement (Section 11).

## Architecture (BRD Section 9)

- **Streamlit** (`app.py`) — the only UI. Run tab + Dashboard tab.
- **LangGraph** (`src/pipeline.py`) — 4 nodes in a `StateGraph`: Extraction → PO Matching →
  Validation → Decision. Each node is narrow so failures are traceable to one stage; a node
  failure sets `error`/`error_stage` on the graph state and routes straight to `END` instead of
  crashing (graceful failure, BRD Section 11).
- **pdfplumber** — PDF text extraction. When a PDF has no usable text layer, extraction falls back
  to rendering pages as images (PyMuPDF) and reading them with a vision-capable model instead of
  raising immediately — see "Beyond the BRD" below. `ExtractionFailedError` is now reserved for
  PDFs that genuinely can't be opened/rendered at all (corrupt file, zero pages).
- **LLM calls** — one to extract structured JSON from the invoice (text or page images) via forced
  tool-use (constrained to the schema in `src/schemas.py`), one to turn an already-decided rule
  outcome into a plain-English sentence. The verdict itself is never decided by the LLM — see below.
- **Plain Python functions** (`src/validation.py`) — BR-1 through BR-5, deterministic and
  unit-tested. The amount tolerance (BR-4) is two named constants
  (`AMOUNT_TOLERANCE_PERCENT = 0.02`, `AMOUNT_TOLERANCE_FLAT = 50.0`), not a magic number.
- **JSON log** (`run_history/history.json`) — flat file, append-only, read by both the duplicate
  check (BR-3), the partial-PO-balance check (BR-5), and the Dashboard.

**Extensibility:** adding EC-3/4/5 or any new rule means adding one function to
`validation.py` and one line to `run_validation()`'s sequence — the pipeline's 4-node shape
doesn't change. BR-5 (partial PO balance) is a working example of this: implemented and
unit-tested, even though no shipped test invoice happens to exercise it (that scenario is EC-4,
explicitly deferred per the BRD).

## Deviations from the BRD

**Model provider — Claude (Anthropic) → Groq (Llama 3.3 70B).** BRD Section 9 specifies the
Claude API as non-negotiable for both structured extraction and decision reasoning. This build
uses Groq instead, at the candidate's explicit request made mid-build (no Anthropic API key was
available in the environment). The architecture the BRD asks for — LLM output forced into a
schema via tool-use/function-calling for extraction, plain rule-based logic for the actual
decision, LLM used only to phrase the reasoning — is unchanged; only the provider and model
differ (`src/extraction.py`, `src/decision.py`). **This is a real, acknowledged scope deviation
from a stated non-negotiable requirement, not a judgment call** — own it directly if asked in
the interview, and be ready to speak to how a swap back to Claude would work (it's a
provider-specific rewrite of two files; the rest of the pipeline — matching, validation, decision
logic, LangGraph wiring, UI — has no provider dependency).

**Other assumptions** (per BRD Section 14, and judgment calls the BRD left open):
- Test data is fabricated but realistic; no real vendors or companies.
- PO reference may be explicit (printed on the invoice) or implicit (inferred by vendor name +
  amount proximity) — both are supported by `src/matching.py`.
- If an invoice states a PO number explicitly but no PO with that number exists in the dataset,
  that's treated as "no matching PO" (BR-1 reject) rather than falling back to vendor+amount
  matching — an explicit-but-wrong PO reference is a real data problem, not something to paper
  over silently.
- Currency is assumed to be a single currency (USD) throughout — no conversion logic.
- The extraction prompt explicitly instructs the model not to compute `total` from
  `subtotal + tax` when no total is printed — a field is only populated if it's genuinely present
  on the invoice, per BRD Section 7.1 EC-2's requirement.
