"""Merge OpenAI SDK ``extra_body`` into the HTTP JSON body."""

from typing import Any, Dict


def hoist_openai_extra_body(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Copy ``extra_body`` onto the JSON object and drop the nested key.

    The OpenAI Python SDK merges ``extra_body`` before the request. httpx
    does not. DashScope ``deepseek-v4.1-flash`` thinks unless
    ``enable_thinking`` is a top-level field. A short ``max_tokens`` cap is
    then spent on reasoning and the answer stream is empty.
    """
    extra = payload.pop("extra_body", None)
    if isinstance(extra, dict):
        for key, value in extra.items():
            payload[key] = value
    return payload
