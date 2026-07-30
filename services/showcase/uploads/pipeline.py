"""Domain helpers for Showcase upload init/complete."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from models.domain.showcase import ShowcasePost
from services.showcase.infra.observability import showcase_wf_log
from services.showcase.storage import storage_backend
from services.showcase.uploads.roles import UploadRoleSpec


def apply_key_to_post(
    post: ShowcasePost,
    *,
    role_spec: UploadRoleSpec,
    logical_key: str,
    filename: Optional[str],
) -> list[str]:
    """Persist logical key onto post fields; returns previous keys to delete."""
    to_delete: list[str] = []

    def _track_previous(previous: Optional[str]) -> None:
        if previous and previous != logical_key:
            to_delete.append(previous)

    if role_spec.is_thumbnail:
        previous = post.thumbnail_path
        post.thumbnail_path = logical_key
        _track_previous(previous)
        return to_delete

    spec_obj: dict[str, Any]
    if isinstance(post.spec, dict):
        spec_obj = dict(post.spec)
    else:
        spec_obj = {"type": post.case_type}

    if role_spec.is_gallery and role_spec.gallery_slot is not None:
        gallery = spec_obj.get("gallery")
        if not isinstance(gallery, list):
            gallery = []
            spec_obj["gallery"] = gallery
        while len(gallery) <= role_spec.gallery_slot:
            gallery.append({"kind": "image", "pending": True})
        entry = gallery[role_spec.gallery_slot]
        if not isinstance(entry, dict):
            entry = {"kind": "image"}
            gallery[role_spec.gallery_slot] = entry
        prev_path = entry.get("path")
        previous = prev_path if isinstance(prev_path, str) else None
        entry["path"] = logical_key
        entry["kind"] = "image"
        if filename:
            entry["filename"] = Path(filename).name
        entry.pop("pending", None)
        spec_obj["source"] = "gallery"
        post.spec = spec_obj
        _track_previous(previous)
        return to_delete

    if role_spec.spec_field:
        prev_field = spec_obj.get(role_spec.spec_field)
        previous = prev_field if isinstance(prev_field, str) else None
        spec_obj[role_spec.spec_field] = logical_key
        if role_spec.role == "attachment":
            if filename:
                spec_obj["attachment_filename"] = Path(filename).name
            # Attachment change invalidates LO preview; cover job regenerates PPTX preview.
            old_preview = spec_obj.pop("preview_path", None)
            if isinstance(old_preview, str) and old_preview:
                to_delete.append(old_preview)
            # Drop stale cover so cover-stream waits for the new Celery job (no early cover_ready).
            if post.thumbnail_path:
                to_delete.append(post.thumbnail_path)
                post.thumbnail_path = None
        post.spec = spec_obj
        _track_previous(previous)
        return to_delete

    post.spec = spec_obj
    return to_delete


def log_upload_init(
    *,
    post_id: str,
    user_id: int,
    role: str,
    logical_key: str,
    put_url_present: bool,
) -> None:
    """Workflow log for successful upload init."""
    showcase_wf_log(
        "upload_init",
        f"put_url={'yes' if put_url_present else 'no'}",
        post_id=post_id,
        user_id=user_id,
        role=role,
        key=logical_key,
        backend=storage_backend(),
    )


def log_upload_init_fail(
    *,
    post_id: str,
    user_id: int,
    role: str,
    reason: str,
) -> None:
    """Workflow log for failed upload init."""
    showcase_wf_log(
        "upload_init_fail",
        reason,
        post_id=post_id,
        user_id=user_id,
        role=role,
        backend=storage_backend(),
    )


def log_upload_complete(
    *,
    post_id: str,
    user_id: int,
    role: str,
    logical_key: str,
) -> None:
    """Workflow log for successful upload complete."""
    showcase_wf_log(
        "upload_complete",
        "ok",
        post_id=post_id,
        user_id=user_id,
        role=role,
        key=logical_key,
        backend=storage_backend(),
    )


def log_upload_complete_fail(
    *,
    post_id: str,
    user_id: int,
    role: str,
    reason: str,
    key: str = "",
) -> None:
    """Workflow log for failed upload complete."""
    showcase_wf_log(
        "upload_complete_fail",
        reason,
        post_id=post_id,
        user_id=user_id,
        role=role,
        key=key,
        backend=storage_backend(),
    )
