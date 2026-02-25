#!/usr/bin/env python3
"""
Check admin status for users.

Verifies which users have admin access based on:
1. role='admin' in database
2. phone in ADMIN_PHONES env variable

Run from project root: python scripts/db/check_admin_status.py
"""
import os
import sys
from pathlib import Path

# Load .env before importing config
_project_root = Path(__file__).resolve().parent.parent.parent
env_path = _project_root / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().split("#")[0].strip())

from config.database import SessionLocal
from models.domain.auth import User
from utils.auth.config import ADMIN_PHONES

# Also check AUTH_MODE for demo/bayi admin
AUTH_MODE = os.getenv("AUTH_MODE", "standard").strip().lower()


def main():
    """Check and print admin status for all users."""
    admin_phones = [p.strip() for p in ADMIN_PHONES if p.strip()]
    print("=" * 60)
    print("Admin Status Check")
    print("=" * 60)
    print(f"AUTH_MODE: {AUTH_MODE}")
    print(f"ADMIN_PHONES from .env: {admin_phones or '(empty)'}")
    print()

    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        if not users:
            print("No users found in database.")
            return

        print(f"Found {len(users)} user(s):\n")
        for u in users:
            db_admin = (u.role or "").lower() == "admin"
            phone_admin = u.phone in admin_phones if admin_phones else False
            demo_admin = AUTH_MODE == "demo" and u.phone == "demo-admin@system.com"
            bayi_admin = AUTH_MODE == "bayi" and u.phone == "bayi-admin@system.com"
            is_admin = db_admin or phone_admin or demo_admin or bayi_admin

            reasons = []
            if db_admin:
                reasons.append("role=admin in DB")
            if phone_admin:
                reasons.append("phone in ADMIN_PHONES")
            if demo_admin:
                reasons.append("demo-admin@system.com in demo mode")
            if bayi_admin:
                reasons.append("bayi-admin@system.com in bayi mode")

            status = "ADMIN" if is_admin else "user/manager"
            reason_str = f" ({', '.join(reasons)})" if reasons else ""
            print(f"  id={u.id}  phone={u.phone}  role={u.role or 'user'}  -> {status}{reason_str}")

        print()
        admin_users = [
            u for u in users
            if (u.role or "").lower() == "admin"
            or (admin_phones and u.phone in admin_phones)
            or (AUTH_MODE == "demo" and u.phone == "demo-admin@system.com")
            or (AUTH_MODE == "bayi" and u.phone == "bayi-admin@system.com")
        ]
        if admin_users:
            print(f"Users with admin access: {[u.phone for u in admin_users]}")
        else:
            print("WARNING: No users have admin access!")
            print("  - Set role='admin' in DB for a user, OR")
            print("  - Add phone to ADMIN_PHONES in .env (e.g. ADMIN_PHONES=17801353751)")
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
