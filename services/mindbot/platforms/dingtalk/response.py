"""DingTalk OpenAPI v1 JSON body semantics (HTTP 200 may still indicate business failure)."""

from __future__ import annotations

import json
from typing import Any


def dingtalk_v1_response_ok(body: dict[str, Any]) -> bool:
    """
    Return True when the JSON body indicates a successful v1 API call.

    DingTalk may return HTTP 200 with ``success: false``, non-empty ``code``,
    ``errcode != 0``, or nested ``error`` payloads. Treat those as failure.
    """
    if body.get("success") is False:
        return False
    if body.get("success") is True:
        return True

    errcode = body.get("errcode")
    if errcode is not None and errcode != 0:
        return False

    code = body.get("code")
    if isinstance(code, str):
        stripped = code.strip()
        if stripped and stripped != "0":
            return False
    elif isinstance(code, int) and code != 0:
        return False

    err = body.get("error")
    if isinstance(err, dict) and err:
        ec = err.get("code")
        if isinstance(ec, str) and ec.strip():
            return False
        if isinstance(ec, int) and ec != 0:
            return False

    return True


def dingtalk_v1_body_log_snippet(body: dict[str, Any], max_len: int = 400) -> str:
    """Compact JSON for logs (truncated)."""
    try:
        s = json.dumps(body, ensure_ascii=False, default=str)
    except TypeError:
        s = str(body)
    if len(s) > max_len:
        return f"{s[:max_len]}..."
    return s
