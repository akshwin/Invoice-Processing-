"""Stage 4 — Decision Engine (BRD Section 5, 6, 8.3).

The verdict (APPROVE / FLAG_FOR_REVIEW / REJECT) is deterministic, derived purely from the
rule outcomes — the LLM never decides the verdict. An LLM call is used only to turn the
already-decided rule outcome into a plain-English sentence a non-technical AP manager can read.

NOTE — deviation from BRD Section 9 tech stack: uses Groq (Llama 3.3 70B) instead of the
Claude API specified in the BRD, at the candidate's explicit request. See README.
"""
import os

from dotenv import load_dotenv
from groq import Groq

from .llm_utils import call_with_retry
from .matching import MatchResult
from .schemas import ExtractedInvoice
from .validation import ValidationResult

load_dotenv()

MODEL = "llama-3.3-70b-versatile"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client


# BRD Section 6 flowchart — the failing rule determines the verdict.
_RULE_TO_DECISION = {
    "BR-1": "REJECT",
    "BR-2": "FLAG_FOR_REVIEW",
    "BR-3": "REJECT",
    "BR-4": "FLAG_FOR_REVIEW",
    "BR-5": "FLAG_FOR_REVIEW",
}


def determine_decision(validation: ValidationResult) -> tuple[str, list[str]]:
    """Deterministic verdict from rule outcomes. Returns (decision, rules_triggered)."""
    if validation.failed_outcome is None:
        return "APPROVE", [o.rule_id for o in validation.outcomes]
    decision = _RULE_TO_DECISION[validation.failed_outcome.rule_id]
    return decision, [validation.failed_outcome.rule_id]


REASONING_SYSTEM_PROMPT = """You write short, plain-English explanations of invoice processing \
decisions for a non-technical Accounts Payable manager. You are given the decision that has \
already been made (Approve, Flag for Review, or Reject) and the specific rule outcome that \
caused it. Write 1-3 sentences explaining why, in plain language a busy AP manager could read \
in a few seconds without needing to look anything up. State concrete numbers (amounts, dates, \
names) when they're given to you. Never mention internal rule IDs like "BR-4" — describe the \
underlying reason instead. Do not hedge or add caveats beyond what's given."""


def generate_reasoning(
    invoice: ExtractedInvoice,
    match: MatchResult,
    validation: ValidationResult,
    decision: str,
) -> str:
    if decision == "APPROVE":
        context = (
            f"Decision: APPROVE. Invoice {invoice.invoice_number} from {invoice.vendor_name} "
            f"for {invoice.total} matched PO {match.matched_po.po_number} "
            f"({match.matched_po.po_amount}) within tolerance. Match method: {match.match_method}."
        )
    else:
        failing = validation.failed_outcome
        context = (
            f"Decision: {decision}. Failing rule: {failing.rule_id}. Detail: {failing.message}. "
            f"Invoice number: {invoice.invoice_number}. Vendor: {invoice.vendor_name}."
        )

    client = _get_client()

    def _call():
        return client.chat.completions.create(
            model=MODEL,
            max_tokens=300,
            messages=[
                {"role": "system", "content": REASONING_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
        )

    response = call_with_retry(_call)
    return response.choices[0].message.content.strip()
