"""CLI smoke test — run every invoice in data/invoices through the full pipeline.

Note: this fires ~2 LLM calls per invoice back-to-back across the whole test set,
which is a testing artifact, not how the app is actually used (the UI processes one
invoice per human click, naturally spaced out). A small delay between invoices here
avoids tripping a free-tier rate limit during batch testing.
"""
import glob
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pipeline import build_pipeline

INVOICE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "invoices")
DELAY_BETWEEN_INVOICES_SECONDS = 3


def main():
    pipeline = build_pipeline()
    paths = sorted(glob.glob(os.path.join(INVOICE_DIR, "*.pdf")))
    for i, path in enumerate(paths):
        if i > 0:
            time.sleep(DELAY_BETWEEN_INVOICES_SECONDS)
        name = os.path.basename(path)
        print(f"\n=== {name} ===")
        initial_state = {"pdf_path": path, "run_id": str(uuid.uuid4())}
        final_state = {}
        for step in pipeline.stream(initial_state):
            node_name = list(step.keys())[0]
            final_state.update(step[node_name])

        if final_state.get("error"):
            print(f"  ERROR at {final_state['error_stage']}: {final_state['error']}")
            continue

        record = final_state["decision"]
        print(f"  Decision: {record['decision']}")
        print(f"  Matched PO: {record['matched_po']}")
        print(f"  Rules triggered: {record['rules_triggered']}")
        print(f"  Reasoning: {record['reasoning']}")


if __name__ == "__main__":
    main()
