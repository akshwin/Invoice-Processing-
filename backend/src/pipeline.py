"""Stage 6 — LangGraph wiring (BRD Section 5, 9).

Four nodes, chained in a StateGraph: Extraction -> PO Matching -> Validation -> Decision.
Each node is narrow on purpose so failures are traceable to a specific stage (BRD Section 9
component notes). A node failure sets `error`/`error_stage` on the state and the graph routes
straight to END instead of crashing or hanging (BRD Section 11 — Reliability).
"""
import os
from datetime import datetime, timezone
from typing import Optional, TypedDict

import groq
from langgraph.graph import END, StateGraph

from . import storage
from .decision import determine_decision, generate_reasoning
from .extraction import ExtractionFailedError, extract_invoice
from .matching import MatchResult, PurchaseOrder, load_po_dataset, match_invoice_to_po
from .schemas import ExtractedInvoice
from .validation import ValidationResult, run_validation

PO_DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "po_dataset.csv")


class PipelineState(TypedDict, total=False):
    pdf_path: str
    run_id: str
    extracted_invoice: Optional[ExtractedInvoice]
    extraction_method: Optional[str]
    match_result: Optional[MatchResult]
    validation_result: Optional[ValidationResult]
    decision: Optional[dict]
    error: Optional[str]
    error_stage: Optional[str]


def _friendly_api_error(e: Exception) -> str:
    if isinstance(e, groq.AuthenticationError):
        return "Groq API authentication failed — check that GROQ_API_KEY is set correctly."
    if isinstance(e, groq.RateLimitError):
        return "Groq API rate limit hit — please wait a moment and try again."
    if isinstance(e, groq.APIConnectionError):
        return "Could not connect to the Groq API — check your network connection."
    if isinstance(e, groq.APIStatusError):
        return f"Groq API returned an error ({e.status_code}): {e.message}"
    return str(e)


def extraction_node(state: PipelineState) -> dict:
    try:
        invoice, method = extract_invoice(state["pdf_path"])
        return {"extracted_invoice": invoice, "extraction_method": method}
    except ExtractionFailedError as e:
        return {"error": str(e), "error_stage": "Extraction"}
    except Exception as e:
        return {"error": _friendly_api_error(e), "error_stage": "Extraction"}


def po_matching_node(state: PipelineState) -> dict:
    try:
        pos = load_po_dataset(PO_DATASET_PATH)
        match = match_invoice_to_po(state["extracted_invoice"], pos)
        return {"match_result": match}
    except Exception as e:
        return {"error": str(e), "error_stage": "PO Matching"}


def validation_node(state: PipelineState) -> dict:
    try:
        history = storage.load_history()
        validation = run_validation(state["extracted_invoice"], state["match_result"], history)
        return {"validation_result": validation}
    except Exception as e:
        return {"error": str(e), "error_stage": "Validation"}


def decision_node(state: PipelineState) -> dict:
    try:
        invoice = state["extracted_invoice"]
        match = state["match_result"]
        validation = state["validation_result"]

        decision, rules_triggered = determine_decision(validation)
        reasoning = generate_reasoning(invoice, match, validation, decision)

        record = {
            "run_id": state["run_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "invoice_number": invoice.invoice_number,
            "vendor_name": invoice.vendor_name,
            "matched_po": match.matched_po.po_number if match.matched_po else None,
            "total": invoice.total,
            "decision": decision,
            "reasoning": reasoning,
            "rules_triggered": rules_triggered,
            "extracted_invoice": invoice.model_dump(),
            "match_method": match.match_method,
            "extraction_method": state.get("extraction_method"),
        }
        storage.append_run(record)
        return {"decision": record}
    except Exception as e:
        return {"error": _friendly_api_error(e), "error_stage": "Decision"}


def _route_on_error(state: PipelineState) -> str:
    return "end" if state.get("error") else "continue"


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("extraction", extraction_node)
    graph.add_node("po_matching", po_matching_node)
    graph.add_node("validation", validation_node)
    graph.add_node("decision", decision_node)

    graph.set_entry_point("extraction")
    graph.add_conditional_edges("extraction", _route_on_error, {"continue": "po_matching", "end": END})
    graph.add_conditional_edges("po_matching", _route_on_error, {"continue": "validation", "end": END})
    graph.add_conditional_edges("validation", _route_on_error, {"continue": "decision", "end": END})
    graph.add_edge("decision", END)

    return graph.compile()
