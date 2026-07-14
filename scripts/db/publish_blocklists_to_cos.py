#!/usr/bin/env python3
"""
One-shot pull + publish of IP blocklists (and optional GeoLite) to Tencent COS.

Requires ``COS_SYNC_ENABLED=true`` and ``COS_SYNC_ROLE=publisher`` (or pass
``--as-publisher`` to set those for this process only).

Usage (repo root, WSL + conda)::

  python scripts/db/publish_blocklists_to_cos.py
  python scripts/db/publish_blocklists_to_cos.py --crowdsec-only
  python scripts/db/publish_blocklists_to_cos.py --abuseipdb-only
  python scripts/db/publish_blocklists_to_cos.py --geolite-only
  python scripts/db/publish_blocklists_to_cos.py --migrate-legacy-sync
  python scripts/db/publish_blocklists_to_cos.py --prune-orphan-qdrant

Do **not** run CrowdSec force-pull on more than one host the same day.
If CrowdSec returns HTTP 429, this script falls back to publishing the local
``data/crowdsec/blocklist_baseline.txt`` when present.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from _path_setup import project_root
except ModuleNotFoundError:
    from scripts.db._path_setup import project_root

from services.infrastructure.security.crowdsec_blocklist_service import (
    crowdsec_baseline_blacklist_path,
)
from services.infrastructure.security.ip_reputation_blacklist_redis import (
    parse_baseline_file_lines,
)
from services.infrastructure.sync.abuseipdb_cos_sync import (
    read_abuseipdb_cos_meta,
    sync_blacklist_for_role,
)
from services.infrastructure.sync.cos_sync_env import (
    abuseipdb_blocklist_cos_key,
    cos_sync_role,
    crowdsec_blocklist_cos_key,
    geolite_mmdb_cos_key,
    is_cos_publisher,
    normalized_cos_sync_prefix,
)
from services.infrastructure.sync.crowdsec_cos_sync import (
    merge_crowdsec_blocklist_for_role,
    publish_crowdsec_blocklist_to_cos,
    read_crowdsec_cos_meta,
)
from services.infrastructure.sync.geolite_cos_sync import (
    read_geolite_cos_meta,
    sync_geolite_for_role,
)
from services.redis.redis_client import init_redis_sync, is_redis_available
from services.utils import tencent_cos_client
from services.utils.tencent_cos_client import (
    COS_KEY_PREFIX,
    cos_object_key,
    download_file,
    get_json,
    list_prefix,
    normalized_cos_prefix,
    upload_file,
)

_ = project_root


def _force_publisher_env() -> None:
    os.environ["COS_SYNC_ENABLED"] = "true"
    os.environ["COS_SYNC_ROLE"] = "publisher"


def _print_json(label: str, payload: Dict[str, Any]) -> None:
    print(f"\n=== {label} ===")
    print(json.dumps(payload, indent=2, default=str))


async def _publish_crowdsec_from_baseline() -> Dict[str, Any]:
    """Upload local CrowdSec baseline when API is rate-limited."""
    path = crowdsec_baseline_blacklist_path()
    if not path.is_file():
        return {"ok": False, "error": "baseline_missing", "path": str(path)}
    text = await asyncio.to_thread(path.read_text, encoding="utf-8")
    ips = parse_baseline_file_lines(text)
    if not ips:
        return {"ok": False, "error": "baseline_empty", "path": str(path)}
    published = await publish_crowdsec_blocklist_to_cos(text, len(ips))
    return {
        "ok": published,
        "count": len(ips),
        "source": "baseline",
        "cos_published": published,
        "path": str(path),
    }


async def _migrate_legacy_sync_objects() -> Dict[str, Any]:
    """Copy sync/* from legacy COS_KEY_PREFIX into COS_SYNC_KEY_PREFIX."""
    legacy = normalized_cos_prefix(COS_KEY_PREFIX)
    shared = normalized_cos_sync_prefix()
    if legacy == shared:
        return {"ok": True, "skipped": True, "reason": "prefixes_identical"}

    items = list_prefix(f"{legacy}/sync/")
    copied: List[str] = []
    failed: List[str] = []
    for item in items:
        src = item.get("key") or ""
        if not src or src.endswith("/"):
            continue
        rel = src[len(legacy) + 1 :] if src.startswith(f"{legacy}/") else src
        dest = f"{shared}/{rel}"
        if dest == src:
            continue
        tmp = Path(tempfile.gettempdir()) / f"mg-cos-migrate-{Path(src).name}"
        try:
            if not download_file(src, tmp, log_prefix="[MigrateSync]"):
                failed.append(src)
                continue
            if not upload_file(tmp, dest, log_prefix="[MigrateSync]"):
                failed.append(src)
                continue
            copied.append(f"{src} -> {dest}")
        finally:
            if tmp.is_file():
                tmp.unlink(missing_ok=True)
    return {
        "ok": not failed,
        "legacy_prefix": legacy,
        "shared_prefix": shared,
        "copied": copied,
        "failed": failed,
    }


async def _prune_orphan_qdrant(*, prefix: Optional[str] = None) -> Dict[str, Any]:
    """Delete Qdrant tarballs not referenced by meta.json under a prefix."""
    base = prefix or normalized_cos_sync_prefix()
    meta_key = cos_object_key("sync/qdrant/meta.json", prefix=base)
    meta = get_json(meta_key)
    if not meta:
        return {"ok": False, "error": "qdrant_meta_missing", "prefix": base}
    version = str(meta.get("version") or "").lstrip("v")
    tarball_key = meta.get("tarball_key")
    items = list_prefix(f"{base}/sync/qdrant/")
    deleted: List[str] = []
    kept: List[str] = []
    for item in items:
        key = item.get("key") or ""
        if key.endswith("meta.json"):
            kept.append(key)
            continue
        if tarball_key and key == tarball_key:
            kept.append(key)
            continue
        if version and f"/v{version}/" in key:
            kept.append(key)
            continue
        if "/v" in key and key.endswith(".tar.gz"):
            if tencent_cos_client.delete_object(key):
                deleted.append(key)
            else:
                return {
                    "ok": False,
                    "error": f"delete_failed:{key}",
                    "deleted": deleted,
                    "prefix": base,
                }
        else:
            kept.append(key)
    return {
        "ok": True,
        "deleted": deleted,
        "kept": kept,
        "meta_version": version,
        "prefix": base,
    }


async def _run(args: argparse.Namespace) -> int:
    if args.as_publisher:
        _force_publisher_env()

    if not is_cos_publisher():
        print(
            f"ERROR: COS_SYNC_ROLE must be publisher (current={cos_sync_role()!r}). Pass --as-publisher or set .env.",
            file=sys.stderr,
        )
        return 2

    if not tencent_cos_client.cos_credentials_configured():
        print("ERROR: COS credentials / bucket not configured", file=sys.stderr)
        return 2

    if not init_redis_sync():
        print("ERROR: Redis init failed (required for blacklist merge)", file=sys.stderr)
        return 2
    if not is_redis_available():
        print("ERROR: Redis unavailable after init", file=sys.stderr)
        return 2

    print(f"sync_prefix={normalized_cos_sync_prefix()}")
    print(f"role={cos_sync_role()}")

    failed = False
    do_all = not (args.crowdsec_only or args.abuseipdb_only or args.geolite_only or args.migrate_legacy_sync)

    if args.migrate_legacy_sync or do_all:
        migrated = await _migrate_legacy_sync_objects()
        _print_json("Migrate legacy sync prefix", migrated)
        if not migrated.get("ok") and not migrated.get("skipped"):
            failed = True

    if do_all or args.crowdsec_only:
        cs = await merge_crowdsec_blocklist_for_role(force=True)
        if cs.get("rate_limited"):
            print("CrowdSec API rate-limited; publishing local baseline to COS")
            cs = await _publish_crowdsec_from_baseline()
        _print_json("CrowdSec", cs)
        if not cs.get("ok"):
            failed = True
        else:
            print(f"crowdsec_cos_key={crowdsec_blocklist_cos_key()}")
            print(f"crowdsec_cos_meta={read_crowdsec_cos_meta()}")

    if do_all or args.abuseipdb_only:
        ab = await sync_blacklist_for_role(force=True, force_crowdsec_merge=False)
        _print_json("AbuseIPDB", ab)
        if not ab.get("ok"):
            failed = True
        else:
            print(f"abuseipdb_cos_key={abuseipdb_blocklist_cos_key()}")
            print(f"abuseipdb_cos_meta={read_abuseipdb_cos_meta()}")

    if do_all or args.geolite_only:
        gl = await sync_geolite_for_role(force=True)
        _print_json("GeoLite", gl)
        if gl.get("error") == "local_mmdb_missing":
            print("GeoLite: local MMDB missing — skipped (not a hard failure)")
        elif not gl.get("ok"):
            failed = True
        else:
            print(f"geolite_cos_key={geolite_mmdb_cos_key()}")
            print(f"geolite_cos_meta={read_geolite_cos_meta()}")

    if args.prune_orphan_qdrant or do_all:
        for label, prefix in (
            ("shared", normalized_cos_sync_prefix()),
            ("legacy", normalized_cos_prefix(COS_KEY_PREFIX)),
        ):
            pruned = await _prune_orphan_qdrant(prefix=prefix)
            _print_json(f"Prune orphan Qdrant ({label})", pruned)
            if pruned.get("error") == "qdrant_meta_missing":
                print(f"Prune {label}: no meta — skip")
                continue
            if not pruned.get("ok"):
                failed = True

    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-publisher",
        action="store_true",
        help="Force COS_SYNC_ENABLED=true and COS_SYNC_ROLE=publisher for this process",
    )
    parser.add_argument("--crowdsec-only", action="store_true")
    parser.add_argument("--abuseipdb-only", action="store_true")
    parser.add_argument("--geolite-only", action="store_true")
    parser.add_argument(
        "--migrate-legacy-sync",
        action="store_true",
        help="Copy sync/* from COS_KEY_PREFIX to COS_SYNC_KEY_PREFIX",
    )
    parser.add_argument(
        "--prune-orphan-qdrant",
        action="store_true",
        help="Delete sync/qdrant version tarballs not referenced by meta.json",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
