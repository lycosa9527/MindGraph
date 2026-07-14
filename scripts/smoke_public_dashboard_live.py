#!/usr/bin/env python3
"""
Live smoke for national dashboard SSE against a running MindGraph process.

Usage (WSL + conda):
  # terminal A — signed in as super-admin in the browser is not required;
  # this script needs a JWT access_token cookie from a super-admin session.
  cd /mnt/d/MindGraph && python main.py
  # terminal B
  PUBLIC_DASHBOARD_SMOKE_ACCESS_TOKEN='<jwt>' \\
    python scripts/smoke_public_dashboard_live.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def _wait_ready(base: str, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    last_err = ""
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base}/health", timeout=2.0)
            if response.status_code < 500:
                return
            last_err = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last_err = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"Server not ready at {base}: {last_err}")


def _run_flow(base: str, access_token: str) -> None:
    with httpx.Client(base_url=base, timeout=30.0, follow_redirects=True) as client:
        denied = client.get("/api/public/stats")
        assert denied.status_code in {401, 403}, denied.text

        client.cookies.set("access_token", access_token)

        stats = client.get("/api/public/stats")
        assert stats.status_code == 200, stats.text
        body = stats.json()
        for key in (
            "connected_users",
            "registered_users",
            "tokens_used_today",
            "total_tokens_used",
        ):
            assert key in body

        map_resp = client.get("/api/public/map-data")
        assert map_resp.status_code == 200, map_resp.text
        map_body = map_resp.json()
        assert isinstance(map_body.get("map_data"), list)
        assert isinstance(map_body.get("flag_data"), list)

        history = client.get("/api/public/activity-history?limit=10")
        assert history.status_code == 200, history.text

        geo = client.get("/static/data/china-geo.json")
        assert geo.status_code == 200, geo.text
        assert geo.json().get("type") == "FeatureCollection"

        page = client.get("/dashboard", follow_redirects=False)
        assert page.status_code in {301, 302, 307, 308}, page.text
        assert "tab=settings" in page.headers.get("location", "")
        assert "subtab=public_dashboard" in page.headers.get("location", "")

        admin_page = client.get("/admin?tab=settings&subtab=public_dashboard")
        assert admin_page.status_code == 200, admin_page.text

        for path in ("/dashboard/login", "/pub-dash"):
            legacy = client.get(path, follow_redirects=False)
            assert legacy.status_code in {301, 302, 307, 308}, f"{path} -> {legacy.status_code}"
            assert "subtab=public_dashboard" in legacy.headers.get("location", "")

        with client.stream("GET", "/api/public/activity-stream", timeout=20.0) as stream:
            assert stream.status_code == 200
            assert "text/event-stream" in stream.headers.get("content-type", "")
            collected = ""
            for chunk in stream.iter_text():
                collected += chunk
                if "\n\n" in collected:
                    break
                if len(collected) > 8000:
                    break
        assert "data:" in collected
        payload = json.loads(
            next(line[5:].strip() for line in collected.splitlines() if line.startswith("data:"))
        )
        assert payload.get("type") in {
            "initial",
            "heartbeat",
            "stats_update",
            "activity",
            "error",
        }
        print("SSE first event:", payload.get("type"))

    print("national dashboard live smoke OK")


def main() -> int:
    """Run live smoke against an already-running MindGraph server."""
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("PUBLIC_DASHBOARD_SMOKE_BASE", "http://127.0.0.1:9527"),
        help="Existing MindGraph server (prefer `python main.py`, which starts Celery)",
    )
    args = parser.parse_args()

    access_token = (os.getenv("PUBLIC_DASHBOARD_SMOKE_ACCESS_TOKEN") or "").strip()
    if not access_token:
        print(
            "Set PUBLIC_DASHBOARD_SMOKE_ACCESS_TOKEN to a super-admin JWT access_token",
            file=sys.stderr,
        )
        return 2

    base = args.base_url
    try:
        _wait_ready(base, timeout=15.0)
    except RuntimeError as exc:
        print(
            f"{exc}\nStart the full app first: python main.py\n"
            "Then: PUBLIC_DASHBOARD_SMOKE_ACCESS_TOKEN=… "
            "python scripts/smoke_public_dashboard_live.py",
            file=sys.stderr,
        )
        return 1

    _run_flow(base, access_token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
