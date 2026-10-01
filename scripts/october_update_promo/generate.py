#!/usr/bin/env python3
"""October update promo: closed-mouth Wan 3 clips, foley, one instrumental bed.

Examples (from repo root):

  python -m scripts.october_update_promo.generate
  python -m scripts.october_update_promo.generate --ids 01,07
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image

from scripts.october_update_promo.board import pin_screenshot
from scripts.october_update_promo.catalog import (
    NEGATIVE,
    RATIO,
    RESOLUTION,
    PromoClip,
    clip_prompt,
    clip_stem,
    overlay_sheet,
    select_clips,
)
from scripts.october_update_promo.music import download_audio, synthesize_bgm
from scripts.october_update_promo.narration import mix_narration
from scripts.october_update_promo.paths import DESKTOP_DIR, WORK_DIR, screenshot_for
from scripts.sync_classroom_video.plates import ffmpeg_bin, write_character_plate, write_lineup_plate
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
FINAL_NAME = "October-update-promo.mp4"


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


def _run_ffmpeg(args: list[str], label: str) -> None:
    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "ffmpeg failed"
        raise RuntimeError(f"{label}: {tail}")


def _submit_video(api_key: str, clip: PromoClip, prompt: str, media: list[dict[str, str]]) -> str:
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
                audio=True,
                prompt_extend=False,
                watermark=False,
            )
        except RuntimeError as exc:
            last_error = exc
            print(f"{clip_stem(clip)} duration {duration}s failed: {exc}", flush=True)
    raise RuntimeError(str(last_error or f"{clip_stem(clip)} submit failed"))


def _submit_one(
    api_key: str,
    clip: PromoClip,
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
    print(f"submit {stem} {WAN3_VIDEO_PRIME} {clip['seconds']}s {RESOLUTION} audio", flush=True)
    try:
        tasks[stem] = _submit_video(api_key, clip, prompt, media)
    except RuntimeError as exc:
        if len(media) <= 1:
            raise
        print(f"{stem} retry lineup plate: {exc}", flush=True)
        tasks[stem] = _submit_video(api_key, clip, prompt, _lineup_media(roles))
    _save_tasks(tasks)
    time.sleep(1)


def _download_one(api_key: str, clip: PromoClip, tasks: dict[str, str], force: bool) -> Path:
    stem = clip_stem(clip)
    original = WORK_DIR / f"{stem}.mp4"
    if _existing_mp4(original) and not force:
        print(f"{stem} exists, skip download", flush=True)
        return original
    task_id = tasks.get(stem)
    if not task_id:
        raise RuntimeError(f"{stem} has no task id")
    video_url = poll_video_url(api_key, task_id, stem, timeout_seconds=LONG_POLL_SECONDS)
    download_mp4(video_url, original)
    return original


def _decorate(api_key: str, clip: PromoClip, original: Path, skip_voice: bool) -> Path:
    stem = clip_stem(clip)
    pinned = WORK_DIR / f"{stem}-board.mp4"
    pin_screenshot(original, screenshot_for(clip["id"]), clip["crops"], pinned)
    if skip_voice:
        return pinned
    voiced = WORK_DIR / f"{stem}-vo.mp4"
    mix_narration(api_key, pinned, clip["speech"], voiced)
    return voiced


def _publish_clip(original: Path, clip: PromoClip) -> Path:
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    dest = DESKTOP_DIR / f"{clip_stem(clip)}.mp4"
    shutil.copy2(original, dest)
    print(f"desktop {dest}", flush=True)
    return dest


def _ffprobe() -> str:
    found = shutil.which("ffprobe")
    if found:
        return found
    sibling = Path(ffmpeg_bin()).with_name("ffprobe")
    if sibling.is_file():
        return str(sibling)
    raise RuntimeError("ffprobe not on PATH")


def _has_audio(path: Path) -> bool:
    completed = subprocess.run(
        [
            _ffprobe(),
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return "audio" in completed.stdout


def _concat(clips: list[Path], dest: Path) -> None:
    listing = WORK_DIR / "concat.txt"
    lines = [f"file '{path.resolve().as_posix()}'" for path in clips]
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ffmpeg(
        [ffmpeg_bin(), "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(dest)],
        "concat",
    )


def _mix_bed(video: Path, bed: Path, dest: Path) -> None:
    if _has_audio(video):
        filter_complex = "[1:a]volume=0.38[bed];[0:a][bed]amix=inputs=2:duration=first:dropout_transition=2[a]"
        args = [
            ffmpeg_bin(),
            "-y",
            "-i",
            str(video),
            "-stream_loop",
            "-1",
            "-i",
            str(bed),
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-shortest",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(dest),
        ]
    else:
        args = [
            ffmpeg_bin(),
            "-y",
            "-i",
            str(video),
            "-stream_loop",
            "-1",
            "-i",
            str(bed),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-shortest",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(dest),
        ]
    _run_ffmpeg(args, "mix bed")


def _finish(clips: list[Path], bed: Path | None) -> Path:
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    (DESKTOP_DIR / "overlays.txt").write_text(overlay_sheet(), encoding="utf-8")
    joined = WORK_DIR / "joined.mp4"
    _concat(clips, joined)
    dest = DESKTOP_DIR / FINAL_NAME
    if bed is None:
        shutil.copy2(joined, dest)
    else:
        _mix_bed(joined, bed, dest)
    print(f"final {dest}", flush=True)
    return dest


def main() -> None:
    """CLI entry: submit, poll, copy cuts, lay the instrumental bed under them."""
    parser = argparse.ArgumentParser(description="October update promo from mascot stills")
    parser.add_argument("--ids", help="Comma ids such as 01 or 01,07")
    parser.add_argument("--force", action="store_true", help="Resubmit even if an MP4 exists")
    parser.add_argument("--skip-bgm", action="store_true", help="Keep Wan foley and skip the bed")
    parser.add_argument("--skip-voice", action="store_true", help="Pin the screenshot and skip narration")
    args = parser.parse_args()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
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
    bed: Path | None = None
    if not args.skip_bgm and not args.ids:
        try:
            bgm_path = WORK_DIR / "bgm.mp3"
            if not (bgm_path.is_file() and bgm_path.stat().st_size > 10000) or args.force:
                download_audio(synthesize_bgm(api_key), bgm_path)
            shutil.copy2(bgm_path, DESKTOP_DIR / "bgm.mp3")
            bed = bgm_path
        except (RuntimeError, OSError) as exc:
            print(f"bgm-error: {exc}", flush=True)
            bed = None
    published: list[Path] = []
    for clip in clips:
        stem = clip_stem(clip)
        if stem in failed:
            continue
        try:
            original = _download_one(api_key, clip, tasks, args.force)
            ready = _decorate(api_key, clip, original, args.skip_voice)
            published.append(_publish_clip(ready, clip))
        except (RuntimeError, TimeoutError, ValueError, OSError) as exc:
            print(f"{stem} download-error: {exc}", flush=True)
            failed.append(stem)
    if published and not args.ids and len(published) == len(clips):
        _finish(published, bed)
    if failed:
        raise RuntimeError(f"promo failed: {','.join(failed)}")
    print(f"all-done {DESKTOP_DIR}", flush=True)


if __name__ == "__main__":
    main()
