"""
visualizations.py — Plotly chart factories for the dashboard.

All functions accept a pandas DataFrame or dict and return a plotly Figure.
Palette is aligned with the GitHub-dark design system used in app.py.
"""

from typing import Optional
import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Shared theme settings (GitHub-dark palette)
# ---------------------------------------------------------------------------

_DARK_BG      = "rgba(0,0,0,0)"     # transparent — lets Streamlit theme show through
_PAPER_BG     = "rgba(0,0,0,0)"
_SURFACE      = "#0d1117"
_BORDER       = "#21262d"
_GRID_COLOR   = "#21262d"
_TEXT_PRIMARY = "#e6edf3"
_TEXT_MUTED   = "#8b949e"
_FONT         = dict(family="'Segoe UI', system-ui, sans-serif", color=_TEXT_PRIMARY)

# Level → colour mapping (consistent with the UI severity palette)
LEVEL_COLORS = {
    "DEBUG":     "#484f58",
    "TRACE":     "#484f58",
    "INFO":      "#58a6ff",   # blue-400
    "NOTICE":    "#3fb950",   # green-400
    "WARN":      "#d29922",   # amber
    "WARNING":   "#d29922",
    "ERROR":     "#f85149",   # red
    "CRITICAL":  "#f85149",
    "FATAL":     "#ff7b72",   # lighter red
    "EMERGENCY": "#ffa198",
}

_DEFAULT_LAYOUT = dict(
    plot_bgcolor=_DARK_BG,
    paper_bgcolor=_PAPER_BG,
    font=_FONT,
    margin=dict(l=16, r=16, t=40, b=16),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor=_BORDER,
        font=dict(color=_TEXT_MUTED, size=12),
    ),
    xaxis=dict(
        gridcolor=_GRID_COLOR,
        linecolor=_BORDER,
        tickfont=dict(color=_TEXT_MUTED, size=11),
        title_font=dict(color=_TEXT_MUTED, size=12),
    ),
    yaxis=dict(
        gridcolor=_GRID_COLOR,
        linecolor=_BORDER,
        tickfont=dict(color=_TEXT_MUTED, size=11),
        title_font=dict(color=_TEXT_MUTED, size=12),
    ),
)


def _apply_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(**_DEFAULT_LAYOUT)
    return fig


# ---------------------------------------------------------------------------
# 1. Log-level distribution — donut chart
# ---------------------------------------------------------------------------

def log_level_pie(by_level: dict) -> go.Figure:
    labels = list(by_level.keys())
    values = list(by_level.values())
    colors = [LEVEL_COLORS.get(lv, "#484f58") for lv in labels]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            marker=dict(
                colors=colors,
                line=dict(color="#010409", width=2),
            ),
            textinfo="label+percent",
            textfont=dict(color=_TEXT_PRIMARY, size=11),
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text="Log Level Distribution", font=dict(color=_TEXT_MUTED, size=13)),
        showlegend=True,
        **{k: v for k, v in _DEFAULT_LAYOUT.items() if k not in ("xaxis", "yaxis")},
    )
    return fig


# ---------------------------------------------------------------------------
# 2. Error timeline — area chart
# ---------------------------------------------------------------------------

def error_timeline(df: pd.DataFrame, resample_freq: str = "1min") -> go.Figure:
    ts_df = df[df["timestamp"].notna()].copy()

    def _empty(msg: str) -> go.Figure:
        fig = go.Figure()
        fig.add_annotation(
            text=msg, xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(color=_TEXT_MUTED, size=13),
        )
        _apply_theme(fig)
        fig.update_layout(title=dict(text="Error Timeline", font=dict(color=_TEXT_MUTED, size=13)))
        return fig

    if ts_df.empty or ts_df["timestamp"].isna().all():
        return _empty("No timestamped data")

    ts_df["timestamp"] = pd.to_datetime(ts_df["timestamp"], errors="coerce", utc=True)
    ts_df = ts_df.dropna(subset=["timestamp"])

    if ts_df.empty:
        return _empty("No parseable timestamps found")

    ts_df = ts_df.set_index("timestamp").sort_index()

    traces = []
    for level, color in [
        ("ERROR",    LEVEL_COLORS["ERROR"]),
        ("CRITICAL", LEVEL_COLORS["CRITICAL"]),
        ("WARN",     LEVEL_COLORS["WARN"]),
        ("INFO",     LEVEL_COLORS["INFO"]),
    ]:
        sub = ts_df[ts_df["level"] == level]
        if sub.empty:
            continue
        try:
            counts = sub["level"].resample(resample_freq).count()
        except Exception:
            continue
        traces.append(
            go.Scatter(
                x=counts.index,
                y=counts.values,
                mode="lines",
                fill="tozeroy",
                name=level,
                line=dict(color=color, width=1.5),
                fillcolor=color + "22",
                hovertemplate=f"{level}: %{{y}} at %{{x}}<extra></extra>",
            )
        )

    fig = go.Figure(data=traces)
    _apply_theme(fig)
    fig.update_layout(
        title=dict(text="Event Timeline by Level", font=dict(color=_TEXT_MUTED, size=13)),
        xaxis_title="Time",
        yaxis_title="Count",
        hovermode="x unified",
    )
    return fig


# ---------------------------------------------------------------------------
# 3. Top error messages — horizontal bar chart
# ---------------------------------------------------------------------------

def top_errors_bar(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    error_df = df[df["level"].isin(["ERROR", "CRITICAL", "FATAL", "EMERGENCY"])]

    if error_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No errors found 🎉", xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(color=_TEXT_MUTED, size=14),
        )
        _apply_theme(fig)
        fig.update_layout(title=dict(text="Top Error Messages", font=dict(color=_TEXT_MUTED, size=13)))
        return fig

    top = (
        error_df["message"]
        .str[:120]
        .value_counts()
        .head(top_n)
        .reset_index()
    )
    top.columns = ["message", "count"]
    top = top.sort_values("count")

    fig = go.Figure(
        go.Bar(
            x=top["count"],
            y=top["message"],
            orientation="h",
            marker=dict(
                color=top["count"],
                colorscale=[[0, "#d29922"], [0.5, "#f85149"], [1, "#ff7b72"]],
                showscale=False,
                line=dict(width=0),
            ),
            hovertemplate="%{y}<br>Count: %{x}<extra></extra>",
        )
    )
    _apply_theme(fig)
    fig.update_layout(
        title=dict(text=f"Top {top_n} Error Messages", font=dict(color=_TEXT_MUTED, size=13)),
        xaxis_title="Occurrences",
        yaxis=dict(automargin=True, tickfont=dict(size=10, color=_TEXT_MUTED)),
        height=max(280, top_n * 36),
        bargap=0.25,
    )
    return fig


# ---------------------------------------------------------------------------
# 4. Error groups bar chart (AI analysis)
# ---------------------------------------------------------------------------

def error_groups_bar(error_groups: list[dict]) -> Optional[go.Figure]:
    if not error_groups:
        return None

    labels     = [eg.get("pattern", "Unknown")[:80] for eg in error_groups]
    counts     = [eg.get("count", 1) for eg in error_groups]
    severities = [eg.get("severity", "ERROR") for eg in error_groups]
    colors     = [LEVEL_COLORS.get(s, "#f85149") for s in severities]

    fig = go.Figure(
        go.Bar(
            x=counts,
            y=labels,
            orientation="h",
            marker=dict(color=colors, line=dict(width=0)),
            hovertemplate="%{y}<br>Count: %{x}<extra></extra>",
        )
    )
    _apply_theme(fig)
    fig.update_layout(
        title=dict(text="AI-Identified Error Groups", font=dict(color=_TEXT_MUTED, size=13)),
        xaxis_title="Occurrences",
        yaxis=dict(automargin=True, tickfont=dict(size=10, color=_TEXT_MUTED)),
        height=max(280, len(labels) * 38 + 80),
        bargap=0.25,
    )
    return fig


# ---------------------------------------------------------------------------
# 5. Health score gauge
# ---------------------------------------------------------------------------

def health_gauge(score: int) -> go.Figure:
    if score >= 80:
        bar_color = "#3fb950"   # green
        steps = [
            {"range": [0,  50], "color": "#161b22"},
            {"range": [50, 80], "color": "#161b22"},
            {"range": [80, 100], "color": "#0f2a18"},
        ]
    elif score >= 50:
        bar_color = "#d29922"   # amber
        steps = [
            {"range": [0,  50], "color": "#161b22"},
            {"range": [50, 80], "color": "#2d1e00"},
            {"range": [80, 100], "color": "#161b22"},
        ]
    else:
        bar_color = "#f85149"   # red
        steps = [
            {"range": [0,  50], "color": "#3d1010"},
            {"range": [50, 80], "color": "#161b22"},
            {"range": [80, 100], "color": "#161b22"},
        ]

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            domain={"x": [0, 1], "y": [0, 1]},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickcolor": _TEXT_MUTED,
                    "tickfont": dict(color=_TEXT_MUTED, size=10),
                },
                "bar": {"color": bar_color, "thickness": 0.22},
                "bgcolor": _SURFACE,
                "borderwidth": 1,
                "bordercolor": _BORDER,
                "steps": steps,
                "threshold": {
                    "line": {"color": _TEXT_MUTED, "width": 2},
                    "thickness": 0.75,
                    "value": score,
                },
            },
            number={"suffix": "/100", "font": {"color": _TEXT_PRIMARY, "size": 26}},
            title={"text": "Health Score", "font": {"color": _TEXT_MUTED, "size": 12}},
        )
    )
    fig.update_layout(
        plot_bgcolor=_DARK_BG,
        paper_bgcolor=_PAPER_BG,
        font=_FONT,
        margin=dict(l=16, r=16, t=20, b=16),
        height=210,
    )
    return fig


# ---------------------------------------------------------------------------
# 6. Log volume bar chart — hourly bucketing
# ---------------------------------------------------------------------------

def log_volume_bar(df: pd.DataFrame) -> go.Figure:
    ts_df = df[df["timestamp"].notna()].copy()
    ts_df["timestamp"] = pd.to_datetime(ts_df["timestamp"], errors="coerce", utc=True)
    ts_df = ts_df.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()

    if ts_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No timestamped data", xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(color=_TEXT_MUTED, size=13),
        )
        _apply_theme(fig)
        fig.update_layout(title=dict(text="Log Volume Over Time", font=dict(color=_TEXT_MUTED, size=13)))
        return fig

    hourly = ts_df.resample("1h")["level"].count().reset_index()
    hourly.columns = ["time", "count"]

    fig = go.Figure(
        go.Bar(
            x=hourly["time"],
            y=hourly["count"],
            marker=dict(color="#388bfd", opacity=0.9, line=dict(width=0)),
            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>Events: %{y}<extra></extra>",
        )
    )
    _apply_theme(fig)
    fig.update_layout(
        title=dict(text="Log Volume (Hourly)", font=dict(color=_TEXT_MUTED, size=13)),
        xaxis_title="Time",
        yaxis_title="Events",
        bargap=0.15,
    )
    return fig
