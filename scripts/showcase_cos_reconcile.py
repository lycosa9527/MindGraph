#!/usr/bin/env python3
"""CLI: reconcile Showcase Postgres keys with COS (report; optional purge).

Usage (WSL, repo root)::

    PYTHONPATH=. python scripts/showcase_cos_reconcile.py
    PYTHONPATH=. python scripts/showcase_cos_reconcile.py --purge --i-know-what-im-doing

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from config.database import AsyncSessionLocal
from services.showcase.sync import (
    build_storage_status,
    purge_orphans_from_reconcile,
    reconcile_showcase_storage,
)


async def _run(*, purge: bool, confirm: bool) -> int:
    status = build_storage_status()
    print(json.dumps({"status": status.to_dict()}, indent=2, ensure_ascii=False))

    async with AsyncSessionLocal() as db:
        if purge:
            if not confirm:
                print(
                    "Refusing purge without --i-know-what-im-doing (use without --purge for report-only).",
                    file=sys.stderr,
                )
                return 2
            result = await purge_orphans_from_reconcile(db, dry_run=False)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0

        report = await reconcile_showcase_storage(db)
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    """Parse CLI args and run reconcile or purge."""
    parser = argparse.ArgumentParser(description="Showcase COS ↔ DB reconcile")
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Delete orphan COS objects (requires --i-know-what-im-doing)",
    )
    parser.add_argument(
        "--i-know-what-im-doing",
        action="store_true",
        help="Confirm destructive orphan purge",
    )
    args = parser.parse_args()
    return asyncio.run(_run(purge=args.purge, confirm=args.i_know_what_im_doing))


if __name__ == "__main__":
    sys.exit(main())
