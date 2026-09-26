"""
app.py — AI Log Analyzer: Streamlit entry-point (redesigned).

Run with:
    streamlit run app.py

Layout:
  - Top navigation bar (branding + status indicator)
  - Modal-style expandable configuration & ingestion panel
  - Overview is the landing page after upload
  - AI Insights renders as a full-page report
"""

import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src.core.analyzer import AnalysisResult, analyze_logs
from src.core.config import (
    DECOMMISSIONED_MODELS,
    DEFAULT_MODELS,
    PROVIDER_ANTHROPIC,
    PROVIDER_GROQ,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    SUPPORTED_PROVIDERS,
    settings,
)
from src.core.llm_client import LLMClient, LLMClientError
from src.core.log_parser import get_summary_stats, parse_logs
from src.core.preprocessor import redact_dataframe_column, redact_lines
from src.utils.export_utils import to_json, to_markdown
from src.utils.visualizations import (
    error_groups_bar,
    error_timeline,
    health_gauge,
    log_level_pie,
    log_volume_bar,
    top_errors_bar,
)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="TraceLens · AI Log Analyzer",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Design system — CSS injected once
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
      /* ── Global resets ─────────────────────────────────── */
      [data-testid="collapsedControl"] { display: none !important; }
      section[data-testid="stSidebar"] { display: none !important; }
      .block-container { padding: 0 2rem 3rem 2rem !important; max-width: 1280px; }
      footer { display: none !important; }

      /* ── Top navigation bar ─────────────────────────────── */
      .tl-navbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.7rem 1.5rem;
        background: #0d1117;
        border-bottom: 1px solid #21262d;
        margin: 0 -2rem 1.8rem -2rem;
        position: sticky;
        top: 0;
        z-index: 999;
      }
      .tl-brand {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        font-size: 1.15rem;
        font-weight: 700;
        color: #e6edf3;
        letter-spacing: -0.3px;
      }
      .tl-brand span.accent { color: #58a6ff; }
      .tl-badge {
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        padding: 2px 8px;
        border-radius: 20px;
        background: #161b22;
        border: 1px solid #30363d;
        color: #8b949e;
        text-transform: uppercase;
      }
      .tl-nav-actions { display: flex; align-items: center; gap: 0.75rem; }
      .tl-status-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 5px;
      }
      .tl-status-ok   { background: #3fb950; box-shadow: 0 0 6px #3fb95066; }
      .tl-status-warn { background: #d29922; box-shadow: 0 0 6px #d2992266; }
      .tl-status-err  { background: #f85149; box-shadow: 0 0 6px #f8514966; }
      .tl-status-idle { background: #484f58; }
      .tl-status-text { font-size: 0.78rem; color: #8b949e; }

      /* ── Config panel (expander) ────────────────────────── */
      [data-testid="stExpander"] {
        border: 1px solid #21262d !important;
        border-radius: 8px !important;
        background: #0d1117 !important;
        margin-bottom: 1.4rem;
      }
      [data-testid="stExpander"] summary {
        font-weight: 600 !important;
        color: #c9d1d9 !important;
      }

      /* ── Metric cards ───────────────────────────────────── */
      [data-testid="metric-container"] {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 1rem 1.2rem 0.8rem 1.2rem;
      }
      [data-testid="metric-container"] label {
        font-size: 0.72rem !important;
        color: #8b949e !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }
      [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: #e6edf3 !important;
      }

      /* ── Section headings ───────────────────────────────── */
      .tl-section {
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #484f58;
        margin: 1.8rem 0 0.7rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid #21262d;
      }

      /* ── Report card ────────────────────────────────────── */
      .tl-report-card {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 10px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1.2rem;
      }
      .tl-report-card h4 {
        font-size: 0.9rem;
        font-weight: 600;
        color: #c9d1d9;
        margin: 0 0 0.6rem 0;
      }

      /* ── Severity badges ────────────────────────────────── */
      .badge { display: inline-block; padding: 2px 10px; border-radius: 20px;
               font-size: 0.7rem; font-weight: 700; letter-spacing: 0.05em; }
      .badge-red    { background: #3d1010; color: #f85149; border: 1px solid #f8514944; }
      .badge-yellow { background: #2d1e00; color: #d29922; border: 1px solid #d2992244; }
      .badge-green  { background: #0f2a18; color: #3fb950; border: 1px solid #3fb95044; }
      .badge-blue   { background: #0c2040; color: #58a6ff; border: 1px solid #58a6ff44; }

      /* ── Tab styling ────────────────────────────────────── */
      .stTabs [data-baseweb="tab-list"] {
        border-bottom: 1px solid #21262d !important;
        gap: 0 !important;
      }
      .stTabs [data-baseweb="tab"] {
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.2rem !important;
        color: #8b949e !important;
        border-radius: 0 !important;
        border-bottom: 2px solid transparent !important;
      }
      .stTabs [aria-selected="true"] {
        color: #58a6ff !important;
        border-bottom: 2px solid #58a6ff !important;
        background: transparent !important;
      }

      /* ── Dividers ───────────────────────────────────────── */
      hr { border-color: #21262d !important; margin: 1.2rem 0 !important; }

      /* ── Code blocks ────────────────────────────────────── */
      .stCodeBlock pre { font-size: 0.8rem !important; background: #161b22 !important; }

      /* ── Buttons ────────────────────────────────────────── */
      .stButton button[kind="primary"] {
        background: #238636 !important;
        border: 1px solid #2ea043 !important;
        font-weight: 600 !important;
      }
      .stButton button[kind="primary"]:hover {
        background: #2ea043 !important;
      }

      /* ── Landing hero ───────────────────────────────────── */
      .tl-hero {
        text-align: center;
        padding: 4rem 2rem 3rem 2rem;
      }
      .tl-hero h1 {
        font-size: 2.4rem;
        font-weight: 800;
        color: #e6edf3;
        margin-bottom: 0.5rem;
        letter-spacing: -0.5px;
      }
      .tl-hero p {
        font-size: 1.05rem;
        color: #8b949e;
        max-width: 540px;
        margin: 0 auto 2rem auto;
        line-height: 1.6;
      }
      .tl-feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        max-width: 820px;
        margin: 0 auto;
        text-align: left;
      }
      .tl-feature {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 10px;
        padding: 1.2rem 1.3rem;
      }
      .tl-feature .icon { font-size: 1.4rem; margin-bottom: 0.4rem; display: block; }
      .tl-feature strong { color: #c9d1d9; font-size: 0.88rem; display: block; margin-bottom: 0.25rem; }
      .tl-feature span { color: #8b949e; font-size: 0.78rem; line-height: 1.5; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

def _init_state() -> None:
    defaults = {
        "raw_df": None,
        "clean_df": None,
        "stats": None,
        "analysis": None,
        "log_filename": "",
        "redaction_counts": {},
        "show_sanitized": True,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

_init_state()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _health_class(score: int) -> str:
    if score >= 80:
        return "tl-status-ok"
    if score >= 50:
        return "tl-status-warn"
    return "tl-status-err"

def _severity_badge(sev: str) -> str:
    s = sev.upper()
    if s in ("HIGH", "CRITICAL", "FATAL", "ERROR"):
        return f'<span class="badge badge-red">{s}</span>'
    if s in ("MEDIUM", "WARN", "WARNING"):
        return f'<span class="badge badge-yellow">{s}</span>'
    if s == "LOW":
        return f'<span class="badge badge-green">{s}</span>'
    return f'<span class="badge badge-blue">{s}</span>'

# ---------------------------------------------------------------------------
# Top navigation bar
# ---------------------------------------------------------------------------

stats_now = st.session_state.stats
if stats_now:
    h = stats_now.get("health_score", 100)
    dot_cls = _health_class(h)
    status_label = f"Health {h}/100"
else:
    dot_cls = "tl-status-idle"
    status_label = "No logs loaded"

st.markdown(
    f"""
    <div class="tl-navbar">
      <div class="tl-brand">
        🔭 Trace<span class="accent">Lens</span>
        <span class="tl-badge">AI Log Analyzer</span>
      </div>
      <div class="tl-nav-actions">
        <span class="tl-status-text">
          <span class="tl-status-dot {dot_cls}"></span>{status_label}
        </span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Configuration & Ingestion panel (collapsible top panel)
# ---------------------------------------------------------------------------

panel_label = "⚙ Configure & Load Logs" if st.session_state.stats is None else "⚙ Reconfigure / Load New Logs"
with st.expander(panel_label, expanded=(st.session_state.stats is None)):

    cfg_col, ingest_col = st.columns([1, 1], gap="large")

    # ── LLM configuration ──────────────────────────────────────────────────
    with cfg_col:
        st.markdown("**LLM Provider**")
        provider = st.selectbox(
            "Provider",
            options=SUPPORTED_PROVIDERS,
            index=SUPPORTED_PROVIDERS.index(settings.default_provider)
            if settings.default_provider in SUPPORTED_PROVIDERS
            else 0,
            key="provider_select",
            label_visibility="collapsed",
        )

        default_model = DEFAULT_MODELS.get(provider, "")
        session_key = f"model_input_{provider}"
        if st.session_state.get(session_key, "") in DECOMMISSIONED_MODELS:
            st.session_state[session_key] = default_model
        model = st.text_input("Model", value=default_model, key=session_key)

        if provider == PROVIDER_OPENAI:
            api_key = st.text_input(
                "OpenAI API Key", value=settings.openai_api_key,
                type="password", placeholder="sk-…", key="oai_key",
            )
            extra_kwargs: dict = {}
        elif provider == PROVIDER_ANTHROPIC:
            api_key = st.text_input(
                "Anthropic API Key", value=settings.anthropic_api_key,
                type="password", placeholder="sk-ant-…", key="ant_key",
            )
            extra_kwargs = {}
        elif provider == PROVIDER_GROQ:
            api_key = st.text_input(
                "Groq API Key", value=settings.groq_api_key,
                type="password", placeholder="gsk_…", key="groq_key",
            )
            extra_kwargs = {}
        else:  # Ollama
            api_key = ""
            ollama_url = st.text_input(
                "Ollama Base URL", value=settings.ollama_base_url, key="ollama_url",
            )
            extra_kwargs = {"base_url": ollama_url}

        max_chunks = st.slider(
            "Max analysis chunks",
            min_value=1, max_value=10, value=3,
            help="Higher = more thorough but slower & more expensive.",
        )

    # ── Log ingestion ───────────────────────────────────────────────────────
    with ingest_col:
        st.markdown("**Log Input**")
        ingestion_mode = st.radio(
            "Method",
            options=["Upload file", "Paste text"],
            horizontal=True,
            key="ingest_mode",
            label_visibility="collapsed",
        )

        raw_content: str = ""
        filename: str = "pasted_log.txt"

        if ingestion_mode == "Upload file":
            uploaded = st.file_uploader(
                "Upload log file",
                type=["log", "txt", "json", "csv"],
                help="Supports .log .txt .json .csv — max 50 MB",
                label_visibility="collapsed",
            )
            if uploaded:
                raw_content = uploaded.read().decode("utf-8", errors="replace")
                filename = uploaded.name
        else:
            raw_content = st.text_area(
                "Paste log content",
                height=155,
                placeholder="Paste log lines here…",
                key="paste_area",
                label_visibility="collapsed",
            )

        st.caption("🔒 All PII is redacted **before** being sent to the LLM.")
        process_btn = st.button("🚀 Process Logs", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Processing pipeline
# ---------------------------------------------------------------------------

if process_btn and raw_content.strip():
    with st.spinner("Parsing logs…"):
        raw_df = parse_logs(raw_content, filename=filename)

    if raw_df.empty:
        st.error("Could not parse any log lines from the input. Check the format.")
        st.stop()

    with st.spinner("Redacting PII…"):
        clean_lines, redaction_counts = redact_lines(raw_df["raw"].tolist())
        clean_df = raw_df.copy()
        clean_df["raw"] = clean_lines
        clean_df["message"] = redact_dataframe_column(raw_df["message"])

    stats = get_summary_stats(clean_df)

    st.session_state.raw_df = raw_df
    st.session_state.clean_df = clean_df
    st.session_state.stats = stats
    st.session_state.log_filename = filename
    st.session_state.redaction_counts = redaction_counts
    st.session_state.analysis = None
    st.rerun()

elif process_btn:
    st.warning("Please provide log content before processing.")

# ---------------------------------------------------------------------------
# Landing / empty state
# ---------------------------------------------------------------------------

if st.session_state.stats is None:
    st.markdown(
        """
        <div class="tl-hero">
          <h1>Understand your logs instantly</h1>
          <p>TraceLens parses, redacts, and applies AI to surface root causes,
             remediation steps, and security threats — in seconds.</p>
          <div class="tl-feature-grid">
            <div class="tl-feature">
              <span class="icon">📂</span>
              <strong>Multi-format ingestion</strong>
              <span>Nginx, Apache, Syslog, Python, Spring Boot, Node.js/Winston, JSON, CSV, and generic timestamped logs.</span>
            </div>
            <div class="tl-feature">
              <span class="icon">🔒</span>
              <strong>Automatic PII redaction</strong>
              <span>Emails, API keys, JWTs, credit cards, IPs, SSNs stripped before any data leaves your machine.</span>
            </div>
            <div class="tl-feature">
              <span class="icon">🤖</span>
              <strong>AI-powered insights</strong>
              <span>Root cause analysis, remediation playbooks, security threat detection, and anomaly highlights.</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ---------------------------------------------------------------------------
# Main dashboard — rendered after processing
# ---------------------------------------------------------------------------

stats = st.session_state.stats
clean_df: pd.DataFrame = st.session_state.clean_df
raw_df: pd.DataFrame = st.session_state.raw_df

tab_overview, tab_logs, tab_insights, tab_export = st.tabs(
    ["📊 Overview", "📋 Log Explorer", "🤖 AI Insights", "📤 Export"]
)

# ===========================================================================
# TAB 1 — Overview
# ===========================================================================

with tab_overview:
    fn = st.session_state.log_filename
    st.markdown(f'<p class="tl-section">Overview — {fn}</p>', unsafe_allow_html=True)

    # ── Metric row ──────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Events",  f"{stats['total']:,}")
    m2.metric("Errors",        f"{stats['error_count']:,}")
    m3.metric("Criticals",     f"{stats['critical_count']:,}")
    m4.metric("Warnings",      f"{stats['warning_count']:,}")
    pii_total = sum(st.session_state.redaction_counts.values())
    m5.metric("PII Redacted",  f"{pii_total:,}")

    # ── Health + distribution row ────────────────────────────────────────────
    st.markdown('<p class="tl-section">System Health</p>', unsafe_allow_html=True)
    gc, pc, vc = st.columns([1, 1, 2])
    with gc:
        st.plotly_chart(health_gauge(stats["health_score"]), use_container_width=True, key="ov_gauge")
    with pc:
        st.plotly_chart(log_level_pie(stats["by_level"]), use_container_width=True, key="ov_pie")
    with vc:
        st.plotly_chart(log_volume_bar(clean_df), use_container_width=True, key="ov_vol")

    # ── Timeline ─────────────────────────────────────────────────────────────
    st.markdown('<p class="tl-section">Event Timeline</p>', unsafe_allow_html=True)
    st.plotly_chart(error_timeline(clean_df), use_container_width=True, key="ov_timeline")

    # ── Top errors ────────────────────────────────────────────────────────────
    st.markdown('<p class="tl-section">Top Error Messages</p>', unsafe_allow_html=True)
    st.plotly_chart(top_errors_bar(clean_df), use_container_width=True, key="ov_top_err")

    # ── PII summary ──────────────────────────────────────────────────────────
    if st.session_state.redaction_counts:
        with st.expander("🔒 PII Redaction Summary"):
            rc = st.session_state.redaction_counts
            rd_df = pd.DataFrame(
                {"Category": list(rc.keys()), "Items Redacted": list(rc.values())}
            ).sort_values("Items Redacted", ascending=False)
            st.dataframe(rd_df, hide_index=True, use_container_width=True)

# ===========================================================================
# TAB 2 — Log Explorer
# ===========================================================================

with tab_logs:
    st.markdown('<p class="tl-section">Log Explorer</p>', unsafe_allow_html=True)

    ctrl1, ctrl2 = st.columns([3, 1])
    with ctrl2:
        show_sanitized = st.toggle(
            "Show redacted logs", value=True, key="san_toggle"
        )
    display_df = clean_df if show_sanitized else raw_df

    fcol1, fcol2, fcol3 = st.columns([2, 2, 3])
    with fcol1:
        all_levels = sorted(display_df["level"].dropna().unique().tolist())
        selected_levels = st.multiselect("Level", options=all_levels, default=all_levels)
    with fcol2:
        all_sources = sorted(display_df["source"].dropna().unique().tolist())
        selected_sources = st.multiselect("Source", options=all_sources, default=all_sources)
    with fcol3:
        keyword = st.text_input("🔍 Search", placeholder="e.g. NullPointerException")

    filtered = display_df[
        display_df["level"].isin(selected_levels)
        & display_df["source"].isin(selected_sources)
    ]
    if keyword:
        mask = (
            filtered["message"].str.contains(keyword, case=False, na=False)
            | filtered["raw"].str.contains(keyword, case=False, na=False)
        )
        filtered = filtered[mask]

    st.caption(f"**{len(filtered):,}** of **{len(display_df):,}** log lines")

    display_cols = ["timestamp", "level", "source", "message"]
    st.dataframe(
        filtered[display_cols].reset_index(drop=True),
        use_container_width=True,
        height=480,
        column_config={
            "timestamp": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm:ss"),
            "level":     st.column_config.TextColumn("Level", width="small"),
            "source":    st.column_config.TextColumn("Source", width="medium"),
            "message":   st.column_config.TextColumn("Message"),
        },
    )

    with st.expander("View raw log lines"):
        n_lines = st.slider("Lines to display", 10, 500, 100, step=10)
        raw_text = "\n".join(filtered["raw"].head(n_lines).tolist())
        st.code(raw_text, language="text")

# ===========================================================================
# TAB 3 — AI Insights  (full-page report layout)
# ===========================================================================

with tab_insights:
    # ── Build LLM client from panel config ─────────────────────────────────
    resolved_model = model or DEFAULT_MODELS.get(provider, "")
    if resolved_model in DECOMMISSIONED_MODELS:
        resolved_model = DEFAULT_MODELS.get(provider, "")
    client_kwargs = dict(
        provider=provider,
        model=resolved_model,
        api_key=api_key,
        **extra_kwargs,
    )
    llm_client = LLMClient(**client_kwargs)

    # ── Header row with run button ──────────────────────────────────────────
    hdr_l, hdr_r = st.columns([3, 1])
    with hdr_l:
        st.markdown('<p class="tl-section">AI Incident Report</p>', unsafe_allow_html=True)
    with hdr_r:
        if not llm_client.is_configured():
            st.warning("API key not configured.", icon="⚠️")
        analyse_btn = st.button(
            "▶ Run Analysis",
            type="primary",
            disabled=not llm_client.is_configured(),
            use_container_width=True,
        )

    if analyse_btn:
        progress_bar = st.progress(0, text="Starting analysis…")

        def _update_progress(current: int, total: int, message: str) -> None:
            pct = int((current / total) * 100) if total else 0
            progress_bar.progress(pct, text=message)

        with st.spinner("Analysing logs with AI…"):
            analysis_result: AnalysisResult = analyze_logs(
                df=clean_df,
                stats=stats,
                client=llm_client,
                max_chunks=max_chunks,
                progress_callback=_update_progress,
            )

        progress_bar.empty()

        if analysis_result.has_error:
            st.error(f"Analysis failed: {analysis_result.error}")
        else:
            st.session_state.analysis = analysis_result
            st.success(
                f"✅ Analysis complete — {analysis_result.chunks_analyzed} chunk(s) processed."
            )

    ar: AnalysisResult = st.session_state.analysis

    if ar is None:
        st.info("Click **▶ Run Analysis** above to generate the AI incident report.")
    else:
        # ── Executive summary banner ──────────────────────────────────────────
        status_icon = {"Healthy": "🟢", "Degraded": "🟡", "Critical": "🔴"}.get(ar.system_status, "⚪")
        dot_cls = _health_class(ar.health_score)

        sum_l, sum_r = st.columns([1, 3])
        with sum_l:
            st.plotly_chart(health_gauge(ar.health_score), use_container_width=True, key="ins_gauge")
        with sum_r:
            st.markdown(f"### {status_icon} System Status: {ar.system_status}")
            if ar.overview:
                st.markdown(ar.overview)
            if ar.top_concerns:
                st.markdown("**Top Concerns**")
                for c in ar.top_concerns:
                    st.markdown(f"- {c}")

        # ── Error groups chart ────────────────────────────────────────────────
        if ar.error_groups:
            fig_eg = error_groups_bar(ar.error_groups)
            if fig_eg:
                st.markdown('<p class="tl-section">Error Group Breakdown</p>', unsafe_allow_html=True)
                st.plotly_chart(fig_eg, use_container_width=True, key="ins_eg")

        # ── Root Cause Analysis ───────────────────────────────────────────────
        if ar.root_causes:
            st.markdown('<p class="tl-section">Root Cause Analysis</p>', unsafe_allow_html=True)
            for i, rc in enumerate(ar.root_causes, start=1):
                confidence = rc.get("confidence", 0)
                conf_pct = f"{confidence * 100:.0f}%" if isinstance(confidence, float) else str(confidence)
                comps = rc.get("affected_components", [])
                evidence = rc.get("evidence", [])

                with st.container():
                    st.markdown(
                        f"""
                        <div class="tl-report-card">
                          <h4>#{i} &nbsp; {rc.get('title', 'Unknown')} &nbsp;
                          <span style="font-size:0.78rem;color:#8b949e;font-weight:400;">
                            Confidence: {conf_pct}
                          </span></h4>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.markdown(rc.get("description", ""))
                    if comps:
                        st.caption(f"**Affected components:** {', '.join(comps)}")
                    if evidence:
                        with st.expander("Evidence log lines"):
                            st.code("\n".join(evidence[:8]), language="text")
                    st.divider()

        # ── Remediation ───────────────────────────────────────────────────────
        if ar.remediation:
            st.markdown('<p class="tl-section">Remediation Playbook</p>', unsafe_allow_html=True)
            rem = ar.remediation
            r1, r2, r3 = st.columns(3)

            with r1:
                if rem.get("immediate"):
                    st.markdown("#### ⚡ Immediate")
                    for item in rem["immediate"]:
                        st.markdown(f"- {item}")

            with r2:
                if rem.get("short_term"):
                    st.markdown("#### 📅 Short-term")
                    for item in rem["short_term"]:
                        st.markdown(f"- {item}")

            with r3:
                if rem.get("long_term"):
                    st.markdown("#### 🏗 Long-term")
                    for item in rem["long_term"]:
                        st.markdown(f"- {item}")

            if rem.get("code_fixes"):
                with st.expander("💻 Code / Config Fixes"):
                    for fix in rem["code_fixes"]:
                        st.markdown(
                            f"**`{fix.get('file_hint', 'file')}`** — {fix.get('description', '')}"
                        )
                        snippet = fix.get("snippet", "")
                        if snippet:
                            st.code(snippet)

        # ── Security Threats ──────────────────────────────────────────────────
        if ar.security_threats:
            st.markdown('<p class="tl-section">Security Threats</p>', unsafe_allow_html=True)
            for threat in ar.security_threats:
                sev = threat.get("severity", "UNKNOWN")
                badge_html = _severity_badge(sev)
                with st.container():
                    st.markdown(
                        f"""
                        <div class="tl-report-card">
                          <h4>{badge_html} &nbsp; {threat.get('type', 'Unknown threat')}</h4>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.markdown(threat.get("description", ""))
                    rec = threat.get("recommendation", "")
                    if rec:
                        st.info(f"💡 **Recommendation:** {rec}")
                    st.divider()

        # ── Anomalies ─────────────────────────────────────────────────────────
        if ar.anomalies:
            st.markdown('<p class="tl-section">Anomalies Detected</p>', unsafe_allow_html=True)
            for anomaly in ar.anomalies:
                ts = anomaly.get("timestamp", "?")
                desc = anomaly.get("description", "")
                cause = anomaly.get("likely_cause", "?")
                st.markdown(f"- **{ts}** — {desc}  \n  *Likely cause: {cause}*")

        # ── Raw LLM debug ─────────────────────────────────────────────────────
        with st.expander("🗒 Raw LLM Response (debug)", expanded=False):
            for i, raw_resp in enumerate(ar.raw_responses, start=1):
                st.markdown(f"**Chunk {i}:**")
                st.code(raw_resp[:3000], language="json")

# ===========================================================================
# TAB 4 — Export
# ===========================================================================

with tab_export:
    st.markdown('<p class="tl-section">Export Report</p>', unsafe_allow_html=True)
    ar_export: AnalysisResult = st.session_state.analysis

    if ar_export is None:
        st.info("Run AI Analysis first to enable report export.")
    else:
        ecol1, ecol2 = st.columns(2)

        with ecol1:
            md_report = to_markdown(ar_export, log_filename=st.session_state.log_filename)
            st.download_button(
                label="⬇ Download Markdown Report",
                data=md_report,
                file_name="log_analysis_report.md",
                mime="text/markdown",
                use_container_width=True,
            )
            with st.expander("Preview Markdown"):
                st.markdown(md_report)

        with ecol2:
            json_report = to_json(ar_export, log_filename=st.session_state.log_filename)
            st.download_button(
                label="⬇ Download JSON Report",
                data=json_report,
                file_name="log_analysis_report.json",
                mime="application/json",
                use_container_width=True,
            )
            with st.expander("Preview JSON"):
                st.code(json_report[:4000], language="json")

    st.divider()
    st.markdown("**Download parsed logs as CSV**")
    if st.session_state.clean_df is not None:
        csv_buf = io.StringIO()
        clean_df.to_csv(csv_buf, index=False)
        st.download_button(
            label="⬇ Download Parsed Logs (CSV)",
            data=csv_buf.getvalue(),
            file_name="parsed_logs.csv",
            mime="text/csv",
            use_container_width=True,
        )
