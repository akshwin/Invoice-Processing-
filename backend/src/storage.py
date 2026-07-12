"""Run history persistence — SQLite (BRD Section 9, 11 Auditability).

Backend variant: swaps the Streamlit app's flat JSON file for SQLite, since a real
API serving concurrent requests shouldn't do read-modify-write on a JSON file (a
genuine correctness risk, not just a style preference). Exposes the same
list[dict] interface as the original storage.py, so pipeline.py and validation.py
need zero changes — they don't know or care which one is behind it.
"""
import json
import os
import sqlite3
from threading import Lock

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "run_history", "history.db")
_lock = Lock()


def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            data TEXT NOT NULL
        )
        """
    )
    return conn


def load_history() -> list[dict]:
    with _lock:
        conn = _get_connection()
        try:
            rows = conn.execute("SELECT data FROM runs ORDER BY timestamp ASC").fetchall()
        finally:
            conn.close()
    return [json.loads(row[0]) for row in rows]


def get_run(run_id: str) -> dict | None:
    with _lock:
        conn = _get_connection()
        try:
            row = conn.execute("SELECT data FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        finally:
            conn.close()
    return json.loads(row[0]) if row else None


def append_run(record: dict) -> None:
    with _lock:
        conn = _get_connection()
        try:
            conn.execute(
                "INSERT INTO runs (run_id, timestamp, data) VALUES (?, ?, ?)",
                (record["run_id"], record["timestamp"], json.dumps(record, default=str)),
            )
            conn.commit()
        finally:
            conn.close()
