"""
Showcase LibreOffice preview fonts on Tencent COS (Windows CJK pack).

Publisher uploads common Word fonts (宋体/楷体/仿宋/黑体/微软雅黑) under
``sync/fonts/office-preview/``. Runtime caches under ``data/office_preview_fonts/``
and pulls from COS on miss — same pattern as mind-map export fonts.

Do not commit font binaries to git (Microsoft font license). Publish from a
Windows Fonts directory you are allowed to use on private COS.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional
from xml.sax.saxutils import escape

from services.infrastructure.sync.cos_sync_env import (
    office_preview_font_cos_key,
    office_preview_fonts_meta_cos_key,
    office_preview_fonts_rel_prefix,
)
from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    download_file,
    get_json,
    put_json,
    upload_file,
)

logger = logging.getLogger(__name__)


class _FontWarmHolder:
    """Process-local warm flag (avoids module global mutation)."""

    warmed: bool = False
    lock: threading.Lock = threading.Lock()


_FONT_WARM = _FontWarmHolder()

# Basenames as found under C:\\Windows\\Fonts (and WSL /mnt/c/Windows/Fonts).
FONT_FILES: tuple[str, ...] = (
    "simsun.ttc",  # 宋体 / SimSun
    "simhei.ttf",  # 黑体 / SimHei
    "simkai.ttf",  # 楷体 / KaiTi
    "simfang.ttf",  # 仿宋 / FangSong
    "msyh.ttc",  # 微软雅黑
    "msyhbd.ttc",  # 微软雅黑 Bold
)

_WINDOWS_FONTS_CANDIDATES = (
    Path("/mnt/c/Windows/Fonts"),
    Path("C:/Windows/Fonts"),
    Path(r"C:\Windows\Fonts"),
)


def office_preview_fonts_cache_dir() -> Path:
    """Local cache for COS-backed office-preview fonts."""
    return Path("data") / "office_preview_fonts"


def default_windows_fonts_dir() -> Optional[Path]:
    """Return a readable Windows Fonts directory when present (WSL/native)."""
    for candidate in _WINDOWS_FONTS_CANDIDATES:
        if candidate.is_dir():
            return candidate
    return None


def is_allowed_office_preview_font(filename: str) -> bool:
    """True when filename is a known office-preview font basename."""
    return filename in FONT_FILES


def resolve_local_font_path(filename: str) -> Optional[Path]:
    """Prefer cache; optionally fall back to Windows Fonts on this host."""
    if not is_allowed_office_preview_font(filename):
        return None
    cache = office_preview_fonts_cache_dir() / filename
    if cache.is_file() and cache.stat().st_size > 1024:
        return cache
    windows_dir = default_windows_fonts_dir()
    if windows_dir is not None:
        windows_font = windows_dir / filename
        if windows_font.is_file() and windows_font.stat().st_size > 1024:
            return windows_font
    return None


def ensure_font_cached_from_cos(filename: str) -> Optional[Path]:
    """
    Return a cache path for ``filename``.

    Order: existing cache → seed from Windows Fonts (WSL/dev) → download COS.
    """
    if not is_allowed_office_preview_font(filename):
        return None
    cache_path = office_preview_fonts_cache_dir() / filename
    if cache_path.is_file() and cache_path.stat().st_size > 1024:
        return cache_path

    windows_dir = default_windows_fonts_dir()
    if windows_dir is not None:
        windows_font = windows_dir / filename
        if windows_font.is_file() and windows_font.stat().st_size > 1024:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(windows_font.read_bytes())
            return cache_path

    if not cos_credentials_configured():
        logger.warning("[OfficePreviewFonts] COS not configured; missing %s", filename)
        return None
    object_key = office_preview_font_cos_key(filename)
    tmp_path = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
    try:
        ok = download_file(object_key, tmp_path, log_prefix="[OfficePreviewFonts]")
        if not ok or not tmp_path.is_file() or tmp_path.stat().st_size <= 1024:
            return None
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp_path, cache_path)
    finally:
        if tmp_path.is_file():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    if not cache_path.is_file():
        return None
    return cache_path


def ensure_office_preview_fonts_ready() -> dict[str, Optional[Path]]:
    """Ensure all pack fonts are cached; return filename → path (or None)."""
    resolved: dict[str, Optional[Path]] = {}
    for name in FONT_FILES:
        resolved[name] = ensure_font_cached_from_cos(name)
    present = sum(1 for path in resolved.values() if path is not None)
    logger.info(
        "[OfficePreviewFonts] ready %s/%s under %s",
        present,
        len(FONT_FILES),
        office_preview_fonts_cache_dir(),
    )
    return resolved


def warm_office_preview_fonts_once() -> dict[str, Optional[Path]]:
    """Idempotent warm of the office-preview font pack (Celery worker boot)."""
    with _FONT_WARM.lock:
        if _FONT_WARM.warmed:
            return {name: resolve_local_font_path(name) for name in FONT_FILES}
        resolved = ensure_office_preview_fonts_ready()
        # Only suppress re-warm when the full pack landed; partial pulls retry
        # on the next warm call (job path still calls ensure_* every convert).
        _FONT_WARM.warmed = all(path is not None for path in resolved.values())
        return resolved


def write_office_preview_fontconfig(conf_path: Path, fonts_dir: Path) -> Path:
    """Write a fonts.conf that includes system fonts plus ``fonts_dir``."""
    conf_path.parent.mkdir(parents=True, exist_ok=True)
    fonts_uri = escape(str(fonts_dir.resolve()))
    # Prefer real Windows family names when present; Noto remains system fallback.
    body = f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
  <dir>{fonts_uri}</dir>
  <alias>
    <family>宋体</family>
    <prefer><family>SimSun</family><family>Noto Serif CJK SC</family></prefer>
  </alias>
  <alias>
    <family>新宋体</family>
    <prefer><family>NSimSun</family><family>SimSun</family><family>Noto Serif CJK SC</family></prefer>
  </alias>
  <alias>
    <family>黑体</family>
    <prefer><family>SimHei</family><family>Noto Sans CJK SC</family></prefer>
  </alias>
  <alias>
    <family>楷体</family>
    <prefer><family>KaiTi</family><family>Noto Serif CJK SC</family></prefer>
  </alias>
  <alias>
    <family>仿宋</family>
    <prefer><family>FangSong</family><family>Noto Serif CJK SC</family></prefer>
  </alias>
  <alias>
    <family>微软雅黑</family>
    <prefer><family>Microsoft YaHei</family><family>Noto Sans CJK SC</family></prefer>
  </alias>
</fontconfig>
"""
    conf_path.write_text(body, encoding="utf-8")
    return conf_path


def office_preview_fontconfig_env(work_dir: Path) -> dict[str, str]:
    """
    Build env vars so LibreOffice/fontconfig see the cached Windows CJK pack.

    Safe to merge into ``subprocess.run(..., env=...)``.
    """
    fonts_dir = office_preview_fonts_cache_dir()
    fonts_dir.mkdir(parents=True, exist_ok=True)
    conf_path = write_office_preview_fontconfig(
        work_dir / "fonts.conf",
        fonts_dir,
    )
    env = os.environ.copy()
    env["FONTCONFIG_FILE"] = str(conf_path.resolve())
    # Some LO builds also honor XDG font config paths.
    env["XDG_CONFIG_HOME"] = str((work_dir / "xdg-config").resolve())
    return env


def publish_office_preview_fonts(source_dir: Path) -> Dict[str, object]:
    """Upload font files from ``source_dir`` to COS and write meta.json."""
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
        key = office_preview_font_cos_key(name)
        ok = upload_file(local, key, log_prefix="[OfficePreviewFonts]")
        entry["ok"] = ok
        entry["key"] = key
        entry["size_bytes"] = local.stat().st_size
        if ok:
            uploaded += 1
            cache_path = office_preview_fonts_cache_dir() / name
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            if cache_path.resolve() != local.resolve():
                cache_path.write_bytes(local.read_bytes())
        else:
            entry["error"] = "upload_file failed"
        results.append(entry)

    meta = {
        "updated_at": datetime.now(UTC).isoformat(),
        "prefix": office_preview_fonts_rel_prefix(),
        "files": [
            {
                "file": row["file"],
                "ok": row["ok"],
                "size_bytes": row.get("size_bytes"),
                "key": row.get("key"),
            }
            for row in results
        ],
        "note": "Private Windows CJK pack for Showcase LO preview; do not commit binaries.",
    }
    meta_ok = put_json(office_preview_fonts_meta_cos_key(), meta)
    return {
        "ok": uploaded == len(FONT_FILES) and meta_ok,
        "uploaded": uploaded,
        "expected": len(FONT_FILES),
        "meta_ok": meta_ok,
        "files": results,
        "meta": meta,
    }


def read_office_preview_fonts_meta() -> Optional[dict]:
    """Read COS meta for office-preview fonts, or None."""
    if not cos_credentials_configured():
        return None
    return get_json(office_preview_fonts_meta_cos_key())


def fonts_status_snapshot() -> dict:
    """Admin/debug status (no secrets)."""
    local_present = {name: resolve_local_font_path(name) is not None for name in FONT_FILES}
    meta = read_office_preview_fonts_meta()
    windows_dir = default_windows_fonts_dir()
    return {
        "cos_configured": cos_credentials_configured(),
        "rel_prefix": office_preview_fonts_rel_prefix(),
        "cache_dir": str(office_preview_fonts_cache_dir()),
        "windows_fonts_dir": str(windows_dir) if windows_dir else None,
        "local_present": local_present,
        "meta": meta,
    }


def format_publish_summary(result: Dict[str, object]) -> str:
    """Human-readable publish summary."""
    return json.dumps(result, ensure_ascii=False, indent=2)
