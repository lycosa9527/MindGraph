"""Store-ready zip builder for the MindGraph browser extension (Chrome / Edge)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTENSION_DIR = _PROJECT_ROOT / "chrome-extension"
DEFAULT_OUTPUT = EXTENSION_DIR / "dist" / "mindgraph-extension.zip"

_SKIP_DIR_NAMES = frozenset({"node_modules", "test", "scripts", "dist"})
_SKIP_FILE_NAMES = frozenset(
    {
        "package.json",
        "package-lock.json",
        "vitest.config.js",
        "README.md",
        "DEPLOY_VERIFICATION.md",
        "HOST_PERMISSIONS.md",
    }
)
_SKIP_FILE_SUFFIXES = (".zip", ".example", ".env")
_SKIP_ICON_NAMES = frozenset({"icon300.png", "icon.svg"})


def _should_skip(relative: Path) -> bool:
    if any(part in _SKIP_DIR_NAMES for part in relative.parts):
        return True
    if relative.name in _SKIP_FILE_NAMES:
        return True
    if relative.name.startswith("."):
        return True
    if relative.parts[:1] == ("icons",) and relative.name in _SKIP_ICON_NAMES:
        return True
    if relative.parts[:1] == ("doc-extract",) and relative.name == "REFERENCES.md":
        return True
    return relative.name.endswith(_SKIP_FILE_SUFFIXES)


def build_store_zip_bytes() -> bytes:
    """Return zip bytes with manifest.json at archive root (Edge/Chrome store format)."""
    if not EXTENSION_DIR.is_dir():
        raise FileNotFoundError(str(EXTENSION_DIR))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(EXTENSION_DIR.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(EXTENSION_DIR)
            if _should_skip(relative):
                continue
            archive.write(path, arcname=relative.as_posix())
    data = buffer.getvalue()
    if not data:
        raise RuntimeError("Extension store zip is empty")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if "manifest.json" not in archive.namelist():
            raise RuntimeError("Extension store zip missing manifest.json at archive root")
    return data


def build_store_zip(output_path: Path | None = None) -> Path:
    """Write store zip to disk and return the output path."""
    out = output_path or DEFAULT_OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_store_zip_bytes())
    return out
