"""Key white-cat MP4s to desktop WebP and WeChat GIF. Does not ship public roles."""

from __future__ import annotations

from pathlib import Path

from scripts.training_roles.catalog import RoleAction
from scripts.training_roles.export import (
    extract_keyed_frames,
    export_wechat_gif,
    save_webp,
    scale_width,
)
from scripts.white_cat_emoji.catalog import clip_name
from scripts.white_cat_emoji.paths import OUT_DIR, WECHAT_DIR, WORK_DIR


def export_clip(mp4: Path, action: RoleAction) -> None:
    """Write a transparent WebP and a WeChat GIF next to the source MP4."""
    frames_dir = WORK_DIR / "frames" / mp4.stem
    frames = scale_width(extract_keyed_frames(mp4, frames_dir), 480)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WECHAT_DIR.mkdir(parents=True, exist_ok=True)
    save_webp(frames, OUT_DIR / f"{clip_name(action)}.webp", lossless=True)
    export_wechat_gif(mp4, WECHAT_DIR / f"{clip_name(action)}.gif", frames_dir)
