"""Domain helpers for Showcase upload init/complete."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from models.domain.showcase import ShowcasePost
from services.showcase.infra.observability import showcase_wf_log
from services.showcase.storage import storage_backend
from services.showcase.uploads.roles import UploadRoleSpec


def _assign_post_spec(post: ShowcasePost, spec_obj: dict[str, Any]) -> None:
    """Assign JSONB spec so SQLAlchemy persists nested gallery/path mutations.

    A shallow ``dict(post.spec)`` shares nested gallery dicts with the loaded
    value; mutating ``entry['path']`` in place then reassigning can look like a
    no-op to JSONB change tracking (approve then sees pending gallery forever).
    """
    post.spec = spec_obj
    flag_modified(post, "spec")


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
        spec_obj = copy.deepcopy(post.spec)
    else:
        spec_obj = {"type": post.case_type}

    if role_spec.is_gallery and role_spec.gallery_slot is not None:
        gallery = spec_obj.get("gallery")
        if not isinstance(gallery, list):
            gallery = []
            spec_obj["gallery"] = gallery
        while len(gallery) <= role_spec.gallery_slot:
            gallery.append({"kind": "image", "pending": True})
        prev_entry = gallery[role_spec.gallery_slot]
        prev_path = prev_entry.get("path") if isinstance(prev_entry, dict) else None
        previous = prev_path if isinstance(prev_path, str) else None
        # Replace the slot with a new dict (do not mutate nested JSONB in place).
        new_entry: dict[str, Any] = {
            "kind": "image",
            "path": logical_key,
        }
        if filename:
            new_entry["filename"] = Path(filename).name
        elif isinstance(prev_entry, dict):
            prev_name = prev_entry.get("filename")
            if isinstance(prev_name, str) and prev_name.strip():
                new_entry["filename"] = prev_name
        gallery[role_spec.gallery_slot] = new_entry
        spec_obj["source"] = "gallery"
        _assign_post_spec(post, spec_obj)
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
        _assign_post_spec(post, spec_obj)
        _track_previous(previous)
        return to_delete

    _assign_post_spec(post, spec_obj)
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
