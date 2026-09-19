#!/usr/bin/env python3
"""Upload silent /auth login heroes to the live COS folder layout.

Bucket folders (no ``production/`` tree):

* ``dev/auth-login/`` — local ENVIRONMENT=development
* ``test/auth-login/`` — test server
* ``auth-login/mindgraph/`` — live production (same as documents/mindgraph)

  python -m scripts.auth_login_video.publish
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config.cos_env_prefix import cos_production_tree_enabled
from config.settings import config
from scripts.auth_login_video.catalog import CONCEPTS, hero_object_name
from scripts.auth_login_video.paths import DESKTOP_DIR, WORK_DIR
from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    cos_object_key,
    head_object,
    upload_file,
)

HERO_CONTENT_TYPE = "video/mp4"
_SHARED_ROOTS = ("dev", "test")


def hero_cos_prefixes() -> tuple[str, ...]:
    """Current prefix plus shared catalog roots and live ``auth-login/mindgraph``."""
    prefixes: list[str] = []
    current = (config.COS_AUTH_LOGIN_PREFIX or "").strip().rstrip("/")
    if current:
        prefixes.append(current)
    if current.startswith("production/") or cos_production_tree_enabled():
        return tuple(prefixes)
    for root in _SHARED_ROOTS:
        candidate = f"{root}/auth-login"
        if candidate not in prefixes:
            prefixes.append(candidate)
    live = "auth-login/mindgraph"
    if live not in prefixes:
        prefixes.append(live)
    return tuple(prefixes)


def _reencode_path(object_name: str) -> Path | None:
    stem = object_name.removesuffix(".mp4")
    desktop = DESKTOP_DIR / f"{stem}-reencode.mp4"
    if desktop.is_file() and desktop.stat().st_size > 10000:
        return desktop
    work = WORK_DIR / f"{stem}-wan3-reencode.mp4"
    if work.is_file() and work.stat().st_size > 10000:
        return work
    return None


def _object_matches(object_key: str, local_size: int) -> bool:
    meta = head_object(object_key)
    if not meta:
        return False
    remote = meta.get("ContentLength")
    if remote is None:
        remote = meta.get("Content-Length")
    return int(remote or 0) == local_size


def publish_heroes(prefixes: tuple[str, ...]) -> int:
    """Upload four silent heroes. Returns failed count."""
    failed = 0
    for concept in CONCEPTS:
        name = hero_object_name(concept)
        local = _reencode_path(name)
        if local is None:
            print(f"missing {name}", file=sys.stderr)
            failed += 1
            continue
        size = local.stat().st_size
        for prefix in prefixes:
            object_key = cos_object_key(name, prefix=prefix)
            if _object_matches(object_key, size):
                print(f"skip {object_key}")
                continue
            ok = upload_file(
                local,
                object_key,
                content_type=HERO_CONTENT_TYPE,
                log_prefix="[AuthLogin/COS]",
            )
            if ok:
                print(f"uploaded {object_key} {size}")
            else:
                print(f"failed {object_key}", file=sys.stderr)
                failed += 1
    return failed


def main() -> None:
    """CLI: publish silent login heroes to COS."""
    parser = argparse.ArgumentParser(description="Publish /auth login heroes to COS")
    parser.add_argument("--prefixes", help="Comma prefixes; default is shared catalog")
    args = parser.parse_args()
    if not config.COS_AUTH_LOGIN_ENABLED or not cos_credentials_configured():
        raise RuntimeError("COS auth-login is off or credentials are missing")
    if args.prefixes:
        prefixes = tuple(item.strip() for item in args.prefixes.split(",") if item.strip())
    else:
        prefixes = hero_cos_prefixes()
    print(f"prefixes {list(prefixes)}", flush=True)
    failed = publish_heroes(prefixes)
    if failed:
        raise RuntimeError(f"publish failed: {failed}")
    print("publish-done", flush=True)


if __name__ == "__main__":
    main()
