#!/usr/bin/env python3
"""Generate Siamese tester-cat green-screen stills with Wan 2.7 image.

Examples (from repo root, conda env python313):

  python -m scripts.siamese_cat_emoji.generate_stills --ids 2
  python -m scripts.siamese_cat_emoji.generate_stills --ids 2,1
  python -m scripts.siamese_cat_emoji.generate_stills --ids 1 --force

Exports land in Pictures/mascots/siamese-cat-mascot/. Repo copies go to
scripts/cat_emoji/stills/siamese/. Front idle (2) should be generated first
so the 3/4 still can lock the same face and glasses.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from scripts.cat_emoji.paths import BLACK_STILL_FRONT, BLACK_STILL_THREE_QUARTER
from scripts.siamese_cat_emoji.catalog import NEGATIVE, SHELL, STILL_SHOTS, StillShot, shot_by_id
from scripts.siamese_cat_emoji.paths import (
    EXPORT_DIR,
    STILL_SIZE,
    STILLS_DIR,
    WORK_DIR,
    export_still_path,
    repo_still_path,
)
from services.t2i.wan_image_studio import download_image, poll_storyboard, submit_icon


def _select_shots(raw_ids: str | None) -> list[StillShot]:
    if not raw_ids:
        return list(STILL_SHOTS)
    return [shot_by_id(item.strip()) for item in raw_ids.split(",") if item.strip()]


def _require_style_refs() -> None:
    if not BLACK_STILL_FRONT.is_file():
        raise RuntimeError(f"style ref missing: {BLACK_STILL_FRONT}")


def _refs_for(shot: StillShot) -> list[Path]:
    front_export = export_still_path("2")
    front_repo = repo_still_path("2")
    front_lock = front_repo if front_repo.is_file() else front_export
    if shot["id"] == "1" and front_lock.is_file():
        return [front_lock, BLACK_STILL_THREE_QUARTER]
    return [BLACK_STILL_FRONT]


def _copy_to_repo(export_path: Path, repo_path: Path) -> None:
    STILLS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(export_path, repo_path)
    print(f"repo {repo_path} bytes={repo_path.stat().st_size}", flush=True)


def _generate_one(shot: StillShot, force: bool) -> None:
    dest = export_still_path(shot["id"])
    repo = repo_still_path(shot["id"])
    if dest.is_file() and dest.stat().st_size > 10000 and not force:
        print(f"{shot['id']} exists, skip (use --force to redo)", flush=True)
        if not repo.is_file():
            _copy_to_repo(dest, repo)
        return
    refs = _refs_for(shot)
    for path in refs:
        if not path.is_file():
            raise RuntimeError(f"ref missing: {path}")
    prompt = f"{SHELL}{shot['prompt']} 不要出现：{NEGATIVE}"
    print(f"still {shot['id']}-{shot['slug']} {shot['name']}", flush=True)
    task_id = submit_icon(prompt, refs, STILL_SIZE)
    urls = poll_storyboard(task_id)
    if not urls:
        raise RuntimeError(f"{shot['id']} returned no images")
    dest.parent.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    download_image(urls[0], dest)
    download_image(urls[0], WORK_DIR / dest.name)
    _copy_to_repo(dest, repo)


def main() -> None:
    """CLI entry: generate selected Siamese-cat green-screen stills."""
    parser = argparse.ArgumentParser(description="Wan image Siamese tester-cat stills")
    parser.add_argument("--ids", help="Comma ids such as 2 or 2,1")
    parser.add_argument("--force", action="store_true", help="Regenerate even if stills exist")
    args = parser.parse_args()
    _require_style_refs()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    for shot in _select_shots(args.ids):
        _generate_one(shot, args.force)
    print("still-done", flush=True)


if __name__ == "__main__":
    main()
