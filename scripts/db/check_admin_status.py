#!/usr/bin/env python3
"""
Check admin status for users.

Verifies which users have superadmin access based on:
1. role='superadmin' (or legacy 'admin') in database
2. ADMIN_USER_IDS env (comma-separated users.id values)
3. ADMIN_PHONES env (identifiers stored on users.phone, including SSO UUID strings;
   UUID comparison is case-insensitive.)

Run from project root: python scripts/db/check_admin_status.py
"""

try:
    from _path_setup import project_root
except ModuleNotFoundError:
    from scripts.db._path_setup import project_root

import sys

from config.database import SyncSessionLocal
from models.domain.auth import User
from utils.auth.config import ADMIN_PHONES, ADMIN_USER_IDS
from utils.auth.role_constants import SUPERADMIN_ROLES
from utils.auth.roles import is_admin, phone_matches_admin_env_token

_ = project_root


def main():
    """Check and print admin status for all users."""
    admin_phones = [p.strip() for p in ADMIN_PHONES if p.strip()]
    ids_sorted = sorted(ADMIN_USER_IDS)
    print("=" * 60)
    print("Admin Status Check")
    print("=" * 60)
    print(f"ADMIN_PHONES from .env: {admin_phones or '(empty)'}")
    print(f"ADMIN_USER_IDS from .env: {ids_sorted or '(empty)'}")
    print()

    db = SyncSessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        if not users:
            print("No users found in database.")
            return

        print(f"Found {len(users)} user(s):\n")
        for u in users:
            matched = bool(is_admin(u))

            reasons = []
            role_val = getattr(u, "role", None)
            if role_val in SUPERADMIN_ROLES:
                reasons.append("role in DB")
            if u.id in ADMIN_USER_IDS:
                reasons.append("id in ADMIN_USER_IDS")
            if admin_phones and any(phone_matches_admin_env_token(u.phone, t) for t in admin_phones):
                reasons.append("ADMIN_PHONES match")

            status = "SUPERADMIN" if matched else "other"
            reason_str = f" ({', '.join(reasons)})" if reasons else ""
            print(f"  id={u.id}  phone={u.phone}  role={u.role or 'teacher'}  -> {status}{reason_str}")

        print()
        admin_users = [u for u in users if is_admin(u)]
        if admin_users:
            labels = []
            for u in admin_users:
                ident = u.phone or u.email or f"id={u.id}"
                labels.append(ident)
            print(f"Users with superadmin access ({len(admin_users)}): {labels}")
        else:
            print("WARNING: No users have superadmin access!")
            print("  - Set role='superadmin' in DB for a user, OR")
            print(
                "  - ADMIN_USER_IDS=id,... and/or ADMIN_PHONES=... "
                "(phones, bayi@system.com, or Bayi SSO UUID in users.phone)."
            )
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
