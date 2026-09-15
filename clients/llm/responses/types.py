"""Provider-neutral Responses API request and event shapes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

ResponsesInput = Union[str, List[Dict[str, Any]]]

CANONICAL_TOOLS = frozenset({"web_search", "web_extractor", "web_search_image"})

STATUS_SEARCHING = "searching"
STATUS_EXTRACTING = "extracting"
STATUS_IMAGES = "images"
STATUS_SUMMARIZING = "summarizing"


@dataclass
class ResponsesRequest:
    """One Responses-API turn. ``tools`` uses canonical names only."""

    model: str
    input: ResponsesInput
    tools: List[str]
    enable_thinking: bool = True
    max_output_tokens: int = 4096
    temperature: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def canonical_tools(self) -> List[str]:
        """Drop unknown tool names so adapters stay stable."""
        return [name for name in self.tools if name in CANONICAL_TOOLS]


def status_event(
    phase: str,
    *,
    query: str = "",
    urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a normalized status event."""
    return {
        "type": "status",
        "phase": phase,
        "query": query,
        "urls": list(urls or []),
    }


def search_source_event(query: str, sources: List[Dict[str, str]]) -> Dict[str, Any]:
    """Build a normalized search-source event."""
    return {"type": "search_source", "query": query, "sources": sources}


def extract_event(goal: str, urls: List[str]) -> Dict[str, Any]:
    """Build a normalized extract event."""
    return {"type": "extract", "goal": goal, "urls": urls}


def image_event(images: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a normalized image-search event."""
    return {"type": "image", "images": images}


def thinking_event(content: str) -> Dict[str, Any]:
    """Build a normalized thinking delta."""
    return {"type": "thinking", "content": content}


def token_event(content: str) -> Dict[str, Any]:
    """Build a normalized answer-token delta."""
    return {"type": "token", "content": content}


def usage_event(usage: Dict[str, Any]) -> Dict[str, Any]:
    """Build a normalized usage event."""
    return {"type": "usage", "usage": usage}


def error_event(message: str) -> Dict[str, Any]:
    """Build a normalized error event."""
    return {"type": "error", "content": message}
