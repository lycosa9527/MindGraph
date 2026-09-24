#!/usr/bin/env python3
"""Generate silent classroom clips with Wan 3.0 from every mascot still.

Examples (from repo root, conda env python313):

  python -m scripts.sync_classroom_video.generate
  python -m scripts.sync_classroom_video.generate --ids 01,03
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import time
from pathlib import Path

from PIL import Image

from scripts.sync_classroom_video.catalog import (
    NEGATIVE,
    RATIO,
    RESOLUTION,
    ClassroomClip,
    clip_prompt,
    clip_stem,
    select_clips,
)
from scripts.sync_classroom_video.paths import DESKTOP_DIR, WORK_DIR
from scripts.sync_classroom_video.plates import reencode_clip, write_character_plate, write_lineup_plate
from scripts.sync_classroom_video.roles import RoleStill, discover_roles
from scripts.training_roles.env import dashscope_api_key
from scripts.training_roles.wan_client import (
    LONG_POLL_SECONDS,
    WAN3_VIDEO_PRIME,
    download_mp4,
    poll_video_url,
    submit_video,
)

TASKS_PATH = WORK_DIR / "tasks.json"


def _load_tasks() -> dict[str, str]:
    if not TASKS_PATH.is_file():
        return {}
    raw = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"invalid tasks file: {TASKS_PATH}")
    tasks: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, str) and key and value:
            tasks[key] = value
    return tasks


def _save_tasks(tasks: dict[str, str]) -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_PATH.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")


def _existing_mp4(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 10000


def _plate_data_url(plate: Path) -> str:
    image = Image.open(plate)
    payload = base64.b64encode(plate.read_bytes()).decode("ascii")
    print(f"ref {plate.name} size={image.size} bytes={plate.stat().st_size}", flush=True)
    return f"data:image/jpeg;base64,{payload}"


def _role_media(roles: list[RoleStill]) -> list[dict[str, str]]:
    media: list[dict[str, str]] = []
    for role in roles:
        dest = WORK_DIR / f"ref-{role['slug']}.jpg"
        write_character_plate(role["still"], dest)
        media.append({"type": "reference_image", "url": _plate_data_url(dest)})
    return media


def _lineup_media(roles: list[RoleStill]) -> list[dict[str, str]]:
    dest = WORK_DIR / "ref-lineup.jpg"
    write_lineup_plate([role["still"] for role in roles], dest)
    return [{"type": "reference_image", "url": _plate_data_url(dest)}]


def _submit_video(
    api_key: str,
    clip: ClassroomClip,
    prompt: str,
    media: list[dict[str, str]],
) -> str:
    last_error: Exception | None = None
    durations = [clip["seconds"]]
    if clip["seconds"] > 15:
        durations.append(15)
    for duration in durations:
        try:
            return submit_video(
                api_key,
                prompt,
                clip_stem(clip),
                model=WAN3_VIDEO_PRIME,
                negative=NEGATIVE,
                media=media,
                resolution=RESOLUTION,
                duration=duration,
                ratio=RATIO,
                audio=False,
                prompt_extend=False,
                watermark=False,
            )
        except RuntimeError as exc:
            last_error = exc
            print(f"{clip_stem(clip)} duration {duration}s failed: {exc}", flush=True)
    raise RuntimeError(str(last_error or f"{clip_stem(clip)} submit failed"))


def _submit_one(
    api_key: str,
    clip: ClassroomClip,
    roles: list[RoleStill],
    tasks: dict[str, str],
    media: list[dict[str, str]],
    force: bool,
) -> None:
    stem = clip_stem(clip)
    original = WORK_DIR / f"{stem}.mp4"
    if _existing_mp4(original) and not force:
        print(f"{stem} exists, skip submit", flush=True)
        return
    if stem in tasks and not force:
        print(f"{stem} already submitted {tasks[stem]}", flush=True)
        return
    prompt = clip_prompt(clip, roles)
    print(f"submit {stem} {WAN3_VIDEO_PRIME} {clip['seconds']}s {RESOLUTION}", flush=True)
    try:
        tasks[stem] = _submit_video(api_key, clip, prompt, media)
    except RuntimeError as exc:
        if len(media) <= 1:
            raise
        print(f"{stem} retry lineup plate: {exc}", flush=True)
        tasks[stem] = _submit_video(api_key, clip, prompt, _lineup_media(roles))
    _save_tasks(tasks)
    time.sleep(1)


def _publish(original: Path, clip: ClassroomClip) -> Path:
    encoded = reencode_clip(original, WORK_DIR / f"{clip_stem(clip)}-reencode.mp4", WORK_DIR)
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    dest = DESKTOP_DIR / f"{clip_stem(clip)}.mp4"
    shutil.copy2(encoded, dest)
    print(f"desktop {dest}", flush=True)
    return dest


def _download_one(api_key: str, clip: ClassroomClip, tasks: dict[str, str], force: bool) -> Path:
    stem = clip_stem(clip)
    original = WORK_DIR / f"{stem}.mp4"
    if _existing_mp4(original) and not force:
        print(f"{stem} exists, skip download", flush=True)
        return original
    task_id = tasks.get(stem)
    if not task_id:
        raise RuntimeError(f"{stem} has no task id")
    video_url = poll_video_url(
        api_key,
        task_id,
        stem,
        timeout_seconds=LONG_POLL_SECONDS,
    )
    download_mp4(video_url, original)
    return original


def main() -> None:
    """CLI entry: submit, poll, trim reference opens, copy to Pictures/mascots."""
    parser = argparse.ArgumentParser(description="Wan 3.0 classroom clips from mascot stills")
    parser.add_argument("--ids", help="Comma ids such as 01 or 01,04a")
    parser.add_argument("--force", action="store_true", help="Resubmit even if an MP4 exists")
    args = parser.parse_args()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    roles = discover_roles()
    print("roles " + ",".join(role["label"] for role in roles), flush=True)
    clips = select_clips(args.ids)
    tasks = _load_tasks()
    api_key = dashscope_api_key()
    media = _role_media(roles)
    failed: list[str] = []
    for clip in clips:
        stem = clip_stem(clip)
        try:
            _submit_one(api_key, clip, roles, tasks, media, args.force)
        except (RuntimeError, ValueError) as exc:
            print(f"{stem} submit-error: {exc}", flush=True)
            failed.append(stem)
    for clip in clips:
        stem = clip_stem(clip)
        if stem in failed:
            continue
        try:
            original = _download_one(api_key, clip, tasks, args.force)
            dest = _publish(original, clip)
            print(f"ready {dest}", flush=True)
        except (RuntimeError, TimeoutError, ValueError, OSError) as exc:
            print(f"{stem} download-error: {exc}", flush=True)
            failed.append(stem)
    if failed:
        raise RuntimeError(f"video failed: {','.join(failed)}")
    print(f"all-done {DESKTOP_DIR}", flush=True)


if __name__ == "__main__":
    main()
