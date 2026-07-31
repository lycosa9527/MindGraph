"""
Maite upload storage helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import base64
import uuid
from pathlib import Path

_UPLOAD_ROOT = Path("data/maite/uploads")


async def save_user_upload(
    user_id: int,
    data: bytes,
    *,
    suffix: str = ".bin",
) -> str:
    """Persist upload bytes under ``data/maite/uploads/{user_id}/``."""
    user_dir = _UPLOAD_ROOT / str(user_id)
    filename = f"{uuid.uuid4().hex}{suffix}"
    relative = Path("maite/uploads") / str(user_id) / filename
    absolute = _UPLOAD_ROOT / str(user_id) / filename

    def _write() -> None:
        user_dir.mkdir(parents=True, exist_ok=True)
        absolute.write_bytes(data)

    await asyncio.to_thread(_write)
    return relative.as_posix()


def resolve_safe_upload_path(relative_path: str) -> Path:
    """Resolve a stored relative path and reject path traversal."""
    candidate = (_UPLOAD_ROOT.parent / relative_path).resolve()
    root = _UPLOAD_ROOT.resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("Invalid upload path")
    if not candidate.is_file():
        raise FileNotFoundError(relative_path)
    return candidate


def to_data_url(relative_path: str, mime_type: str = "image/png") -> str:
    """Build a data URL from a stored relative upload path."""
    path = resolve_safe_upload_path(relative_path)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
