#!/usr/bin/env python3
"""Generate office-battle scene stills or 1080P I2V, then WebP + 1:1 WeChat GIF.

Examples (from repo root, conda env python313):

  python -m scripts.cat_office_battles.generate --ids 01
  python -m scripts.cat_office_battles.generate --video --ids 01
  python -m scripts.cat_office_battles.generate --export-stills --ids 01,02

Scenes keep the office set. Video is Wan I2V 1080P. WeChat emoji is 240x240.
Each zone is a separate job so one battle can be regenerated later.
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

from PIL import Image

from scripts.cat_office_battles.catalog import (
    BATTLE_ZONES,
    MOTION_SHELL,
    NEGATIVE,
    SHELL,
    VIDEO_DURATION,
    VIDEO_RESOLUTION,
    BattleZone,
    opening_still_prompt,
    zone_by_id,
)
from scripts.cat_office_battles.export import (
    clip_stem,
    export_scene_bundle,
    export_video_bundle,
    load_still_frames,
)
from scripts.cat_office_battles.paths import (
    ACTIONS_DIR,
    BLACK_STILL,
    WHITE_STILL,
    WORK_DIR,
    zone_dir,
)
from scripts.cat_office_battles.wan_image import download_image, poll_storyboard, submit_storyboard
from scripts.training_roles.env import dashscope_api_key
from scripts.training_roles.wan_client import download_mp4, poll_video_url, submit_i2v


def _select_zones(raw_ids: str | None) -> list[BattleZone]:
    if not raw_ids:
        return list(BATTLE_ZONES)
    return [zone_by_id(item.strip()) for item in raw_ids.split(",") if item.strip()]


def _export_stills(zone: BattleZone) -> None:
    folder = zone_dir(zone["id"], zone["slug"])
    frames = load_still_frames(folder)
    ACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    export_scene_bundle(frames, zone, ACTIONS_DIR)
    print(f"exported {zone['id']}-{zone['slug']} frames={len(frames)}", flush=True)


def _first_frame_data_url(still: Path) -> str:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(still).convert("RGB")
    dest = WORK_DIR / "first-frame.jpg"
    image.save(dest, format="JPEG", quality=95, optimize=True)
    payload = base64.b64encode(dest.read_bytes()).decode("ascii")
    print(f"first_frame={dest} size={image.size}", flush=True)
    return f"data:image/jpeg;base64,{payload}"


def _require_character_stills() -> None:
    if not BLACK_STILL.is_file():
        raise RuntimeError(f"black still missing: {BLACK_STILL}")
    if not WHITE_STILL.is_file():
        raise RuntimeError(f"white still missing: {WHITE_STILL}")


def _generate_first_frame(zone: BattleZone, force: bool) -> Path:
    dest = zone_dir(zone["id"], zone["slug"])
    first = dest / "01.png"
    if first.is_file() and first.stat().st_size > 10000 and not force:
        return first
    _require_character_stills()
    print(f"first-still {zone['id']}-{zone['slug']}", flush=True)
    prompt = (
        f"{SHELL}只画开场这一瞬间，两只猫各一只，不要把后面的动作叠进同一张图。"
        f"{opening_still_prompt(zone['prompt'])} 不要出现：{NEGATIVE}"
    )
    task_id = submit_storyboard(prompt, [BLACK_STILL, WHITE_STILL], 1)
    urls = poll_storyboard(task_id)
    if not urls:
        raise RuntimeError(f"{zone['id']} first still returned no images")
    dest.mkdir(parents=True, exist_ok=True)
    (WORK_DIR / zone["id"]).mkdir(parents=True, exist_ok=True)
    download_image(urls[0], first)
    download_image(urls[0], WORK_DIR / zone["id"] / "01.png")
    return first


def _generate_video(zone: BattleZone, force: bool) -> None:
    still = _generate_first_frame(zone, force)
    stem = clip_stem(zone)
    mp4 = ACTIONS_DIR / f"{stem}.mp4"
    if mp4.is_file() and mp4.stat().st_size > 10000 and not force:
        print(f"{zone['id']} video exists, skip (use --force to redo)", flush=True)
        return
    print(
        f"i2v {zone['id']}-{zone['slug']} {VIDEO_RESOLUTION} {VIDEO_DURATION}s",
        flush=True,
    )
    ACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    api_key = dashscope_api_key()
    prompt = f"{MOTION_SHELL}{zone['prompt']} 不要出现：{NEGATIVE}"
    frame_url = _first_frame_data_url(still)
    last_error: Exception | None = None
    video_url = ""
    for attempt in range(1, 3):
        try:
            task_id = submit_i2v(
                api_key,
                frame_url,
                prompt,
                NEGATIVE,
                zone["id"],
                resolution=VIDEO_RESOLUTION,
                duration=VIDEO_DURATION,
            )
            video_url = poll_video_url(api_key, task_id, zone["id"])
            break
        except (RuntimeError, TimeoutError) as exc:
            last_error = exc
            print(f"{zone['id']} i2v attempt {attempt} failed: {exc}", flush=True)
    if not video_url:
        raise RuntimeError(str(last_error or f"{zone['id']} i2v failed"))
    download_mp4(video_url, mp4)
    (WORK_DIR / zone["id"]).mkdir(parents=True, exist_ok=True)
    download_mp4(video_url, WORK_DIR / zone["id"] / f"{stem}.mp4")
    export_video_bundle(mp4, zone, ACTIONS_DIR)


def _generate_one(zone: BattleZone, force: bool) -> None:
    dest = zone_dir(zone["id"], zone["slug"])
    first = dest / "01.png"
    if first.is_file() and first.stat().st_size > 10000 and not force:
        print(f"{zone['id']} exists, skip (use --force to redo)", flush=True)
        return
    print(f"generate {zone['id']}-{zone['slug']} {zone['name']}", flush=True)
    prompt = f"{SHELL}{zone['prompt']} 不要出现：{NEGATIVE}"
    task_id = submit_storyboard(prompt, [BLACK_STILL, WHITE_STILL], zone["n"])
    urls = poll_storyboard(task_id)
    dest.mkdir(parents=True, exist_ok=True)
    for index, url in enumerate(urls, start=1):
        download_image(url, dest / f"{index:02d}.png")
        download_image(url, WORK_DIR / zone["id"] / f"{index:02d}.png")


def main() -> None:
    """CLI entry: generate selected battle-zone storyboards to the desktop."""
    parser = argparse.ArgumentParser(description="Wan office-battle scenes, one zone per job")
    parser.add_argument("--ids", help="Comma ids such as 01 or 01,04,11")
    parser.add_argument("--force", action="store_true", help="Regenerate even if stills exist")
    parser.add_argument(
        "--export-stills",
        action="store_true",
        help="Export existing scene stills to 16:9 WebP and 240x240 WeChat GIF",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="Make a first still if needed, then 1080P I2V MP4 + WebP + WeChat GIF",
    )
    args = parser.parse_args()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if args.export_stills:
        for zone in _select_zones(args.ids):
            _export_stills(zone)
        print("export-done", flush=True)
        return
    if args.video:
        failed: list[str] = []
        for zone in _select_zones(args.ids):
            try:
                _generate_video(zone, args.force)
            except (RuntimeError, TimeoutError) as exc:
                print(f"{zone['id']} skip-after-error: {exc}", flush=True)
                failed.append(zone["id"])
        if failed:
            raise RuntimeError(f"video failed: {','.join(failed)}")
        print("video-done", flush=True)
        return
    _require_character_stills()
    for zone in _select_zones(args.ids):
        _generate_one(zone, args.force)
    print("done", flush=True)


if __name__ == "__main__":
    main()
