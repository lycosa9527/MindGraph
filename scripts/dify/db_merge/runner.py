"""
Dump the Dify database and run a history merge.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from scripts.dify.db_merge.compose import run_psql, stream_pg_dump
from scripts.dify.db_merge.models import ComposeError, ComposeTarget, MergePlan
from scripts.dify.db_merge.schema import CATALOG_SQL, SchemaFacts, parse_column_csv
from scripts.dify.db_merge.sql import apps_inventory_sql, build_merge_sql


def list_apps(target: ComposeTarget, timeout: int) -> str:
    """CSV of apps in this Dify database."""
    facts = inspect_schema(target, timeout)
    return run_psql(target, apps_inventory_sql(facts), timeout)


def dump_database(target: ComposeTarget, out_dir: Path, timeout: int) -> tuple[Path, Path, str]:
    """Write a custom-format dump and an apps CSV. Returns both paths and the CSV text."""
    directory = out_dir.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d_%H%M%SZ")
    dump_path = directory / f"dify_{stamp}.dump"
    apps_path = directory / f"dify_{stamp}.apps.csv"
    facts = inspect_schema(target, timeout)
    stream_pg_dump(target, dump_path, timeout)
    try:
        csv_text = run_psql(target, apps_inventory_sql(facts), timeout)
    except ComposeError as exc:
        raise ComposeError(f"{exc} (database dump kept at {dump_path})") from exc
    apps_path.write_text(csv_text, encoding="utf-8")
    return dump_path, apps_path, csv_text


def merge_script(target: ComposeTarget, plan: MergePlan, timeout: int) -> str:
    """Build the psql script for this live schema."""
    return build_merge_sql(plan, inspect_schema(target, timeout))


def execute_sql(target: ComposeTarget, sql: str, timeout: int) -> str:
    """Run a psql script already built for this database."""
    return run_psql(target, sql, timeout)


def inspect_schema(target: ComposeTarget, timeout: int) -> SchemaFacts:
    """Read the column catalog from the live database."""
    catalog = run_psql(target, CATALOG_SQL, timeout)
    return SchemaFacts.from_catalog(parse_column_csv(catalog))
