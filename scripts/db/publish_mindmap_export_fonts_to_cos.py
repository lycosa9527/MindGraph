#!/usr/bin/env python3
"""
Publish mind-map PDF export fonts to Tencent COS.

Reads TrueType files from ``frontend/public/fonts/`` (or ``--source``) and
uploads them under ``{COS_SYNC_KEY_PREFIX}/sync/fonts/mindmap-export/``.

Runtime: browser loads ``/api/mindmap_export_fonts/{file}``; the API serves a
local cache and pulls from COS on miss (no CDN). jsPDF requires TrueType.

Usage (repo root, WSL + conda)::

  python scripts/db/publish_mindmap_export_fonts_to_cos.py
  python scripts/db/publish_mindmap_export_fonts_to_cos.py --source frontend/public/fonts
  python scripts/db/publish_mindmap_export_fonts_to_cos.py --status

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from _path_setup import project_root
except ModuleNotFoundError:
    from scripts.db._path_setup import project_root

from services.infrastructure.sync.mindmap_export_fonts_cos import (
    FONT_FILES,
    fonts_status_snapshot,
    format_publish_summary,
    mindmap_export_fonts_vendor_dir,
    publish_mindmap_export_fonts,
)
from services.utils.tencent_cos_client import cos_credentials_configured


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Directory containing NotoSansSC-*.ttf (default: frontend/public/fonts)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print local/COS status and exit",
    )
    return parser.parse_args()


def main() -> int:
    root = project_root
    args = _parse_args()
    if args.status:
        print(json.dumps(fonts_status_snapshot(), ensure_ascii=False, indent=2))
        return 0

    if not cos_credentials_configured():
        print("ERROR: COS credentials not configured (COS_BUCKET / secrets).", file=sys.stderr)
        return 2

    source = args.source
    if source is None:
        source = root / mindmap_export_fonts_vendor_dir()
    elif not source.is_absolute():
        source = root / source

    missing = [name for name in FONT_FILES if not (source / name).is_file()]
    if missing:
        print(
            "ERROR: missing font files in "
            f"{source}: {', '.join(missing)}\n"
            "Run: cd frontend && npm run vendor:mindmap-export-fonts",
            file=sys.stderr,
        )
        return 3

    result = publish_mindmap_export_fonts(source)
    print(format_publish_summary(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
