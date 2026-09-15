"""Meaning facet streams Responses events and falls back only when unused."""

import asyncio
from typing import Any, AsyncGenerator, Dict, List

import pytest

from agents.mind_maps.node_explain import (
    MindMapNodeExplainGenerator,
    _should_fallback_to_chat,
)
from agents.mind_maps.node_explain_prompts import (
    RESEARCH_IMAGE_MAX,
    RESEARCH_IMAGE_TOOLS,
    RESEARCH_TOOLS,
)
from agents.mind_maps.node_explain_research import (
    clip_research_images,
    merge_research_streams,
    split_image_events,
)
from clients.llm.responses.dashscope_events import normalize_responses_event
from services.infrastructure.http.error_handler import (
    LLMInvalidParameterError,
    LLMModelNotFoundError,
    LLMRateLimitError,
)
from services.llm.responses.registry import ResponsesClientRegistry, get_responses_registry


class _FakeResponses:
    def __init__(
        self,
        events: List[Dict[str, Any]] | Exception,
        image_events: List[Dict[str, Any]] | Exception | None = None,
    ) -> None:
        self.events = events
        self.image_events = image_events if image_events is not None else []
        self.calls: List[Dict[str, Any]] = []

    @property
    def kwargs(self) -> Dict[str, Any] | None:
        """Write-path kwargs (search), not the parallel image call."""
        for call in self.calls:
            if list(call.get("tools") or []) != list(RESEARCH_IMAGE_TOOLS):
                return call
        return self.calls[-1] if self.calls else None

    def _is_image_call(self, kwargs: Dict[str, Any]) -> bool:
        return list(kwargs.get("tools") or []) == list(RESEARCH_IMAGE_TOOLS)

    async def stream(self, **kwargs: Any) -> AsyncGenerator[Dict[str, Any], None]:
        """Record kwargs and yield canned events or raise."""
        self.calls.append(kwargs)
        payload = self.image_events if self._is_image_call(kwargs) else self.events
        if isinstance(payload, Exception):
            raise payload
        for event in payload:
            yield event


class _FakeChat:
    def __init__(self) -> None:
        self.called = False

    async def chat_stream(self, **_kwargs: Any) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield one chat-completion token for fallback tests."""
        self.called = True
        yield {"type": "token", "content": "chat gloss"}


def _generator(responses: _FakeResponses, chat: _FakeChat | None = None) -> MindMapNodeExplainGenerator:
    gen = MindMapNodeExplainGenerator()
    setattr(gen, "responses_service", responses)
    if chat is not None:
        setattr(gen, "llm_service", chat)
    return gen


async def _collect(gen: MindMapNodeExplainGenerator) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    async for event in gen.stream_explain(
        node_label="光合作用",
        topic="植物",
        language="zh",
        facet="meaning",
    ):
        events.append(event)
    return events


def test_fallback_only_for_missing_or_unsupported_model() -> None:
    """Rate limits stay hard errors; missing / unsupported models may use chat."""
    assert _should_fallback_to_chat(LLMModelNotFoundError("missing"))
    assert _should_fallback_to_chat(LLMInvalidParameterError("model does not support tools"))
    assert not _should_fallback_to_chat(LLMInvalidParameterError("bad temperature"))
    assert not _should_fallback_to_chat(LLMRateLimitError("slow down"))


@pytest.mark.asyncio
async def test_meaning_path_uses_research_tools() -> None:
    """Meaning explain searches on the write path; images are a parallel call."""
    responses = _FakeResponses(
        [
            {"type": "status", "phase": "searching", "query": "光合作用"},
            {"type": "token", "content": "叶片把光变成糖。"},
        ],
        image_events=[{"type": "image", "images": [{"url": "https://example.com/leaf.jpg"}]}],
    )
    events = await _collect(_generator(responses))
    assert responses.kwargs is not None
    assert responses.kwargs["tools"] == list(RESEARCH_TOOLS)
    assert responses.kwargs["enable_thinking"] is True
    assert responses.kwargs["request_type"] == "mindmap_node_explain"
    assert responses.kwargs.get("bill_usage", True) is True
    image_calls = [call for call in responses.calls if list(call.get("tools") or []) == list(RESEARCH_IMAGE_TOOLS)]
    assert len(image_calls) == 1
    assert image_calls[0]["bill_usage"] is False
    kinds = [event["event"] for event in events]
    assert "status" in kinds
    assert "token" in kinds
    assert "image" in kinds
    assert events[-1] == {"event": "end", "facet": "meaning"}


@pytest.mark.asyncio
async def test_model_not_found_falls_back_to_chat() -> None:
    """A Responses model miss uses the existing chat_stream gloss."""
    chat = _FakeChat()
    events = await _collect(_generator(_FakeResponses(LLMModelNotFoundError("gone")), chat))
    assert chat.called
    assert events == [
        {"event": "token", "text": "chat gloss", "facet": "meaning"},
        {"event": "end", "facet": "meaning"},
    ]


@pytest.mark.asyncio
async def test_no_chat_fallback_after_research_already_streamed() -> None:
    """Once research events went out, a late unsupported error must not mix chat."""

    class _PartialThenBoom(_FakeResponses):
        async def stream(self, **kwargs: Any) -> AsyncGenerator[Dict[str, Any], None]:
            self.calls.append(kwargs)
            if self._is_image_call(kwargs):
                return
            yield {"type": "status", "phase": "searching", "query": "光合作用"}
            raise LLMInvalidParameterError("does not support web_extractor")

    chat = _FakeChat()
    gen = _generator(_PartialThenBoom([]), chat)
    with pytest.raises(LLMInvalidParameterError):
        await _collect(gen)
    assert not chat.called


@pytest.mark.asyncio
async def test_image_failure_does_not_abort_write() -> None:
    """A failed image companion must not drop the search-then-write gloss."""
    responses = _FakeResponses(
        [{"type": "token", "content": "叶片把光变成糖。"}],
        image_events=LLMRateLimitError("image quota"),
    )
    events = await _collect(_generator(responses))
    assert events == [
        {"event": "token", "text": "叶片把光变成糖。", "facet": "meaning"},
        {"event": "end", "facet": "meaning"},
    ]


@pytest.mark.asyncio
async def test_merge_yields_write_before_slow_images() -> None:
    """Write tokens are not gated on the image Responses turn."""

    async def _write() -> AsyncGenerator[Dict[str, Any], None]:
        yield {"type": "token", "content": "gloss"}

    async def _images() -> AsyncGenerator[Dict[str, Any], None]:
        await asyncio.sleep(0.05)
        yield {"type": "thinking", "content": "ignore"}
        yield {"type": "status", "phase": "images"}
        yield {"type": "image", "images": [{"url": "https://example.com/a.jpg"}]}

    events = [event async for event in merge_research_streams(_write(), _images())]
    assert events[0] == {"type": "token", "content": "gloss"}
    assert events[1]["type"] == "status"
    assert events[2]["type"] == "image"


@pytest.mark.asyncio
async def test_merge_clips_images_at_research_max() -> None:
    """The image companion stops after the 20–30 card budget."""

    async def _write() -> AsyncGenerator[Dict[str, Any], None]:
        yield {"type": "token", "content": "gloss"}

    async def _images() -> AsyncGenerator[Dict[str, Any], None]:
        yield {
            "type": "image",
            "images": [{"url": f"https://example.com/{index}.jpg"} for index in range(40)],
        }
        yield {"type": "image", "images": [{"url": "https://example.com/extra.jpg"}]}

    events = [event async for event in merge_research_streams(_write(), _images())]
    image_events = [event for event in events if event.get("type") == "image"]
    assert len(image_events) == RESEARCH_IMAGE_MAX
    assert all(len(event["images"]) == 1 for event in image_events)


def test_clip_research_images_stops_at_limit() -> None:
    """A later image batch is dropped once the cap is already filled."""
    event = {"type": "image", "images": [{"url": "https://example.com/a.jpg"}]}
    clipped, nxt = clip_research_images(event, RESEARCH_IMAGE_MAX)
    assert clipped is None
    assert nxt == RESEARCH_IMAGE_MAX


def _normalized(payload: dict) -> list[dict]:
    return list(normalize_responses_event(payload))


def test_search_item_added_is_status_searching() -> None:
    """web_search_call.added becomes a searching status with the query."""
    events = _normalized(
        {
            "type": "response.output_item.added",
            "item": {
                "type": "web_search_call",
                "action": {"type": "search", "query": "光合作用"},
            },
        }
    )
    assert events == [{"type": "status", "phase": "searching", "query": "光合作用", "urls": []}]


def test_search_item_done_emits_sources_without_dashscope_names() -> None:
    """Completed search yields url/title cards, not web_search_call."""
    events = _normalized(
        {
            "type": "response.output_item.done",
            "item": {
                "type": "web_search_call",
                "action": {
                    "type": "search",
                    "query": "光合作用",
                    "sources": [
                        {"type": "url", "url": "https://www.wikipedia.org/wiki/Photosynthesis"},
                    ],
                },
            },
        }
    )
    assert len(events) == 1
    event = events[0]
    assert event["type"] == "search_source"
    assert event["query"] == "光合作用"
    assert event["sources"] == [
        {
            "url": "https://www.wikipedia.org/wiki/Photosynthesis",
            "title": "www.wikipedia.org",
        }
    ]
    dumped = str(event)
    assert "web_search_call" not in dumped
    assert "output_item" not in dumped


def test_extractor_done_uses_item_urls() -> None:
    """web_extractor_call.done becomes extract with the fetched URLs."""
    events = _normalized(
        {
            "type": "response.output_item.done",
            "item": {
                "type": "web_extractor_call",
                "goal": "Extract the photosynthesis page",
                "urls": ["https://en.wikipedia.org/wiki/Photosynthesis"],
            },
        }
    )
    assert events == [
        {
            "type": "extract",
            "goal": "Extract the photosynthesis page",
            "urls": ["https://en.wikipedia.org/wiki/Photosynthesis"],
        }
    ]


def test_image_done_parses_output_json() -> None:
    """web_search_image_call.done emits one image event per card."""
    events = _normalized(
        {
            "type": "response.output_item.done",
            "item": {
                "type": "web_search_image_call",
                "output": (
                    '[{"title": "Leaf", "url": "https://example.com/leaf.jpg", "index": 1},'
                    '{"title": "Stem", "url": "https://example.com/stem.jpg", "index": 2}]'
                ),
            },
        }
    )
    assert events == [
        {
            "type": "image",
            "images": [{"title": "Leaf", "url": "https://example.com/leaf.jpg", "index": 1}],
        },
        {
            "type": "image",
            "images": [{"title": "Stem", "url": "https://example.com/stem.jpg", "index": 2}],
        },
    ]


def test_split_image_events_drips_a_batch() -> None:
    """A provider batch becomes one SSE card at a time."""
    pieces = split_image_events(
        {
            "type": "image",
            "images": [
                {"url": "https://example.com/a.jpg"},
                {"url": "https://example.com/b.jpg"},
            ],
        }
    )
    assert [piece["images"][0]["url"] for piece in pieces] == [
        "https://example.com/a.jpg",
        "https://example.com/b.jpg",
    ]


def test_text_delta_keeps_leading_space() -> None:
    """Answer deltas must not be stripped or words glue together."""
    events = _normalized({"type": "response.output_text.delta", "delta": " 绿色"})
    assert events == [{"type": "token", "content": " 绿色"}]


def test_reasoning_text_delta_is_thinking() -> None:
    """Both reasoning event names map to thinking."""
    summary = _normalized({"type": "response.reasoning_summary_text.delta", "delta": "先搜"})
    raw = _normalized({"type": "response.reasoning_text.delta", "delta": "再读"})
    assert summary == [{"type": "thinking", "content": "先搜"}]
    assert raw == [{"type": "thinking", "content": "再读"}]


def test_completed_emits_usage_only() -> None:
    """response.completed becomes usage, then the adapter is done."""
    events = _normalized(
        {
            "type": "response.completed",
            "response": {
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 4,
                    "total_tokens": 14,
                    "x_tools": {"web_search": {"count": 1}},
                }
            },
        }
    )
    assert events == [
        {
            "type": "usage",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 4,
                "total_tokens": 14,
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "x_tools": {"web_search": {"count": 1}},
            },
        }
    ]


def test_registry_defaults_unknown_provider_to_qwen() -> None:
    """Node explain's qwen key (and unknown keys) resolve to DashScope."""
    registry = ResponsesClientRegistry()
    qwen = registry.get_client("qwen")
    assert registry.get_client("unknown") is qwen
    assert get_responses_registry().get_client("qwen") is not None
