"""FastAPI backend — REST + SSE API over the same LangGraph pipeline used by the
Streamlit app (src/pipeline.py, unchanged). Two extra concerns a UI framework
handled for free and an API has to do explicitly:

- Live stage-by-stage progress: pipeline.stream() is a synchronous generator, so
  it runs in a background thread per request; each yielded step is pushed onto a
  thread-safe queue.Queue, and an async SSE endpoint drains that queue and streams
  it to the client as it arrives. Each stage_done event carries a `data` payload
  with that stage's actual output (extracted fields, PO match detail, rule-by-rule
  validation outcomes) so the UI can render more than a checkmark.
- Run history: SQLite (src/storage.py) instead of the Streamlit app's flat JSON
  file, since concurrent API requests writing to a JSON file is a real correctness
  risk that a single-user Streamlit session never had to worry about.
"""
import json
import os
import queue
import tempfile
import threading
import uuid
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from src import storage
from src.pipeline import build_pipeline

load_dotenv()

app = FastAPI(title="Invoice Processing API")

# Demo-scope simplification: no auth/cookies are involved (plain fetch calls only),
# so a wildcard origin is a low-risk simplification here. Tighten to the specific
# Vercel domain for anything beyond a demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_TO_STAGE = {
    "extraction": "Extraction",
    "po_matching": "PO Matching",
    "validation": "Validation",
    "decision": "Decision",
}
STAGE_ORDER = ["Extraction", "PO Matching", "Validation", "Decision"]

# run_id -> queue.Queue of progress events for that run, while it's in flight.
_RUN_QUEUES: dict[str, "queue.Queue"] = {}

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "data", "invoices")

# Human-readable metadata for the canonical test invoices, exposed via /api/samples so a
# tester can pick a specific scenario (clean, scanned, mismatched, novel format, ...)
# instead of needing their own PDFs to try the app.
SAMPLE_INVOICES = [
    {
        "filename": "INV-1001_bluebird.pdf",
        "label": "Clean happy path",
        "vendor_name": "Bluebird Supplies Inc.",
        "description": "Straightforward text invoice, exact PO number and amount match.",
        "expected_outcome": "APPROVE",
    },
    {
        "filename": "INV-2044_meridian.pdf",
        "label": "Clean, compact layout",
        "vendor_name": "Meridian Office Solutions",
        "description": "Different visual layout from the first sample, still an exact match.",
        "expected_outcome": "APPROVE",
    },
    {
        "filename": "INV-3390_crestview.pdf",
        "label": "Within tolerance, not exact",
        "vendor_name": "Crestview Logistics LLC",
        "description": "Invoice total differs slightly from the PO amount but within the BR-4 tolerance band.",
        "expected_outcome": "APPROVE",
    },
    {
        "filename": "INV-4502_northgate.pdf",
        "label": "No PO number on invoice",
        "vendor_name": "Northgate Industrial Parts",
        "description": "No explicit PO reference — matched implicitly by vendor name and amount proximity.",
        "expected_outcome": "APPROVE",
    },
    {
        "filename": "INV-5810_alderwood_EC1_amount_mismatch.pdf",
        "label": "EC-1: amount mismatch",
        "vendor_name": "Alderwood Consulting Group",
        "description": "Invoice total is well outside tolerance of the matched PO amount.",
        "expected_outcome": "FLAG_FOR_REVIEW",
    },
    {
        "filename": "INV-6021_fairview_EC2_missing_total.pdf",
        "label": "EC-2: missing required field",
        "vendor_name": "Fairview Business Services",
        "description": "Invoice is missing its total, tripping the BR-2 required-fields check.",
        "expected_outcome": "FLAG_FOR_REVIEW",
    },
    {
        "filename": "INV-7188_summit_EC3_scanned.pdf",
        "label": "EC-3: scanned invoice",
        "vendor_name": "Summit Hardware Co.",
        "description": "Image-only PDF with no text layer — exercises the vision-based extraction fallback.",
        "expected_outcome": "APPROVE",
    },
    {
        "filename": "INV-7742_riverside_complex_multipage.pdf",
        "label": "Multi-page text invoice",
        "vendor_name": "Riverside Manufacturing Co.",
        "description": "Line items span multiple pages of machine-readable text.",
        "expected_outcome": "APPROVE",
    },
    {
        "filename": "INV-8850_harborpoint_complex_discount_tax.pdf",
        "label": "Discount + split tax lines",
        "vendor_name": "Harbor Point Consulting",
        "description": "More complex totals section with a discount line and split tax rates.",
        "expected_outcome": "APPROVE",
    },
    {
        "filename": "INV-9110_cascade_scanned_skewed.pdf",
        "label": "Scanned, skewed page",
        "vendor_name": "Cascade Parts & Supply",
        "description": "Scanned invoice photographed at an angle — stresses the vision fallback further.",
        "expected_outcome": "APPROVE",
    },
    {
        "filename": "INV-9225_ironclad_scanned_lowquality.pdf",
        "label": "Scanned, low quality / noisy",
        "vendor_name": "Ironclad Freight Co.",
        "description": "Low-resolution, noisy scan of a printed invoice.",
        "expected_outcome": "APPROVE",
    },
    {
        "filename": "INV-9340_pinnacle_scanned_multipage.pdf",
        "label": "Scanned, multi-page",
        "vendor_name": "Pinnacle Equipment Rentals",
        "description": "Multi-page scanned invoice, every page processed through the vision fallback.",
        "expected_outcome": "APPROVE",
    },
    {
        "filename": "INV-ZCS-0442_zenith_freeform_format.pdf",
        "label": "Completely different format",
        "vendor_name": "Zenith Cloud Services",
        "description": "A wholly novel invoice layout never seen in the other samples — proves the extraction generalizes rather than pattern-matching a known template.",
        "expected_outcome": "APPROVE",
    },
]
_SAMPLE_FILENAMES = {s["filename"] for s in SAMPLE_INVOICES}


def _serialize_stage_data(node_name: str, output: dict) -> dict:
    """Turn a pipeline node's raw output into a JSON-safe detail payload for the UI."""
    if node_name == "extraction":
        invoice = output["extracted_invoice"]
        return {
            "extracted_invoice": invoice.model_dump(),
            "extraction_method": output.get("extraction_method"),
        }

    if node_name == "po_matching":
        match = output["match_result"]
        po = match.matched_po
        return {
            "match_method": match.match_method,
            "notes": match.notes,
            "matched_po": (
                {
                    "po_number": po.po_number,
                    "vendor_name": po.vendor_name,
                    "po_amount": po.po_amount,
                    "po_date": po.po_date,
                    "status": po.status,
                }
                if po
                else None
            ),
        }

    if node_name == "validation":
        validation = output["validation_result"]
        return {
            "rules_checked": [
                {"rule_id": o.rule_id, "passed": o.passed, "message": o.message}
                for o in validation.outcomes
            ],
            "failed_rule": validation.failed_outcome.rule_id if validation.failed_outcome else None,
        }

    if node_name == "decision":
        return output["decision"]

    return {}


def _process_run(run_id: str, pdf_path: str, q: "queue.Queue") -> None:
    try:
        pipeline = build_pipeline()
        initial_state = {"pdf_path": pdf_path, "run_id": run_id}
        for step in pipeline.stream(initial_state):
            node_name = list(step.keys())[0]
            output = step[node_name]
            stage_name = NODE_TO_STAGE[node_name]

            if output.get("error"):
                q.put({"type": "error", "stage": stage_name, "message": output["error"]})
                q.put({"type": "end"})
                return

            q.put({"type": "stage_done", "stage": stage_name, "data": _serialize_stage_data(node_name, output)})
            if "decision" in output:
                q.put({"type": "result", "record": output["decision"]})
        q.put({"type": "end"})
    except Exception as e:  # last-resort net — a node-level error should already be caught
        q.put({"type": "error", "stage": "Pipeline", "message": str(e)})
        q.put({"type": "end"})
    finally:
        try:
            os.unlink(pdf_path)
        except OSError:
            pass


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.get("/api/samples")
def list_samples():
    return SAMPLE_INVOICES


@app.get("/api/samples/{filename}")
def get_sample(filename: str):
    if filename not in _SAMPLE_FILENAMES:
        raise HTTPException(404, "Unknown sample invoice.")
    path = os.path.join(SAMPLES_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "Sample file missing on server.")
    return FileResponse(path, media_type="application/pdf", filename=filename)


@app.post("/api/runs")
async def create_run(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted.")

    run_id = str(uuid.uuid4())
    fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    with os.fdopen(fd, "wb") as f:
        f.write(await file.read())

    q: "queue.Queue" = queue.Queue()
    _RUN_QUEUES[run_id] = q
    threading.Thread(target=_process_run, args=(run_id, tmp_path, q), daemon=True).start()

    return {"run_id": run_id, "stages": STAGE_ORDER}


@app.get("/api/runs/{run_id}/stream")
async def stream_run(run_id: str):
    import asyncio

    q = _RUN_QUEUES.get(run_id)

    async def event_generator():
        if q is None:
            # Not in flight — either finished already or an unknown ID. Fall back to
            # the persisted result so a page refresh / reconnect still resolves.
            record = storage.get_run(run_id)
            if record:
                yield f"data: {json.dumps({'type': 'result', 'record': record})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'stage': 'Unknown', 'message': 'Run not found.'})}\n\n"
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
            return

        loop = asyncio.get_event_loop()
        while True:
            event = await loop.run_in_executor(None, q.get)
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] == "end":
                break
        _RUN_QUEUES.pop(run_id, None)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/runs")
def list_runs(decision: str | None = None):
    history = storage.load_history()
    if decision:
        history = [r for r in history if r["decision"] == decision]
    return sorted(history, key=lambda r: r["timestamp"], reverse=True)


@app.get("/api/runs/{run_id}")
def get_run_detail(run_id: str):
    record = storage.get_run(run_id)
    if record is None:
        raise HTTPException(404, "Run not found.")
    return record
