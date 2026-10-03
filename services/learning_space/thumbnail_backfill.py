"""Scan Learning Space cards that have no COS thumbnail and store one.

Existing data-URL images are uploaded. Cards with no image are rendered from
the diagram spec, then the PNG is written to COS as an ``lsimg:`` ref.
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import HTTPException
from PIL import Image
from playwright.async_api import Error as PlaywrightError

from models.domain.learning_space import LearningAssignment, LearningSubmission
from routers.api.vueflow_screenshot import capture_diagram_screenshot
from services.diagram.semantic_spec_validation import validate_semantic_spec
from services.learning_space.image_storage import (
    MAX_IMAGE_BYTES,
    build_logical_key,
    delete_stored_images_sync,
    is_image_ref,
    logical_key_from_ref,
    promote_data_url_sync,
    put_image_bytes_sync,
)
from services.learning_space.thumbnail_storage import (
    TEMPLATE_THUMBNAIL_REF,
    reference_ids_needing_upload,
    template_thumbnail_ref_ready,
    thumbnail_is_durable,
)
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS

logger = logging.getLogger(__name__)

_SPEC_KEYS = ("type", "topic", "data", "nodes", "children", "context", "attributes", "whole", "event")
_FILL_ERRORS = (HTTPException, PlaywrightError, RuntimeError, OSError, TimeoutError, ValueError, TypeError)
THUMBNAIL_BATCH_LIMIT = 8
_MAX_RENDERS = 1

RenderPng = Callable[[dict[str, Any], str], Awaitable[bytes]]
LoadDiagram = Callable[[int, str], Awaitable[dict[str, Any] | None]]


class _ThumbnailDb(Protocol):
    """Commit hook so a batch can persist one card without a full session type."""

    async def commit(self) -> None:
        """Persist the card that was just updated."""

    async def rollback(self) -> None:
        """Undo the card write when commit fails."""


@dataclass
class _CardJob:
    key: str
    kind: str
    owner_id: int
    diagram_id: str
    inline_thumb: str
    assignment: LearningAssignment | None
    submission: LearningSubmission | None


@dataclass
class _FillResult:
    status: str
    rendered: bool


def _looks_like_spec(spec: dict[str, Any]) -> bool:
    return any(spec.get(key) for key in _SPEC_KEYS)


def renderable_spec(value: object) -> dict[str, Any] | None:
    """Return a diagram spec dict, unwrapping a saved ``{spec: ...}`` envelope."""
    if not isinstance(value, dict):
        return None
    nested = value.get("spec")
    if isinstance(nested, dict) and _looks_like_spec(nested):
        return nested
    if _looks_like_spec(value):
        return value
    return None


def _diagram_type(raw: object, spec: dict[str, Any] | None) -> str:
    if isinstance(raw, str) and raw.strip():
        value = raw.strip()
        return "mind_map" if value == "mindmap" else value
    if spec is not None:
        typed = spec.get("type")
        if isinstance(typed, str) and typed.strip():
            value = typed.strip()
            return "mind_map" if value == "mindmap" else value
    return "mind_map"


def _data_url(value: object) -> str:
    if isinstance(value, str) and value.strip().startswith("data:"):
        return value.strip()
    return ""


def _http_url(value: object) -> str:
    if not isinstance(value, str):
        return ""
    item = value.strip()
    if item.startswith("http://") or item.startswith("https://"):
        return item
    return ""


def _jobs_for_assignment(assignment: LearningAssignment, skip: set[str]) -> list[_CardJob]:
    if assignment.id is None:
        return []
    perms = assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else {}
    owner_id = int(assignment.created_by)
    jobs: list[_CardJob] = []
    template_key = f"template:{int(assignment.id)}"
    if template_key not in skip and not template_thumbnail_ref_ready(perms):
        jobs.append(
            _CardJob(
                key=template_key,
                kind="template",
                owner_id=owner_id,
                diagram_id=str(assignment.template_diagram_id or "").strip(),
                inline_thumb="",
                assignment=assignment,
                submission=None,
            )
        )
    needed = reference_ids_needing_upload(perms)
    references = perms.get("reference_diagrams")
    if not isinstance(references, list):
        return jobs
    seen: set[str] = set()
    for item in references:
        if not isinstance(item, dict):
            continue
        diagram_id = str(item.get("id") or "").strip()
        if not diagram_id or diagram_id not in needed or diagram_id in seen:
            continue
        seen.add(diagram_id)
        key = f"reference:{int(assignment.id)}:{diagram_id}"
        if key in skip:
            continue
        thumb = item.get("thumbnail")
        jobs.append(
            _CardJob(
                key=key,
                kind="reference",
                owner_id=owner_id,
                diagram_id=diagram_id,
                inline_thumb=str(thumb).strip() if isinstance(thumb, str) else "",
                assignment=assignment,
                submission=None,
            )
        )
    return jobs


def _jobs_for_submission(submission: LearningSubmission, skip: set[str]) -> list[_CardJob]:
    if submission.id is None:
        return []
    snap = submission.snapshot_spec if isinstance(submission.snapshot_spec, dict) else None
    diagram_id = str(submission.diagram_id or "").strip()
    if snap is None and not diagram_id:
        return []
    current = snap.get("thumbnail") if snap else None
    if thumbnail_is_durable(current):
        return []
    key = f"submission:{int(submission.id)}"
    if key in skip:
        return []
    return [
        _CardJob(
            key=key,
            kind="submission",
            owner_id=int(submission.student_user_id),
            diagram_id=diagram_id,
            inline_thumb=str(current).strip() if isinstance(current, str) else "",
            assignment=None,
            submission=submission,
        )
    ]


def collect_card_jobs(
    assignments: Sequence[LearningAssignment],
    submissions: Sequence[LearningSubmission],
    skip: set[str],
) -> list[_CardJob]:
    """Cards whose stored thumbnail is not already a COS ref or an http(s) URL."""
    jobs: list[_CardJob] = []
    for assignment in assignments:
        jobs.extend(_jobs_for_assignment(assignment, skip))
    for submission in submissions:
        jobs.extend(_jobs_for_submission(submission, skip))
    return jobs


async def _default_load_diagram(owner_id: int, diagram_id: str) -> dict[str, Any] | None:
    if owner_id <= 0 or not diagram_id:
        return None
    try:
        diagram = await get_diagram_cache().get_diagram(owner_id, diagram_id)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[LearningSpace] Thumbnail source unavailable owner=%s diagram=%s: %s",
            owner_id,
            diagram_id,
            exc,
        )
        return None
    if not isinstance(diagram, dict):
        return None
    return diagram


async def _default_render_png(spec: dict[str, Any], diagram_type: str) -> bytes:
    return await capture_diagram_screenshot(spec, diagram_type, width=960, height=640)


def _fit_png_sync(png: bytes) -> bytes:
    """Shrink a render until it fits the Learning Space image cap."""
    if len(png) <= MAX_IMAGE_BYTES:
        return png
    image = Image.open(io.BytesIO(png)).convert("RGB")
    width, height = image.size
    for _ in range(8):
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        data = buffer.getvalue()
        if len(data) <= MAX_IMAGE_BYTES:
            return data
        if width <= 64 or height <= 64:
            break
        width = max(64, int(round(width * 0.75)))
        height = max(64, int(round(height * 0.75)))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    raise ValueError("thumbnail PNG exceeds the storage cap")


def _store_png_sync(png: bytes, *, owner_id: int) -> str:
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        return ""
    payload = _fit_png_sync(png)
    key = build_logical_key(owner_id=owner_id, filename="thumb.png")
    return put_image_bytes_sync(key, payload, "image/png")


def _write_template(assignment: LearningAssignment, ref: str) -> None:
    raw = dict(assignment.ai_permissions) if isinstance(assignment.ai_permissions, dict) else {}
    raw[TEMPLATE_THUMBNAIL_REF] = ref
    assignment.ai_permissions = raw


def _submission_inline_spec(job: _CardJob) -> tuple[dict[str, Any] | None, str]:
    submission = job.submission
    if submission is None or not isinstance(submission.snapshot_spec, dict):
        return None, ""
    snap = submission.snapshot_spec
    return renderable_spec(snap.get("spec")), str(snap.get("diagram_type") or "")


def _write_reference(assignment: LearningAssignment, diagram_id: str, ref: str) -> None:
    raw = dict(assignment.ai_permissions) if isinstance(assignment.ai_permissions, dict) else {}
    references = raw.get("reference_diagrams")
    cleaned: list[Any] = []
    if isinstance(references, list):
        for item in references:
            if isinstance(item, dict) and str(item.get("id") or "").strip() == diagram_id:
                copy = dict(item)
                copy["thumbnail"] = ref
                cleaned.append(copy)
            else:
                cleaned.append(item)
    raw["reference_diagrams"] = cleaned
    assignment.ai_permissions = raw


def _write_submission(submission: LearningSubmission, ref: str) -> None:
    snap = dict(submission.snapshot_spec) if isinstance(submission.snapshot_spec, dict) else {}
    snap["thumbnail"] = ref
    submission.snapshot_spec = snap


def _persist_ref(job: _CardJob, ref: str) -> None:
    if job.kind == "template" and job.assignment is not None and is_image_ref(ref):
        _write_template(job.assignment, ref)
        return
    if job.kind == "reference" and job.assignment is not None and ref:
        _write_reference(job.assignment, job.diagram_id, ref)
        return
    if job.kind == "submission" and job.submission is not None and is_image_ref(ref):
        _write_submission(job.submission, ref)


async def _library_fields(
    job: _CardJob,
    load_diagram: LoadDiagram,
) -> tuple[str, dict[str, Any] | None, str]:
    inline_spec, inline_type = _submission_inline_spec(job)
    if not job.diagram_id:
        return "", inline_spec, inline_type
    diagram = await load_diagram(job.owner_id, job.diagram_id)
    if not diagram:
        return "", inline_spec, inline_type
    thumb = diagram.get("thumbnail")
    library_thumb = str(thumb).strip() if isinstance(thumb, str) else ""
    spec = inline_spec or renderable_spec(diagram.get("spec"))
    diagram_type = inline_type or _diagram_type(diagram.get("diagram_type"), spec)
    return library_thumb, spec, diagram_type


async def _rendered_ref(
    spec: dict[str, Any],
    diagram_type: str,
    *,
    owner_id: int,
    render_png: RenderPng,
) -> tuple[str, bool]:
    """Return ``(ref, browser_used)``. Invalid specs do not launch a browser."""
    ok, _issues, normalized = validate_semantic_spec(diagram_type, spec)
    if not ok:
        return "", False
    png = await render_png(spec, normalized or diagram_type)
    stored = await asyncio.to_thread(_store_png_sync, png, owner_id=owner_id)
    return stored, True


async def _fill_job(job: _CardJob, *, load_diagram: LoadDiagram, render_png: RenderPng) -> _FillResult:
    """Upload an existing image, or render the spec. ``ready`` means an http image already shows."""
    inline_data = _data_url(job.inline_thumb)
    if inline_data:
        ref = await asyncio.to_thread(promote_data_url_sync, inline_data, owner_id=job.owner_id)
        if is_image_ref(ref):
            _persist_ref(job, ref)
            return _FillResult("stored", False)
    library_thumb, spec, diagram_type = await _library_fields(job, load_diagram)
    library_data = _data_url(library_thumb)
    if library_data and not inline_data:
        ref = await asyncio.to_thread(promote_data_url_sync, library_data, owner_id=job.owner_id)
        if is_image_ref(ref):
            _persist_ref(job, ref)
            return _FillResult("stored", False)
    http_thumb = _http_url(job.inline_thumb) or _http_url(library_thumb)
    if http_thumb and job.kind == "reference":
        _persist_ref(job, http_thumb)
        return _FillResult("stored", False)
    if http_thumb:
        return _FillResult("ready", False)
    if spec is None:
        return _FillResult("failed", False)
    try:
        ref, used_browser = await _rendered_ref(
            spec,
            _diagram_type(diagram_type, spec),
            owner_id=job.owner_id,
            render_png=render_png,
        )
    except _FILL_ERRORS as exc:
        logger.warning("[LearningSpace] Thumbnail render failed key=%s: %s", job.key, exc)
        return _FillResult("failed", True)
    if not is_image_ref(ref):
        return _FillResult("failed", used_browser)
    _persist_ref(job, ref)
    return _FillResult("generated", used_browser)


async def _commit_job(db: _ThumbnailDb, job: _CardJob) -> bool:
    try:
        await db.commit()
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.warning("[LearningSpace] Thumbnail backfill commit failed key=%s: %s", job.key, exc)
        return False
    return True


def _written_ref(job: _CardJob) -> str:
    """Read the ref just written, before a rollback expires the row."""
    if job.kind == "template" and job.assignment is not None:
        raw = job.assignment.ai_permissions
        if isinstance(raw, dict):
            return str(raw.get(TEMPLATE_THUMBNAIL_REF) or "")
        return ""
    if job.kind == "reference" and job.assignment is not None:
        raw = job.assignment.ai_permissions
        references = raw.get("reference_diagrams") if isinstance(raw, dict) else None
        if isinstance(references, list):
            for item in references:
                if isinstance(item, dict) and str(item.get("id") or "").strip() == job.diagram_id:
                    return str(item.get("thumbnail") or "")
        return ""
    if job.kind == "submission" and job.submission is not None:
        snap = job.submission.snapshot_spec
        if isinstance(snap, dict):
            return str(snap.get("thumbnail") or "")
    return ""


async def _drop_uncommitted_image(ref: str) -> None:
    key = logical_key_from_ref(ref)
    if not key:
        return
    await asyncio.to_thread(delete_stored_images_sync, [key])


def _record(result: _FillResult, job: _CardJob, counts: dict[str, Any]) -> None:
    if result.status == "stored":
        counts["stored"] += 1
        return
    if result.status == "generated":
        counts["generated"] += 1
        return
    if result.status == "ready":
        counts["ready_keys"].append(job.key)
        return
    counts["failed_keys"].append(job.key)


async def fill_missing_card_thumbnails(
    db: _ThumbnailDb,
    assignments: Sequence[LearningAssignment],
    submissions: Sequence[LearningSubmission],
    *,
    skip: set[str] | None = None,
    render_png: RenderPng | None = None,
    load_diagram: LoadDiagram | None = None,
) -> dict[str, Any]:
    """Store thumbnails for a bounded batch of cards. Call again until ``remaining`` is 0."""
    ignored = skip or set()
    jobs = collect_card_jobs(assignments, submissions, ignored)
    render = render_png or _default_render_png
    loader = load_diagram or _default_load_diagram
    counts: dict[str, Any] = {"stored": 0, "generated": 0, "failed_keys": [], "ready_keys": []}
    touched = 0
    renders = 0
    for job in jobs:
        if touched >= THUMBNAIL_BATCH_LIMIT or renders >= _MAX_RENDERS:
            break
        try:
            result = await _fill_job(job, load_diagram=loader, render_png=render)
        except _FILL_ERRORS as exc:
            logger.warning("[LearningSpace] Thumbnail backfill failed key=%s: %s", job.key, exc)
            result = _FillResult("failed", False)
        if result.status in {"stored", "generated"}:
            ref = _written_ref(job)
            saved = await _commit_job(db, job)
            if not saved:
                await _drop_uncommitted_image(ref)
                result = _FillResult("failed", result.rendered)
                _record(result, job, counts)
                touched += 1
                break
        _record(result, job, counts)
        touched += 1
        if result.rendered:
            renders += 1
    remaining = max(0, len(jobs) - touched)
    logger.debug(
        "[LearningSpace] Thumbnail batch stored=%s generated=%s failed=%s ready=%s remaining=%s",
        counts["stored"],
        counts["generated"],
        len(counts["failed_keys"]),
        len(counts["ready_keys"]),
        remaining,
    )
    return {
        "stored": counts["stored"],
        "generated": counts["generated"],
        "remaining": remaining,
        "failed_keys": counts["failed_keys"],
        "ready_keys": counts["ready_keys"],
    }
