#!/usr/bin/env python3
"""Generate 1080P /auth login heroes with Wan 3.0 and HappyHorse.

Examples (from repo root, conda env python313):

  python -m scripts.auth_login_video.generate
  python -m scripts.auth_login_video.generate --ids 01 --models wan3.0-video-prime
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
from pathlib import Path

from PIL import Image

from scripts.auth_login_video.catalog import (
    CONCEPTS,
    NEGATIVE,
    LoginConcept,
    clip_duration,
    clip_prompt,
    clip_stem,
    concept_by_id,
    desktop_original_name,
    desktop_reencode_name,
)
from scripts.auth_login_video.paths import (
    BLACK_STILL,
    BLACK_STILL_SIDE,
    DESKTOP_DIR,
    WORK_DIR,
)
from scripts.auth_login_video.plates import reencode_login_clip, write_character_plate
from scripts.training_roles.env import dashscope_api_key
from scripts.training_roles.wan_client import (
    HAPPYHORSE_T2V,
    LONG_POLL_SECONDS,
    WAN3_VIDEO_PRIME,
    download_mp4,
    poll_video_url,
    submit_video,
)

MODEL_ALIASES = {
    "wan": WAN3_VIDEO_PRIME,
    "wan3": WAN3_VIDEO_PRIME,
    WAN3_VIDEO_PRIME: WAN3_VIDEO_PRIME,
    "horse": HAPPYHORSE_T2V,
    "happyhorse": HAPPYHORSE_T2V,
    HAPPYHORSE_T2V: HAPPYHORSE_T2V,
}


def _select_concepts(raw_ids: str | None) -> list[LoginConcept]:
    if not raw_ids:
        return list(CONCEPTS)
    return [concept_by_id(item.strip()) for item in raw_ids.split(",") if item.strip()]


def _select_models(raw_models: str | None) -> list[str]:
    if not raw_models:
        return [WAN3_VIDEO_PRIME]
    chosen: list[str] = []
    for item in raw_models.split(","):
        key = item.strip()
        if not key:
            continue
        model = MODEL_ALIASES.get(key)
        if model is None:
            raise ValueError(f"Unknown model: {key}")
        if model not in chosen:
            chosen.append(model)
    return chosen


def _plate_data_url(still: Path, dest_name: str) -> str:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    dest = write_character_plate(still, WORK_DIR / dest_name)
    image = Image.open(dest)
    payload = base64.b64encode(dest.read_bytes()).decode("ascii")
    print(f"ref {dest.name} size={image.size}", flush=True)
    return f"data:image/jpeg;base64,{payload}"


def _reference_media() -> list[dict[str, str]]:
    if not BLACK_STILL.is_file():
        raise RuntimeError(f"black still missing: {BLACK_STILL}")
    if not BLACK_STILL_SIDE.is_file():
        raise RuntimeError(f"black still missing: {BLACK_STILL_SIDE}")
    return [
        {"type": "reference_image", "url": _plate_data_url(BLACK_STILL, "ref-front.jpg")},
        {"type": "reference_image", "url": _plate_data_url(BLACK_STILL_SIDE, "ref-side.jpg")},
    ]


def _copy_desktop(src: Path, dest_name: str) -> Path:
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    dest = DESKTOP_DIR / dest_name
    shutil.copy2(src, dest)
    print(f"desktop {dest}", flush=True)
    return dest


def _publish_pair(concept: LoginConcept, original: Path, encoded: Path) -> None:
    _copy_desktop(original, desktop_original_name(concept))
    _copy_desktop(encoded, desktop_reencode_name(concept))


def _clean_desktop(keep: set[str]) -> None:
    if not DESKTOP_DIR.is_dir():
        return
    for path in DESKTOP_DIR.glob("*.mp4"):
        if path.name in keep:
            continue
        path.unlink()
        print(f"remove {path}", flush=True)


def _reencode_work(stem: str, original: Path) -> Path:
    dest = WORK_DIR / f"{stem}-reencode.mp4"
    return reencode_login_clip(original, dest, WORK_DIR)


def _generate_one(
    api_key: str,
    concept: LoginConcept,
    model: str,
    tasks: dict[str, str],
    media: list[dict[str, str]] | None,
    force: bool,
) -> Path:
    stem = clip_stem(concept, model)
    mp4 = WORK_DIR / f"{stem}.mp4"
    if mp4.is_file() and mp4.stat().st_size > 10000 and not force:
        print(f"{stem} exists, skip (use --force to redo)", flush=True)
        encoded = _reencode_work(stem, mp4)
        _publish_pair(concept, mp4, encoded)
        return encoded
    duration = clip_duration(concept, model)
    prompt = clip_prompt(concept, model)
    print(f"generate {stem} {model} {duration}s 1080P", flush=True)
    if stem not in tasks:
        audio = True if model == WAN3_VIDEO_PRIME else None
        tasks[stem] = submit_video(
            api_key,
            prompt,
            stem,
            model=model,
            negative=NEGATIVE,
            media=media if model == WAN3_VIDEO_PRIME else None,
            resolution="1080P",
            duration=duration,
            ratio="16:9",
            audio=audio,
        )
        (WORK_DIR / "tasks.json").write_text(json.dumps(tasks, indent=2), encoding="utf-8")
    video_url = poll_video_url(
        api_key,
        tasks[stem],
        stem,
        timeout_seconds=LONG_POLL_SECONDS,
    )
    download_mp4(video_url, mp4)
    encoded = _reencode_work(stem, mp4)
    _publish_pair(concept, mp4, encoded)
    return encoded


def _export_existing(concepts: list[LoginConcept], models: list[str]) -> None:
    keep: set[str] = set()
    for concept in concepts:
        for model in models:
            stem = clip_stem(concept, model)
            original = WORK_DIR / f"{stem}.mp4"
            if not original.is_file() or original.stat().st_size <= 10000:
                raise RuntimeError(f"missing work mp4: {original}")
            encoded = _reencode_work(stem, original)
            _publish_pair(concept, original, encoded)
            keep.add(desktop_original_name(concept))
            keep.add(desktop_reencode_name(concept))
    _clean_desktop(keep)


def main() -> None:
    """CLI entry: generate selected login heroes and copy them to Pictures/mascots."""
    parser = argparse.ArgumentParser(description="Wan 3.0 / HappyHorse /auth login heroes")
    parser.add_argument("--ids", help="Comma ids such as 01 or 01,03")
    parser.add_argument("--models", help="wan3.0-video-prime,happyhorse-1.1-t2v")
    parser.add_argument("--force", action="store_true", help="Resubmit even if an MP4 exists")
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Re-encode existing work MP4s and keep only original + reencode on desktop",
    )
    args = parser.parse_args()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if args.export_only:
        _export_existing(_select_concepts(args.ids), _select_models(args.models))
        print("export-done", flush=True)
        return
    concepts = _select_concepts(args.ids)
    models = _select_models(args.models)
    state_path = WORK_DIR / "tasks.json"
    tasks: dict[str, str] = {}
    if state_path.exists():
        tasks = json.loads(state_path.read_text(encoding="utf-8"))
    media = _reference_media() if WAN3_VIDEO_PRIME in models else None
    api_key = dashscope_api_key()
    failed: list[str] = []
    for concept in concepts:
        for model in models:
            stem = clip_stem(concept, model)
            try:
                _generate_one(api_key, concept, model, tasks, media, args.force)
            except (RuntimeError, TimeoutError, ValueError) as exc:
                print(f"{stem} skip-after-error: {exc}", flush=True)
                failed.append(stem)
    if failed:
        raise RuntimeError(f"video failed: {','.join(failed)}")
    print("all-done", flush=True)


if __name__ == "__main__":
    main()
