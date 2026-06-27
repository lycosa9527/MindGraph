"""
Safe upload filename and path-containment helpers.

Centralizes defenses against path traversal (CWE-22) for user-supplied
upload filenames. Use ``safe_upload_basename`` to strip any directory
components from a client-provided name, and ``ensure_within_directory`` to
assert that a computed destination stays inside its intended base directory
before any filesystem write.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from pathlib import Path


class UnsafeUploadPathError(ValueError):
    """Raised when an upload filename or destination path is unsafe."""


def safe_upload_basename(filename: str) -> str:
    """Return the bare filename, rejecting traversal and empty names.

    Strips any directory components (``../``, absolute paths, Windows
    separators) and rejects names that resolve to nothing usable.
    """
    raw = (filename or "").strip().replace("\\", "/")
    base = Path(raw).name.strip()
    if not base or base in (".", ".."):
        raise UnsafeUploadPathError("Invalid filename")
    return base


def ensure_within_directory(candidate: Path, base_dir: Path) -> Path:
    """Resolve ``candidate`` and assert it stays inside ``base_dir``.

    Returns the resolved path on success; raises ``UnsafeUploadPathError``
    when the candidate escapes the base directory (defense against TOCTOU
    and symlink/traversal escapes prior to a write).
    """
    base_resolved = base_dir.resolve()
    candidate_resolved = candidate.resolve()
    if not candidate_resolved.is_relative_to(base_resolved):
        raise UnsafeUploadPathError("Resolved path escapes base directory")
    return candidate_resolved
