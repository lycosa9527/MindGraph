"""
Import Dify raw dump zip archives into data/dify-dumps/{label}/.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from services.dify.export.raw_dump_config import (
    DUMP_MAX_EXTRACT_BYTES,
    DUMP_MAX_ZIP_MEMBERS,
    is_valid_dump_label,
    resolve_raw_dump_dir,
)
from services.dify.export.raw_dump_library import merge_snapshot_into_library
from services.dify.export.raw_dump_manifest import load_manifest_file, snapshot_from_dir, validate_manifest

logger = logging.getLogger(__name__)

INCOMING_DIRNAME = "incoming"
DONE_DIRNAME = ".done"


@dataclass
class ImportResult:
    """Outcome of importing one or more dump zips."""

    imported: List[Path] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_member_name(name: str) -> str:
    return name.replace("\\", "/").lstrip("/")


def _member_dest(extract_base: Path, member_name: str) -> Path:
    normalized = _normalize_member_name(member_name)
    if not normalized or normalized.startswith("../") or "/../" in normalized:
        raise ValueError(f"unsafe zip path: {member_name}")
    dest = (extract_base / normalized).resolve()
    base_resolved = extract_base.resolve()
    if base_resolved not in dest.parents and dest != base_resolved:
        raise ValueError(f"zip slip rejected: {member_name}")
    return dest


def _validate_zip_archive(archive: zipfile.ZipFile) -> None:
    total_uncompressed = 0
    members = archive.infolist()
    if len(members) > DUMP_MAX_ZIP_MEMBERS:
        raise ValueError(f"zip has too many members (max {DUMP_MAX_ZIP_MEMBERS})")
    for info in members:
        total_uncompressed += int(info.file_size)
        if total_uncompressed > DUMP_MAX_EXTRACT_BYTES:
            raise ValueError(f"zip uncompressed size exceeds limit ({DUMP_MAX_EXTRACT_BYTES} bytes)")


def _safe_extract_zip(archive: zipfile.ZipFile, extract_base: Path) -> None:
    """Extract zip members with zip-slip and zip-bomb guards."""
    _validate_zip_archive(archive)
    extract_base.mkdir(parents=True, exist_ok=True)
    for info in archive.infolist():
        if info.is_dir() or not info.filename:
            continue
        dest = _member_dest(extract_base, info.filename)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info, "r") as src, dest.open("wb") as dst:
            shutil.copyfileobj(src, dst)


def peek_manifest_from_zip(zip_path: Path) -> dict:
    """Read manifest.json from inside a zip without full extraction."""
    with zipfile.ZipFile(zip_path, "r") as archive:
        _validate_zip_archive(archive)
        names = archive.namelist()
        manifest_name = None
        for name in names:
            if name.endswith("/manifest.json") or name == "manifest.json":
                manifest_name = name
                break
        if manifest_name is None:
            raise ValueError(f"manifest.json not found in {zip_path.name}")
        with archive.open(manifest_name) as handle:
            payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("manifest.json must be a JSON object")
    return payload


def _load_sidecar_manifest(zip_path: Path) -> Optional[dict]:
    sidecar = zip_path.with_suffix(".manifest.json")
    if not sidecar.is_file():
        sidecar = Path(f"{zip_path}.manifest.json")
    if not sidecar.is_file():
        return None
    return load_manifest_file(sidecar)


def _verify_archive_sha256(zip_path: Path, manifest: dict) -> None:
    expected = str(manifest.get("archive_sha256") or "").strip().lower()
    if not expected:
        return
    actual = _sha256_file(zip_path)
    if actual.lower() != expected:
        raise ValueError(f"sha256 mismatch for {zip_path.name}: expected {expected}, got {actual}")


def _snapshot_timestamp(manifest: dict, zip_path: Path) -> str:
    staging = str(manifest.get("staging_dir") or "")
    if staging:
        return Path(staging).name
    stem = zip_path.stem
    if stem.startswith("dify-dump_"):
        parts = stem.split("_", 2)
        if len(parts) >= 3:
            return parts[2]
    return zip_path.stem


def _snapshot_dir_usable(path: Path) -> bool:
    if not path.is_dir() or not (path / "manifest.json").is_file():
        return False
    try:
        return snapshot_from_dir(path).is_usable()
    except ValueError:
        return False


def import_zip_file(
    zip_path: Path,
    base_dir: Optional[Path] = None,
    *,
    move_to_done: bool = True,
) -> Path:
    """
    Extract one dump zip into base_dir/{label}/{timestamp}/.

    Returns path to extracted snapshot directory.
    """
    root = base_dir or resolve_raw_dump_dir()
    manifest = peek_manifest_from_zip(zip_path)
    sidecar = _load_sidecar_manifest(zip_path)
    if sidecar is not None:
        manifest = {**sidecar, **manifest}
    validate_manifest(manifest)
    _verify_archive_sha256(zip_path, manifest)
    label = str(manifest["server_label"]).strip().lower()
    timestamp = _snapshot_timestamp(manifest, zip_path)
    label_dir = root / label
    target_root = label_dir / timestamp
    if target_root.exists():
        if _snapshot_dir_usable(target_root):
            logger.info("[RawDump] snapshot already present: %s", target_root)
            merge_snapshot_into_library(root, target_root)
            if move_to_done:
                _move_to_done(zip_path, root)
            return target_root
        shutil.rmtree(target_root, ignore_errors=True)

    label_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            _safe_extract_zip(archive, label_dir)
    except (OSError, ValueError, zipfile.BadZipFile):
        shutil.rmtree(target_root, ignore_errors=True)
        raise

    extracted = target_root
    if not (extracted / "manifest.json").is_file():
        nested = list(label_dir.glob("*/manifest.json"))
        if nested:
            extracted = nested[0].parent
    if not _snapshot_dir_usable(extracted):
        shutil.rmtree(target_root, ignore_errors=True)
        raise ValueError(f"extracted tree unusable from {zip_path.name}")
    merge_snapshot_into_library(root, extracted)
    if move_to_done:
        _move_to_done(zip_path, root)
    logger.info("[RawDump] imported %s -> %s", zip_path.name, extracted)
    return extracted


def _move_to_done(zip_path: Path, root: Path) -> None:
    done_dir = root / INCOMING_DIRNAME / DONE_DIRNAME
    done_dir.mkdir(parents=True, exist_ok=True)
    dest = done_dir / zip_path.name
    if dest.exists():
        dest.unlink()
    shutil.move(str(zip_path), str(dest))
    sidecar = zip_path.with_suffix(".manifest.json")
    if sidecar.is_file():
        shutil.move(str(sidecar), str(done_dir / sidecar.name))
    alt_sidecar = Path(f"{zip_path}.manifest.json")
    if alt_sidecar.is_file():
        shutil.move(str(alt_sidecar), str(done_dir / alt_sidecar.name))


def import_pending_zips(base_dir: Optional[Path] = None) -> ImportResult:
    """Import all *.zip files in incoming/ using manifest server_label routing."""
    root = base_dir or resolve_raw_dump_dir()
    incoming = root / INCOMING_DIRNAME
    result = ImportResult()
    if not incoming.is_dir():
        return result
    for zip_path in sorted(incoming.glob("*.zip")):
        try:
            manifest = peek_manifest_from_zip(zip_path)
            label = str(manifest.get("server_label") or "").strip().lower()
            if not is_valid_dump_label(label):
                result.errors.append(f"invalid label in {zip_path.name}")
                continue
            extracted = import_zip_file(zip_path, root, move_to_done=True)
            result.imported.append(extracted)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            result.errors.append(f"{zip_path.name}: {exc}")
            logger.warning("[RawDump] import failed %s: %s", zip_path.name, exc)
    return result
