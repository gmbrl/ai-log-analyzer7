"""
Dashboard API — FastAPI backend serving log metrics for the React dashboard.

Run with:
    uvicorn api.dashboard_api:app --reload --port 8000

Reads logs from the same sources as the main Streamlit app (sample_logs/,
uploaded files, or a live log path configured via env var LOG_PATH).
Falls back to generating mock data when no logs are available so the
dashboard is always functional during development.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import Response, StreamingResponse
except ImportError as exc:
    raise ImportError(
        "FastAPI is required for the dashboard API.\n"
        "Install it with:  pip install fastapi uvicorn"
    ) from exc

# ---------------------------------------------------------------------------
# Attempt to reuse existing parsing utilities
# ---------------------------------------------------------------------------
try:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.core.log_parser import parse_log_lines  # type: ignore
    from src.core.preprocessor import redact_lines  # type: ignore

    HAS_PARSER = True
except Exception:
    HAS_PARSER = False

# ---------------------------------------------------------------------------
app = FastAPI(title="TraceLens Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helper: read raw log lines from configured sources
# ---------------------------------------------------------------------------
LOG_PATH = os.environ.get("LOG_PATH", "")
SAMPLE_LOG_DIR = Path("sample_logs")


def _read_raw_lines(max_lines: int = 50_000) -> list[str]:
    """Return raw log lines from LOG_PATH env var or sample_logs directory."""
    lines: list[str] = []

    if LOG_PATH and Path(LOG_PATH).exists():
        with open(LOG_PATH, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()[-max_lines:]
        return [l.rstrip() for l in lines]

    if SAMPLE_LOG_DIR.exists():
        for p in sorted(SAMPLE_LOG_DIR.glob("*.log"))[:5]:
            with open(p, encoding="utf-8", errors="replace") as fh:
                lines.extend(fh.readlines())
            if len(lines) >= max_lines:
                break
        return [l.rstrip() for l in lines[-max_lines:]]

    return []


# ---------------------------------------------------------------------------
# Mock data generators (used when no real logs are found)
# ---------------------------------------------------------------------------
SERVICES = [
    "api-gateway",
    "auth-service",
    "payment-service",
    "notification-service",
    "user-service",
    "worker-primary",
    "worker-secondary",
    "postgres-primary",
    "redis-cache",
    "message-queue",
]
SEVERITIES = ["FATAL", "ERROR", "WARN", "INFO", "DEBUG"]
SEV_WEIGHTS = [0.01, 0.08, 0.15, 0.65, 0.11]


def _mock_severity_counts() -> list[dict]:
    base = {"FATAL": 12, "ERROR": 342, "WARN": 891, "INFO": 14503}
    result = []
    for lv, cnt in base.items():
        spark = [max(0, int(cnt * (0.7 + 0.6 * random.random()))) for _ in range(12)]
        delta = round(random.uniform(-18, 22), 1)
        result.append(
            {"level": lv, "count": cnt, "delta_pct": delta, "sparkline": spark}
        )
    return result


def _mock_service_health() -> dict:
    instances = []
    for svc in SERVICES:
        for idx in range(random.randint(1, 4)):
            r = random.random()
            status = "healthy" if r > 0.3 else ("degraded" if r > 0.1 else "failed")
            instances.append(
                {
                    "id": f"{svc}-{idx}",
                    "name": svc,
                    "status": status,
                    "response_time_ms": int(random.gauss(180, 80)),
                }
            )
    healthy = sum(1 for i in instances if i["status"] == "healthy")
    degraded = sum(1 for i in instances if i["status"] == "degraded")
    failed = sum(1 for i in instances if i["status"] == "failed")
    return {
        "instances": instances,
        "healthy": healthy,
        "degraded": degraded,
        "failed": failed,
        "total": len(instances),
    }


def _mock_incidents(n: int = 18) -> list[dict]:
    now = int(time.time())
    incidents = []
    for _ in range(n):
        offset = random.randint(0, 3600)
        ts = now - offset
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        svc = random.choice(SERVICES)
        sev = random.choices(["FATAL", "ERROR", "WARN"], weights=[0.1, 0.6, 0.3])[0]
        incidents.append(
            {
                "time": dt.strftime("%H:%M"),
                "timestamp_unix": ts,
                "service": svc,
                "severity": sev,
                "log_count": random.randint(3, 200),
                "affected_instances": random.randint(1, 4),
                "sample_message": f"{sev}: {svc} encountered an issue at {dt.strftime('%H:%M:%S')}",
            }
        )
    incidents.sort(key=lambda x: x["timestamp_unix"], reverse=True)
    return incidents


def _mock_bubbles() -> list[dict]:
    result = []
    for svc in SERVICES:
        rate = round(random.uniform(0.1, 15), 2)
        vol = random.randint(500, 25000)
        status = "critical" if rate > 8 else ("warning" if rate > 3 else "healthy")
        result.append(
            {
                "service": svc,
                "error_rate": rate,
                "log_volume": vol,
                "error_count": int(vol * rate / 100),
                "status": status,
                "sample_stack": (
                    f"java.lang.NullPointerException\n  at {svc}.Handler.process(Handler.java:42)\n  at ..."
                    if status == "critical"
                    else None
                ),
            }
        )
    return result


def _mock_latency(points: int = 20) -> list[dict]:
    now = int(time.time())
    result = []
    for i in range(points):
        ts = now - (points - i) * 180
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        result.append(
            {
                "time": dt.strftime("%H:%M"),
                "api_avg": int(random.gauss(120, 20)),
                "api_p95": int(random.gauss(280, 40)),
                "api_p99": int(random.gauss(450, 60)),
                "worker_avg": int(random.gauss(340, 50)),
                "worker_p95": int(random.gauss(620, 80)),
                "db_avg": int(random.gauss(80, 15)),
                "db_p95": int(random.gauss(190, 30)),
                "db_p99": int(random.gauss(380, 60)),
            }
        )
    return result


def _mock_log_sources() -> list[dict]:
    sources = ["API Gateway", "Workers", "Database", "Cache", "Queue"]
    result = []
    for src in sources:
        total = random.randint(800, 5000)
        fatal = random.randint(0, 10)
        error = random.randint(20, 300)
        warn = random.randint(50, 500)
        info = total - fatal - error - warn
        result.append(
            {"source": src, "info": max(0, info), "warn": warn, "error": error, "fatal": fatal}
        )
    return result


# ---------------------------------------------------------------------------
# Real log parsing
# ---------------------------------------------------------------------------
LEVEL_MAP = {
    "fatal": "FATAL",
    "error": "ERROR",
    "err": "ERROR",
    "warn": "WARN",
    "warning": "WARN",
    "info": "INFO",
    "information": "INFO",
    "debug": "DEBUG",
    "dbg": "DEBUG",
    "trace": "DEBUG",
}


def _parse_level(raw: str) -> str:
    raw_lower = raw.lower()
    for k, v in LEVEL_MAP.items():
        if k in raw_lower:
            return v
    return "INFO"


def _real_data_from_logs(
    raw_lines: list[str],
    time_range: str,
    services_filter: list[str],
    severities_filter: list[str],
) -> dict:
    """Build dashboard payload from parsed log lines."""
    if HAS_PARSER:
        try:
            import pandas as pd

            df = parse_log_lines(raw_lines)
        except Exception:
            df = None
    else:
        df = None

    if df is None or (hasattr(df, "__len__") and len(df) == 0):
        return {}  # fall back to mock

    # Apply filters
    if services_filter:
        df = df[df["source"].isin(services_filter)]
    if severities_filter:
        df = df[df["level"].isin(severities_filter)]

    # Severity counts
    counts = df["level"].value_counts().to_dict()
    severity = []
    for lv in ["FATAL", "ERROR", "WARN", "INFO", "DEBUG"]:
        cnt = counts.get(lv, 0)
        severity.append(
            {
                "level": lv,
                "count": cnt,
                "delta_pct": round(random.uniform(-10, 20), 1),
                "sparkline": [max(0, int(cnt * (0.6 + 0.8 * random.random()))) for _ in range(10)],
            }
        )

    # Service health (derive from source column)
    sources = df["source"].dropna().unique().tolist()
    instances = []
    for svc in sources[:30]:
        svc_df = df[df["source"] == svc]
        err_rate = svc_df["level"].isin(["ERROR", "FATAL"]).mean()
        status = "healthy" if err_rate < 0.05 else ("degraded" if err_rate < 0.2 else "failed")
        for idx in range(random.randint(1, 3)):
            instances.append(
                {
                    "id": f"{svc}-{idx}",
                    "name": svc,
                    "status": status,
                    "response_time_ms": int(random.gauss(200, 60)),
                }
            )

    # Incidents
    incidents = []
    try:
        import pandas as pd

        df["_ts"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df_sorted = df.dropna(subset=["_ts"]).sort_values("_ts", ascending=False)
        for _, row in df_sorted[df_sorted["level"].isin(["FATAL", "ERROR", "WARN"])].head(30).iterrows():
            ts = row["_ts"]
            incidents.append(
                {
                    "time": ts.strftime("%H:%M"),
                    "timestamp_unix": int(ts.timestamp()),
                    "service": str(row.get("source", "unknown")),
                    "severity": str(row.get("level", "ERROR")),
                    "log_count": random.randint(1, 50),
                    "affected_instances": random.randint(1, 3),
                    "sample_message": str(row.get("message", ""))[:120],
                }
            )
    except Exception:
        incidents = _mock_incidents(10)

    # Bubbles
    bubbles = []
    for svc in sources[:10]:
        svc_df = df[df["source"] == svc]
        total = len(svc_df)
        errs = svc_df["level"].isin(["ERROR", "FATAL"]).sum()
        rate = round((errs / max(total, 1)) * 100, 2)
        status = "critical" if rate > 8 else ("warning" if rate > 3 else "healthy")
        bubbles.append(
            {
                "service": svc,
                "error_rate": rate,
                "log_volume": total,
                "error_count": int(errs),
                "status": status,
                "sample_stack": None,
            }
        )

    return {
        "severity": severity,
        "service_health": {
            "instances": instances,
            "healthy": sum(1 for i in instances if i["status"] == "healthy"),
            "degraded": sum(1 for i in instances if i["status"] == "degraded"),
            "failed": sum(1 for i in instances if i["status"] == "failed"),
            "total": len(instances),
        },
        "incidents": incidents,
        "bubbles": bubbles,
        "latency": _mock_latency(),
        "log_sources": _mock_log_sources(),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/dashboard")
def get_dashboard(
    time_range: str = Query("1h"),
    services: str = Query(""),
    severities: str = Query("FATAL,ERROR,WARN,INFO,DEBUG"),
    incident_types: str = Query(""),
) -> dict:
    services_filter = [s for s in services.split(",") if s]
    severities_filter = [s for s in severities.split(",") if s]

    raw_lines = _read_raw_lines()
    if raw_lines:
        real = _real_data_from_logs(raw_lines, time_range, services_filter, severities_filter)
        if real:
            real["last_updated"] = datetime.now(tz=timezone.utc).isoformat()
            return real

    # Fall back to mock
    return {
        "severity": _mock_severity_counts(),
        "service_health": _mock_service_health(),
        "incidents": _mock_incidents(),
        "bubbles": _mock_bubbles(),
        "latency": _mock_latency(),
        "log_sources": _mock_log_sources(),
        "last_updated": datetime.now(tz=timezone.utc).isoformat(),
    }


@app.get("/api/logs")
def get_logs(
    time_range: str = Query("1h"),
    services: str = Query(""),
    severities: str = Query("FATAL,ERROR,WARN,INFO,DEBUG"),
    service: str = Query(""),
    from_ts: str = Query(""),
    to_ts: str = Query(""),
    limit: int = Query(500),
) -> list[dict]:
    services_filter = [s for s in services.split(",") if s]
    if service:
        services_filter = [service]
    severities_filter = [s for s in severities.split(",") if s]

    raw_lines = _read_raw_lines()
    if raw_lines and HAS_PARSER:
        try:
            import pandas as pd

            df = parse_log_lines(raw_lines)
            if services_filter:
                df = df[df["source"].isin(services_filter)]
            if severities_filter:
                df = df[df["level"].isin(severities_filter)]
            records = df.head(limit).to_dict(orient="records")
            return [
                {
                    "timestamp": str(r.get("timestamp", "")),
                    "level": str(r.get("level", "INFO")),
                    "source": str(r.get("source", "")),
                    "message": str(r.get("message", "")),
                    "raw": str(r.get("raw", "")),
                }
                for r in records
            ]
        except Exception:
            pass

    # Mock logs
    entries = []
    for i in range(min(limit, 100)):
        svc = (services_filter[0] if services_filter else random.choice(SERVICES))
        lv = random.choices(SEVERITIES, weights=SEV_WEIGHTS)[0]
        ts = datetime.now(tz=timezone.utc).isoformat()
        entries.append(
            {
                "timestamp": ts,
                "level": lv,
                "source": svc,
                "message": f"[{lv}] {svc}: sample log message #{i}",
                "raw": f"{ts} {lv} {svc} sample log message #{i}",
            }
        )
    return entries


@app.get("/api/export")
def export_logs(
    format: str = Query("json"),
    time_range: str = Query("1h"),
    services: str = Query(""),
    severities: str = Query("FATAL,ERROR,WARN,INFO,DEBUG"),
) -> Response:
    logs = get_logs(
        time_range=time_range,
        services=services,
        severities=severities,
        limit=10_000,
    )

    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf, fieldnames=["timestamp", "level", "source", "message", "raw"]
        )
        writer.writeheader()
        writer.writerows(logs)
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=logs_export.csv"},
        )

    return Response(
        content=json.dumps(logs, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=logs_export.json"},
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "has_parser": HAS_PARSER}
