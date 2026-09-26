"""
analyzer.py — AI-powered log analysis engine.

Orchestrates the full analysis pipeline:
  1. Receives a parsed + sanitized log DataFrame and summary stats.
  2. Formats structured prompts for the LLM.
  3. Calls the LLM (via LLMClient) with chunked log text.
  4. Parses and merges the structured JSON response.
  5. Returns an AnalysisResult dataclass.

The LLM is instructed to return a strict JSON schema so we can reliably
render findings in the dashboard — with a fallback plain-text path if
the model doesn't comply perfectly.
"""

import json
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.core.config import PROVIDER_GROQ, GROQ_MAX_CHARS_PER_CHUNK, GROQ_MAX_LINES_PER_CHUNK
from src.core.llm_client import LLMClient, LLMClientError, extract_json_from_response
from src.core.log_parser import chunk_dataframe

# ---------------------------------------------------------------------------
# Output schema (what we expect the LLM to return)
# ---------------------------------------------------------------------------

ANALYSIS_SCHEMA = {
    "executive_summary": {
        "health_score": 85,
        "system_status": "Degraded | Healthy | Critical",
        "overview": "One paragraph summary of system health.",
        "top_concerns": ["concern1", "concern2"],
    },
    "error_groups": [
        {
            "pattern": "NullPointerException in PaymentService",
            "count": 12,
            "severity": "ERROR",
            "first_seen": "2024-01-15T14:00:00",
            "last_seen": "2024-01-15T14:30:00",
            "representative_log": "raw log line here",
        }
    ],
    "root_cause_analysis": [
        {
            "title": "Database connection pool exhaustion",
            "description": "Detailed explanation of the root cause.",
            "confidence": 0.87,
            "evidence": ["log line 1", "log line 2"],
            "affected_components": ["PaymentService", "DB pool"],
        }
    ],
    "remediation": {
        "immediate": [
            "Restart the payment-service pod",
            "Increase DB pool max connections to 50",
        ],
        "short_term": [
            "Add circuit breaker around DB calls",
        ],
        "long_term": [
            "Migrate to connection pooling middleware (PgBouncer)",
        ],
        "code_fixes": [
            {
                "file_hint": "application.properties",
                "description": "Increase pool size",
                "snippet": "spring.datasource.hikari.maximum-pool-size=50",
            }
        ],
    },
    "security_threats": [
        {
            "type": "Brute-force attempt",
            "severity": "HIGH",
            "description": "401 responses from 15 unique IPs within 60 seconds.",
            "recommendation": "Enable rate limiting and IP blocking.",
        }
    ],
    "anomalies": [
        {
            "description": "Sudden 10x spike in ERROR rate at 14:22",
            "timestamp": "2024-01-15T14:22:00",
            "likely_cause": "Deployment of v2.3.1",
        }
    ],
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

# Compact schema — field names only, no example values, to minimise prompt tokens.
_SCHEMA_COMPACT = (
    '{"executive_summary":{"health_score":0-100,"system_status":"Healthy|Degraded|Critical",'
    '"overview":"string","top_concerns":["string"]},'
    '"error_groups":[{"pattern":"string","count":0,"severity":"string","first_seen":"ISO","last_seen":"ISO","representative_log":"string"}],'
    '"root_cause_analysis":[{"title":"string","description":"string","confidence":0.0,"evidence":["string"],"affected_components":["string"]}],'
    '"remediation":{"immediate":["string"],"short_term":["string"],"long_term":["string"],'
    '"code_fixes":[{"file_hint":"string","description":"string","snippet":"string"}]},'
    '"security_threats":[{"type":"string","severity":"HIGH|MEDIUM|LOW","description":"string","recommendation":"string"}],'
    '"anomalies":[{"description":"string","timestamp":"ISO","likely_cause":"string"}]}'
)

_SYSTEM_PROMPT = (
    "You are an expert SRE and security analyst. Analyze the provided logs.\n"
    "Respond with ONLY a valid JSON object matching this schema (no markdown, no preamble):\n"
    + _SCHEMA_COMPACT
)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    """Structured output from the AI analysis pipeline."""

    # High-level summary
    health_score: int = 100
    system_status: str = "Healthy"
    overview: str = ""
    top_concerns: list[str] = field(default_factory=list)

    # Grouped errors
    error_groups: list[dict] = field(default_factory=list)

    # Root cause analysis entries
    root_causes: list[dict] = field(default_factory=list)

    # Remediation advice
    remediation: dict = field(default_factory=dict)

    # Security threats
    security_threats: list[dict] = field(default_factory=list)

    # Anomalies
    anomalies: list[dict] = field(default_factory=list)

    # Meta
    chunks_analyzed: int = 0
    raw_responses: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def has_error(self) -> bool:
        return self.error is not None

    def to_dict(self) -> dict:
        return {
            "executive_summary": {
                "health_score": self.health_score,
                "system_status": self.system_status,
                "overview": self.overview,
                "top_concerns": self.top_concerns,
            },
            "error_groups": self.error_groups,
            "root_cause_analysis": self.root_causes,
            "remediation": self.remediation,
            "security_threats": self.security_threats,
            "anomalies": self.anomalies,
        }


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_analysis_prompt(log_chunk: str, stats: dict, chunk_index: int, total_chunks: int) -> str:
    """
    Construct the user-turn prompt for a single log chunk.

    Args:
        log_chunk:     The sanitized log text block.
        stats:         Summary statistics dict from log_parser.get_summary_stats().
        chunk_index:   1-based index of this chunk.
        total_chunks:  Total number of chunks.
    """
    stats_summary = (
        f"Total log lines: {stats.get('total', '?')}\n"
        f"Log levels: {stats.get('by_level', {})}\n"
        f"Errors: {stats.get('error_count', 0)}, "
        f"Criticals: {stats.get('critical_count', 0)}, "
        f"Warnings: {stats.get('warning_count', 0)}\n"
        f"Time range: {stats.get('time_start', 'N/A')} → {stats.get('time_end', 'N/A')}\n"
        f"Pre-computed health score: {stats.get('health_score', '?')}/100\n"
    )

    chunk_note = (
        f"(Analyzing chunk {chunk_index} of {total_chunks} — "
        "focus on patterns visible in this segment)\n"
        if total_chunks > 1
        else ""
    )

    return (
        f"SUMMARY STATISTICS:\n{stats_summary}\n"
        f"{chunk_note}"
        f"LOG CONTENT:\n```\n{log_chunk}\n```\n\n"
        "Analyze the logs above and return the JSON analysis object."
    )


# ---------------------------------------------------------------------------
# Merge helper for multi-chunk analysis
# ---------------------------------------------------------------------------

def _merge_results(base: AnalysisResult, new_data: dict) -> AnalysisResult:
    """
    Merge a newly parsed JSON response into an existing AnalysisResult.
    For lists (error_groups, root_causes, etc.) we append and de-duplicate.
    For scalar fields (health_score, overview) we take the worst-case / latest.
    """
    summary = new_data.get("executive_summary", {})

    # Use lowest health score across chunks (most pessimistic)
    new_score = summary.get("health_score", 100)
    if isinstance(new_score, (int, float)):
        base.health_score = min(base.health_score, int(new_score))

    # Escalate system status
    status_rank = {"Healthy": 0, "Degraded": 1, "Critical": 2}
    new_status = summary.get("system_status", "Healthy")
    if status_rank.get(new_status, 0) > status_rank.get(base.system_status, 0):
        base.system_status = new_status

    # Append overview text
    new_overview = summary.get("overview", "")
    if new_overview and new_overview not in base.overview:
        base.overview = (base.overview + "\n\n" + new_overview).strip()

    # Merge top_concerns (deduplicated)
    for concern in summary.get("top_concerns", []):
        if concern and concern not in base.top_concerns:
            base.top_concerns.append(concern)

    # Append error groups (deduplicated by pattern)
    existing_patterns = {eg.get("pattern", "") for eg in base.error_groups}
    for eg in new_data.get("error_groups", []):
        if eg.get("pattern", "") not in existing_patterns:
            base.error_groups.append(eg)
            existing_patterns.add(eg.get("pattern", ""))

    # Append root causes (deduplicated by title)
    existing_titles = {rc.get("title", "") for rc in base.root_causes}
    for rc in new_data.get("root_cause_analysis", []):
        if rc.get("title", "") not in existing_titles:
            base.root_causes.append(rc)
            existing_titles.add(rc.get("title", ""))

    # Merge remediation (keep most comprehensive version)
    if not base.remediation:
        base.remediation = new_data.get("remediation", {})
    else:
        new_rem = new_data.get("remediation", {})
        for key in ("immediate", "short_term", "long_term", "code_fixes"):
            existing = base.remediation.get(key, [])
            for item in new_rem.get(key, []):
                if item not in existing:
                    existing.append(item)
            base.remediation[key] = existing

    # Append security threats
    existing_threat_types = {t.get("type", "") for t in base.security_threats}
    for threat in new_data.get("security_threats", []):
        if threat.get("type", "") not in existing_threat_types:
            base.security_threats.append(threat)
            existing_threat_types.add(threat.get("type", ""))

    # Append anomalies
    existing_anomaly_descs = {a.get("description", "") for a in base.anomalies}
    for anomaly in new_data.get("anomalies", []):
        if anomaly.get("description", "") not in existing_anomaly_descs:
            base.anomalies.append(anomaly)
            existing_anomaly_descs.add(anomaly.get("description", ""))

    return base


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def analyze_logs(
    df: pd.DataFrame,
    stats: dict,
    client: LLMClient,
    max_chunks: int = 3,
    progress_callback=None,
) -> AnalysisResult:
    """
    Run AI analysis over a parsed + sanitized log DataFrame.

    Args:
        df:                 Parsed log DataFrame (already PII-redacted).
        stats:              Summary stats from log_parser.get_summary_stats().
        client:             Configured LLMClient instance.
        max_chunks:         Maximum number of chunks to send to the LLM.
                            Increase for thoroughness; reduce for speed/cost.
        progress_callback:  Optional callable(current, total, message) for
                            Streamlit progress bar integration.

    Returns:
        AnalysisResult
    """
    result = AnalysisResult()

    # Use tighter chunk limits for Groq's low free-tier TPM ceiling
    groq_mode = client.provider == PROVIDER_GROQ
    chunks = chunk_dataframe(
        df,
        max_chars=GROQ_MAX_CHARS_PER_CHUNK if groq_mode else None,
        max_lines=GROQ_MAX_LINES_PER_CHUNK if groq_mode else None,
    )
    if not chunks:
        result.error = "No log lines to analyze."
        return result

    # Limit chunk count to control API costs
    chunks = chunks[:max_chunks]
    total = len(chunks)
    result.chunks_analyzed = total

    for idx, chunk in enumerate(chunks, start=1):
        if progress_callback:
            progress_callback(idx - 1, total, f"Analyzing chunk {idx}/{total}…")

        prompt = _build_analysis_prompt(chunk, stats, idx, total)

        try:
            response = client.chat(
                user_message=prompt,
                system_prompt=_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=4096,
            )
        except LLMClientError as exc:
            result.error = str(exc)
            return result

        result.raw_responses.append(response.content)

        parsed = extract_json_from_response(response.content)
        if parsed:
            result = _merge_results(result, parsed)
        else:
            # If the LLM didn't return valid JSON, store raw text in overview
            fallback = response.content[:2000]
            if fallback not in result.overview:
                result.overview = (result.overview + "\n\n" + fallback).strip()

    if progress_callback:
        progress_callback(total, total, "Analysis complete.")

    return result
