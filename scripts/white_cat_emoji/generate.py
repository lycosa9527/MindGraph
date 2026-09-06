#!/usr/bin/env python3
"""Generate white-cat emoji clips with Wan I2V, one id at a time.

Examples (from repo root, conda env mindgraph):

  python -m scripts.white_cat_emoji.generate --ids 01
  python -m scripts.white_cat_emoji.generate --ids 04,11
  python -m scripts.white_cat_emoji.generate --ids 08 --force

Green-screen stills live in scripts/cat_emoji/stills/white/. Desktop keeps
export copies. Each clip is a separate Wan job so one id can be regenerated
later without touching the rest.
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

from PIL import Image

from scripts.training_roles.catalog import RoleAction
from scripts.training_roles.env import dashscope_api_key
from scripts.training_roles.wan_client import download_mp4, poll_video_url, submit_i2v
from scripts.white_cat_emoji.catalog import (
    EMOJI_ACTIONS,
    NEGATIVE,
    SHELL,
    action_by_id,
    clip_name,
)
from scripts.white_cat_emoji.export import export_clip
from scripts.white_cat_emoji.paths import OUT_DIR, WECHAT_DIR, WORK_DIR, still_path


def _still_data_url(still: Path) -> str:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(still).convert("RGB")
    dest = WORK_DIR / "first-frame.jpg"
    image.save(dest, format="JPEG", quality=90, optimize=True)
    payload = base64.b64encode(dest.read_bytes()).decode("ascii")
    print(f"first_frame={dest} size={image.size}", flush=True)
    return f"data:image/jpeg;base64,{payload}"


def _select_actions(raw_ids: str | None) -> list[RoleAction]:
    if not raw_ids:
        return list(EMOJI_ACTIONS)
    return [action_by_id(item.strip()) for item in raw_ids.split(",") if item.strip()]


def _generate_one(api_key: str, frame_url: str, action: RoleAction, force: bool) -> None:
    stem = clip_name(action)
    mp4 = OUT_DIR / f"{stem}.mp4"
    webp = OUT_DIR / f"{stem}.webp"
    if webp.is_file() and webp.stat().st_size > 10000 and not force:
        print(f"{action['id']} exists, skip (use --force to redo)", flush=True)
        return
    print(f"generate {stem}", flush=True)
    task_id = submit_i2v(
        api_key,
        frame_url,
        SHELL + action["prompt"],
        NEGATIVE,
        action["id"],
    )
    video_url = poll_video_url(api_key, task_id, action["id"])
    download_mp4(video_url, mp4)
    export_clip(mp4, action)


def main() -> None:
    """CLI entry: generate selected white-cat emoji clips to the desktop."""
    parser = argparse.ArgumentParser(description="Wan I2V white-cat emoji, one clip per job")
    parser.add_argument("--ids", help="Comma ids such as 01 or 01,04,11")
    parser.add_argument("--still", default="2", help="1=3/4 still, 2=front idle (face lock)")
    parser.add_argument("--force", action="store_true", help="Regenerate even if WebP exists")
    args = parser.parse_args()
    still = still_path(args.still)
    if not still.is_file():
        raise RuntimeError(f"still missing: {still}")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WECHAT_DIR.mkdir(parents=True, exist_ok=True)
    frame_url = _still_data_url(still)
    api_key = dashscope_api_key()
    for action in _select_actions(args.ids):
        print(f"generate {clip_name(action)} from {still.name}", flush=True)
        _generate_one(api_key, frame_url, action, args.force)
    print("done", flush=True)


if __name__ == "__main__":
    main()
