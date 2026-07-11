"""Streamlit UI (BRD Section 10) — Run view + Dashboard view."""
import os
import tempfile
import uuid

import pandas as pd
import streamlit as st

from src import storage
from src.pipeline import build_pipeline
from src.theme import STATUS, inject_css, render_hero, stat_tile_html, status_badge_html, stepper_html

# On Streamlit Community Cloud there's no .env file — secrets are configured via the
# app's Settings > Secrets UI instead, exposed as st.secrets. Bridge it into
# os.environ so extraction.py/decision.py (which read os.environ, for local-dev
# parity with .env) work unchanged in both environments.
try:
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass  # no secrets.toml present locally — .env / os.environ handles it instead

st.set_page_config(page_title="Invoice Processing", page_icon="🧾", layout="wide")
inject_css(st)

def md_safe(text) -> str:
    """Escape characters Streamlit's markdown renderer treats specially in free text
    (LLM output and extracted invoice fields) — `$` in particular triggers LaTeX math
    spans, so "$4,500.00 ... $50.00" reads as a formula instead of two dollar amounts."""
    if text is None:
        return ""
    return str(text).replace("$", "\\$")


STAGE_ORDER = ["Extraction", "PO Matching", "Validation", "Decision"]
NODE_TO_STAGE = {
    "extraction": "Extraction",
    "po_matching": "PO Matching",
    "validation": "Validation",
    "decision": "Decision",
}


def extraction_method_caption(record):
    if record.get("extraction_method") == "vision":
        st.caption(
            "📷 This PDF had no machine-readable text layer (scanned/image-based) — "
            "fields were read directly from the page image."
        )


def render_details_expander(record):
    with st.expander("Details — raw extracted data & rule IDs"):
        st.json(
            {
                "rules_triggered": record["rules_triggered"],
                "match_method": record.get("match_method"),
                "extraction_method": record.get("extraction_method"),
                "extracted_invoice": record["extracted_invoice"],
            }
        )


def render_run_view():
    with st.container(border=True):
        st.markdown('<div class="section-label">Upload</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Invoice PDF", type=["pdf"], label_visibility="collapsed"
        )
        run_clicked = st.button("Run pipeline", type="primary", disabled=uploaded is None)

    if uploaded is None:
        st.info("Upload an invoice PDF above, then click **Run pipeline**.")
        return

    if not run_clicked:
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded.getvalue())
        tmp_path = tmp.name

    with st.container(border=True):
        st.markdown('<div class="section-label">Pipeline progress</div>', unsafe_allow_html=True)
        stepper_placeholder = st.empty()

        stage_states = {name: "pending" for name in STAGE_ORDER}

        def redraw():
            stepper_placeholder.markdown(
                stepper_html([(name, stage_states[name]) for name in STAGE_ORDER]),
                unsafe_allow_html=True,
            )

        stage_states["Extraction"] = "running"
        redraw()

        pipeline = build_pipeline()
        run_id = str(uuid.uuid4())
        initial_state = {"pdf_path": tmp_path, "run_id": run_id}

        final_state = {}
        for step in pipeline.stream(initial_state):
            node_name = list(step.keys())[0]
            output = step[node_name]
            final_state.update(output)
            stage_name = NODE_TO_STAGE[node_name]

            if output.get("error"):
                stage_states[stage_name] = "error"
                redraw()
                break

            stage_states[stage_name] = "done"
            idx = STAGE_ORDER.index(stage_name)
            if idx + 1 < len(STAGE_ORDER):
                stage_states[STAGE_ORDER[idx + 1]] = "running"
            redraw()

    os.unlink(tmp_path)

    with st.container(border=True):
        st.markdown('<div class="section-label">Result</div>', unsafe_allow_html=True)

        if final_state.get("error"):
            st.error(
                f"Processing failed at the **{final_state.get('error_stage', 'pipeline')}** stage: "
                f"{final_state.get('error')}"
            )
            return

        record = final_state["decision"]
        st.markdown(status_badge_html(record["decision"]), unsafe_allow_html=True)
        extraction_method_caption(record)
        st.markdown("&nbsp;", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.markdown(f"**Vendor**\n\n{md_safe(record['vendor_name'])}")
        col2.markdown(f"**Invoice number**\n\n{md_safe(record['invoice_number'])}")
        col3.markdown(f"**Matched PO**\n\n{md_safe(record['matched_po'] or 'None')}")
        st.markdown(f"**Reasoning**\n\n{md_safe(record['reasoning'])}")
        render_details_expander(record)


def render_dashboard_view():
    history = storage.load_history()

    if not history:
        st.info("No runs yet. Process an invoice in the Run tab to see it here.")
        return

    df = pd.DataFrame(history)

    total = len(df)
    approved = int((df["decision"] == "APPROVE").sum())
    flagged = int((df["decision"] == "FLAG_FOR_REVIEW").sum())
    rejected = int((df["decision"] == "REJECT").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(stat_tile_html("Total runs", total, "#2a78d6"), unsafe_allow_html=True)
    c2.markdown(stat_tile_html("Approved", approved, STATUS["APPROVE"]["dot"]), unsafe_allow_html=True)
    c3.markdown(stat_tile_html("Flagged for review", flagged, STATUS["FLAG_FOR_REVIEW"]["dot"]), unsafe_allow_html=True)
    c4.markdown(stat_tile_html("Rejected", rejected, STATUS["REJECT"]["dot"]), unsafe_allow_html=True)
    st.write("")

    with st.container(border=True):
        st.markdown('<div class="section-label">Run history</div>', unsafe_allow_html=True)

        filter_options = {
            "All decisions": None,
            "Approved": "APPROVE",
            "Flagged for review": "FLAG_FOR_REVIEW",
            "Rejected": "REJECT",
        }
        filter_choice = st.selectbox("Filter by decision", list(filter_options), label_visibility="collapsed")
        decision_value = filter_options[filter_choice]
        if decision_value is not None:
            mask = df["decision"] == decision_value
        else:
            mask = pd.Series([True] * len(df))

        display_df = df.loc[mask, ["timestamp", "vendor_name", "invoice_number", "decision", "matched_po"]].copy()
        display_df["decision"] = display_df["decision"].map(lambda d: f'{STATUS[d]["icon"]}  {STATUS[d]["label"]}')
        display_df.columns = ["Timestamp", "Vendor", "Invoice #", "Decision", "Matched PO"]
        display_df = display_df.sort_values("Timestamp", ascending=False)
        df_filtered = df.loc[display_df.index].reset_index(drop=True)
        display_df = display_df.reset_index(drop=True)

        event = st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="history_table",
        )

    selected_rows = event.selection.rows if hasattr(event, "selection") else []
    if selected_rows:
        record = df_filtered.iloc[selected_rows[0]]
        with st.container(border=True):
            st.markdown(f'<div class="section-label">Run detail — {record["invoice_number"]}</div>', unsafe_allow_html=True)
            st.markdown(status_badge_html(record["decision"]), unsafe_allow_html=True)
            extraction_method_caption(record)
            st.markdown("&nbsp;", unsafe_allow_html=True)
            st.markdown(f"**Reasoning**\n\n{md_safe(record['reasoning'])}")
            render_details_expander(record)


render_hero(
    st,
    "Invoice Processing",
    "AI-assisted extraction, PO matching, and rule-based decisioning — with the reasoning to back up every call.",
)
tab_run, tab_dashboard = st.tabs(["Run", "Dashboard"])
with tab_run:
    render_run_view()
with tab_dashboard:
    render_dashboard_view()
