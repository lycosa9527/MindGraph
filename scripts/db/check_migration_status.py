"""
Print Alembic revision and mandatory RLS rollout status (delegates to run_migrations).

Usage:
    PYTHONPATH=. python scripts/db/check_migration_status.py

Equivalent to ``python scripts/db/run_migrations.py`` menu option 3.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))


def main() -> int:
    from scripts.db.run_migrations import run_status_check

    return run_status_check()


if __name__ == "__main__":
    sys.exit(main())
