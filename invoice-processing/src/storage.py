"""Run history persistence — flat JSON log (BRD Section 9, 11 Auditability)."""
import json
import os
from threading import Lock

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "run_history", "history.json")
_lock = Lock()


def load_history() -> list[dict]:
    if not os.path.exists(HISTORY_PATH):
        return []
    with open(HISTORY_PATH, encoding="utf-8") as f:
        return json.load(f)


def append_run(record: dict) -> None:
    with _lock:
        history = load_history()
        history.append(record)
        os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, default=str)
