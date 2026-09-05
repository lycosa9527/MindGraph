#!/usr/bin/env python3
"""Generate more Course Builder role clips with Wan I2V.

Examples (from repo root, conda env python313):

  python -m scripts.training_roles.generate --ids 08 --still 2
  python -m scripts.training_roles.generate --ids 05,07 --still 1
  python -m scripts.training_roles.generate --ship-only --ids 11

Stills live in scripts/training_roles/stills/.
Shipped WebPs land in frontend/public/training/roles/.
Scratch MP4s stay in scripts/training_roles/.work/ (gitignored).
"""

from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

from PIL import Image

from scripts.training_roles.catalog import (
    ROLE_ACTIONS,
    RoleAction,
    action_by_id,
    assert_catalog_aligned,
    role_clip_id,
)
from scripts.training_roles.env import dashscope_api_key
from scripts.training_roles.export import export_mp4, export_wechat_gif
from scripts.training_roles.paths import WORK_DIR, still_path
from scripts.training_roles.wan_client import download_mp4, poll_video_url, post_i2v


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
        return [action for action in ROLE_ACTIONS if action.get("keep_existing") != "true"]
    return [action_by_id(item.strip()) for item in raw_ids.split(",") if item.strip()]


def _work_mp4(action: RoleAction) -> Path:
    return WORK_DIR / f"{role_clip_id(action)}.mp4"


def _run_one(
    api_key: str,
    frame_url: str,
    action: RoleAction,
    tasks: dict[str, str],
    wechat: bool,
) -> None:
    mp4 = _work_mp4(action)
    if action["id"] not in tasks:
        tasks[action["id"]] = post_i2v(api_key, frame_url, action)
        (WORK_DIR / "tasks.json").write_text(json.dumps(tasks, indent=2), encoding="utf-8")
        time.sleep(1)
    video_url = poll_video_url(api_key, tasks[action["id"]], action["id"])
    download_mp4(video_url, mp4)
    export_mp4(mp4, action)
    if wechat:
        export_wechat_gif(mp4, WORK_DIR / "wechat" / f"{role_clip_id(action)}.gif")


def main() -> None:
    """CLI entry: generate selected clips and ship public WebPs."""
    assert_catalog_aligned()
    parser = argparse.ArgumentParser(description="Wan I2V Course Builder roles")
    parser.add_argument("--ids", help="Comma ids such as 08 or 01-look-here")
    parser.add_argument("--still", default="2", help="1=3/4 still, 2=front idle")
    parser.add_argument("--ship-only", action="store_true", help="Re-export existing work MP4s")
    parser.add_argument("--wechat", action="store_true", help="Also write 240x240 GIFs")
    args = parser.parse_args()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    actions = _select_actions(args.ids)
    if args.ship_only:
        for action in actions:
            mp4 = _work_mp4(action)
            if not mp4.is_file():
                raise RuntimeError(f"missing work mp4: {mp4}")
            export_mp4(mp4, action)
            if args.wechat:
                export_wechat_gif(mp4, WORK_DIR / "wechat" / f"{role_clip_id(action)}.gif")
        print("ship-done", flush=True)
        return
    still = still_path(args.still)
    if not still.is_file():
        raise RuntimeError(f"still missing: {still}")
    state_path = WORK_DIR / "tasks.json"
    tasks: dict[str, str] = {}
    if state_path.exists():
        tasks = json.loads(state_path.read_text(encoding="utf-8"))
    frame_url = _still_data_url(still)
    api_key = dashscope_api_key()
    for action in actions:
        print(f"generate {role_clip_id(action)} from {still.name}", flush=True)
        _run_one(api_key, frame_url, action, tasks, args.wechat)
    print("all-done", flush=True)


if __name__ == "__main__":
    main()
