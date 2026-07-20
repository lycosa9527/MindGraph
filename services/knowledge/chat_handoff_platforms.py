"""Chat-handoff platform identifiers shared by ingest, chunking, and validation."""

from __future__ import annotations

CHAT_HANDOFF_PLATFORMS = frozenset({"wechat", "dingtalk", "wecom"})

FLAT_TEXT_INGEST_SOURCES = frozenset(
    {
        "paste",
        "web",
        "handdrawn_mindmap",
        "image_ocr",
        *CHAT_HANDOFF_PLATFORMS,
    }
)
