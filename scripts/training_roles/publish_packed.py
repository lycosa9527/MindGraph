"""Upload packed Course Builder role WebPs to COS training prefixes."""

from __future__ import annotations

import argparse
import sys

from services.features.training.roles.catalog import (
    ROLE_CONTENT_TYPE,
    packed_role_file,
    packed_role_filenames,
    parse_packed_role_key,
)
from services.features.training.storage.backend import cos_training_enabled
from services.utils.tencent_cos_client import head_object, upload_bytes


def _object_matches(object_key: str, local_size: int) -> bool:
    meta = head_object(object_key)
    if not meta:
        return False
    return int(meta.get("ContentLength") or 0) == local_size


def publish_prefix(prefix: str) -> tuple[int, int, int]:
    """Upload missing or size-mismatched packed roles. Returns uploaded, skipped, failed."""
    root = prefix.strip().rstrip("/")
    uploaded = 0
    skipped = 0
    failed = 0
    for filename in packed_role_filenames():
        parsed = parse_packed_role_key(f"roles/{filename}")
        if parsed is None:
            failed += 1
            continue
        role_id, thumb = parsed
        local = packed_role_file(role_id, thumb=thumb)
        if local is None:
            print(f"missing {filename}", file=sys.stderr)
            failed += 1
            continue
        object_key = f"{root}/roles/{filename}"
        size = local.stat().st_size
        if _object_matches(object_key, size):
            skipped += 1
            continue
        if upload_bytes(
            local.read_bytes(),
            object_key,
            content_type=ROLE_CONTENT_TYPE,
            log_prefix="[Training/COS]",
        ):
            uploaded += 1
            print(f"uploaded {object_key} ({size} bytes)")
        else:
            failed += 1
            print(f"failed {object_key}", file=sys.stderr)
    return uploaded, skipped, failed


def main(argv: list[str] | None = None) -> int:
    """CLI: publish packed role WebPs to each given COS prefix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "prefixes",
        nargs="+",
        help="COS prefixes such as training/mindgraph-Dev training/mindgraph-Test",
    )
    args = parser.parse_args(argv)
    if not cos_training_enabled():
        print("COS training is off or credentials are missing", file=sys.stderr)
        return 2
    total_failed = 0
    for prefix in args.prefixes:
        uploaded, skipped, failed = publish_prefix(prefix)
        print(f"{prefix}: uploaded={uploaded} skipped={skipped} failed={failed}")
        total_failed += failed
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
