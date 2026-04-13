#!/usr/bin/env python3
"""
Smoke-test a MindBot DingTalk token callback URL from your workstation.

Runs:
  1) GET  — same shape as DingTalk reachability probes (no DB / no body).
  2) POST {} — empty JSON, no timestamp/sign (connectivity probe when routed to a tenant).
  3) Optional POST with valid DingTalk HMAC headers — requires app secret (no Dify call if body has empty text).

Usage (from repo root):
  python scripts/mindbot/dingtalk_callback_smoke_test.py
  python scripts/mindbot/dingtalk_callback_smoke_test.py --url https://example.com/api/mindbot/dingtalk/callback/t/TOKEN
  set MINDBOT_DINGTALK_APP_SECRET=your_robot_app_secret
  python scripts/mindbot/dingtalk_callback_smoke_test.py --signed

Use --verbose to print response bodies. Check server logs for dingtalk_inbound_full / inbound lines
if MINDBOT_LOG_CALLBACK_* is enabled on the server.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from typing import Any

import httpx


def _compute_sign(timestamp_str: str, app_secret: str) -> str:
    """Base64(HMAC-SHA256); must match services.mindbot.platforms.dingtalk.verify.compute_sign."""
    key = app_secret.encode("utf-8")
    msg = f"{timestamp_str}\n{app_secret}".encode("utf-8")
    digest = hmac.new(key, msg, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


_DEFAULT_URL = (
    "https://roy.mindspringedu.com/api/mindbot/dingtalk/callback/t/"
    "3RrrAv6rsoSzKODHcZUB-A"
)


def _print_result(
    name: str,
    status: int,
    headers: httpx.Headers,
    text: str,
    verbose: bool,
) -> None:
    err = headers.get("x-mindbot-error-code") or headers.get("X-MindBot-Error-Code") or ""
    print(f"[{name}] HTTP {status}  X-MindBot-Error-Code={err!r}")
    if verbose and text:
        preview = text[:4000]
        if len(text) > 4000:
            preview += "...(truncated)"
        print(f"    body: {preview!r}")


def _get_secret(args: argparse.Namespace) -> str:
    if args.secret and args.secret.strip():
        return args.secret.strip()
    return (os.environ.get("MINDBOT_DINGTALK_APP_SECRET") or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test MindBot /api/mindbot/dingtalk/callback/t/{token}",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("MINDBOT_CALLBACK_TEST_URL", _DEFAULT_URL),
        help="Full callback URL including https:// and token path",
    )
    parser.add_argument(
        "--secret",
        default="",
        help="Robot app secret for --signed (else MINDBOT_DINGTALK_APP_SECRET)",
    )
    parser.add_argument(
        "--signed",
        action="store_true",
        help="Also send POST with timestamp/sign + empty text (needs app secret)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print response body text",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout seconds",
    )
    args = parser.parse_args()
    url = args.url.strip()
    if not url.startswith("https://") and not url.startswith("http://"):
        print("URL must start with http:// or https://", file=sys.stderr)
        return 2

    timeout = httpx.Timeout(args.timeout)
    limits = httpx.Limits(max_connections=5)

    with httpx.Client(timeout=timeout, limits=limits) as client:
        try:
            get_resp = client.get(url)
            _print_result("GET", get_resp.status_code, get_resp.headers, get_resp.text, args.verbose)
        except httpx.HTTPError as exc:
            print(f"[GET] failed: {exc}", file=sys.stderr)
            return 1

        try:
            post_empty = client.post(url, json={})
            _print_result(
                "POST {}",
                post_empty.status_code,
                post_empty.headers,
                post_empty.text,
                args.verbose,
            )
        except httpx.HTTPError as exc:
            print(f"[POST {{}}] failed: {exc}", file=sys.stderr)
            return 1

        if args.signed:
            secret = _get_secret(args)
            if not secret:
                print(
                    "For --signed, pass --secret or set MINDBOT_DINGTALK_APP_SECRET.",
                    file=sys.stderr,
                )
                return 2
            ts_ms = str(int(time.time() * 1000))
            sign = _compute_sign(ts_ms, secret)
            body: dict[str, Any] = {
                "msgtype": "text",
                "text": {"content": ""},
                "robotCode": "smoke_test",
            }
            try:
                signed_resp = client.post(
                    url,
                    content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "timestamp": ts_ms,
                        "sign": sign,
                    },
                )
                _print_result(
                    "POST signed (empty text)",
                    signed_resp.status_code,
                    signed_resp.headers,
                    signed_resp.text,
                    args.verbose,
                )
            except httpx.HTTPError as exc:
                print(f"[POST signed] failed: {exc}", file=sys.stderr)
                return 1

    print(
        "Done. If the server still shows nothing, middleware may block before MindBot "
        "(check 403/access logs).",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
