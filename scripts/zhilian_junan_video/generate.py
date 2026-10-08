#!/usr/bin/env python3
"""Generate 1080P 智联均安 B-roll with Wan 3.0 text-to-video.

Examples (from repo root, conda env mindgraph):

  python -m scripts.zhilian_junan_video.generate --agent
  python -m scripts.zhilian_junan_video.generate --travel
  python -m scripts.zhilian_junan_video.generate --intro
  python -m scripts.zhilian_junan_video.generate --speech
  python -m scripts.zhilian_junan_video.generate --activities
  python -m scripts.zhilian_junan_video.generate --ids d01,d05,p01
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import time
from pathlib import Path

from scripts.training_roles.env import dashscope_api_key
from scripts.training_roles.wan_client import (
    LONG_POLL_SECONDS,
    WAN3_VIDEO_PRIME,
    download_mp4,
    poll_video_url,
    submit_video,
    synthesize_tts,
    with_reference_audio,
)
from scripts.zhilian_junan_video.activities import (
    ACTIVITY_NEGATIVE,
    QISI_VOICE,
    activity_filename,
    activity_line,
)
from scripts.zhilian_junan_video.bookends import BOOKEND_NEGATIVE, bookend_filename, bookend_line
from scripts.zhilian_junan_video.catalog import (
    AGENT_NEGATIVE,
    INTRO_NEGATIVE,
    NEGATIVE,
    RATIO,
    RESOLUTION,
    PromoScene,
    clip_prompt,
    clip_stem,
    environment_source,
    select_scenes,
    uses_activity,
    uses_agent,
    uses_bookend,
    uses_intro,
    uses_speech,
    uses_travel,
)
from scripts.zhilian_junan_video.paths import (
    ACTIVITY_DIR,
    AGENT_DIR,
    INTRO_DIR,
    MATERIALS_DIR,
    SPEECH_DIR,
    TASKS_PATH,
    TRAVEL_DIR,
    WORK_DIR,
    activity_photo,
)
from scripts.zhilian_junan_video.plates import (
    agent_plate_paths,
    extract_scene_still,
    write_activity_plate,
)
from scripts.zhilian_junan_video.speech import SPEECH_NEGATIVE


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


def _work_mp4(scene: PromoScene) -> Path:
    return WORK_DIR / f"{clip_stem(scene)}.mp4"


def _existing_mp4(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 10000


def _plate_data_url(plate: Path) -> str:
    payload = base64.b64encode(plate.read_bytes()).decode("ascii")
    print(f"ref {plate.name} bytes={plate.stat().st_size}", flush=True)
    return f"data:image/jpeg;base64,{payload}"


def _agent_media() -> list[dict[str, str]]:
    wink, smile = agent_plate_paths()
    return [
        {"type": "reference_image", "url": _plate_data_url(wink)},
        {"type": "reference_image", "url": _plate_data_url(smile)},
    ]


def _travel_media(dragon: list[dict[str, str]], scene: PromoScene) -> list[dict[str, str]]:
    still = extract_scene_still(environment_source(scene), f"{clip_stem(scene)}.jpg")
    return [*dragon, {"type": "reference_image", "url": _plate_data_url(still)}]


def _activity_media(
    dragon: list[dict[str, str]],
    scene: PromoScene,
    speech_url: str,
) -> list[dict[str, str]]:
    photo = activity_photo(environment_source(scene))
    plate = write_activity_plate(photo, WORK_DIR / "activity-ref" / f"{clip_stem(scene)}.jpg")
    images = [*dragon, {"type": "reference_image", "url": _plate_data_url(plate)}]
    return with_reference_audio(images, [speech_url])


def _bookend_media(
    dragon: list[dict[str, str]],
    scene: PromoScene,
    speech_url: str,
) -> list[dict[str, str]]:
    photo = activity_photo(environment_source(scene))
    plate = write_activity_plate(photo, WORK_DIR / "activity-ref" / f"{clip_stem(scene)}.jpg")
    images = [*dragon, {"type": "reference_image", "url": _plate_data_url(plate)}]
    return with_reference_audio(images, [speech_url])


def _scene_negative(scene: PromoScene) -> str:
    if uses_bookend(scene):
        return BOOKEND_NEGATIVE
    if uses_activity(scene):
        return ACTIVITY_NEGATIVE
    if uses_intro(scene):
        return INTRO_NEGATIVE
    if uses_speech(scene):
        return SPEECH_NEGATIVE
    if uses_agent(scene):
        return AGENT_NEGATIVE
    return NEGATIVE


def _publish_folder(scene: PromoScene) -> Path:
    if uses_activity(scene) or uses_bookend(scene):
        return ACTIVITY_DIR
    if uses_speech(scene):
        return SPEECH_DIR
    if uses_intro(scene):
        return INTRO_DIR
    if uses_travel(scene):
        return TRAVEL_DIR
    return AGENT_DIR


def _publish_name(mp4: Path, scene: PromoScene) -> str:
    if uses_bookend(scene):
        return bookend_filename(scene["id"])
    if uses_activity(scene):
        return activity_filename(scene["id"])
    return mp4.name


def _publish_desktop(mp4: Path, scene: PromoScene) -> Path:
    folder = _publish_folder(scene)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / _publish_name(mp4, scene)
    shutil.copy2(mp4, dest)
    print(f"desktop {dest}", flush=True)
    if uses_activity(scene) or uses_bookend(scene):
        materials = MATERIALS_DIR / "v1"
        materials.mkdir(parents=True, exist_ok=True)
        copied = materials / dest.name
        shutil.copy2(mp4, copied)
        print(f"materials {copied}", flush=True)
    return dest


def _clip_has_voice(scene: PromoScene) -> bool:
    """Activity clips speak one line. Wan must not add a music bed."""
    if uses_activity(scene) or uses_bookend(scene):
        return True
    return uses_intro(scene)


def _submit_one(
    api_key: str,
    scene: PromoScene,
    tasks: dict[str, str],
    force: bool,
    media: list[dict[str, str]] | None,
) -> None:
    stem = clip_stem(scene)
    mp4 = _work_mp4(scene)
    if _existing_mp4(mp4) and not force:
        print(f"{stem} exists, skip submit", flush=True)
        return
    if stem in tasks and not force:
        print(f"{stem} already submitted {tasks[stem]}", flush=True)
        return
    print(f"submit {stem} {WAN3_VIDEO_PRIME} {scene['seconds']}s {RESOLUTION}", flush=True)
    scene_media = None
    if uses_activity(scene) and media is not None:
        speech_url = synthesize_tts(api_key, activity_line(scene["id"]), QISI_VOICE)
        scene_media = _activity_media(media, scene, speech_url)
    elif uses_bookend(scene) and media is not None:
        speech_url = synthesize_tts(api_key, bookend_line(scene["id"]), QISI_VOICE)
        scene_media = _bookend_media(media, scene, speech_url)
    elif (uses_travel(scene) or uses_intro(scene)) and media is not None:
        scene_media = _travel_media(media, scene)
    elif uses_agent(scene):
        scene_media = media
    tasks[stem] = submit_video(
        api_key,
        clip_prompt(scene),
        stem,
        model=WAN3_VIDEO_PRIME,
        negative=_scene_negative(scene),
        media=scene_media,
        resolution=RESOLUTION,
        duration=scene["seconds"],
        ratio=RATIO,
        audio=_clip_has_voice(scene),
        prompt_extend=False,
        watermark=False,
    )
    _save_tasks(tasks)
    time.sleep(1)


def _download_one(api_key: str, scene: PromoScene, tasks: dict[str, str], force: bool) -> Path:
    stem = clip_stem(scene)
    mp4 = _work_mp4(scene)
    if _existing_mp4(mp4) and not force:
        print(f"{stem} exists, skip download", flush=True)
        return mp4
    task_id = tasks.get(stem)
    if not task_id:
        raise RuntimeError(f"{stem} has no task id")
    video_url = poll_video_url(
        api_key,
        task_id,
        stem,
        timeout_seconds=LONG_POLL_SECONDS,
    )
    download_mp4(video_url, mp4)
    return mp4


def main() -> None:
    """CLI entry: submit then poll Wan 3.0 clips into .work/."""
    parser = argparse.ArgumentParser(description="Wan 3.0 智联均安 cinematic B-roll")
    parser.add_argument("--ids", help="Comma ids such as 00 or a1,d01")
    parser.add_argument("--agent", action="store_true", help="Generate the yellow-dragon plates")
    parser.add_argument("--travel", action="store_true", help="Send the dragon through earlier scenes")
    parser.add_argument("--intro", action="store_true", help="20s spoken 均安起思楼 self-intro")
    parser.add_argument("--speech", action="store_true", help="8s cinematic plates for 纯演讲稿_v2")
    parser.add_argument("--activities", action="store_true", help="5s dragon visits real activity photos")
    parser.add_argument("--force", action="store_true", help="Resubmit even if an MP4 exists")
    args = parser.parse_args()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    scenes = select_scenes(
        args.ids,
        agent=args.agent,
        travel=args.travel,
        intro=args.intro,
        speech=args.speech,
        activity=args.activities,
    )
    tasks = _load_tasks()
    api_key = dashscope_api_key()
    needs_dragon = any(uses_agent(scene) or uses_activity(scene) or uses_bookend(scene) for scene in scenes)
    media = _agent_media() if needs_dragon else None
    failed: list[str] = []
    for scene in scenes:
        stem = clip_stem(scene)
        try:
            _submit_one(api_key, scene, tasks, args.force, media)
        except (RuntimeError, ValueError) as exc:
            print(f"{stem} submit-error: {exc}", flush=True)
            failed.append(stem)
    for scene in scenes:
        stem = clip_stem(scene)
        if stem in failed:
            continue
        try:
            dest = _download_one(api_key, scene, tasks, args.force)
            if uses_agent(scene) or uses_speech(scene) or uses_activity(scene) or uses_bookend(scene):
                dest = _publish_desktop(dest, scene)
            print(f"ready {dest}", flush=True)
        except (RuntimeError, TimeoutError, ValueError, OSError) as exc:
            print(f"{stem} download-error: {exc}", flush=True)
            failed.append(stem)
    if failed:
        raise RuntimeError(f"video failed: {','.join(failed)}")
    print(f"all-done {WORK_DIR}", flush=True)


if __name__ == "__main__":
    main()
