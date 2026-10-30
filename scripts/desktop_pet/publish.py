#!/usr/bin/env python3
"""Upload one OS zip and merge it into latest.json without wiping the other OS."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from config.cos_env_prefix import cos_env_root
from services.features.desktop_pet.update_manifest import is_newer, manifest_prefix
from services.utils.tencent_cos_client import get_object_bytes, upload_bytes


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _load_manifest(key: str) -> dict[str, object]:
    raw = get_object_bytes(key, log_prefix="[DesktopPet]")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def publish(platform: str, zip_path: Path, version: str) -> str:
    """Upload the zip and merge that platform into latest.json. Returns the object key."""
    prefix = manifest_prefix()
    filename = "MindGraphPet-windows.zip" if platform == "windows" else "MindGraphPet-mac.zip"
    object_key = f"{prefix}/{version}/{filename}"
    payload = zip_path.read_bytes()
    if not upload_bytes(payload, object_key, content_type="application/zip", log_prefix="[DesktopPet]"):
        raise RuntimeError(f"upload failed {object_key}")
    manifest_key = f"{prefix}/latest.json"
    manifest = _load_manifest(manifest_key)
    remote_version = str(manifest.get("version") or "")
    if remote_version and is_newer(remote_version, version):
        raise RuntimeError(f"{version} is older than published {remote_version}")
    manifest["version"] = version
    manifest[platform] = {"key": object_key, "sha256": _sha256(zip_path), "size": zip_path.stat().st_size}
    body = json.dumps(manifest, indent=2).encode("utf-8")
    fresh = _load_manifest(manifest_key)
    if fresh.get("version") not in {None, "", remote_version, version}:
        raise RuntimeError("latest.json changed while publishing; run publish again")
    if not upload_bytes(body, manifest_key, content_type="application/json", log_prefix="[DesktopPet]"):
        raise RuntimeError("latest.json upload failed")
    print(f"published {object_key} env={cos_env_root()}", flush=True)
    return object_key


def main() -> None:
    """CLI: publish the zip built on this machine."""
    parser = argparse.ArgumentParser(description="Publish a desktop pet zip to COS")
    parser.add_argument("--platform", required=True, choices=("windows", "mac"))
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if not args.zip.is_file():
        print(f"missing {args.zip}", file=sys.stderr)
        sys.exit(1)
    publish(args.platform, args.zip, args.version.strip())


if __name__ == "__main__":
    main()
