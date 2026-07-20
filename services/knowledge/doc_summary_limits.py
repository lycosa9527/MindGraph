"""Document Summary size limits (upload + qwen3.6-flash input budget).

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

# Upload gate (original file bytes).
DOC_SUMMARY_MAX_FILE_BYTES = 20 * 1024 * 1024

# qwen3.6-flash: max input 991K tokens, context 1M tokens.
DOC_SUMMARY_MODEL_MAX_INPUT_TOKENS = 991_000

# Hard ceiling on extracted markdown characters sent to / stored for generate.
# Treats ~1 char ≈ 1 token (Chinese-heavy docs) and leaves headroom for the
# system prompt + mind-map instructions under the 991K token input limit.
DOC_SUMMARY_MAX_INPUT_CHARS = 900_000

DOC_SUMMARY_CONTENT_TOO_LONG_CODE = "doc_summary_content_too_long"
DOC_SUMMARY_STORAGE_CONFLICT_CODE = "doc_summary_storage_conflict"


class DocSummaryContentTooLongError(ValueError):
    """Extracted / pasted text exceeds the model input hard cap."""

    def __init__(self, char_count: int) -> None:
        self.char_count = char_count
        super().__init__(
            "Extracted text exceeds the model input limit "
            f"({DOC_SUMMARY_MAX_INPUT_CHARS} characters). "
            "Please use a shorter document."
        )


class DocSummaryStorageConflictError(ValueError):
    """Postgres points at an extract blob that is missing or unreadable."""

    def __init__(
        self,
        *,
        package_id: int,
        object_id: Optional[str] = None,
    ) -> None:
        self.package_id = package_id
        self.object_id = object_id
        super().__init__(
            "Document Summary storage is out of sync with Postgres; "
            "the extract was cleared. Please upload or paste again."
        )


def content_exceeds_model_input(char_count: int) -> bool:
    """True when extracted text would exceed the model input hard cap."""
    return char_count > DOC_SUMMARY_MAX_INPUT_CHARS


def content_too_long_detail(*, char_count: int) -> dict[str, object]:
    """Structured API error payload for oversized Document Summary content."""
    return {
        "code": DOC_SUMMARY_CONTENT_TOO_LONG_CODE,
        "message": (
            "Extracted text exceeds the model input limit "
            f"({DOC_SUMMARY_MAX_INPUT_CHARS} characters / "
            f"~{DOC_SUMMARY_MODEL_MAX_INPUT_TOKENS} tokens)."
        ),
        "char_count": char_count,
        "max_chars": DOC_SUMMARY_MAX_INPUT_CHARS,
        "model_max_input_tokens": DOC_SUMMARY_MODEL_MAX_INPUT_TOKENS,
    }


def storage_conflict_detail(
    *,
    package_id: int,
    object_id: Optional[str] = None,
) -> dict[str, object]:
    """Structured API error when PG metadata and COS/local blob disagree."""
    detail: dict[str, object] = {
        "code": DOC_SUMMARY_STORAGE_CONFLICT_CODE,
        "message": (
            "Document Summary storage is out of sync with Postgres; "
            "the extract was cleared. Please upload or paste again."
        ),
        "package_id": package_id,
    }
    if object_id:
        detail["object_id"] = object_id
    return detail
