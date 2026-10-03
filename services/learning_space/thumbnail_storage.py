"""Learning Space diagram thumbnails: COS bytes, short refs in Postgres.

Card lists receive a same-origin download URL. Opening a card loads the diagram spec.
"""

from __future__ import annotations

import logging
from typing import Any

from services.learning_space.image_storage import (
    is_image_ref,
    logical_key_from_ref,
    promote_data_url_sync,
    ref_for_key,
)

logger = logging.getLogger(__name__)

TEMPLATE_THUMBNAIL_REF = "template_thumbnail_ref"


def submission_thumbnail_src(submission_id: int) -> str:
    """Access-checked download hop for one submitted homework thumbnail."""
    return f"/api/learning-space/thumbnails/submissions/{int(submission_id)}?proxy=1"


def assignment_thumbnail_src(assignment_id: int) -> str:
    """Access-checked download hop for the assignment template thumbnail."""
    return f"/api/learning-space/thumbnails/assignments/{int(assignment_id)}?proxy=1"


def reference_thumbnail_src(assignment_id: int, index: int) -> str:
    """Access-checked download hop for one look-only reference diagram."""
    return f"/api/learning-space/thumbnails/assignments/{int(assignment_id)}/references/{int(index)}?proxy=1"


def display_thumbnail(stored: object, api_src: str) -> str | None:
    """Map a stored ref to the download hop. Leave http and legacy data URLs as-is."""
    if not isinstance(stored, str):
        return None
    item = stored.strip()
    if not item:
        return None
    if is_image_ref(item):
        return api_src
    if item.startswith("data:") or item.startswith("http://") or item.startswith("https://"):
        return item
    return None


def _stable_thumbnail(value: object) -> bool:
    """True when the stored thumbnail is already a COS ref or an http(s) URL."""
    if not isinstance(value, str):
        return False
    item = value.strip()
    if is_image_ref(item):
        return True
    return item.startswith("http://") or item.startswith("https://")


def _promote_reference_thumbnail(
    current: object,
    library_thumb: str | None,
    *,
    owner_id: int,
) -> str:
    """Upload a reference card image. Prefer an existing COS/http value over a new data URL."""
    if _stable_thumbnail(current):
        return promote_data_url_sync(current, owner_id=owner_id)
    if library_thumb:
        promoted = promote_data_url_sync(library_thumb, owner_id=owner_id)
        if promoted:
            return promoted
    return promote_data_url_sync(current, owner_id=owner_id)


def prepare_assignment_thumbnails_sync(
    permissions: dict[str, Any] | None,
    *,
    owner_id: int,
    template_thumbnail: str | None,
    reference_thumbnails: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Copy permissions and replace diagram thumbnail bytes with ``lsimg:`` refs."""
    raw = dict(permissions or {})
    library = reference_thumbnails or {}
    existing = raw.get(TEMPLATE_THUMBNAIL_REF)
    if not (isinstance(existing, str) and is_image_ref(existing)):
        promoted = promote_data_url_sync(template_thumbnail, owner_id=owner_id)
        if is_image_ref(promoted):
            raw[TEMPLATE_THUMBNAIL_REF] = promoted
    references = raw.get("reference_diagrams")
    if isinstance(references, list):
        cleaned: list[Any] = []
        for item in references:
            if not isinstance(item, dict):
                cleaned.append(item)
                continue
            copy = dict(item)
            diagram_id = str(copy.get("id") or "").strip()
            promoted = _promote_reference_thumbnail(
                copy.get("thumbnail"),
                library.get(diagram_id),
                owner_id=owner_id,
            )
            if promoted:
                copy["thumbnail"] = promoted
            cleaned.append(copy)
        raw["reference_diagrams"] = cleaned
    return raw


def template_thumbnail_ref_ready(permissions: object) -> bool:
    """True when the template card already points at a stored image."""
    if not isinstance(permissions, dict):
        return False
    existing = permissions.get(TEMPLATE_THUMBNAIL_REF)
    return isinstance(existing, str) and is_image_ref(existing)


def assignment_thumbnail_promote_pending(permissions: object, template_thumbnail: str | None) -> bool:
    """True when this read still has thumbnail bytes to upload."""
    raw = permissions if isinstance(permissions, dict) else {}
    if not template_thumbnail_ref_ready(raw):
        if isinstance(template_thumbnail, str) and template_thumbnail.strip().startswith("data:"):
            return True
    return bool(reference_ids_needing_upload(raw))


def _reference_thumbnail_gaps(permissions: object) -> tuple[set[str], set[str]]:
    """Return ``(library_ids, upload_ids)`` for reference cards that are not on COS yet."""
    raw = permissions if isinstance(permissions, dict) else {}
    references = raw.get("reference_diagrams")
    library_ids: set[str] = set()
    upload_ids: set[str] = set()
    if not isinstance(references, list):
        return library_ids, upload_ids
    for item in references:
        if not isinstance(item, dict):
            continue
        diagram_id = str(item.get("id") or "").strip()
        if not diagram_id or _stable_thumbnail(item.get("thumbnail")):
            continue
        upload_ids.add(diagram_id)
        thumb = item.get("thumbnail")
        if isinstance(thumb, str) and thumb.strip().startswith("data:"):
            continue
        library_ids.add(diagram_id)
    return library_ids, upload_ids


def reference_ids_needing_library(permissions: object) -> set[str]:
    """Reference diagrams whose card image was stripped and must be read from the library."""
    return _reference_thumbnail_gaps(permissions)[0]


def reference_ids_needing_upload(permissions: object) -> set[str]:
    """Reference diagrams that still need a COS put, including ones that already hold a data URL."""
    return _reference_thumbnail_gaps(permissions)[1]


def assignment_thumbnails_changed(before: dict[str, Any] | None, after: dict[str, Any]) -> bool:
    """True when promote replaced a data URL with a COS ref."""
    return dict(before or {}) != after


def promote_snapshot_thumbnail_sync(snapshot: dict[str, Any], *, owner_id: int) -> bool:
    """Replace a snapshot data-URL thumbnail with a COS ref. Returns True when stored."""
    current = snapshot.get("thumbnail")
    if isinstance(current, str) and is_image_ref(current):
        return False
    if not isinstance(current, str) or not current.strip().startswith("data:"):
        return False
    promoted = promote_data_url_sync(current, owner_id=owner_id)
    if not is_image_ref(promoted):
        logger.warning("[LearningSpace] Snapshot thumbnail was not stored owner=%s", owner_id)
        return False
    snapshot["thumbnail"] = promoted
    return True


def present_reference_diagrams(items: list[Any], *, assignment_id: int) -> list[dict[str, Any]]:
    """Public reference rows: thumbnail is a download URL, not an ``lsimg:`` key."""
    presented: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        copy = dict(item)
        shown = display_thumbnail(copy.get("thumbnail"), reference_thumbnail_src(assignment_id, index))
        copy["thumbnail"] = shown or ""
        presented.append(copy)
    return presented


def collect_thumbnail_keys(permissions: object, snapshots: list[object]) -> list[str]:
    """Logical keys for template, reference, and submission thumbnails."""
    keys: list[str] = []
    if isinstance(permissions, dict):
        template_key = logical_key_from_ref(str(permissions.get(TEMPLATE_THUMBNAIL_REF) or ""))
        if template_key:
            keys.append(template_key)
        references = permissions.get("reference_diagrams")
        if isinstance(references, list):
            for item in references:
                if not isinstance(item, dict):
                    continue
                ref_key = logical_key_from_ref(str(item.get("thumbnail") or ""))
                if ref_key:
                    keys.append(ref_key)
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        snap_key = logical_key_from_ref(str(snapshot.get("thumbnail") or ""))
        if snap_key:
            keys.append(snap_key)
    return keys


def stored_ref(value: object) -> str:
    """Normalize a stored thumbnail to ``lsimg:`` or return an empty string."""
    if not isinstance(value, str):
        return ""
    key = logical_key_from_ref(value)
    if key is None:
        return ""
    return ref_for_key(key)
