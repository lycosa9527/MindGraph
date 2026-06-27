#!/usr/bin/env python3
"""
Rotate the active JWT signing secret in Redis.

Moves the current secret to jwt:secret:previous and generates a new current secret.
Access tokens signed with the previous secret remain valid until they expire
(decode_access_token tries both secrets).

Usage (WSL, from repo root):

    conda activate python313
    python scripts/ops/rotate_jwt_secret.py

Requires live Redis (REDIS_URL) and write access to jwt:secret keys.
"""

from __future__ import annotations

import sys

from utils.auth.jwt_secret import rotate_jwt_secret


def main() -> int:
    """Rotate JWT secret and print a short status summary."""
    try:
        new_secret = rotate_jwt_secret()
    except RuntimeError as exc:
        print(f"JWT rotation failed: {exc}", file=sys.stderr)
        return 1

    print("JWT secret rotated successfully.")
    print(f"New secret length: {len(new_secret)} chars")
    print("Previous secret retained in Redis under jwt:secret:previous for dual-verify window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
