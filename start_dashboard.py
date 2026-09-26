#!/usr/bin/env python3
"""
start_dashboard.py — convenience launcher that starts both the API and the
React dev server together.

Usage:
    python start_dashboard.py

Or run them separately:
    uvicorn api.dashboard_api:app --reload --port 8000
    cd dashboard && npm run dev
"""
import subprocess
import sys
import os
from pathlib import Path


ROOT = Path(__file__).parent


def main():
    procs = []
    try:
        # 1. FastAPI backend
        api_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.dashboard_api:app",
             "--reload", "--port", "8000"],
            cwd=ROOT,
        )
        procs.append(api_proc)
        print("✓ API server starting on http://localhost:8000")

        # 2. React dev server
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        react_proc = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=ROOT / "dashboard",
        )
        procs.append(react_proc)
        print("✓ React dashboard starting on http://localhost:5173")
        print("\nPress Ctrl+C to stop both servers.\n")

        for p in procs:
            p.wait()

    except KeyboardInterrupt:
        print("\nShutting down…")
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
