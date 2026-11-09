"""Export a sample of real diagrams as local rendering fixtures.

Reads the local PostgreSQL with ``DATABASE_MIGRATION_URL`` (bypasses RLS) in a
read-only transaction. For each diagram type it takes a deterministic sample
spread from the smallest to the largest spec, drops the id, owner, and title,
and writes ``tmp/real_diagrams/fixtures/<type>-NN.json`` (``tmp/`` is
gitignored; the files hold real labels and must not be committed).

Usage::

    python -m scripts.render_check.export_real_diagrams --per-type 6 --mind-maps 12
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

import psycopg
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tmp" / "real_diagrams" / "fixtures"
MIND_MAP_TYPES = frozenset({"mindmap", "mind_map"})
CANDIDATES_PER_TYPE = 400
DROPPED_SPEC_KEYS = frozenset({"llm_results"})

CANDIDATE_SQL = """
select diagram_type, language, spec, length(spec::text) as size
from diagrams
where not is_deleted and spec is not null and diagram_type = %s
order by md5(id::text)
limit %s
"""


def _migration_url() -> str:
    url = dotenv_values(REPO_ROOT / ".env").get("DATABASE_MIGRATION_URL")
    if not url:
        raise SystemExit("DATABASE_MIGRATION_URL is not set in .env")
    return url


def _spread(rows: list[tuple[str, str, Any, int]], count: int) -> list[tuple[str, str, Any, int]]:
    """Evenly spaced picks from rows sorted by spec size (small to large)."""
    ordered = sorted(rows, key=lambda row: row[3])
    if len(ordered) <= count:
        return ordered
    step = (len(ordered) - 1) / max(count - 1, 1)
    return [ordered[round(index * step)] for index in range(count)]


def _clean_spec(spec: Any) -> dict[str, Any] | None:
    if isinstance(spec, str):
        spec = json.loads(spec)
    if not isinstance(spec, dict):
        return None
    source = cast(dict[str, Any], spec)
    return {key: value for key, value in source.items() if key not in DROPPED_SPEC_KEYS}


def export_fixtures(per_type: int, mind_maps: int) -> int:
    """Write fixtures; returns how many files were written."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for stale in FIXTURE_DIR.glob("*.json"):
        stale.unlink()
    written = 0
    with psycopg.connect(_migration_url(), connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("set transaction read only")
        cur.execute("select distinct diagram_type from diagrams where not is_deleted")
        types = [row[0] for row in cast(list[tuple[Any, ...]], cur.fetchall())]
        for diagram_type in sorted(t for t in types if isinstance(t, str)):
            count = mind_maps if diagram_type in MIND_MAP_TYPES else per_type
            cur.execute(CANDIDATE_SQL, (diagram_type, CANDIDATES_PER_TYPE))
            rows = cast(list[tuple[str, str, Any, int]], cur.fetchall())
            for index, (dtype, language, spec, size) in enumerate(_spread(rows, count), start=1):
                cleaned = _clean_spec(spec)
                if cleaned is None:
                    continue
                name = f"{dtype}-{index:02d}"
                payload = {"name": name, "diagram_type": dtype, "language": language, "size": size, "spec": cleaned}
                (FIXTURE_DIR / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                written += 1
    return written


def main() -> None:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="Export real diagrams as local rendering fixtures.")
    parser.add_argument("--per-type", type=int, default=6, help="fixtures per thinking-map type")
    parser.add_argument("--mind-maps", type=int, default=12, help="fixtures per mind-map type")
    args = parser.parse_args()
    written = export_fixtures(int(args.per_type), int(args.mind_maps))
    print(f"wrote {written} fixtures to {FIXTURE_DIR}")


if __name__ == "__main__":
    main()
