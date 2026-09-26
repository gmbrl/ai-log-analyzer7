"""
export_utils.py — Report export helpers.

Generates downloadable Markdown and JSON reports from an AnalysisResult.
"""

import json
from datetime import datetime, timezone

from src.core.analyzer import AnalysisResult


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def to_markdown(result: AnalysisResult, log_filename: str = "upload") -> str:
    """
    Render an AnalysisResult as a Markdown report string.

    Args:
        result:       The completed AnalysisResult.
        log_filename: Original log filename (for the report header).

    Returns:
        A multi-line Markdown string suitable for download.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines: list[str] = [
        f"# AI Log Analysis Report",
        f"",
        f"**File:** `{log_filename}`  ",
        f"**Generated:** {now}  ",
        f"**Chunks analysed:** {result.chunks_analyzed}",
        f"",
        "---",
        f"",
        f"## Executive Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Health Score | **{result.health_score} / 100** |",
        f"| System Status | **{result.system_status}** |",
        f"",
    ]

    if result.overview:
        lines += [result.overview, ""]

    if result.top_concerns:
        lines += ["**Top Concerns:**", ""]
        for concern in result.top_concerns:
            lines.append(f"- {concern}")
        lines.append("")

    # ----- Error Groups -----
    if result.error_groups:
        lines += ["---", "", "## Error Groups", ""]
        lines += [
            "| Pattern | Severity | Count | Last Seen |",
            "|---------|----------|-------|-----------|",
        ]
        for eg in result.error_groups:
            pattern = eg.get("pattern", "—")[:100]
            severity = eg.get("severity", "ERROR")
            count = eg.get("count", "?")
            last_seen = eg.get("last_seen", "?")
            lines.append(f"| `{pattern}` | {severity} | {count} | {last_seen} |")
        lines.append("")

    # ----- Root Cause Analysis -----
    if result.root_causes:
        lines += ["---", "", "## Root Cause Analysis", ""]
        for i, rc in enumerate(result.root_causes, start=1):
            confidence = rc.get("confidence", 0)
            confidence_pct = f"{confidence * 100:.0f}%" if isinstance(confidence, float) else str(confidence)
            lines += [
                f"### {i}. {rc.get('title', 'Unknown')}",
                f"",
                f"**Confidence:** {confidence_pct}  ",
                f"**Affected Components:** {', '.join(rc.get('affected_components', []))}",
                f"",
                rc.get("description", ""),
                "",
            ]
            evidence = rc.get("evidence", [])
            if evidence:
                lines += ["**Evidence:**", ""]
                for ev in evidence:
                    lines.append(f"```\n{ev}\n```")
                lines.append("")

    # ----- Remediation -----
    if result.remediation:
        lines += ["---", "", "## Remediation", ""]
        rem = result.remediation

        if rem.get("immediate"):
            lines += ["### Immediate Actions", ""]
            for item in rem["immediate"]:
                lines.append(f"- {item}")
            lines.append("")

        if rem.get("short_term"):
            lines += ["### Short-term Fixes", ""]
            for item in rem["short_term"]:
                lines.append(f"- {item}")
            lines.append("")

        if rem.get("long_term"):
            lines += ["### Long-term Improvements", ""]
            for item in rem["long_term"]:
                lines.append(f"- {item}")
            lines.append("")

        if rem.get("code_fixes"):
            lines += ["### Code / Config Fixes", ""]
            for fix in rem["code_fixes"]:
                lines.append(f"**{fix.get('file_hint', 'File')}** — {fix.get('description', '')}")
                snippet = fix.get("snippet", "")
                if snippet:
                    lines += [f"```\n{snippet}\n```", ""]

    # ----- Security Threats -----
    if result.security_threats:
        lines += ["---", "", "## Security Threats", ""]
        for threat in result.security_threats:
            sev = threat.get("severity", "?")
            lines += [
                f"### ⚠ {threat.get('type', 'Unknown Threat')} [{sev}]",
                "",
                threat.get("description", ""),
                "",
                f"**Recommendation:** {threat.get('recommendation', '')}",
                "",
            ]

    # ----- Anomalies -----
    if result.anomalies:
        lines += ["---", "", "## Anomalies", ""]
        for anomaly in result.anomalies:
            lines += [
                f"- **{anomaly.get('timestamp', '?')}** — {anomaly.get('description', '')}  ",
                f"  *Likely cause:* {anomaly.get('likely_cause', '?')}",
                "",
            ]

    lines += ["---", "", "_Report generated by AI Log Analyzer_", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------

def to_json(result: AnalysisResult, log_filename: str = "upload") -> str:
    """
    Serialise an AnalysisResult to a JSON string.

    Args:
        result:       The completed AnalysisResult.
        log_filename: Original log filename.

    Returns:
        Indented JSON string.
    """
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "meta": {
            "generated_at": now,
            "source_file": log_filename,
            "chunks_analyzed": result.chunks_analyzed,
        },
        **result.to_dict(),
    }
    return json.dumps(payload, indent=2, default=str)
