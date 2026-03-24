"""
SQLite-to-PostgreSQL Merge Service

Analyse a legacy SQLite database, detect orphaned records, build
user/org ID mappings (by phone / org-code), and merge data into the
running PostgreSQL instance without losing any existing PG records.

Tables handled (in FK-safe order):
    organizations, users, api_keys, token_usage,
    dashboard_activities, update_notifications,
    update_notification_dismissed

Skipped (obsolete -- now Redis-backed):
    captchas, sms_verifications

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved -- Proprietary License
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

SKIP_TABLES: Set[str] = {"captchas", "sms_verifications"}

MERGEABLE_TABLES: List[str] = [
    "organizations",
    "users",
    "api_keys",
    "token_usage",
    "dashboard_activities",
    "update_notifications",
    "update_notification_dismissed",
]

_USER_DEFAULT_COLUMNS: Dict[str, Any] = {
    "role": "user",
    "avatar": "🐈‍⬛",
    "ui_language": None,
    "prompt_language": None,
    "workshop_last_seen_at": None,
}

_ORG_DEFAULT_COLUMNS: Dict[str, Any] = {
    "display_name": None,
}

_USER_COLUMN_LIMITS: Dict[str, int] = {
    "phone": 20,
    "name": 100,
    "avatar": 50,
    "role": 20,
}


# ── helpers ──────────────────────────────────────────────────────────

def _sqlite_tables(conn: sqlite3.Connection) -> Dict[str, int]:
    """Return {table_name: row_count} for every user table in the SQLite db."""
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    result: Dict[str, int] = {}
    for (name,) in cur.fetchall():
        cur.execute(f'SELECT COUNT(*) FROM [{name}]')
        result[name] = cur.fetchone()[0]
    return result


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info([{table}])")
    return [row[1] for row in cur.fetchall()]


def _pg_existing_phones(pg_engine: Engine) -> Dict[str, int]:
    """Return {phone: user_id} for every user already in PostgreSQL."""
    with pg_engine.connect() as conn:
        rows = conn.execute(text("SELECT phone, id FROM users"))
        return {r[0]: r[1] for r in rows}


def _pg_existing_org_names(pg_engine: Engine) -> Dict[str, int]:
    """Return {name: org_id} for every org already in PostgreSQL."""
    with pg_engine.connect() as conn:
        rows = conn.execute(text("SELECT name, id FROM organizations"))
        return {r[0]: r[1] for r in rows}


def _pg_existing_api_keys(pg_engine: Engine) -> Set[str]:
    with pg_engine.connect() as conn:
        rows = conn.execute(text("SELECT key FROM api_keys"))
        return {r[0] for r in rows}


def _pg_token_usage_keys(pg_engine: Engine) -> Set[str]:
    """Build a set of (user_id, session_id, created_at) strings for dedup."""
    with pg_engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT user_id, session_id, created_at FROM token_usage"
        ))
        return {
            f"{r[0]}|{r[1]}|{r[2]}" for r in rows
        }


def _validate_user_column_lengths(
    values: Dict[str, Any], sq_id: int,
) -> bool:
    """Return True if all string values fit within PG column limits."""
    for col, max_len in _USER_COLUMN_LIMITS.items():
        val = values.get(col)
        if val is not None and isinstance(val, str) and len(val) > max_len:
            logger.warning(
                "[SQLiteMerge] Skipping SQLite user id=%d: "
                "%s='%s' exceeds VARCHAR(%d)",
                sq_id, col, val, max_len,
            )
            return False
    return True


def _pg_boolean_columns(pg_engine: Engine, table: str) -> Set[str]:
    """Return the set of column names that are BOOLEAN in PostgreSQL."""
    with pg_engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :tbl AND data_type = 'boolean'"
        ), {"tbl": table})
        return {r[0] for r in rows}


def _coerce_booleans(
    values: Dict[str, Any], bool_cols: Set[str],
) -> None:
    """Convert SQLite integer booleans (0/1) to Python bool in-place."""
    for col in bool_cols:
        val = values.get(col)
        if isinstance(val, int):
            values[col] = bool(val)


# ── SQLite orphan cleanup ────────────────────────────────────────────

def cleanup_sqlite_orphans(sqlite_path: Path) -> Dict[str, int]:
    """Delete orphaned records from a SQLite file and return counts."""
    conn = sqlite3.connect(str(sqlite_path))
    try:
        return _cleanup_sqlite_orphans_impl(conn)
    finally:
        conn.close()


def _cleanup_sqlite_orphans_impl(sq: sqlite3.Connection) -> Dict[str, int]:
    cur = sq.cursor()
    table_names = set(_sqlite_tables(sq).keys())
    cleaned: Dict[str, int] = {}

    cur.execute(
        "DELETE FROM users "
        "WHERE organization_id IS NOT NULL "
        "AND organization_id NOT IN (SELECT id FROM organizations)"
    )
    if cur.rowcount > 0:
        cleaned["users_nullified_missing_org"] = cur.rowcount

    if "token_usage" in table_names:
        cur.execute(
            "DELETE FROM token_usage "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)"
        )
        if cur.rowcount > 0:
            cleaned["token_usage_deleted_missing_user"] = cur.rowcount

        cur.execute(
            "DELETE FROM token_usage "
            "WHERE organization_id IS NOT NULL "
            "AND organization_id NOT IN (SELECT id FROM organizations)"
        )
        if cur.rowcount > 0:
            cleaned["token_usage_deleted_missing_org"] = cur.rowcount

    if "dashboard_activities" in table_names:
        cur.execute(
            "DELETE FROM dashboard_activities "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)"
        )
        if cur.rowcount > 0:
            cleaned["dashboard_deleted_missing_user"] = cur.rowcount

    if "update_notification_dismissed" in table_names:
        cur.execute(
            "DELETE FROM update_notification_dismissed "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)"
        )
        if cur.rowcount > 0:
            cleaned["dismissed_deleted_missing_user"] = cur.rowcount

    sq.commit()

    total = sum(cleaned.values())
    logger.info(
        "[SQLiteMerge] SQLite orphan cleanup: %d records removed (%s)",
        total, cleaned,
    )
    return cleaned


# ── analyse ──────────────────────────────────────────────────────────

def analyze_sqlite(
    sqlite_path: Path,
    pg_engine: Engine,
) -> Dict[str, Any]:
    """
    Open a SQLite file and compare its contents against the live PG database.

    Returns a dict with keys:
        sqlite_tables   -- {table: row_count}
        orphans         -- {description: count}
        user_mapping    -- {sqlite_id: pg_id} for matched users
        org_mapping     -- {sqlite_id: pg_id} for matched orgs
        new_users       -- count of users only in SQLite
        matched_users   -- count of users matched by phone
        new_orgs        -- count of orgs only in SQLite
        matched_orgs    -- count of orgs matched by code
        skipped_tables  -- list of skipped table names
        merge_preview   -- per-table {table: {"total": n, "new": n, "skip": n}}
    """
    conn = sqlite3.connect(str(sqlite_path))
    try:
        return _analyze_impl(conn, pg_engine)
    finally:
        conn.close()


def _analyze_impl(
    sq: sqlite3.Connection,
    pg_engine: Engine,
) -> Dict[str, Any]:
    cur = sq.cursor()
    table_counts = _sqlite_tables(sq)

    # ── orphan detection ──
    orphans: Dict[str, int] = {}

    cur.execute(
        "SELECT COUNT(*) FROM users "
        "WHERE organization_id IS NOT NULL "
        "AND organization_id NOT IN (SELECT id FROM organizations)"
    )
    orphans["users_with_missing_org"] = cur.fetchone()[0]

    if "token_usage" in table_counts:
        cur.execute(
            "SELECT COUNT(*) FROM token_usage "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)"
        )
        orphans["token_usage_missing_user"] = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM token_usage "
            "WHERE organization_id IS NOT NULL "
            "AND organization_id NOT IN (SELECT id FROM organizations)"
        )
        orphans["token_usage_missing_org"] = cur.fetchone()[0]

    # ── user mapping ──
    pg_phones = _pg_existing_phones(pg_engine)
    cur.execute("SELECT id, phone FROM users")
    sq_users = cur.fetchall()

    user_mapping: Dict[int, int] = {}
    new_user_ids: List[int] = []
    for sq_id, phone in sq_users:
        if phone in pg_phones:
            user_mapping[sq_id] = pg_phones[phone]
        else:
            new_user_ids.append(sq_id)

    # ── org mapping (by name) ──
    pg_names = _pg_existing_org_names(pg_engine)
    cur.execute("SELECT id, name FROM organizations")
    sq_orgs = cur.fetchall()

    org_mapping: Dict[int, int] = {}
    new_org_ids: List[int] = []
    for sq_id, name in sq_orgs:
        if name in pg_names:
            org_mapping[sq_id] = pg_names[name]
        else:
            new_org_ids.append(sq_id)

    # ── per-table merge preview ──
    merge_preview: Dict[str, Dict[str, int]] = {}
    for table in MERGEABLE_TABLES:
        total = table_counts.get(table, 0)
        if table == "organizations":
            merge_preview[table] = {
                "total": total,
                "new": len(new_org_ids),
                "skip": len(org_mapping),
            }
        elif table == "users":
            merge_preview[table] = {
                "total": total,
                "new": len(new_user_ids),
                "skip": len(user_mapping),
            }
        elif table == "token_usage":
            merge_preview[table] = {
                "total": total,
                "new": total - orphans.get("token_usage_missing_user", 0),
                "skip": orphans.get("token_usage_missing_user", 0),
            }
        else:
            merge_preview[table] = {"total": total, "new": total, "skip": 0}

    skipped = [t for t in table_counts if t in SKIP_TABLES]

    return {
        "sqlite_tables": table_counts,
        "orphans": orphans,
        "user_mapping": user_mapping,
        "org_mapping": org_mapping,
        "new_users": len(new_user_ids),
        "matched_users": len(user_mapping),
        "new_orgs": len(new_org_ids),
        "matched_orgs": len(org_mapping),
        "skipped_tables": skipped,
        "merge_preview": merge_preview,
    }


# ── merge ────────────────────────────────────────────────────────────

def merge_sqlite_into_postgres(
    sqlite_path: Path,
    pg_engine: Engine,
) -> Dict[str, Any]:
    """
    Execute a full SQLite-into-PG merge.

    Returns a results dict with per-table inserted/skipped counts.
    """
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    try:
        return _merge_impl(conn, pg_engine)
    finally:
        conn.close()


def _merge_impl(
    sq: sqlite3.Connection,
    pg_engine: Engine,
) -> Dict[str, Any]:
    cur = sq.cursor()
    results: Dict[str, Dict[str, int]] = {}
    started = datetime.utcnow()

    sq_table_names = set(_sqlite_tables(sq).keys())

    # ── build mappings ──
    pg_phones = _pg_existing_phones(pg_engine)
    pg_names = _pg_existing_org_names(pg_engine)

    cur.execute("SELECT id, phone FROM users")
    user_map: Dict[int, Optional[int]] = {}
    new_user_sq_ids: List[int] = []
    for sq_id, phone in cur.fetchall():
        if phone in pg_phones:
            user_map[sq_id] = pg_phones[phone]
        else:
            new_user_sq_ids.append(sq_id)

    cur.execute("SELECT id, name FROM organizations")
    org_map: Dict[int, Optional[int]] = {}
    new_org_sq_ids: List[int] = []
    for sq_id, name in cur.fetchall():
        if name in pg_names:
            org_map[sq_id] = pg_names[name]
        else:
            new_org_sq_ids.append(sq_id)

    # ── pre-fetch boolean column sets for type coercion ──
    bool_cols_cache: Dict[str, Set[str]] = {}
    for tbl in MERGEABLE_TABLES:
        if tbl in sq_table_names or tbl in ("organizations", "users"):
            bool_cols_cache[tbl] = _pg_boolean_columns(pg_engine, tbl)

    # ── 1. organizations ──
    results["organizations"] = _merge_organizations(
        sq, pg_engine, org_map, new_org_sq_ids,
        bool_cols_cache.get("organizations", set()),
    )

    # ── 2. users ──
    results["users"] = _merge_users(
        sq, pg_engine, user_map, new_user_sq_ids, org_map,
        bool_cols_cache.get("users", set()),
    )

    # ── 3. api_keys ──
    if "api_keys" in sq_table_names:
        results["api_keys"] = _merge_api_keys(
            sq, pg_engine, org_map,
            bool_cols_cache.get("api_keys", set()),
        )

    # ── 4. token_usage ──
    if "token_usage" in sq_table_names:
        results["token_usage"] = _merge_token_usage(
            sq, pg_engine, user_map, org_map,
            bool_cols_cache.get("token_usage", set()),
        )

    # ── 5. dashboard_activities ──
    if "dashboard_activities" in sq_table_names:
        results["dashboard_activities"] = _merge_dashboard_activities(
            sq, pg_engine, user_map,
            bool_cols_cache.get("dashboard_activities", set()),
        )

    # ── 6. update_notifications ──
    if "update_notifications" in sq_table_names:
        results["update_notifications"] = _merge_simple_table(
            sq, pg_engine, "update_notifications",
            bool_cols_cache.get("update_notifications", set()),
        )

    # ── 7. update_notification_dismissed ──
    if "update_notification_dismissed" in sq_table_names:
        results["update_notification_dismissed"] = (
            _merge_update_notification_dismissed(
                sq, pg_engine, user_map,
                bool_cols_cache.get("update_notification_dismissed", set()),
            )
        )

    # ── reset sequences ──
    _reset_sequences(pg_engine)

    elapsed = (datetime.utcnow() - started).total_seconds()
    logger.info("[SQLiteMerge] Merge completed in %.1fs", elapsed)

    return {
        "tables": results,
        "elapsed_seconds": round(elapsed, 1),
    }


# ── per-table merge helpers ──────────────────────────────────────────

def _merge_organizations(
    sq: sqlite3.Connection,
    pg_engine: Engine,
    org_map: Dict[int, Optional[int]],
    new_org_sq_ids: List[int],
    bool_cols: Set[str],
) -> Dict[str, int]:
    if not new_org_sq_ids:
        return {"inserted": 0, "skipped": len(org_map)}

    cur = sq.cursor()
    sq_cols = _sqlite_columns(sq, "organizations")

    inserted = 0
    for sq_id in new_org_sq_ids:
        cur.execute(
            "SELECT * FROM organizations WHERE id = ?", (sq_id,)
        )
        row = cur.fetchone()
        if row is None:
            continue

        values = {sq_cols[i]: row[i] for i in range(len(sq_cols))}
        values.pop("id")
        for col, default in _ORG_DEFAULT_COLUMNS.items():
            if col not in values:
                values[col] = default
        _coerce_booleans(values, bool_cols)

        col_names = list(values.keys())
        placeholders = ", ".join(f":{c}" for c in col_names)
        cols_sql = ", ".join(f'"{c}"' for c in col_names)

        with pg_engine.begin() as conn:
            result = conn.execute(
                text(f'INSERT INTO organizations ({cols_sql}) '
                     f'VALUES ({placeholders}) RETURNING id'),
                values,
            )
            new_pg_id = result.scalar()
            org_map[sq_id] = new_pg_id
            inserted += 1

    logger.info(
        "[SQLiteMerge] organizations: inserted=%d, skipped=%d",
        inserted, len(org_map) - inserted,
    )
    return {"inserted": inserted, "skipped": len(org_map) - inserted}


def _merge_users(
    sq: sqlite3.Connection,
    pg_engine: Engine,
    user_map: Dict[int, Optional[int]],
    new_user_sq_ids: List[int],
    org_map: Dict[int, Optional[int]],
    bool_cols: Set[str],
) -> Dict[str, int]:
    if not new_user_sq_ids:
        return {"inserted": 0, "skipped": len(user_map)}

    cur = sq.cursor()
    sq_cols = _sqlite_columns(sq, "users")
    inserted = 0
    rejected = 0

    for sq_id in new_user_sq_ids:
        cur.execute("SELECT * FROM users WHERE id = ?", (sq_id,))
        row = cur.fetchone()
        if row is None:
            continue

        values: Dict[str, Any] = {}
        for i, col in enumerate(sq_cols):
            if col == "id":
                continue
            if col == "organization_id" and row[i] is not None:
                values[col] = org_map.get(row[i])
            else:
                values[col] = row[i]

        for col, default in _USER_DEFAULT_COLUMNS.items():
            if col not in values:
                values[col] = default

        if not _validate_user_column_lengths(values, sq_id):
            rejected += 1
            continue

        _coerce_booleans(values, bool_cols)

        col_names = list(values.keys())
        placeholders = ", ".join(f":{c}" for c in col_names)
        cols_sql = ", ".join(f'"{c}"' for c in col_names)

        with pg_engine.begin() as conn:
            result = conn.execute(
                text(f'INSERT INTO users ({cols_sql}) '
                     f'VALUES ({placeholders}) RETURNING id'),
                values,
            )
            new_pg_id = result.scalar()
            user_map[sq_id] = new_pg_id
            inserted += 1

    logger.info(
        "[SQLiteMerge] users: inserted=%d, skipped=%d, rejected=%d",
        inserted, len(user_map) - inserted, rejected,
    )
    return {
        "inserted": inserted,
        "skipped": len(user_map) - inserted,
        "rejected": rejected,
    }


def _merge_api_keys(
    sq: sqlite3.Connection,
    pg_engine: Engine,
    org_map: Dict[int, Optional[int]],
    bool_cols: Set[str],
) -> Dict[str, int]:
    existing_keys = _pg_existing_api_keys(pg_engine)
    cur = sq.cursor()
    sq_cols = _sqlite_columns(sq, "api_keys")
    cur.execute("SELECT * FROM api_keys")
    rows = cur.fetchall()

    inserted = 0
    skipped = 0
    for row in rows:
        values = {sq_cols[i]: row[i] for i in range(len(sq_cols))}
        if values.get("key") in existing_keys:
            skipped += 1
            continue

        values.pop("id")
        sq_org = values.get("organization_id")
        if sq_org is not None:
            values["organization_id"] = org_map.get(sq_org)
        _coerce_booleans(values, bool_cols)

        col_names = list(values.keys())
        placeholders = ", ".join(f":{c}" for c in col_names)
        cols_sql = ", ".join(f'"{c}"' for c in col_names)

        with pg_engine.begin() as conn:
            conn.execute(
                text(f'INSERT INTO api_keys ({cols_sql}) '
                     f'VALUES ({placeholders})'),
                values,
            )
            inserted += 1

    logger.info(
        "[SQLiteMerge] api_keys: inserted=%d, skipped=%d",
        inserted, skipped,
    )
    return {"inserted": inserted, "skipped": skipped}


def _merge_token_usage(
    sq: sqlite3.Connection,
    pg_engine: Engine,
    user_map: Dict[int, Optional[int]],
    org_map: Dict[int, Optional[int]],
    bool_cols: Set[str],
) -> Dict[str, int]:
    cur = sq.cursor()
    sq_cols = _sqlite_columns(sq, "token_usage")

    existing_keys = _pg_token_usage_keys(pg_engine)

    cur.execute("SELECT * FROM token_usage")
    batch_size = 500
    inserted = 0
    skipped = 0
    orphaned = 0

    rows = cur.fetchmany(batch_size)
    while rows:
        batch_values: List[Dict[str, Any]] = []
        for row in rows:
            values = {sq_cols[i]: row[i] for i in range(len(sq_cols))}
            sq_uid = values.get("user_id")

            if sq_uid is not None and sq_uid not in user_map:
                orphaned += 1
                continue

            pg_uid = user_map.get(sq_uid) if sq_uid is not None else None
            dedup_key = f"{pg_uid}|{values.get('session_id')}|{values.get('created_at')}"
            if dedup_key in existing_keys:
                skipped += 1
                continue

            values.pop("id")
            if sq_uid is not None:
                values["user_id"] = pg_uid
            sq_org = values.get("organization_id")
            if sq_org is not None:
                values["organization_id"] = org_map.get(sq_org)
            _coerce_booleans(values, bool_cols)

            batch_values.append(values)
            existing_keys.add(dedup_key)

        if batch_values:
            col_names = list(batch_values[0].keys())
            placeholders = ", ".join(f":{c}" for c in col_names)
            cols_sql = ", ".join(f'"{c}"' for c in col_names)
            with pg_engine.begin() as conn:
                conn.execute(
                    text(f'INSERT INTO token_usage ({cols_sql}) '
                         f'VALUES ({placeholders})'),
                    batch_values,
                )
            inserted += len(batch_values)

        rows = cur.fetchmany(batch_size)

    logger.info(
        "[SQLiteMerge] token_usage: inserted=%d, skipped=%d, orphaned=%d",
        inserted, skipped, orphaned,
    )
    return {"inserted": inserted, "skipped": skipped, "orphaned": orphaned}


def _merge_dashboard_activities(
    sq: sqlite3.Connection,
    pg_engine: Engine,
    user_map: Dict[int, Optional[int]],
    bool_cols: Set[str],
) -> Dict[str, int]:
    cur = sq.cursor()
    cur.execute("SELECT COUNT(*) FROM dashboard_activities")
    total = cur.fetchone()[0]
    if total == 0:
        return {"inserted": 0, "skipped": 0}

    sq_cols = _sqlite_columns(sq, "dashboard_activities")
    cur.execute("SELECT * FROM dashboard_activities")
    rows = cur.fetchall()

    inserted = 0
    skipped = 0
    for row in rows:
        values = {sq_cols[i]: row[i] for i in range(len(sq_cols))}
        values.pop("id")
        sq_uid = values.get("user_id")
        if sq_uid is not None:
            if sq_uid not in user_map:
                skipped += 1
                continue
            values["user_id"] = user_map[sq_uid]
        _coerce_booleans(values, bool_cols)

        col_names = list(values.keys())
        placeholders = ", ".join(f":{c}" for c in col_names)
        cols_sql = ", ".join(f'"{c}"' for c in col_names)

        with pg_engine.begin() as conn:
            conn.execute(
                text(f'INSERT INTO dashboard_activities ({cols_sql}) '
                     f'VALUES ({placeholders})'),
                values,
            )
            inserted += 1

    return {"inserted": inserted, "skipped": skipped}


def _merge_simple_table(
    sq: sqlite3.Connection,
    pg_engine: Engine,
    table_name: str,
    bool_cols: Set[str],
) -> Dict[str, int]:
    """Merge a small table by checking if an id already exists in PG."""
    cur = sq.cursor()
    cur.execute(f"SELECT COUNT(*) FROM [{table_name}]")
    total = cur.fetchone()[0]
    if total == 0:
        return {"inserted": 0, "skipped": 0}

    sq_cols = _sqlite_columns(sq, table_name)
    cur.execute(f"SELECT * FROM [{table_name}]")
    rows = cur.fetchall()

    with pg_engine.connect() as conn:
        pg_ids = {
            r[0]
            for r in conn.execute(text(f'SELECT id FROM "{table_name}"'))
        }

    inserted = 0
    skipped = 0
    for row in rows:
        values = {sq_cols[i]: row[i] for i in range(len(sq_cols))}
        if values.get("id") in pg_ids:
            skipped += 1
            continue
        values.pop("id")
        _coerce_booleans(values, bool_cols)

        col_names = list(values.keys())
        placeholders = ", ".join(f":{c}" for c in col_names)
        cols_sql = ", ".join(f'"{c}"' for c in col_names)

        with pg_engine.begin() as conn:
            conn.execute(
                text(f'INSERT INTO "{table_name}" ({cols_sql}) '
                     f'VALUES ({placeholders})'),
                values,
            )
            inserted += 1

    return {"inserted": inserted, "skipped": skipped}


def _merge_update_notification_dismissed(
    sq: sqlite3.Connection,
    pg_engine: Engine,
    user_map: Dict[int, Optional[int]],
    bool_cols: Set[str],
) -> Dict[str, int]:
    cur = sq.cursor()
    cur.execute("SELECT COUNT(*) FROM update_notification_dismissed")
    total = cur.fetchone()[0]
    if total == 0:
        return {"inserted": 0, "skipped": 0}

    sq_cols = _sqlite_columns(sq, "update_notification_dismissed")
    cur.execute("SELECT * FROM update_notification_dismissed")
    rows = cur.fetchall()

    inserted = 0
    skipped = 0
    for row in rows:
        values = {sq_cols[i]: row[i] for i in range(len(sq_cols))}
        values.pop("id")
        sq_uid = values.get("user_id")
        if sq_uid is not None:
            pg_uid = user_map.get(sq_uid)
            if pg_uid is None:
                skipped += 1
                continue
            values["user_id"] = pg_uid
        _coerce_booleans(values, bool_cols)

        col_names = list(values.keys())
        placeholders = ", ".join(f":{c}" for c in col_names)
        cols_sql = ", ".join(f'"{c}"' for c in col_names)

        try:
            with pg_engine.begin() as conn:
                conn.execute(
                    text(
                        f'INSERT INTO update_notification_dismissed '
                        f'({cols_sql}) VALUES ({placeholders})'
                    ),
                    values,
                )
                inserted += 1
        except Exception:
            skipped += 1

    return {"inserted": inserted, "skipped": skipped}


# ── sequence reset ───────────────────────────────────────────────────

def _reset_sequences(pg_engine: Engine) -> None:
    """Reset PG serial sequences to max(id)+1 for all merged tables."""
    tables_with_serial = [
        "organizations", "users", "api_keys", "token_usage",
        "dashboard_activities", "update_notifications",
        "update_notification_dismissed",
    ]
    with pg_engine.begin() as conn:
        for table in tables_with_serial:
            try:
                seq_name = f"{table}_id_seq"
                conn.execute(text(
                    f"SELECT setval('{seq_name}', "
                    f"COALESCE((SELECT MAX(id) FROM \"{table}\"), 1))"
                ))
            except Exception as exc:
                logger.debug(
                    "[SQLiteMerge] Could not reset sequence for %s: %s",
                    table, exc,
                )


# ── PG orphan detection ─────────────────────────────────────────────

def detect_pg_orphans(pg_engine: Engine) -> Dict[str, int]:
    """Detect orphaned FK references in the current PostgreSQL database."""
    orphans: Dict[str, int] = {}
    fk_checks = [
        (
            "users_missing_org",
            "SELECT COUNT(*) FROM users "
            "WHERE organization_id IS NOT NULL "
            "AND organization_id NOT IN (SELECT id FROM organizations)",
        ),
        (
            "token_usage_missing_user",
            "SELECT COUNT(*) FROM token_usage "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "token_usage_missing_org",
            "SELECT COUNT(*) FROM token_usage "
            "WHERE organization_id IS NOT NULL "
            "AND organization_id NOT IN (SELECT id FROM organizations)",
        ),
        (
            "dashboard_activities_missing_user",
            "SELECT COUNT(*) FROM dashboard_activities "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "update_dismissed_missing_user",
            "SELECT COUNT(*) FROM update_notification_dismissed "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)",
        ),
    ]
    with pg_engine.connect() as conn:
        for label, query in fk_checks:
            try:
                result = conn.execute(text(query))
                count = result.scalar() or 0
                if count > 0:
                    orphans[label] = count
            except Exception as exc:
                logger.debug("[OrphanDetect] %s failed: %s", label, exc)
    return orphans


def cleanup_pg_orphans(pg_engine: Engine) -> Dict[str, int]:
    """Delete or nullify orphaned FK references in PostgreSQL."""
    cleaned: Dict[str, int] = {}
    operations = [
        (
            "users_nullify_missing_org",
            "UPDATE users SET organization_id = NULL "
            "WHERE organization_id IS NOT NULL "
            "AND organization_id NOT IN (SELECT id FROM organizations)",
        ),
        (
            "token_usage_delete_missing_user",
            "DELETE FROM token_usage "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "token_usage_nullify_missing_org",
            "UPDATE token_usage SET organization_id = NULL "
            "WHERE organization_id IS NOT NULL "
            "AND organization_id NOT IN (SELECT id FROM organizations)",
        ),
        (
            "dashboard_delete_missing_user",
            "DELETE FROM dashboard_activities "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "dismissed_delete_missing_user",
            "DELETE FROM update_notification_dismissed "
            "WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)",
        ),
    ]
    with pg_engine.begin() as conn:
        for label, query in operations:
            try:
                result = conn.execute(text(query))
                affected = result.rowcount
                if affected > 0:
                    cleaned[label] = affected
                    logger.info(
                        "[OrphanCleanup] %s: %d rows affected",
                        label, affected,
                    )
            except Exception as exc:
                logger.warning(
                    "[OrphanCleanup] %s failed: %s", label, exc,
                )
    return cleaned
