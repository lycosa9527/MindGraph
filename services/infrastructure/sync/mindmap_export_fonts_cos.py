"""
Mind-map PDF export fonts on Tencent COS (offline app load via API proxy).

Publisher uploads TrueType files under ``sync/fonts/mindmap-export/``.
Runtime serves ``/api/mindmap_export_fonts/{file}`` from local cache, pulling
from COS on miss — no public CDN. jsPDF requires TrueType (not OTF/CFF).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional

from services.infrastructure.sync.cos_sync_env import (
    mindmap_export_font_cos_key,
    mindmap_export_fonts_meta_cos_key,
    mindmap_export_fonts_rel_prefix,
)
from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    download_file,
    get_json,
    put_json,
    upload_file,
)

logger = logging.getLogger(__name__)

FONT_FILES: tuple[str, ...] = (
    "NotoSansSC-Regular.ttf",
    "NotoSansSC-Bold.ttf",
)

_CONTENT_TYPE = "font/ttf"


def mindmap_export_fonts_cache_dir() -> Path:
    """Local cache for COS-backed export fonts."""
    return Path("data") / "mindmap_export_fonts"


def mindmap_export_fonts_vendor_dir() -> Path:
    """Optional vendor copy under frontend/public/fonts (dev convenience)."""
    return Path("frontend") / "public" / "fonts"


def is_allowed_mindmap_export_font(filename: str) -> bool:
    """True when filename is a known export font basename."""
    return filename in FONT_FILES


def resolve_local_font_path(filename: str) -> Optional[Path]:
    """Prefer cache, then frontend/public/fonts vendor copy."""
    if not is_allowed_mindmap_export_font(filename):
        return None
    for root in (mindmap_export_fonts_cache_dir(), mindmap_export_fonts_vendor_dir()):
        candidate = root / filename
        if candidate.is_file() and candidate.stat().st_size > 1024:
            return candidate
    return None


def ensure_font_cached_from_cos(filename: str) -> Optional[Path]:
    """
    Return a local path for ``filename``, downloading from COS into the cache
    when missing. Returns None when unavailable.
    """
    if not is_allowed_mindmap_export_font(filename):
        return None
    local = resolve_local_font_path(filename)
    if local is not None:
        return local
    if not cos_credentials_configured():
        logger.warning("[MindMapFonts] COS not configured; missing %s", filename)
        return None
    cache_path = mindmap_export_fonts_cache_dir() / filename
    object_key = mindmap_export_font_cos_key(filename)
    ok = download_file(object_key, cache_path, log_prefix="[MindMapFonts]")
    if not ok or not cache_path.is_file():
        return None
    return cache_path


def publish_mindmap_export_fonts(source_dir: Path) -> Dict[str, object]:
    """
    Upload font files from ``source_dir`` to COS and write meta.json.

    Returns a result dict with per-file status (no secrets).
    """
    if not cos_credentials_configured():
        return {"ok": False, "error": "COS credentials not configured", "files": []}

    results: List[Dict[str, object]] = []
    uploaded = 0
    for name in FONT_FILES:
        local = source_dir / name
        entry: Dict[str, object] = {"file": name, "ok": False}
        if not local.is_file():
            entry["error"] = f"missing local file: {local}"
            results.append(entry)
            continue
        key = mindmap_export_font_cos_key(name)
        ok = upload_file(local, key, log_prefix="[MindMapFonts]")
        entry["ok"] = ok
        entry["key"] = key
        entry["size_bytes"] = local.stat().st_size
        if ok:
            uploaded += 1
            # Keep server cache warm for this host
            cache_path = mindmap_export_fonts_cache_dir() / name
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            if cache_path.resolve() != local.resolve():
                cache_path.write_bytes(local.read_bytes())
        else:
            entry["error"] = "upload_file failed"
        results.append(entry)

    meta = {
        "updated_at": datetime.now(UTC).isoformat(),
        "prefix": mindmap_export_fonts_rel_prefix(),
        "files": [
            {
                "file": row["file"],
                "ok": row["ok"],
                "size_bytes": row.get("size_bytes"),
                "key": row.get("key"),
            }
            for row in results
        ],
        "content_type": _CONTENT_TYPE,
    }
    meta_ok = put_json(mindmap_export_fonts_meta_cos_key(), meta)
    return {
        "ok": uploaded == len(FONT_FILES) and meta_ok,
        "uploaded": uploaded,
        "expected": len(FONT_FILES),
        "meta_ok": meta_ok,
        "files": results,
        "meta": meta,
    }


def read_mindmap_export_fonts_meta() -> Optional[dict]:
    """Read COS meta for export fonts, or None."""
    if not cos_credentials_configured():
        return None
    return get_json(mindmap_export_fonts_meta_cos_key())


def fonts_status_snapshot() -> dict:
    """Admin/debug status (no secrets)."""
    local_present = {name: resolve_local_font_path(name) is not None for name in FONT_FILES}
    meta = read_mindmap_export_fonts_meta()
    return {
        "cos_configured": cos_credentials_configured(),
        "rel_prefix": mindmap_export_fonts_rel_prefix(),
        "local_present": local_present,
        "meta": meta,
        "api_path": "/api/mindmap_export_fonts/{filename}",
    }


def format_publish_summary(result: Dict[str, object]) -> str:
    """Human-readable publish summary."""
    return json.dumps(result, ensure_ascii=False, indent=2)
