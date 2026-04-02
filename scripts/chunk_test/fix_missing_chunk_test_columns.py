"""
Legacy migration stub — superseded by Alembic.

The columns this script used to add (``session_id`` on ``chunk_test_results``,
``meta_data`` on ``chunk_test_documents``) are now part of the baseline schema
managed by Alembic.

Run ``alembic upgrade head`` from the project root to apply any pending
migrations.
"""

import sys


def main() -> int:
    print("This script is no longer needed.")
    print("Schema migrations are now managed by Alembic.")
    print()
    print("  alembic upgrade head")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
