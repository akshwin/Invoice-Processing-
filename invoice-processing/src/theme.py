"""Design system for the Streamlit UI: injected CSS + small HTML component helpers.

Palette and component contracts (stat tile, status badges, stepper) follow a
validated status palette (good/warning/critical) and the "icon + label, never
color alone" rule — colors are supporting signal, not the only signal.
"""

STATUS = {
    "APPROVE": {
        "label": "Approved",
        "icon": "✓",
        "text": "#0a7227",
        "bg": "#e9f8ec",
        "border": "#bce8c4",
        "dot": "#0ca30c",
    },
    "FLAG_FOR_REVIEW": {
        "label": "Flagged for Review",
        "icon": "!",
        "text": "#8a5a00",
        "bg": "#fff6e0",
        "border": "#f3d98f",
        "dot": "#fab219",
    },
    "REJECT": {
        "label": "Rejected",
        "icon": "✕",
        "text": "#a3312f",
        "bg": "#fdecec",
        "border": "#f3c1c0",
        "dot": "#d03b3b",
    },
}

ACCENT = "#2a78d6"

CSS = """
<style>
#MainMenu, footer, header {visibility: hidden;}

.block-container {
    max-width: 1100px;
    padding-top: 2.2rem;
    padding-bottom: 3rem;
}

html, body, [class*="css"] {
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}

/* ---- Hero header ---- */
.app-hero {
    padding-bottom: 18px;
    margin-bottom: 28px;
    border-bottom: 1px solid #e1e0d9;
}
.app-hero h1 {
    font-size: 30px;
    font-weight: 700;
    margin: 0;
    color: #0b0b0b;
    letter-spacing: -0.01em;
}
.app-hero p {
    margin: 6px 0 0;
    color: #52514e;
    font-size: 15px;
}

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] {
    font-size: 15px;
    font-weight: 600;
    padding: 10px 4px;
}

/* ---- Cards ---- */
.app-card {
    background: #ffffff;
    border: 1px solid rgba(11,11,11,0.08);
    border-radius: 12px;
    padding: 22px 26px;
    box-shadow: 0 1px 2px rgba(11,11,11,0.04);
    margin-bottom: 18px;
}
.app-card h3 {
    margin-top: 0;
    font-size: 16px;
    font-weight: 700;
    color: #0b0b0b;
}
.section-label {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #898781;
    margin: 4px 0 14px;
}

/* ---- Buttons ---- */
.stButton>button {
    border-radius: 8px;
    font-weight: 600;
    padding: 0.55rem 1.6rem;
}

/* ---- File uploader ---- */
[data-testid="stFileUploaderDropzone"] {
    border-radius: 12px;
    background: #f9f9f7;
}

/* ---- Stat tiles ---- */
.stat-tile {
    background: #ffffff;
    border: 1px solid rgba(11,11,11,0.08);
    border-radius: 12px;
    padding: 16px 20px;
}
.stat-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 13px;
    color: #52514e;
    font-weight: 500;
}
.stat-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}
.stat-value {
    font-size: 32px;
    font-weight: 700;
    color: #0b0b0b;
    margin-top: 4px;
    line-height: 1.2;
}

/* ---- Status badge ---- */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 10px 20px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 17px;
    border: 1px solid;
}
.status-badge .badge-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    font-size: 14px;
    font-weight: 800;
    color: #ffffff;
}

/* ---- Stepper ---- */
.stepper {
    display: flex;
    align-items: flex-start;
    margin: 4px 0 8px;
}
.step-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 0 0 auto;
    width: 130px;
}
.step-connector {
    flex: 1 1 auto;
    height: 2px;
    background: #e1e0d9;
    margin-top: 19px;
}
.step-connector.filled { background: #2a78d6; }
.step-circle {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 16px;
    border: 2px solid #e1e0d9;
    color: #898781;
    background: #ffffff;
}
.step-circle.done { background: #2a78d6; border-color: #2a78d6; color: #ffffff; }
.step-circle.running {
    border-color: #2a78d6;
    color: #2a78d6;
    animation: step-pulse 1.4s infinite;
}
.step-circle.error { background: #d03b3b; border-color: #d03b3b; color: #ffffff; }
@keyframes step-pulse {
    0% { box-shadow: 0 0 0 0 rgba(42,120,214,0.35); }
    70% { box-shadow: 0 0 0 9px rgba(42,120,214,0); }
    100% { box-shadow: 0 0 0 0 rgba(42,120,214,0); }
}
.step-label {
    margin-top: 9px;
    font-size: 13px;
    font-weight: 600;
    color: #0b0b0b;
    text-align: center;
}
.step-status {
    font-size: 11px;
    color: #898781;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 2px;
}
.step-status.running { color: #2a78d6; }
.step-status.error { color: #d03b3b; }
</style>
"""


def inject_css(st):
    st.markdown(CSS, unsafe_allow_html=True)


def render_hero(st, title: str, subtitle: str):
    st.markdown(
        f'<div class="app-hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def status_badge_html(decision: str) -> str:
    s = STATUS[decision]
    return (
        f'<div class="status-badge" style="background:{s["bg"]};border-color:{s["border"]};color:{s["text"]}">'
        f'<span class="badge-icon" style="background:{s["dot"]}">{s["icon"]}</span>'
        f'{s["label"]}</div>'
    )


def stat_tile_html(label: str, value, dot_color: str) -> str:
    return (
        '<div class="stat-tile">'
        f'<div class="stat-label"><span class="stat-dot" style="background:{dot_color}"></span>{label}</div>'
        f'<div class="stat-value">{value}</div>'
        "</div>"
    )


STEP_ICONS = {"pending": "○", "running": "●", "done": "✓", "error": "✕"}
STEP_STATUS_TEXT = {"pending": "Pending", "running": "Running", "done": "Done", "error": "Failed"}


def stepper_html(stages: list[tuple[str, str]]) -> str:
    """stages: list of (label, state) where state in pending/running/done/error."""
    items = []
    for i, (label, state) in enumerate(stages):
        icon = STEP_ICONS[state]
        status_text = STEP_STATUS_TEXT[state]
        status_class = state if state in ("running", "error") else ""
        items.append(
            '<div class="step-item">'
            f'<div class="step-circle {state}">{icon}</div>'
            f'<div class="step-label">{label}</div>'
            f'<div class="step-status {status_class}">{status_text}</div>'
            "</div>"
        )
        if i < len(stages) - 1:
            filled = "filled" if state == "done" else ""
            items.append(f'<div class="step-connector {filled}"></div>')
    return f'<div class="stepper">{"".join(items)}</div>'
