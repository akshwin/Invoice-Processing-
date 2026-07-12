"""FastAPI backend — REST + SSE API over the same LangGraph pipeline used by the
Streamlit app (src/pipeline.py, unchanged). Two extra concerns a UI framework
handled for free and an API has to do explicitly:

- Live stage-by-stage progress: pipeline.stream() is a synchronous generator, so
  it runs in a background thread per request; each yielded step is pushed onto a
  thread-safe queue.Queue, and an async SSE endpoint drains that queue and streams
  it to the client as it arrives.
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
from fastapi.responses import StreamingResponse

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

            q.put({"type": "stage_done", "stage": stage_name})
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
