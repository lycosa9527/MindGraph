#!/usr/bin/env python3
"""
Upload ZhiHui landing seed images to COS (or local static fallback).

Reads resized JPEGs from ``frontend/public/zhihui/seeds/seed-N.jpg`` and writes
them to logical keys ``zhihui/seeds/seed-N.jpg`` via ZhiHui storage.

Usage (repo root, WSL + conda)::

  python scripts/db/seed_zhihui_landing_images.py
  python scripts/db/seed_zhihui_landing_images.py --dry-run
  python scripts/db/seed_zhihui_landing_images.py --source frontend/public/zhihui/seeds

Requires ``COS_ZHIHUI_ENABLED=true`` and Tencent credentials for COS; otherwise
files are written under ``static/zhihui/seeds/``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from _path_setup import project_root
except ModuleNotFoundError:
    from scripts.db._path_setup import project_root

from services.zhihui.storage.backend import put_bytes_sync, storage_backend
from services.zhihui.storage.keys import (
    LANDING_SEED_FILENAMES,
    build_seed_key,
    full_cos_key,
)


def _default_source_dir() -> Path:
    return project_root / "frontend" / "public" / "zhihui" / "seeds"


def main() -> int:
    """CLI entry: upload landing seed JPEGs to ZhiHui COS/local storage."""
    parser = argparse.ArgumentParser(description="Seed ZhiHui landing images to COS/local storage")
    parser.add_argument(
        "--source",
        type=Path,
        default=_default_source_dir(),
        help="Directory containing seed-N.jpg files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List planned uploads without writing",
    )
    args = parser.parse_args()
    source_dir: Path = args.source
    if not source_dir.is_absolute():
        source_dir = (project_root / source_dir).resolve()
    if not source_dir.is_dir():
        print(f"ERROR: source directory not found: {source_dir}", file=sys.stderr)
        return 1

    backend = storage_backend()
    print(f"backend={backend}")
    print(f"source={source_dir}")

    uploaded = 0
    for filename in LANDING_SEED_FILENAMES:
        path = source_dir / filename
        if not path.is_file():
            print(f"ERROR: missing {path}", file=sys.stderr)
            return 1
        logical = build_seed_key(filename)
        data = path.read_bytes()
        cos_key = full_cos_key(logical)
        print(f"{filename}: bytes={len(data)} logical={logical} cos={cos_key}")
        if args.dry_run:
            continue
        put_bytes_sync(logical, data, content_type="image/jpeg")
        uploaded += 1
        print("  uploaded ok")

    if args.dry_run:
        print(f"dry-run complete ({len(LANDING_SEED_FILENAMES)} files)")
        return 0
    print(f"done: uploaded={uploaded} backend={backend}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
