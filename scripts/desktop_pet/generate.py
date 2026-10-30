#!/usr/bin/env python3
"""Generate Wan 3.0 desktop-pet scenes and copy them to the Desktop review tree.

Examples (repo root, conda env python313):

  python -m scripts.desktop_pet.generate --all --workers 3
  python -m scripts.desktop_pet.generate --mascot black --ids 01
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from scripts.desktop_pet.actions import actions_for
from scripts.desktop_pet.actions.pack import PetAction, clip_id
from scripts.desktop_pet.catalog import VIDEO_DURATION, VIDEO_MODEL, VIDEO_RATIO, VIDEO_RESOLUTION
from scripts.desktop_pet.interactions import PAIRS, PairScene, pair_clip_id, pair_prompt
from scripts.desktop_pet.mascots import MASCOTS, NEGATIVE, Mascot, clip_prompt, mascot_by_slug
from scripts.desktop_pet.paths import ASSETS_DIR, DESKTOP_REVIEW_DIR, WORK_DIR
from scripts.training_roles.env import dashscope_api_key
from scripts.training_roles.export import extract_keyed_frames, save_webp
from scripts.training_roles.wan_client import LONG_POLL_SECONDS, WAN3_VIDEO, download_mp4, poll_video_url, submit_video

_TASKS_LOCK = threading.Lock()


def _ensure_ffmpeg() -> None:
    """Prefer ffmpeg on PATH. Fall back to the imageio-ffmpeg binary in this env."""
    if shutil.which("ffmpeg"):
        return
    matches = sorted(Path(sys.prefix).glob("lib/python*/site-packages/imageio_ffmpeg/binaries/ffmpeg-*"))
    if not matches:
        raise RuntimeError("ffmpeg not on PATH")
    link_dir = WORK_DIR / "bin"
    link_dir.mkdir(parents=True, exist_ok=True)
    link = link_dir / "ffmpeg"
    if not link.exists():
        link.symlink_to(matches[-1])
    os.environ["PATH"] = f"{link_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def ensure_review_dirs() -> None:
    """Create Desktop folders for each mascot and for the pair scenes."""
    for mascot in MASCOTS:
        (DESKTOP_REVIEW_DIR / mascot["slug"]).mkdir(parents=True, exist_ok=True)
        (mascot["pictures_dir"] / "pet-actions").mkdir(parents=True, exist_ok=True)
        (ASSETS_DIR / mascot["slug"]).mkdir(parents=True, exist_ok=True)
    (DESKTOP_REVIEW_DIR / "together").mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR / "together").mkdir(parents=True, exist_ok=True)


def _jpeg_data_url(still: Path, dest: Path) -> str:
    image = Image.open(still).convert("RGB")
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="JPEG", quality=90, optimize=True)
    payload = base64.b64encode(dest.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}"


def _reference_media(mascots: tuple[Mascot, ...], stem: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for index, mascot in enumerate(mascots):
        if not mascot["front"].is_file():
            raise RuntimeError(f"still missing: {mascot['front']}")
        dest = WORK_DIR / "refs" / f"{stem}-{index}-front.jpg"
        refs.append({"type": "reference_image", "url": _jpeg_data_url(mascot["front"], dest)})
        side = mascot["three_quarter"]
        if side.is_file() and len(mascots) == 1:
            side_dest = WORK_DIR / "refs" / f"{stem}-{index}-side.jpg"
            refs.append({"type": "reference_image", "url": _jpeg_data_url(side, side_dest)})
    return refs


def _load_tasks() -> dict[str, str]:
    path = WORK_DIR / "tasks.json"
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    return {str(key): str(value) for key, value in loaded.items()}


def _save_task(tasks: dict[str, str], stem: str, task_id: str) -> None:
    with _TASKS_LOCK:
        tasks[stem] = task_id
        (WORK_DIR / "tasks.json").write_text(json.dumps(tasks, indent=2), encoding="utf-8")


def _publish(mp4: Path, review_dir: Path, asset_dir: Path, stem: str) -> None:
    _ensure_ffmpeg()
    frames = extract_keyed_frames(mp4, WORK_DIR / "frames" / stem)
    review_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mp4, review_dir / f"{stem}.mp4")
    webp_name = f"{stem}.webp"
    review_webp = review_dir / webp_name
    save_webp(frames, review_webp, lossless=True)
    shutil.copy2(review_webp, asset_dir / webp_name)
    print(f"review {review_webp}", flush=True)


def _render(
    api_key: str,
    tasks: dict[str, str],
    stem: str,
    prompt: str,
    media_mascots: tuple[Mascot, ...],
    review_dir: Path,
    asset_dir: Path,
) -> None:
    if (review_dir / f"{stem}.webp").is_file():
        print(f"skip {stem}", flush=True)
        return
    mp4 = WORK_DIR / f"{stem}.mp4"
    if not (mp4.is_file() and mp4.stat().st_size > 10000):
        if stem not in tasks:
            if VIDEO_MODEL != WAN3_VIDEO:
                raise RuntimeError(f"refusing model {VIDEO_MODEL}")
            task_id = submit_video(
                api_key,
                prompt,
                stem,
                model=VIDEO_MODEL,
                negative=NEGATIVE,
                media=_reference_media(media_mascots, stem),
                resolution=VIDEO_RESOLUTION,
                duration=VIDEO_DURATION,
                ratio=VIDEO_RATIO,
                audio=False,
            )
            _save_task(tasks, stem, task_id)
        video_url = poll_video_url(api_key, tasks[stem], stem, timeout_seconds=LONG_POLL_SECONDS)
        download_mp4(video_url, mp4)
    _publish(mp4, review_dir, asset_dir, stem)


def _solo_job(api_key: str, tasks: dict[str, str], mascot: Mascot, action: PetAction) -> None:
    stem = f"{mascot['slug']}-{clip_id(action)}"
    try:
        _render(
            api_key,
            tasks,
            stem,
            clip_prompt(mascot, action["prompt"], action.get("costume", "")),
            (mascot,),
            DESKTOP_REVIEW_DIR / mascot["slug"] / clip_id(action),
            ASSETS_DIR / mascot["slug"],
        )
    except (RuntimeError, TimeoutError, OSError) as exc:
        print(f"fail {stem} {exc}", flush=True)


def _pair_job(api_key: str, tasks: dict[str, str], scene: PairScene) -> None:
    stem = f"together-{pair_clip_id(scene)}"
    try:
        _render(
            api_key,
            tasks,
            stem,
            pair_prompt(scene),
            (mascot_by_slug(scene["left"]), mascot_by_slug(scene["right"])),
            DESKTOP_REVIEW_DIR / "together" / pair_clip_id(scene),
            ASSETS_DIR / "together",
        )
    except (RuntimeError, TimeoutError, OSError) as exc:
        print(f"fail {stem} {exc}", flush=True)


def _reexport_one(stem: str, review_dir: Path, asset_dir: Path) -> None:
    mp4 = WORK_DIR / f"{stem}.mp4"
    if not (mp4.is_file() and mp4.stat().st_size > 10000):
        print(f"fail {stem} missing mp4", flush=True)
        return
    try:
        _publish(mp4, review_dir, asset_dir, stem)
    except (RuntimeError, OSError) as exc:
        print(f"fail {stem} {exc}", flush=True)


def _reexport_targets(args: argparse.Namespace) -> list[tuple[str, Path, Path]]:
    targets: list[tuple[str, Path, Path]] = []
    if args.all or (args.mascot and not args.pairs):
        slugs = [mascot["slug"] for mascot in MASCOTS] if args.all else [args.mascot.strip()]
        for slug in slugs:
            for action in _selected_actions(slug, "" if args.all else args.ids):
                targets.append(
                    (
                        f"{slug}-{clip_id(action)}",
                        DESKTOP_REVIEW_DIR / slug / clip_id(action),
                        ASSETS_DIR / slug,
                    )
                )
    if args.all or args.pairs:
        for scene in PAIRS:
            clip = pair_clip_id(scene)
            targets.append(
                (
                    f"together-{clip}",
                    DESKTOP_REVIEW_DIR / "together" / clip,
                    ASSETS_DIR / "together",
                )
            )
    return targets


def _reexport(args: argparse.Namespace) -> None:
    targets = _reexport_targets(args)

    def _run(item: tuple[str, Path, Path]) -> None:
        _reexport_one(item[0], item[1], item[2])

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(_run, targets))
    print("review-done", flush=True)


def _selected_actions(slug: str, raw_ids: str) -> list[PetAction]:
    actions = list(actions_for(slug))
    if not raw_ids.strip():
        return actions
    wanted = {item.strip() for item in raw_ids.split(",") if item.strip()}
    return [action for action in actions if action["id"] in wanted or clip_id(action) in wanted]


def main() -> None:
    """CLI entry: generate missing scenes and copy MP4 plus keyed WebP to the Desktop."""
    parser = argparse.ArgumentParser(description="Wan 3.0 desktop-pet scenes")
    parser.add_argument("--all", action="store_true", help="Every mascot's fifty scenes plus the ten pairs")
    parser.add_argument("--mascot", default="", help="One of black, white, siamese, raven, schnauzer")
    parser.add_argument("--ids", default="", help="Comma ids. Empty means every scene for the mascot.")
    parser.add_argument("--pairs", action="store_true", help="Only the ten two-mascot scenes")
    parser.add_argument("--reexport", action="store_true", help="Rewrite WebPs from existing MP4s at native resolution")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    ensure_review_dirs()
    _ensure_ffmpeg()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if args.reexport:
        _reexport(args)
        return
    tasks = _load_tasks()
    api_key = dashscope_api_key()
    jobs: list[tuple[str, Mascot | None, PetAction | None, PairScene | None]] = []
    if args.all or (args.mascot and not args.pairs):
        slugs = [mascot["slug"] for mascot in MASCOTS] if args.all else [args.mascot.strip()]
        for slug in slugs:
            mascot = mascot_by_slug(slug)
            for action in _selected_actions(slug, "" if args.all else args.ids):
                jobs.append(("solo", mascot, action, None))
    if args.all or args.pairs:
        for scene in PAIRS:
            jobs.append(("pair", None, None, scene))
    workers = max(1, args.workers)

    def _run(job: tuple[str, Mascot | None, PetAction | None, PairScene | None]) -> None:
        kind, mascot, action, scene = job
        if kind == "solo" and mascot is not None and action is not None:
            _solo_job(api_key, tasks, mascot, action)
            return
        if scene is not None:
            _pair_job(api_key, tasks, scene)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_run, jobs))
    print("review-done", flush=True)


if __name__ == "__main__":
    main()
