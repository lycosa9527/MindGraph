"""One-shot RLS role bootstrap (same as run_migrations.py option 3)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from scripts.db.run_migrations import run_status_check

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))


def main() -> int:
    """Main."""
    print("=" * 60)
    print("MindGraph — bootstrap RLS roles (delegates to status check)")
    print("=" * 60)
    return run_status_check()


if __name__ == "__main__":
    sys.exit(main())
