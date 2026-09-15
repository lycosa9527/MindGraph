"""Normalize DashScope Responses SSE payloads into provider-neutral events."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from clients.llm.responses.types import (
    STATUS_EXTRACTING,
    STATUS_IMAGES,
    STATUS_SEARCHING,
    error_event,
    extract_event,
    image_event,
    search_source_event,
    status_event,
    thinking_event,
    token_event,
    usage_event,
)

logger = logging.getLogger(__name__)

_ITEM_ADDED = "response.output_item.added"
_ITEM_DONE = "response.output_item.done"
_TEXT_DELTA = "response.output_text.delta"
_REASONING_DELTA = "response.reasoning_summary_text.delta"
_REASONING_TEXT_DELTA = "response.reasoning_text.delta"
_COMPLETED = "response.completed"
_INCOMPLETE = "response.incomplete"
_FAILED = "response.failed"
_ERROR = "error"

_SEARCH_ITEM = "web_search_call"
_EXTRACT_ITEM = "web_extractor_call"
_IMAGE_ITEM = "web_search_image_call"


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_str(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _as_delta(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""


def _host_from_url(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc or "").strip()


def _source_from_entry(entry: Any) -> Optional[Dict[str, str]]:
    payload = _as_dict(entry)
    url = _as_str(payload.get("url"))
    if not url:
        return None
    title = _as_str(payload.get("title")) or _host_from_url(url) or url
    return {"url": url, "title": title}


def _sources_from_action(action: Dict[str, Any]) -> List[Dict[str, str]]:
    raw = action.get("sources")
    if not isinstance(raw, list):
        return []
    sources: List[Dict[str, str]] = []
    for entry in raw:
        source = _source_from_entry(entry)
        if source is not None:
            sources.append(source)
    return sources


def _urls_from_item(item: Dict[str, Any]) -> List[str]:
    raw = item.get("urls")
    if not isinstance(raw, list):
        raw = _as_dict(item.get("action")).get("urls")
    if not isinstance(raw, list):
        return []
    urls: List[str] = []
    for entry in raw:
        url = _as_str(entry)
        if url and url not in urls:
            urls.append(url)
    return urls


def _parse_image_output(raw: Any) -> List[Dict[str, Any]]:
    payload: Any = raw
    if isinstance(raw, str) and raw.strip():
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[ResponsesEvents] Invalid web_search_image output JSON")
            return []
    if not isinstance(payload, list):
        return []
    images: List[Dict[str, Any]] = []
    for entry in payload:
        item = _as_dict(entry)
        url = _as_str(item.get("url"))
        if not url:
            continue
        index = item.get("index")
        images.append(
            {
                "url": url,
                "title": _as_str(item.get("title")),
                "index": index if isinstance(index, int) else len(images) + 1,
            }
        )
    return images


def _usage_from_response(response: Dict[str, Any]) -> Dict[str, Any]:
    usage = _as_dict(response.get("usage"))
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens)
    normalized = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
    }
    extra_tools = usage.get("x_tools")
    if isinstance(extra_tools, dict):
        normalized["x_tools"] = extra_tools
    return normalized


def _status_for_item(item_type: str, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    action = _as_dict(item.get("action"))
    query = _as_str(action.get("query"))
    if item_type == _SEARCH_ITEM:
        return status_event(STATUS_SEARCHING, query=query)
    if item_type == _EXTRACT_ITEM:
        return status_event(STATUS_EXTRACTING, urls=_urls_from_item(item))
    if item_type == _IMAGE_ITEM:
        return status_event(STATUS_IMAGES)
    return None


def _done_events_for_item(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    item_type = _as_str(item.get("type"))
    action = _as_dict(item.get("action"))
    query = _as_str(action.get("query"))
    if item_type == _SEARCH_ITEM:
        sources = _sources_from_action(action)
        return [search_source_event(query, sources)]
    if item_type == _EXTRACT_ITEM:
        return [extract_event(_as_str(item.get("goal")), _urls_from_item(item))]
    if item_type == _IMAGE_ITEM:
        images = _parse_image_output(item.get("output"))
        return [image_event([image]) for image in images]
    return []


def normalize_responses_event(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Map one DashScope Responses SSE object to zero or more normalized events."""
    event_type = _as_str(payload.get("type"))
    if event_type == _ITEM_ADDED:
        item = _as_dict(payload.get("item"))
        status = _status_for_item(_as_str(item.get("type")), item)
        if status is not None:
            yield status
        return
    if event_type == _ITEM_DONE:
        item = _as_dict(payload.get("item"))
        yield from _done_events_for_item(item)
        return
    if event_type == _TEXT_DELTA:
        delta = _as_delta(payload.get("delta"))
        if delta:
            yield token_event(delta)
        return
    if event_type in {_REASONING_DELTA, _REASONING_TEXT_DELTA}:
        delta = _as_delta(payload.get("delta"))
        if delta:
            yield thinking_event(delta)
        return
    if event_type in {_COMPLETED, _INCOMPLETE}:
        response = _as_dict(payload.get("response"))
        yield usage_event(_usage_from_response(response))
        if event_type == _INCOMPLETE:
            yield error_event("Responses output incomplete (token or tool limit)")
        return
    if event_type in {_FAILED, _ERROR}:
        message = _as_str(payload.get("message")) or _as_str(_as_dict(payload.get("error")).get("message"))
        yield error_event(message or "Responses request failed")
