"""Bulk INSERT helper for SQLite→PostgreSQL migration (psycopg3-compatible execute_values)."""

from typing import Any, Iterable, Sequence


def execute_values(
    cur: Any,
    sql: str,
    argslist: Iterable[Sequence[Any]],
    template: str | None = None,
    page_size: int = 100,
    fetch: bool = False,
) -> list[Any] | None:
    """
    Insert many rows in one or more statements.

    ``sql`` must contain a single ``%s`` placeholder where the VALUES clause
    belongs (legacy psycopg2.extras.execute_values compatibility).
    """
    rows = list(argslist)
    if not rows:
        return [] if fetch else None
    if "%s" not in sql:
        raise ValueError("sql must contain %s placeholder for VALUES expansion")

    ncols = len(rows[0])
    if template is None:
        template = "(" + ", ".join(["%s"] * ncols) + ")"

    result: list[Any] = []
    for page_start in range(0, len(rows), page_size):
        page = rows[page_start : page_start + page_size]
        values_sql = ", ".join([template] * len(page))
        page_sql = sql.replace("%s", values_sql, 1)
        flat_args = [item for row in page for item in row]
        cur.execute(page_sql, flat_args)
        if fetch:
            result.extend(cur.fetchall())
    return result if fetch else None
