"""
log_parser.py — Multi-format log parser, normaliser, and chunker.

Supported formats (auto-detected):
  - Nginx access log (combined)
  - Apache access log (common / combined)
  - Syslog (RFC 3164 / journald)
  - Python standard logging
  - Spring Boot / Java (logback / log4j)
  - Node.js / Winston (plain-text and JSON)
  - Generic timestamped lines (best-effort)
  - Raw JSON log files (each line is a JSON object)
  - CSV log files

Parsing produces a unified pandas DataFrame with columns:
    timestamp, level, source, message, raw

Chunking splits the DataFrame into text windows suitable for an LLM context.
"""

import io
import json
import re
from typing import Optional

import pandas as pd
from dateutil import parser as dateutil_parser

from src.core.config import (
    ALL_LOG_LEVELS,
    MAX_CHARS_PER_CHUNK,
    MAX_LINES_PER_CHUNK,
)

# ---------------------------------------------------------------------------
# Format-specific regex patterns
# ---------------------------------------------------------------------------

# Nginx / Apache combined access log
# 127.0.0.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /index.html HTTP/1.1" 200 2326
_RE_NGINX = re.compile(
    r'(?P<ip>\S+)\s+\S+\s+\S+\s+'
    r'\[(?P<ts>[^\]]+)\]\s+'
    r'"(?P<request>[^"]+)"\s+'
    r'(?P<status>\d{3})\s+(?P<bytes>\S+)'
)

# Syslog (RFC 3164): Oct 15 14:23:01 hostname process[pid]: message
_RE_SYSLOG = re.compile(
    r'(?P<ts>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})'
    r'\s+(?P<host>\S+)\s+(?P<proc>[^\[:]+)(?:\[(?P<pid>\d+)\])?:\s+(?P<msg>.*)'
)

# Python logging: 2024-01-15 14:23:01,234 - name - LEVEL - message
_RE_PYTHON = re.compile(
    r'(?P<ts>\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)'
    r'\s*[-–]\s*(?P<logger>\S+)\s*[-–]\s*'
    r'(?P<level>TRACE|DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|CRITICAL|FATAL|EMERGENCY)'
    r'\s*[-–]\s*(?P<msg>.*)'
)

# Spring Boot / Logback: 2024-01-15 14:23:01.234  INFO 12345 --- [thread] class : message
_RE_SPRING = re.compile(
    r'(?P<ts>\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:\.\d+)?)'
    r'\s+(?P<level>TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|CRITICAL|FATAL)'
    r'\s+(?P<pid>\d+)\s+---\s+\[(?P<thread>[^\]]+)\]\s+(?P<class>\S+)\s*:\s*(?P<msg>.*)'
)

# Node.js / Winston plain-text: [2024-01-15T14:23:01.234Z] [INFO] message
_RE_WINSTON = re.compile(
    r'\[(?P<ts>[^\]]+)\]\s+\[(?P<level>TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\]\s+(?P<msg>.*)'
)

# Generic ISO timestamp + optional level (fallback)
_RE_GENERIC = re.compile(
    r'(?P<ts>\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)'
    r'(?:.*?\b(?P<level>TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|CRITICAL|FATAL|EMERGENCY)\b)?'
    r'\s*(?P<msg>.*)'
)

# Level anywhere in line (last resort level extraction)
_RE_LEVEL_ANY = re.compile(
    r'\b(TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|CRITICAL|FATAL|EMERGENCY)\b',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_ts(raw_ts: str) -> Optional[pd.Timestamp]:
    """Attempt to parse an arbitrary timestamp string into a pandas Timestamp."""
    try:
        ts = pd.Timestamp(dateutil_parser.parse(raw_ts, fuzzy=True))
        return ts if isinstance(ts, pd.Timestamp) else None
    except Exception:
        return None


def _normalize_level(raw: Optional[str]) -> str:
    if not raw:
        return "INFO"
    upper = raw.upper()
    if upper == "WARNING":
        return "WARN"
    if upper in ALL_LOG_LEVELS:
        return upper
    return "INFO"


def _try_nginx(line: str) -> Optional[dict]:
    m = _RE_NGINX.match(line)
    if not m:
        return None
    status = int(m.group("status"))
    level = "ERROR" if status >= 500 else ("WARN" if status >= 400 else "INFO")
    ts = _parse_ts(m.group("ts"))
    return {
        "timestamp": ts,
        "level": level,
        "source": "nginx",
        "message": f'{m.group("request")} -> {status}',
        "raw": line,
    }


def _try_syslog(line: str) -> Optional[dict]:
    m = _RE_SYSLOG.match(line)
    if not m:
        return None
    msg = m.group("msg")
    level_match = _RE_LEVEL_ANY.search(msg)
    level = _normalize_level(level_match.group(1)) if level_match else "INFO"
    ts = _parse_ts(m.group("ts"))
    proc = m.group("proc").strip()
    return {
        "timestamp": ts,
        "level": level,
        "source": proc,
        "message": msg,
        "raw": line,
    }


def _try_python_logging(line: str) -> Optional[dict]:
    m = _RE_PYTHON.match(line)
    if not m:
        return None
    ts = _parse_ts(m.group("ts"))
    return {
        "timestamp": ts,
        "level": _normalize_level(m.group("level")),
        "source": m.group("logger"),
        "message": m.group("msg"),
        "raw": line,
    }


def _try_spring(line: str) -> Optional[dict]:
    m = _RE_SPRING.match(line)
    if not m:
        return None
    ts = _parse_ts(m.group("ts"))
    return {
        "timestamp": ts,
        "level": _normalize_level(m.group("level")),
        "source": m.group("class"),
        "message": m.group("msg"),
        "raw": line,
    }


def _try_winston(line: str) -> Optional[dict]:
    m = _RE_WINSTON.match(line)
    if not m:
        return None
    ts = _parse_ts(m.group("ts"))
    return {
        "timestamp": ts,
        "level": _normalize_level(m.group("level")),
        "source": "winston",
        "message": m.group("msg"),
        "raw": line,
    }


def _try_json_line(line: str) -> Optional[dict]:
    """Parse a single JSON log line (e.g. Winston JSON, Bunyan, Pino)."""
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None

    # Try common field names for timestamp
    raw_ts = (
        obj.get("time") or obj.get("timestamp") or obj.get("ts")
        or obj.get("@timestamp") or obj.get("date") or ""
    )
    ts = _parse_ts(str(raw_ts)) if raw_ts else None

    # Level
    raw_level = (
        obj.get("level") or obj.get("severity") or obj.get("log_level") or "INFO"
    )
    if isinstance(raw_level, int):
        # Bunyan numeric levels
        raw_level = {10: "TRACE", 20: "DEBUG", 30: "INFO",
                     40: "WARN", 50: "ERROR", 60: "FATAL"}.get(raw_level, "INFO")

    # Message
    msg = (
        obj.get("message") or obj.get("msg") or obj.get("event")
        or obj.get("log") or str(obj)
    )
    source = obj.get("name") or obj.get("logger") or obj.get("service") or "json"

    return {
        "timestamp": ts,
        "level": _normalize_level(str(raw_level)),
        "source": str(source),
        "message": str(msg),
        "raw": line,
    }


def _try_generic(line: str) -> dict:
    """Last-resort parser: extract timestamp and level if present."""
    m = _RE_GENERIC.match(line)
    ts = _parse_ts(m.group("ts")) if m else None
    if m and m.group("level"):
        level = _normalize_level(m.group("level"))
        msg = m.group("msg").strip() or line
    else:
        level_match = _RE_LEVEL_ANY.search(line)
        level = _normalize_level(level_match.group(1)) if level_match else "INFO"
        msg = line

    return {
        "timestamp": ts,
        "level": level,
        "source": "generic",
        "message": msg.strip(),
        "raw": line,
    }


def _parse_line(line: str) -> Optional[dict]:
    """Try each parser in order; return the first successful result."""
    line = line.rstrip("\n\r")
    if not line.strip():
        return None

    for fn in (_try_json_line, _try_spring, _try_python_logging,
               _try_winston, _try_nginx, _try_syslog):
        result = fn(line)
        if result:
            return result

    # Fallback: use generic parser (always succeeds)
    return _try_generic(line)


# ---------------------------------------------------------------------------
# CSV and JSON file parsers
# ---------------------------------------------------------------------------

def _parse_csv(content: str) -> list[dict]:
    """Parse a CSV log file.  Attempts to detect timestamp/level/message columns."""
    try:
        df = pd.read_csv(io.StringIO(content))
    except Exception:
        return []

    rows = []
    col_lower = {c.lower(): c for c in df.columns}

    ts_col = next((col_lower[k] for k in ("timestamp", "time", "ts", "date", "@timestamp") if k in col_lower), None)
    level_col = next((col_lower[k] for k in ("level", "severity", "log_level", "loglevel") if k in col_lower), None)
    msg_col = next((col_lower[k] for k in ("message", "msg", "log", "text", "event") if k in col_lower), None)

    for _, row in df.iterrows():
        raw = row.to_json()
        ts = _parse_ts(str(row[ts_col])) if ts_col else None
        level = _normalize_level(str(row[level_col])) if level_col else "INFO"
        msg = str(row[msg_col]) if msg_col else raw

        rows.append({
            "timestamp": ts,
            "level": level,
            "source": "csv",
            "message": msg,
            "raw": raw,
        })
    return rows


def _parse_json_file(content: str) -> list[dict]:
    """Parse a log file that is a JSON array of objects."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        data = [data]

    rows = []
    for obj in data:
        if not isinstance(obj, dict):
            continue
        result = _try_json_line(json.dumps(obj))
        if result:
            rows.append(result)
    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_logs(content: str, filename: str = "") -> pd.DataFrame:
    """
    Parse raw log content into a normalised pandas DataFrame.

    Auto-detects format from content and optional filename hint.

    Columns: timestamp, level, source, message, raw

    Args:
        content: Raw text content of the log file.
        filename: Original filename (used for format hints like .csv, .json).

    Returns:
        pd.DataFrame with schema described above.
    """
    rows: list[dict] = []
    fname_lower = filename.lower()

    # --- CSV files ---
    if fname_lower.endswith(".csv"):
        rows = _parse_csv(content)

    # --- JSON array files ---
    elif fname_lower.endswith(".json") and content.strip().startswith("["):
        rows = _parse_json_file(content)

    else:
        # Line-by-line parsing (handles mixed formats)
        for line in content.splitlines():
            parsed = _parse_line(line)
            if parsed:
                rows.append(parsed)

    if not rows:
        # Return empty but correctly-shaped DataFrame
        return pd.DataFrame(columns=["timestamp", "level", "source", "message", "raw"])

    df = pd.DataFrame(rows)

    # Ensure all required columns exist
    for col in ["timestamp", "level", "source", "message", "raw"]:
        if col not in df.columns:
            df[col] = None

    # Normalise all timestamps to UTC-aware before sorting to avoid
    # tz-naive vs tz-aware comparison errors when mixing log formats.
    def _to_utc(ts):
        if ts is None or (hasattr(ts, '__class__') and ts.__class__.__name__ == 'NaTType'):
            return ts
        try:
            t = pd.Timestamp(ts)
            if t is pd.NaT:
                return t
            if t.tzinfo is None:
                return t.tz_localize("UTC")
            return t.tz_convert("UTC")
        except Exception:
            return pd.NaT

    df["timestamp"] = df["timestamp"].apply(_to_utc)
    df = df.sort_values("timestamp", na_position="first").reset_index(drop=True)

    return df


def get_summary_stats(df: pd.DataFrame) -> dict:
    """
    Compute summary statistics from a parsed log DataFrame.

    Returns a dict with total, by_level counts, error_rate, and time range.
    """
    total = len(df)
    by_level = df["level"].value_counts().to_dict()

    error_count = by_level.get("ERROR", 0) + by_level.get("CRITICAL", 0) + by_level.get("FATAL", 0)
    critical_count = by_level.get("CRITICAL", 0) + by_level.get("FATAL", 0)
    warning_count = by_level.get("WARN", 0) + by_level.get("WARNING", 0)

    # Health score: 100 — weighted penalty for errors/criticals
    if total > 0:
        error_rate = error_count / total
        critical_rate = critical_count / total
        health_score = max(0, round(100 - (error_rate * 50) - (critical_rate * 50)))
    else:
        health_score = 100

    ts_series = df["timestamp"].dropna()
    time_start = str(ts_series.min()) if not ts_series.empty else "N/A"
    time_end = str(ts_series.max()) if not ts_series.empty else "N/A"

    return {
        "total": total,
        "by_level": by_level,
        "error_count": error_count,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "health_score": health_score,
        "time_start": time_start,
        "time_end": time_end,
    }


def chunk_dataframe(
    df: pd.DataFrame,
    max_lines: Optional[int] = None,
    max_chars: Optional[int] = None,
) -> list[str]:
    """
    Split the DataFrame into text chunks suitable for LLM context windows.

    Strategy:
      1. Sort by timestamp (already done in parse_logs).
      2. Group into windows of at most max_lines lines (default: MAX_LINES_PER_CHUNK).
      3. If a window exceeds max_chars characters, split it further.

    Args:
        df:         Parsed log DataFrame.
        max_lines:  Override for maximum lines per chunk (default: MAX_LINES_PER_CHUNK).
        max_chars:  Override for maximum characters per chunk (default: MAX_CHARS_PER_CHUNK).

    Returns a list of plain-text strings, each representing one chunk.
    """
    _max_lines = max_lines if max_lines is not None else MAX_LINES_PER_CHUNK
    _max_chars = max_chars if max_chars is not None else MAX_CHARS_PER_CHUNK

    chunks: list[str] = []
    lines = df["raw"].tolist()
    total = len(lines)

    start = 0
    while start < total:
        end = min(start + _max_lines, total)
        window_lines = lines[start:end]
        block = "\n".join(str(ln) for ln in window_lines)

        # If the block is still too large, split by characters
        if len(block) > _max_chars:
            sub_chunks = [
                block[i : i + _max_chars]
                for i in range(0, len(block), _max_chars)
            ]
            chunks.extend(sub_chunks)
        else:
            chunks.append(block)

        start = end

    return chunks
