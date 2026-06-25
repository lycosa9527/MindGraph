"""
PG-to-PG merge table operations (insert, preview, sequence reset).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import insert, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import Table

from models.domain.registry import Base
from services.admin.pg_merge_config import TABLE_MERGE_CONFIG
from services.admin.pg_merge_dedup import dedup_tuple, fingerprint_key
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)


def _row_for_orm_table(table: Table, values: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only keys that exist on the model table."""
    return {k: v for k, v in values.items() if k in table.c}


def _build_dedup_lookup(
    live_engine: Engine,
    table_name: str,
    pk_col: str,
    config: Dict[str, Any],
) -> Dict[Any, Any]:
    """Pre-fetch natural-key → live PK mapping for dedup checking."""
    dedup_key: Optional[str] = config.get("dedup_key")
    dedup_columns: Optional[Tuple[str, ...]] = config.get("dedup_columns")
    dedup_fingerprint: Optional[str] = config.get("dedup_fingerprint")

    if dedup_key:
        with live_engine.connect() as conn:
            rows = conn.execute(text(f'SELECT "{dedup_key}", "{pk_col}" FROM "{table_name}"'))
            return {r[0]: r[1] for r in rows if r[0] is not None}

    if dedup_columns:
        cols_sql = ", ".join(f'"{c}"' for c in dedup_columns)
        with live_engine.connect() as conn:
            rows = conn.execute(text(f'SELECT {cols_sql}, "{pk_col}" FROM "{table_name}"'))
            lookup: Dict[Any, Any] = {}
            for row in rows:
                parts = row[:-1]
                row_dict = dict(zip(dedup_columns, parts, strict=True))
                lookup[dedup_tuple(row_dict, dedup_columns)] = row[-1]
            return lookup

    if dedup_fingerprint:
        with live_engine.connect() as conn:
            rows = conn.execute(text(f'SELECT * FROM "{table_name}"')).mappings().all()
        fingerprint_lookup: Dict[Any, Any] = {}
        for row in rows:
            key = fingerprint_key(dedup_fingerprint, dict(row))
            if key is not None:
                fingerprint_lookup[key] = row[pk_col]
        return fingerprint_lookup

    return {}


def _fetch_live_watermark(
    live_engine: Engine,
    table_name: str,
    watermark_col: str,
) -> Optional[datetime]:
    """Return MAX(watermark_col) from live table, or None if empty."""
    with live_engine.connect() as conn:
        result = conn.execute(text(f'SELECT MAX("{watermark_col}") FROM "{table_name}"'))
        return result.scalar()


def _fetch_nullable_fk_cols(
    live_engine: Engine,
    table_name: str,
    fk_columns: List[str],
) -> Set[str]:
    """Return FK columns that are nullable in the live DB."""
    if not fk_columns:
        return set()
    with live_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :tbl AND is_nullable = 'YES' "
                "AND column_name = ANY(:cols)"
            ),
            {"tbl": table_name, "cols": fk_columns},
        )
        return {r[0] for r in rows}


def _load_user_org_cache(live_engine: Engine) -> Dict[int, int]:
    """Map live user id → organization_id for org backfill on merge."""
    with live_engine.connect() as conn:
        rows = conn.execute(text("SELECT id, organization_id FROM users WHERE organization_id IS NOT NULL"))
        return {row[0]: row[1] for row in rows}


def _backfill_org_from_user(
    values: Dict[str, Any],
    config: Dict[str, Any],
    user_org_cache: Dict[int, int],
) -> None:
    """Set organization_id from the mapped user when the dump row omitted it."""
    if not config.get("backfill_org_from_user"):
        return
    if values.get("organization_id") is not None:
        return
    user_id = values.get("user_id")
    if isinstance(user_id, int) and user_id in user_org_cache:
        values["organization_id"] = user_org_cache[user_id]


def _remap_fk_values(
    values: Dict[str, Any],
    fk_remaps: Dict[str, str],
    id_maps: Dict[str, Dict],
    nullable_fk_cols: Set[str],
) -> bool:
    """Remap FK columns; return True if a non-nullable FK is broken."""
    for col, source_table in fk_remaps.items():
        old_val = values.get(col)
        if old_val is None:
            continue
        source_map = id_maps.get(source_table, {})
        new_val = source_map.get(old_val)
        if new_val is not None:
            values[col] = new_val
        elif col in nullable_fk_cols:
            values[col] = None
        else:
            return True
    return False


def _is_duplicate(
    values: Dict[str, Any],
    config: Dict[str, Any],
    dedup_lookup: Dict[Any, Any],
    table_id_map: Dict[Any, Any],
    old_pk: Any,
    dedup_key: Optional[str],
    dedup_columns: Optional[Tuple[str, ...]],
    dedup_fingerprint: Optional[str],
) -> bool:
    """Return True when staging row already exists on live (maps old_pk in table_id_map)."""
    if dedup_key:
        key_val = values.get(dedup_key)
        if config.get("skip_dedup_key_when_null") and key_val is None:
            return False
        if key_val in dedup_lookup:
            table_id_map[old_pk] = dedup_lookup[key_val]
            return True
    elif dedup_columns:
        key_tuple = dedup_tuple(values, dedup_columns)
        if key_tuple in dedup_lookup:
            table_id_map[old_pk] = dedup_lookup[key_tuple]
            return True
    elif dedup_fingerprint:
        fp = fingerprint_key(dedup_fingerprint, values)
        if fp is not None and fp in dedup_lookup:
            table_id_map[old_pk] = dedup_lookup[fp]
            return True
    return False


def _apply_self_ref_updates(
    live_engine: Engine,
    table_name: str,
    pk_col: str,
    self_ref_col: str,
    updates: List[Tuple[Any, Any]],
    table_id_map: Dict[Any, Any],
) -> None:
    """Resolve self-referencing FK columns after all rows are inserted."""
    resolved: List[Dict[str, Any]] = []
    for new_pk, old_ref_val in updates:
        new_ref_val = table_id_map.get(old_ref_val)
        if new_ref_val is not None:
            resolved.append({"ref": new_ref_val, "pk": new_pk})

    if not resolved:
        return

    update_sql = text(f'UPDATE "{table_name}" SET "{self_ref_col}" = :ref WHERE "{pk_col}" = :pk')
    applied = 0
    with live_engine.connect() as conn:
        txn = conn.begin()
        try:
            for params in resolved:
                sp = conn.begin_nested()
                try:
                    conn.execute(update_sql, params)
                    sp.commit()
                    applied += 1
                except DATABASE_ERRORS as exc:
                    sp.rollback()
                    logger.debug(
                        "[PGMerge] Self-ref update failed for %s pk=%s: %s",
                        table_name,
                        params["pk"],
                        exc,
                    )
            txn.commit()
        except DATABASE_ERRORS:
            txn.rollback()
            raise

    if applied:
        logger.info(
            "[PGMerge] %s: applied %d self-ref updates for %s",
            table_name,
            applied,
            self_ref_col,
        )


def _classify_row(
    table_name: str,
    config: Dict[str, Any],
    staging_engine: Engine,
    live_engine: Engine,
    id_maps: Dict[str, Dict],
) -> Dict[str, int]:
    """Dry-run merge counts for one table without writing to live DB."""
    pk_col = config.get("pk_column", "id")
    pk_type = config.get("pk_type", "serial")
    dedup_key: Optional[str] = config.get("dedup_key")
    dedup_columns: Optional[Tuple[str, ...]] = config.get("dedup_columns")
    dedup_fingerprint: Optional[str] = config.get("dedup_fingerprint")
    fk_remaps: Dict[str, str] = config.get("fk_remaps", {})
    singleton = config.get("singleton_user", False)
    watermark_col: Optional[str] = config.get("incremental_watermark")
    preserve_pk = config.get("preserve_staging_pk", False)

    with staging_engine.connect() as conn:
        rows = conn.execute(text(f'SELECT * FROM "{table_name}"')).mappings().all()

    if not rows:
        return {"new_rows": 0, "duplicate_rows": 0, "orphaned_rows": 0}

    dedup_lookup = _build_dedup_lookup(live_engine, table_name, pk_col, config)
    nullable_fk_cols = _fetch_nullable_fk_cols(live_engine, table_name, list(fk_remaps.keys()))

    singleton_map: Dict[int, int] = {}
    if singleton:
        with live_engine.connect() as conn:
            result = conn.execute(text(f'SELECT "user_id", "{pk_col}" FROM "{table_name}"'))
            singleton_map = {r[0]: r[1] for r in result}

    existing_uuids: Set[str] = set()
    if pk_type in ("uuid", "string_pk"):
        with live_engine.connect() as conn:
            result = conn.execute(text(f'SELECT "{pk_col}" FROM "{table_name}"'))
            existing_uuids = {r[0] for r in result}

    existing_pks: Set[Any] = set()
    if preserve_pk:
        with live_engine.connect() as conn:
            result = conn.execute(text(f'SELECT "{pk_col}" FROM "{table_name}"'))
            existing_pks = {r[0] for r in result}

    live_watermark = None
    if watermark_col:
        live_watermark = _fetch_live_watermark(live_engine, table_name, watermark_col)

    user_org_cache: Dict[int, int] = {}
    if config.get("backfill_org_from_user"):
        user_org_cache = _load_user_org_cache(live_engine)

    new_rows = 0
    duplicate_rows = 0
    orphaned_rows = 0
    scratch_id_map: Dict[Any, Any] = {}

    for row in rows:
        values = dict(row)
        old_pk = values[pk_col]

        broken = _remap_fk_values(values, fk_remaps, id_maps, nullable_fk_cols)
        if broken:
            orphaned_rows += 1
            continue

        _backfill_org_from_user(values, config, user_org_cache)

        if singleton:
            live_uid = values.get("user_id")
            if live_uid is not None and live_uid in singleton_map:
                duplicate_rows += 1
                continue

        if _is_duplicate(
            values,
            config,
            dedup_lookup,
            scratch_id_map,
            old_pk,
            dedup_key,
            dedup_columns,
            dedup_fingerprint,
        ):
            duplicate_rows += 1
            continue

        if pk_type in ("uuid", "string_pk") and old_pk in existing_uuids:
            duplicate_rows += 1
            continue

        if preserve_pk and old_pk in existing_pks:
            duplicate_rows += 1
            continue

        if watermark_col and live_watermark is not None:
            row_ts = values.get(watermark_col)
            if row_ts is not None and row_ts <= live_watermark:
                duplicate_rows += 1
                continue

        new_rows += 1

    return {
        "new_rows": new_rows,
        "duplicate_rows": duplicate_rows,
        "orphaned_rows": orphaned_rows,
    }


def _simulate_new_row_ids(
    table_name: str,
    config: Dict[str, Any],
    staging_engine: Engine,
    live_engine: Engine,
    id_maps: Dict[str, Dict],
) -> None:
    """Assign synthetic live PKs for rows that would be inserted (for downstream FK preview)."""
    pk_col = config.get("pk_column", "id")
    pk_type = config.get("pk_type", "serial")
    dedup_key: Optional[str] = config.get("dedup_key")
    dedup_columns: Optional[Tuple[str, ...]] = config.get("dedup_columns")
    dedup_fingerprint: Optional[str] = config.get("dedup_fingerprint")
    fk_remaps: Dict[str, str] = config.get("fk_remaps", {})
    singleton = config.get("singleton_user", False)
    watermark_col: Optional[str] = config.get("incremental_watermark")
    preserve_pk = config.get("preserve_staging_pk", False)

    with staging_engine.connect() as conn:
        rows = conn.execute(text(f'SELECT * FROM "{table_name}"')).mappings().all()

    if not rows:
        id_maps[table_name] = {}
        return

    dedup_lookup = _build_dedup_lookup(live_engine, table_name, pk_col, config)
    nullable_fk_cols = _fetch_nullable_fk_cols(live_engine, table_name, list(fk_remaps.keys()))

    singleton_map: Dict[int, int] = {}
    if singleton:
        with live_engine.connect() as conn:
            result = conn.execute(text(f'SELECT "user_id", "{pk_col}" FROM "{table_name}"'))
            singleton_map = {r[0]: r[1] for r in result}

    existing_uuids: Set[str] = set()
    if pk_type in ("uuid", "string_pk"):
        with live_engine.connect() as conn:
            result = conn.execute(text(f'SELECT "{pk_col}" FROM "{table_name}"'))
            existing_uuids = {r[0] for r in result}

    existing_pks: Set[Any] = set()
    if preserve_pk:
        with live_engine.connect() as conn:
            result = conn.execute(text(f'SELECT "{pk_col}" FROM "{table_name}"'))
            existing_pks = {r[0] for r in result}

    live_watermark = None
    if watermark_col:
        live_watermark = _fetch_live_watermark(live_engine, table_name, watermark_col)

    user_org_cache: Dict[int, int] = {}
    if config.get("backfill_org_from_user"):
        user_org_cache = _load_user_org_cache(live_engine)

    table_id_map: Dict[Any, Any] = dict(id_maps.get(table_name, {}))
    synthetic = 900_000_000

    for row in rows:
        values = dict(row)
        old_pk = values[pk_col]

        if _remap_fk_values(values, fk_remaps, id_maps, nullable_fk_cols):
            continue

        _backfill_org_from_user(values, config, user_org_cache)

        if singleton:
            live_uid = values.get("user_id")
            if live_uid is not None and live_uid in singleton_map:
                table_id_map[old_pk] = singleton_map[live_uid]
                continue

        if _is_duplicate(
            values,
            config,
            dedup_lookup,
            table_id_map,
            old_pk,
            dedup_key,
            dedup_columns,
            dedup_fingerprint,
        ):
            continue

        if pk_type in ("uuid", "string_pk") and old_pk in existing_uuids:
            table_id_map[old_pk] = old_pk
            continue

        if preserve_pk and old_pk in existing_pks:
            table_id_map[old_pk] = old_pk
            continue

        if watermark_col and live_watermark is not None:
            row_ts = values.get(watermark_col)
            if row_ts is not None and row_ts <= live_watermark:
                continue

        if pk_type == "serial" and not preserve_pk:
            table_id_map[old_pk] = synthetic
            synthetic += 1
        else:
            table_id_map[old_pk] = old_pk

    id_maps[table_name] = table_id_map


def preview_table(
    table_name: str,
    staging_engine: Engine,
    live_engine: Engine,
    id_maps: Dict[str, Dict],
    *,
    simulate_ids: bool = False,
) -> Dict[str, int]:
    """Dry-run counts for merge preview."""
    config = TABLE_MERGE_CONFIG[table_name]
    counts = _classify_row(table_name, config, staging_engine, live_engine, id_maps)
    if simulate_ids:
        _simulate_new_row_ids(table_name, config, staging_engine, live_engine, id_maps)
    return counts


def merge_table(
    table_name: str,
    staging_engine: Engine,
    live_engine: Engine,
    id_maps: Dict[str, Dict],
) -> Dict[str, Any]:
    """Merge a single table from staging into live."""
    config = TABLE_MERGE_CONFIG[table_name]
    pk_col = config.get("pk_column", "id")
    pk_type = config.get("pk_type", "serial")
    dedup_key: Optional[str] = config.get("dedup_key")
    dedup_columns: Optional[Tuple[str, ...]] = config.get("dedup_columns")
    dedup_fingerprint: Optional[str] = config.get("dedup_fingerprint")
    fk_remaps: Dict[str, str] = config.get("fk_remaps", {})
    self_ref: Optional[str] = config.get("self_ref")
    singleton = config.get("singleton_user", False)
    watermark_col: Optional[str] = config.get("incremental_watermark")
    preserve_pk = config.get("preserve_staging_pk", False)

    with staging_engine.connect() as conn:
        rows = conn.execute(text(f'SELECT * FROM "{table_name}"')).mappings().all()

    if not rows:
        id_maps[table_name] = {}
        return {"inserted": 0, "skipped": 0, "orphaned": 0}

    dedup_lookup = _build_dedup_lookup(live_engine, table_name, pk_col, config)
    nullable_fk_cols = _fetch_nullable_fk_cols(live_engine, table_name, list(fk_remaps.keys()))

    singleton_map: Dict[int, int] = {}
    if singleton:
        with live_engine.connect() as conn:
            result = conn.execute(text(f'SELECT "user_id", "{pk_col}" FROM "{table_name}"'))
            singleton_map = {r[0]: r[1] for r in result}

    existing_uuids: Set[str] = set()
    if pk_type in ("uuid", "string_pk"):
        with live_engine.connect() as conn:
            result = conn.execute(text(f'SELECT "{pk_col}" FROM "{table_name}"'))
            existing_uuids = {r[0] for r in result}

    existing_pks: Set[Any] = set()
    if preserve_pk:
        with live_engine.connect() as conn:
            result = conn.execute(text(f'SELECT "{pk_col}" FROM "{table_name}"'))
            existing_pks = {r[0] for r in result}

    live_watermark = None
    if watermark_col:
        live_watermark = _fetch_live_watermark(live_engine, table_name, watermark_col)

    user_org_cache: Dict[int, int] = {}
    if config.get("backfill_org_from_user"):
        user_org_cache = _load_user_org_cache(live_engine)

    table_id_map: Dict[Any, Any] = {}
    inserted = 0
    skipped = 0
    orphaned = 0
    self_ref_updates: List[Tuple[Any, Any]] = []
    pending_inserts: List[Tuple[Any, Dict[str, Any], Optional[Any]]] = []
    inserted_user_ids: List[int] = []

    for row in rows:
        values = dict(row)
        old_pk = values[pk_col]

        broken = _remap_fk_values(values, fk_remaps, id_maps, nullable_fk_cols)
        if broken:
            orphaned += 1
            continue

        _backfill_org_from_user(values, config, user_org_cache)

        if singleton:
            live_uid = values.get("user_id")
            if live_uid is not None and live_uid in singleton_map:
                table_id_map[old_pk] = singleton_map[live_uid]
                skipped += 1
                continue

        if _is_duplicate(
            values,
            config,
            dedup_lookup,
            table_id_map,
            old_pk,
            dedup_key,
            dedup_columns,
            dedup_fingerprint,
        ):
            skipped += 1
            continue

        if pk_type in ("uuid", "string_pk") and old_pk in existing_uuids:
            table_id_map[old_pk] = old_pk
            skipped += 1
            continue

        if preserve_pk and old_pk in existing_pks:
            table_id_map[old_pk] = old_pk
            skipped += 1
            continue

        if watermark_col and live_watermark is not None:
            row_ts = values.get(watermark_col)
            if row_ts is not None and row_ts <= live_watermark:
                skipped += 1
                continue

        old_self_ref = None
        if self_ref and values.get(self_ref) is not None:
            old_self_ref = values[self_ref]
            values[self_ref] = None

        if pk_type == "serial" and not preserve_pk:
            values.pop(pk_col, None)

        pending_inserts.append((old_pk, values, old_self_ref))

    if pending_inserts:
        try:
            orm_table = Base.metadata.tables[table_name]
        except KeyError as err:
            raise KeyError(
                f"Table {table_name!r} is not on Base.metadata — register the model in models/domain/registry.py"
            ) from err

        with live_engine.connect() as conn:
            txn = conn.begin()
            try:
                for old_pk, values, old_self_ref in pending_inserts:
                    savepoint = conn.begin_nested()
                    try:
                        row = _row_for_orm_table(orm_table, values)
                        if preserve_pk:
                            cols = list(row.keys())
                            cols_sql = ", ".join(f'"{c}"' for c in cols)
                            placeholders = ", ".join(f":{c}" for c in cols)
                            sql = (
                                f"INSERT INTO {table_name} ({cols_sql}) "
                                f"VALUES ({placeholders}) ON CONFLICT ({pk_col}) DO NOTHING"
                            )
                            result = conn.execute(text(sql), row)
                            if result.rowcount == 0:
                                table_id_map[old_pk] = old_pk
                                savepoint.commit()
                                skipped += 1
                                continue
                            new_pk = old_pk
                        else:
                            stmt = insert(orm_table).values(**row)
                            if pk_type == "serial":
                                stmt = stmt.returning(orm_table.c[pk_col])
                            result = conn.execute(stmt)
                            new_pk = result.scalar() if pk_type == "serial" else old_pk

                        table_id_map[old_pk] = new_pk
                        savepoint.commit()
                        inserted += 1
                        uid = row.get("user_id")
                        if isinstance(uid, int):
                            inserted_user_ids.append(uid)
                        if old_self_ref is not None:
                            self_ref_updates.append((new_pk, old_self_ref))

                        if dedup_key and not config.get("skip_dedup_key_when_null"):
                            key_val = row.get(dedup_key)
                            if key_val is not None:
                                dedup_lookup[key_val] = new_pk
                        elif dedup_columns:
                            key_tuple = dedup_tuple(row, dedup_columns)
                            dedup_lookup[key_tuple] = new_pk
                        elif dedup_fingerprint:
                            fp = fingerprint_key(dedup_fingerprint, row)
                            if fp is not None:
                                dedup_lookup[fp] = new_pk

                    except DATABASE_ERRORS as exc:
                        savepoint.rollback()
                        logger.debug(
                            "[PGMerge] Insert failed %s pk=%s: %s",
                            table_name,
                            old_pk,
                            exc,
                        )
                        orphaned += 1
                txn.commit()
            except DATABASE_ERRORS:
                txn.rollback()
                raise

    if self_ref and self_ref_updates:
        _apply_self_ref_updates(
            live_engine,
            table_name,
            pk_col,
            self_ref,
            self_ref_updates,
            table_id_map,
        )

    id_maps[table_name] = table_id_map
    logger.info(
        "[PGMerge] %s: inserted=%d skipped=%d orphaned=%d",
        table_name,
        inserted,
        skipped,
        orphaned,
    )
    merge_result: Dict[str, Any] = {"inserted": inserted, "skipped": skipped, "orphaned": orphaned}
    if inserted_user_ids:
        merge_result["_inserted_user_ids"] = inserted_user_ids
    return merge_result


def reset_all_sequences(live_engine: Engine) -> None:
    """Reset all serial PK sequences to max(pk)+1 after merge."""
    with live_engine.connect() as conn:
        txn = conn.begin()
        try:
            for table_name, config in TABLE_MERGE_CONFIG.items():
                if config.get("pk_type") != "serial":
                    continue
                pk_col = config.get("pk_column", "id")
                sp = conn.begin_nested()
                try:
                    seq_name = conn.execute(
                        text("SELECT pg_get_serial_sequence(:tbl, :col)"),
                        {"tbl": table_name, "col": pk_col},
                    ).scalar()
                    if seq_name is None:
                        sp.rollback()
                        continue
                    conn.execute(
                        text(f'SELECT setval(:seq, COALESCE((SELECT MAX("{pk_col}") FROM "{table_name}"), 1))'),
                        {"seq": seq_name},
                    )
                    sp.commit()
                except DATABASE_ERRORS as exc:
                    sp.rollback()
                    logger.debug(
                        "[PGMerge] Sequence reset skipped for %s: %s",
                        table_name,
                        exc,
                    )
            txn.commit()
        except DATABASE_ERRORS:
            txn.rollback()
            raise
