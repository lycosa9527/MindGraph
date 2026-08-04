#!/usr/bin/env python3
"""
Publish Showcase LibreOffice CJK preview fonts to Tencent COS.

Default source: Windows Fonts (``/mnt/c/Windows/Fonts`` on WSL, or
``C:\\Windows\\Fonts``). Uploads under
``{COS_SYNC_KEY_PREFIX}/sync/fonts/office-preview/``.

Runtime: Showcase cover jobs auto-pull into ``data/office_preview_fonts/``
before LibreOffice convert (no manual pull on test/prod when COS creds work).

Do not commit font binaries to git.

Usage (repo root, WSL + conda)::

  python scripts/db/publish_office_preview_fonts_to_cos.py
  python scripts/db/publish_office_preview_fonts_to_cos.py --source /mnt/c/Windows/Fonts
  python scripts/db/publish_office_preview_fonts_to_cos.py --status
  python scripts/db/publish_office_preview_fonts_to_cos.py --pull

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

from services.infrastructure.sync.office_preview_fonts_cos import (
    FONT_FILES,
    default_windows_fonts_dir,
    ensure_office_preview_fonts_ready,
    fonts_status_snapshot,
    format_publish_summary,
    publish_office_preview_fonts,
)
from services.utils.tencent_cos_client import cos_credentials_configured


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Directory with simsun.ttc / simkai.ttf / … (default: Windows Fonts)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print local/COS status and exit",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Download pack into data/office_preview_fonts/ (test/prod warm cache)",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entry: publish, status, or pull office-preview fonts."""
    _ = project_root
    args = _parse_args()
    if args.status:
        print(json.dumps(fonts_status_snapshot(), ensure_ascii=False, indent=2))
        return 0

    if args.pull:
        if not cos_credentials_configured() and default_windows_fonts_dir() is None:
            print(
                "ERROR: need COS credentials or local Windows Fonts to pull/seed.",
                file=sys.stderr,
            )
            return 2
        resolved = ensure_office_preview_fonts_ready()
        present = {name: path is not None for name, path in resolved.items()}
        print(json.dumps({"ok": all(present.values()), "present": present}, indent=2))
        return 0 if all(present.values()) else 1

    if not cos_credentials_configured():
        print("ERROR: COS credentials not configured (COS_BUCKET / secrets).", file=sys.stderr)
        return 2

    source = args.source
    if source is None:
        source = default_windows_fonts_dir()
        if source is None:
            print(
                "ERROR: Windows Fonts not found. Pass --source /mnt/c/Windows/Fonts",
                file=sys.stderr,
            )
            return 3
    elif not source.is_absolute():
        source = project_root / source

    missing = [name for name in FONT_FILES if not (source / name).is_file()]
    if missing:
        print(
            f"ERROR: missing font files in {source}: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 3

    result = publish_office_preview_fonts(source)
    print(format_publish_summary(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
