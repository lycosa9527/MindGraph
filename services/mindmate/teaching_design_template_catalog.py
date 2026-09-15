"""Named catalog of uploaded teaching-design Word templates."""

from __future__ import annotations

import json
import logging
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from services.mindmate.teaching_design_template_paths import (
    BUNDLED_TEMPLATE_PATH,
    MAX_CATALOG_TEMPLATES,
    MAX_TEMPLATE_NAME_LEN,
    OVERRIDE_FILENAME,
    TEMPLATE_ID_PREFIX,
    TEMPLATE_KEY_BUNDLED,
    TEMPLATE_KEY_SYSTEM,
    TEMPLATE_KEY_UPLOADED,
    catalog_files_dir,
    catalog_path,
    override_docx_path,
    override_meta_path,
)

logger = logging.getLogger(__name__)

_TEMPLATE_ID_RE = re.compile(rf"^(?:{TEMPLATE_KEY_BUNDLED}|{TEMPLATE_KEY_UPLOADED}|td_[a-f0-9]{{8}})$")
_JSON_READ_ERRORS = (OSError, json.JSONDecodeError, TypeError, ValueError)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically write UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object; empty dict if missing or invalid."""
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except _JSON_READ_ERRORS:
        logger.warning("[TeachingDesignTemplate] json unreadable path=%s", path)
        return {}
    if isinstance(loaded, dict):
        return loaded
    return {}


def _clean_name(value: object, fallback: str) -> str:
    """Trim and cap a display name, using ``fallback`` when empty."""
    text = str(value or "").strip()
    if not text:
        text = fallback
    return text[:MAX_TEMPLATE_NAME_LEN]


def _empty_state() -> dict[str, Any]:
    """Catalog document used when no JSON file exists yet."""
    return {
        "version": 1,
        "default_id": TEMPLATE_KEY_BUNDLED,
        "bundled_name": "",
        "templates": [],
    }


def _normalize_item(raw: object) -> dict[str, Any] | None:
    """Return a sanitized catalog row, or None when the id is invalid."""
    if not isinstance(raw, dict):
        return None
    template_id = str(raw.get("id") or "").strip()
    if not _TEMPLATE_ID_RE.fullmatch(template_id) or template_id == TEMPLATE_KEY_BUNDLED:
        return None
    stored = Path(str(raw.get("stored_filename") or "")).name
    if not stored.endswith(".docx"):
        stored = f"{template_id}.docx"
    original = Path(str(raw.get("original_filename") or stored)).name
    uploaded_by = raw.get("uploaded_by_name")
    if uploaded_by is not None and not isinstance(uploaded_by, str):
        uploaded_by = None
    try:
        size_bytes = int(raw.get("size_bytes") or 0)
    except (TypeError, ValueError):
        size_bytes = 0
    return {
        "id": template_id,
        "name": _clean_name(raw.get("name"), Path(original).stem or template_id),
        "original_filename": original or OVERRIDE_FILENAME,
        "stored_filename": stored,
        "uploaded_at": str(raw.get("uploaded_at") or "").strip() or None,
        "uploaded_by_user_id": raw.get("uploaded_by_user_id"),
        "uploaded_by_name": (uploaded_by or "").strip() or None,
        "size_bytes": max(0, size_bytes),
    }


def _stored_path(item: dict[str, Any]) -> Path:
    """On-disk path for an uploaded row, including the legacy override file."""
    stored = Path(str(item.get("stored_filename") or "")).name
    catalog_file = catalog_files_dir() / stored
    if catalog_file.is_file():
        return catalog_file
    legacy = override_docx_path()
    if stored == OVERRIDE_FILENAME and legacy.is_file():
        return legacy
    return catalog_file


def _migrate_legacy(state: dict[str, Any]) -> dict[str, Any]:
    """Turn the old single override file into catalog row ``uploaded``."""
    legacy = override_docx_path()
    if not legacy.is_file():
        return state
    templates = list(state.get("templates") or [])
    if any(item.get("id") == TEMPLATE_KEY_UPLOADED for item in templates):
        return state
    meta = _read_json(override_meta_path())
    original = Path(str(meta.get("original_filename") or OVERRIDE_FILENAME)).name
    target_dir = catalog_files_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{TEMPLATE_KEY_UPLOADED}.docx"
    target = target_dir / stored_name
    if not target.is_file():
        target.write_bytes(legacy.read_bytes())
    templates.append(
        {
            "id": TEMPLATE_KEY_UPLOADED,
            "name": _clean_name(meta.get("original_filename"), Path(original).stem),
            "original_filename": original,
            "stored_filename": stored_name,
            "uploaded_at": str(meta.get("uploaded_at") or "").strip() or None,
            "uploaded_by_user_id": meta.get("uploaded_by_user_id"),
            "uploaded_by_name": str(meta.get("uploaded_by_name") or "").strip() or None,
            "size_bytes": target.stat().st_size,
        }
    )
    state["templates"] = templates
    if state.get("default_id") == TEMPLATE_KEY_BUNDLED:
        state["default_id"] = TEMPLATE_KEY_UPLOADED
    logger.info("[TeachingDesignTemplate] migrated_legacy_override")
    return state


def load_catalog() -> dict[str, Any]:
    """Load catalog JSON, migrating the legacy single override if needed."""
    raw = _read_json(catalog_path())
    state = _empty_state()
    if raw:
        default_id = str(raw.get("default_id") or TEMPLATE_KEY_BUNDLED).strip()
        state["default_id"] = default_id or TEMPLATE_KEY_BUNDLED
        state["bundled_name"] = _clean_name(raw.get("bundled_name"), "")
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw_item in raw.get("templates") or []:
            item = _normalize_item(raw_item)
            if item is None or item["id"] in seen:
                continue
            seen.add(item["id"])
            items.append(item)
        state["templates"] = items
    state = _migrate_legacy(state)
    known = {TEMPLATE_KEY_BUNDLED, *(item["id"] for item in state["templates"])}
    if state["default_id"] not in known:
        state["default_id"] = TEMPLATE_KEY_BUNDLED
    return state


def save_catalog(state: dict[str, Any]) -> None:
    """Persist catalog JSON."""
    _write_json(catalog_path(), state)


def find_template(template_id: str) -> dict[str, Any] | None:
    """Return an uploaded catalog row, or None."""
    key = template_id.strip()
    for item in load_catalog()["templates"]:
        if item["id"] == key:
            return item
    return None


def template_exists_on_disk(template_id: str) -> bool:
    """True when the catalog id points at a readable .docx."""
    key = template_id.strip()
    if key == TEMPLATE_KEY_BUNDLED:
        return BUNDLED_TEMPLATE_PATH.is_file()
    item = find_template(key)
    if item is None:
        return False
    return _stored_path(item).is_file()


def template_file_path(template_id: str) -> Path:
    """Resolve a catalog id (or bundled) to a .docx path."""
    key = template_id.strip()
    if key in {"", TEMPLATE_KEY_SYSTEM, TEMPLATE_KEY_BUNDLED}:
        return BUNDLED_TEMPLATE_PATH
    item = find_template(key)
    if item is None:
        return BUNDLED_TEMPLATE_PATH
    path = _stored_path(item)
    if path.is_file():
        return path
    return BUNDLED_TEMPLATE_PATH


def default_template_id() -> str:
    """Id used when a school follows the system template."""
    return str(load_catalog().get("default_id") or TEMPLATE_KEY_BUNDLED)


def list_known_template_ids() -> set[str]:
    """Bundled plus every uploaded catalog id."""
    return {TEMPLATE_KEY_BUNDLED, *(item["id"] for item in load_catalog()["templates"])}


def _new_template_id(existing: set[str]) -> str:
    """Allocate a ``td_`` catalog id that is not already in use."""
    for _ in range(16):
        candidate = f"{TEMPLATE_ID_PREFIX}{secrets.token_hex(4)}"
        if candidate not in existing:
            return candidate
    raise ValueError("teaching_design_template_id_exhausted")


def _write_docx(target: Path, payload: bytes) -> None:
    """Write bytes to ``target`` via a sibling temp file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".docx.tmp")
    tmp.write_bytes(payload)
    tmp.replace(target)


def add_catalog_template(
    payload: bytes,
    *,
    original_filename: str,
    display_name: str | None,
    uploaded_by_user_id: int | None,
    uploaded_by_name: str | None,
) -> dict[str, Any]:
    """Append an uploaded template and return the new row."""
    state = load_catalog()
    templates: list[dict[str, Any]] = list(state["templates"])
    if len(templates) >= MAX_CATALOG_TEMPLATES:
        raise ValueError("teaching_design_template_limit")
    existing = {item["id"] for item in templates}
    template_id = _new_template_id(existing)
    original = Path(original_filename).name or OVERRIDE_FILENAME
    stored_name = f"{template_id}.docx"
    target = catalog_files_dir() / stored_name
    _write_docx(target, payload)
    fallback_name = Path(original).stem or f"template-{len(templates) + 1}"
    item = {
        "id": template_id,
        "name": _clean_name(display_name, fallback_name),
        "original_filename": original,
        "stored_filename": stored_name,
        "uploaded_at": datetime.now(tz=UTC).isoformat(),
        "uploaded_by_user_id": uploaded_by_user_id,
        "uploaded_by_name": (uploaded_by_name or "").strip() or None,
        "size_bytes": len(payload),
    }
    templates.append(item)
    state["templates"] = templates
    save_catalog(state)
    logger.info(
        "[TeachingDesignTemplate] catalog_added id=%s user=%s filename=%s",
        template_id,
        uploaded_by_user_id,
        original,
    )
    return item


def update_catalog_template(
    template_id: str,
    *,
    name: str | None = None,
    is_default: bool | None = None,
    payload: bytes | None = None,
    original_filename: str | None = None,
    uploaded_by_user_id: int | None = None,
    uploaded_by_name: str | None = None,
) -> dict[str, Any]:
    """Rename, pin as system default, and/or replace the Word file."""
    key = template_id.strip()
    if not _TEMPLATE_ID_RE.fullmatch(key):
        raise ValueError("teaching_design_template_invalid_key")
    state = load_catalog()
    if key == TEMPLATE_KEY_BUNDLED:
        if name is not None:
            state["bundled_name"] = _clean_name(name, "")
        if is_default is True:
            state["default_id"] = TEMPLATE_KEY_BUNDLED
        if payload is not None:
            raise ValueError("teaching_design_template_bundled_readonly")
        save_catalog(state)
        return {"id": TEMPLATE_KEY_BUNDLED}
    updated = None
    templates: list[dict[str, Any]] = []
    for item in state["templates"]:
        if item["id"] != key:
            templates.append(item)
            continue
        next_item = dict(item)
        if name is not None:
            cleaned = str(name).strip()
            if not cleaned:
                raise ValueError("teaching_design_template_name_required")
            next_item["name"] = _clean_name(cleaned, item["name"])
        if payload is not None:
            target = _stored_path(next_item)
            _write_docx(target, payload)
            next_item["size_bytes"] = len(payload)
            next_item["uploaded_at"] = datetime.now(tz=UTC).isoformat()
            if original_filename:
                next_item["original_filename"] = Path(original_filename).name
            if uploaded_by_name is not None:
                next_item["uploaded_by_name"] = uploaded_by_name.strip() or None
            if uploaded_by_user_id is not None:
                next_item["uploaded_by_user_id"] = uploaded_by_user_id
        templates.append(next_item)
        updated = next_item
    if updated is None:
        raise ValueError("teaching_design_template_not_found")
    state["templates"] = templates
    if is_default is True:
        state["default_id"] = key
    save_catalog(state)
    logger.info("[TeachingDesignTemplate] catalog_updated id=%s", key)
    return updated


def delete_catalog_template(template_id: str) -> None:
    """Remove an uploaded template file and catalog row."""
    key = template_id.strip()
    if key == TEMPLATE_KEY_BUNDLED:
        raise ValueError("teaching_design_template_bundled_readonly")
    state = load_catalog()
    item = next((row for row in state["templates"] if row["id"] == key), None)
    if item is None:
        raise ValueError("teaching_design_template_not_found")
    path = _stored_path(item)
    if path.is_file():
        path.unlink()
    state["templates"] = [row for row in state["templates"] if row["id"] != key]
    if state.get("default_id") == key:
        state["default_id"] = TEMPLATE_KEY_BUNDLED
    save_catalog(state)
    logger.info("[TeachingDesignTemplate] catalog_deleted id=%s", key)


def set_default_bundled(*, user_id: int | None) -> None:
    """Point 跟随系统 at the built-in BNU form without deleting uploads."""
    state = load_catalog()
    state["default_id"] = TEMPLATE_KEY_BUNDLED
    save_catalog(state)
    logger.info("[TeachingDesignTemplate] default_bundled user=%s", user_id)
