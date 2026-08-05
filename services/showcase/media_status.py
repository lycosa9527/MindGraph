"""Derive Showcase media pipeline status for moderation queues."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

# Progressive readiness for reviewers (teaching-design cover/preview pipeline).
# cover_ready = cover thumbnail + PDF preview both available (terminal for teaching).
MEDIA_STATUS_AWAITING_UPLOAD = "awaiting_upload"
MEDIA_STATUS_CONVERTING_PREVIEW = "converting_preview"
MEDIA_STATUS_GENERATING_COVER = "generating_cover"
MEDIA_STATUS_PREVIEW_READY = "preview_ready"
MEDIA_STATUS_COVER_READY = "cover_ready"
MEDIA_STATUS_READY = "ready"
MEDIA_STATUS_PREVIEW_FAILED = "preview_failed"
MEDIA_STATUS_COVER_FAILED = "cover_failed"
# Legacy token kept for importers / stale clients; teaching derivation no longer emits it.
MEDIA_STATUS_CONVERSION_FAILED = "conversion_failed"

_NATIVE_PREVIEW_SUFFIXES = frozenset({".pdf"})
# Keep in sync with services.showcase.covers.enqueue._OFFICE_PREVIEW_SUFFIXES.
_OFFICE_PREVIEW_SUFFIXES = frozenset({".doc", ".docx", ".pptx"})


def cover_event_indicates_failure(last_event_payload: Optional[str]) -> bool:
    """True when Redis last cover event is a terminal cover_fail."""
    if not last_event_payload:
        return False
    try:
        parsed = json.loads(last_event_payload)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and parsed.get("type") == "cover_fail"


def _has_nonempty_path(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _attachment_is_native_pdf(attachment: str) -> bool:
    return Path(attachment).suffix.lower() in _NATIVE_PREVIEW_SUFFIXES


def _office_needs_preview(spec_obj: dict) -> bool:
    """True when teaching Office attachment still lacks preview_path."""
    attachment = spec_obj.get("attachment_path")
    if not _has_nonempty_path(attachment):
        return False
    if Path(str(attachment)).suffix.lower() not in _OFFICE_PREVIEW_SUFFIXES:
        return False
    return not _has_nonempty_path(spec_obj.get("preview_path"))


def _pending_gallery_images(spec_obj: dict) -> int:
    gallery = spec_obj.get("gallery")
    if not isinstance(gallery, list):
        return 0
    return sum(1 for item in gallery if isinstance(item, dict) and item.get("kind") == "image" and not item.get("path"))


def _teaching_has_preview(attachment: str, spec_obj: dict) -> bool:
    """Native PDF uses the attachment as the reader source (no preview_path)."""
    preview_path = spec_obj.get("preview_path")
    return _has_nonempty_path(preview_path) or _attachment_is_native_pdf(attachment)


def resolve_showcase_media_status(
    *,
    case_type: str,
    thumbnail_path: Optional[str],
    spec: Any,
    cover_failed: bool = False,
    cover_job_status: Optional[str] = None,
) -> str:
    """Return a stable media_status token for admin moderation tables.

    Teaching designs move through upload → Office PDF convert → preview ready →
    cover generation → cover and preview ready. Failures distinguish preview vs
    cover. Diagram cases only report upload completeness and optional cover.

    When ``cover_job_status`` is set (cold manifesto), prefer it over Redis
    ephemeral failure: queued/running → phase-aware in-flight; failed →
    preview_failed or cover_failed; succeeded → derive from stored paths only.
    """
    spec_obj = spec if isinstance(spec, dict) else {}
    has_thumb = _has_nonempty_path(thumbnail_path)

    if case_type == "teaching_design":
        attachment = spec_obj.get("attachment_path")
        if not _has_nonempty_path(attachment):
            return MEDIA_STATUS_AWAITING_UPLOAD

        attachment_str = str(attachment)
        office_needs = _office_needs_preview(spec_obj)
        has_preview = _teaching_has_preview(attachment_str, spec_obj)
        in_flight = cover_job_status in {"queued", "running"}
        failed = cover_job_status == "failed" or cover_failed

        if in_flight:
            if office_needs:
                return MEDIA_STATUS_CONVERTING_PREVIEW
            return MEDIA_STATUS_GENERATING_COVER

        if failed:
            if office_needs or not has_preview:
                return MEDIA_STATUS_PREVIEW_FAILED
            if not has_thumb:
                return MEDIA_STATUS_COVER_FAILED
            # Both paths still present after a later failed refresh.
            return MEDIA_STATUS_COVER_READY

        if office_needs:
            return MEDIA_STATUS_CONVERTING_PREVIEW
        if not has_thumb:
            if has_preview:
                return MEDIA_STATUS_PREVIEW_READY
            return MEDIA_STATUS_CONVERTING_PREVIEW
        return MEDIA_STATUS_COVER_READY

    if _pending_gallery_images(spec_obj) > 0:
        return MEDIA_STATUS_AWAITING_UPLOAD
    if has_thumb:
        return MEDIA_STATUS_COVER_READY
    return MEDIA_STATUS_READY
