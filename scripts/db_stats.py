#!/usr/bin/env python
"""
PostgreSQL quick-look statistics helper.
========================================

Run this script against the production (or staging) database when you
suspect a regression to print three of the most actionable stat reports:

* Top 20 statements from ``pg_stat_statements`` ordered by total time.
* Top 20 user tables by sequential scans (likely missing index).
* Top 20 user indexes by size that have never been scanned (dead weight).

Usage::

    python scripts/db_stats.py [--limit 20] [--dsn postgresql://...]

The script uses the same DSN as the application by default
(:envvar:`DATABASE_URL`).  ``pg_stat_statements`` must be loaded via
``shared_preload_libraries`` and the extension created in the target
database (both are ensured by ``init_db()`` in MindGraph 0.x+).

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence


_TOP_STATEMENTS_SQL = """
SELECT
    calls,
    ROUND(total_exec_time::numeric, 2) AS total_ms,
    ROUND(mean_exec_time::numeric, 2)  AS mean_ms,
    rows,
    LEFT(REGEXP_REPLACE(query, E'\\s+', ' ', 'g'), 120) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT %s;
"""

_TOP_SEQ_SCAN_TABLES_SQL = """
SELECT
    schemaname || '.' || relname AS table,
    seq_scan,
    seq_tup_read,
    idx_scan,
    n_live_tup
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC
LIMIT %s;
"""

_UNUSED_INDEXES_SQL = """
SELECT
    schemaname || '.' || relname AS table,
    indexrelname               AS index,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size,
    idx_scan
FROM pg_stat_user_indexes
JOIN pg_index USING (indexrelid)
WHERE NOT indisunique
  AND NOT indisprimary
  AND idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT %s;
"""


def _print_table(title: str, columns: Sequence[str], rows: Sequence[tuple]) -> None:
    """Render rows as a fixed-width text table (no third-party deps)."""
    print(f"\n=== {title} ===")
    if not rows:
        print("(no rows)")
        return
    widths = [max(len(str(col)), *(len(str(row[i])) for row in rows)) for i, col in enumerate(columns)]
    header = " | ".join(col.ljust(widths[i]) for i, col in enumerate(columns))
    print(header)
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(" | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--limit", type=int, default=20, help="Rows per section (default 20).")
    parser.add_argument(
        "--dsn",
        default=os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN") or "postgresql://localhost:5432/mindgraph",
        help="PostgreSQL DSN; falls back to DATABASE_URL / POSTGRES_DSN.",
    )
    args = parser.parse_args(argv)

    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError:
        try:
            import psycopg2 as psycopg  # type: ignore[import-not-found, no-redef]
        except ImportError:
            print(
                "[db_stats] Neither psycopg nor psycopg2 is installed; install one to run this helper.",
                file=sys.stderr,
            )
            return 2

    try:
        conn = psycopg.connect(args.dsn)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[db_stats] Could not connect to {args.dsn!r}: {exc}", file=sys.stderr)
        return 1

    try:
        with conn.cursor() as cur:
            try:
                cur.execute(_TOP_STATEMENTS_SQL, (args.limit,))
                _print_table(
                    "Top statements (pg_stat_statements)",
                    ["calls", "total_ms", "mean_ms", "rows", "query"],
                    cur.fetchall(),
                )
            except Exception as exc:  # pylint: disable=broad-except
                print(f"[db_stats] pg_stat_statements unavailable: {exc}", file=sys.stderr)

            cur.execute(_TOP_SEQ_SCAN_TABLES_SQL, (args.limit,))
            _print_table(
                "Top tables by sequential scans",
                ["table", "seq_scan", "seq_tup_read", "idx_scan", "n_live_tup"],
                cur.fetchall(),
            )

            cur.execute(_UNUSED_INDEXES_SQL, (args.limit,))
            _print_table(
                "Largest unused indexes (idx_scan = 0)",
                ["table", "index", "size", "idx_scan"],
                cur.fetchall(),
            )
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
