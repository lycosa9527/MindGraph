"""
PG-to-PG Merge: Table Configuration and Generic Merge Logic

Defines the merge configuration for every database table:
- FK-safe processing order (topological sort of FK dependencies)
- Natural dedup keys (phone, code, composite unique constraints)
- FK column remapping rules (staging IDs → live IDs)
- PK type handling (serial auto-increment vs UUID string)

The generic ``merge_table()`` function processes a single table
from the staging database into the live database using the config.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved -- Proprietary License
"""

import logging
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from sqlalchemy import insert, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import Table

from models.domain.registry import Base

logger = logging.getLogger(__name__)

SKIP_TABLES: FrozenSet[str] = frozenset(
    {
        "alembic_version",
        "gewe_contacts",
        "gewe_group_members",
        "gewe_messages",
    }
)

# ---------------------------------------------------------------------------
# TABLE_MERGE_CONFIG
# ---------------------------------------------------------------------------
# Keys:
#   order           – FK-safe processing order (lower = earlier)
#   pk_type         – "serial" | "uuid" | "string_pk"
#   pk_column       – PK column name (default "id")
#   dedup_key       – single-column natural key for dedup
#   dedup_columns   – multi-column composite key for dedup (tuple)
#   fk_remaps       – {column: source_table} for ID remapping
#   self_ref        – self-referencing FK column name
#   singleton_user  – True when unique per user_id (e.g. knowledge_spaces)
# ---------------------------------------------------------------------------

TABLE_MERGE_CONFIG: Dict[str, Dict[str, Any]] = {
    # ── Tier 0: root tables (no FK dependencies) ──
    "organizations": {
        "order": 0,
        "pk_type": "serial",
        "dedup_key": "code",
        "fk_remaps": {},
    },
    "feature_access_rules": {
        "order": 0,
        "pk_type": "string_pk",
        "pk_column": "feature_key",
        "dedup_key": "feature_key",
        "fk_remaps": {},
    },
    "teacher_usage_config": {
        "order": 0,
        "pk_type": "serial",
        "dedup_key": "config_key",
        "fk_remaps": {},
    },
    # ── Tier 1: depends on organizations ──
    "users": {
        "order": 1,
        "pk_type": "serial",
        "dedup_key": "phone",
        "fk_remaps": {"organization_id": "organizations"},
    },
    "api_keys": {
        "order": 1,
        "pk_type": "serial",
        "dedup_key": "key",
        "fk_remaps": {"organization_id": "organizations"},
    },
    "update_notifications": {
        "order": 1,
        "pk_type": "serial",
        "fk_remaps": {"organization_id": "organizations"},
    },
    # ── Tier 2: depends on users / orgs ──
    "feature_access_org_grants": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("feature_key", "organization_id"),
        "fk_remaps": {"organization_id": "organizations"},
    },
    "feature_access_user_grants": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("feature_key", "user_id"),
        "fk_remaps": {"user_id": "users"},
    },
    "update_notification_dismissed": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("user_id", "version"),
        "fk_remaps": {"user_id": "users"},
    },
    "user_usage_stats": {
        "order": 2,
        "pk_type": "serial",
        "singleton_user": True,
        "fk_remaps": {"user_id": "users"},
    },
    "knowledge_spaces": {
        "order": 2,
        "pk_type": "serial",
        "singleton_user": True,
        "fk_remaps": {"user_id": "users"},
    },
    "pinned_conversations": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("user_id", "conversation_id"),
        "fk_remaps": {"user_id": "users"},
    },
    "devices": {
        "order": 2,
        "pk_type": "serial",
        "dedup_key": "watch_id",
        "fk_remaps": {"student_id": "users"},
    },
    "user_activity_log": {
        "order": 2,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users"},
    },
    "dashboard_activities": {
        "order": 2,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users"},
    },
    "direct_messages": {
        "order": 2,
        "pk_type": "serial",
        "fk_remaps": {"sender_id": "users", "recipient_id": "users"},
    },
    # ── Tier 3: core content tables ──
    "diagrams": {
        "order": 3,
        "pk_type": "uuid",
        "fk_remaps": {"user_id": "users"},
    },
    "document_batches": {
        "order": 3,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users"},
    },
    "token_usage": {
        "order": 3,
        "pk_type": "serial",
        "fk_remaps": {
            "user_id": "users",
            "organization_id": "organizations",
            "api_key_id": "api_keys",
        },
    },
    "community_posts": {
        "order": 3,
        "pk_type": "uuid",
        "fk_remaps": {"author_id": "users"},
    },
    "shared_diagrams": {
        "order": 3,
        "pk_type": "uuid",
        "fk_remaps": {"organization_id": "organizations", "author_id": "users"},
    },
    "debate_sessions": {
        "order": 3,
        "pk_type": "uuid",
        "fk_remaps": {"user_id": "users"},
    },
    "library_documents": {
        "order": 3,
        "pk_type": "serial",
        "fk_remaps": {"uploader_id": "users"},
    },
    # ── Tier 4: depends on tier-3 tables ──
    "chat_channels": {
        "order": 4,
        "pk_type": "serial",
        "fk_remaps": {
            "organization_id": "organizations",
            "created_by": "users",
            "diagram_id": "diagrams",
        },
        "self_ref": "parent_id",
    },
    "diagram_snapshots": {
        "order": 4,
        "pk_type": "serial",
        "dedup_columns": ("diagram_id", "version_number"),
        "fk_remaps": {"user_id": "users", "diagram_id": "diagrams"},
    },
    "knowledge_documents": {
        "order": 4,
        "pk_type": "serial",
        "dedup_columns": ("space_id", "file_name"),
        "fk_remaps": {"space_id": "knowledge_spaces", "batch_id": "document_batches"},
    },
    "community_post_likes": {
        "order": 4,
        "pk_type": "serial",
        "dedup_columns": ("post_id", "user_id"),
        "fk_remaps": {"user_id": "users", "post_id": "community_posts"},
    },
    "community_post_comments": {
        "order": 4,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users", "post_id": "community_posts"},
    },
    "shared_diagram_likes": {
        "order": 4,
        "pk_type": "serial",
        "dedup_columns": ("diagram_id", "user_id"),
        "fk_remaps": {"user_id": "users", "diagram_id": "shared_diagrams"},
    },
    "shared_diagram_comments": {
        "order": 4,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users", "diagram_id": "shared_diagrams"},
    },
    "debate_participants": {
        "order": 4,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users", "session_id": "debate_sessions"},
    },
    "library_danmaku": {
        "order": 4,
        "pk_type": "serial",
        "fk_remaps": {"document_id": "library_documents", "user_id": "users"},
    },
    "library_bookmarks": {
        "order": 4,
        "pk_type": "serial",
        "dedup_columns": ("document_id", "user_id", "page_number"),
        "fk_remaps": {"document_id": "library_documents", "user_id": "users"},
    },
    # ── Tier 5 ──
    "chat_topics": {
        "order": 5,
        "pk_type": "serial",
        "fk_remaps": {"channel_id": "chat_channels", "created_by": "users"},
    },
    "channel_members": {
        "order": 5,
        "pk_type": "serial",
        "dedup_columns": ("channel_id", "user_id"),
        "fk_remaps": {"channel_id": "chat_channels", "user_id": "users"},
    },
    # ── Tier 6 ──
    "document_chunks": {
        "order": 6,
        "pk_type": "serial",
        "fk_remaps": {"document_id": "knowledge_documents"},
    },
    "document_versions": {
        "order": 6,
        "pk_type": "serial",
        "dedup_columns": ("document_id", "version_number"),
        "fk_remaps": {"document_id": "knowledge_documents", "created_by": "users"},
    },
    "document_relationships": {
        "order": 6,
        "pk_type": "serial",
        "dedup_columns": (
            "source_document_id",
            "target_document_id",
            "relationship_type",
        ),
        "fk_remaps": {
            "source_document_id": "knowledge_documents",
            "target_document_id": "knowledge_documents",
            "created_by": "users",
        },
    },
    "chat_messages": {
        "order": 6,
        "pk_type": "serial",
        "fk_remaps": {
            "channel_id": "chat_channels",
            "topic_id": "chat_topics",
            "sender_id": "users",
        },
        "self_ref": "parent_id",
    },
    "library_danmaku_likes": {
        "order": 6,
        "pk_type": "serial",
        "dedup_columns": ("danmaku_id", "user_id"),
        "fk_remaps": {"danmaku_id": "library_danmaku", "user_id": "users"},
    },
    "library_danmaku_replies": {
        "order": 6,
        "pk_type": "serial",
        "fk_remaps": {"danmaku_id": "library_danmaku", "user_id": "users"},
        "self_ref": "parent_reply_id",
    },
    "debate_messages": {
        "order": 6,
        "pk_type": "serial",
        "fk_remaps": {
            "session_id": "debate_sessions",
            "participant_id": "debate_participants",
        },
        "self_ref": "parent_message_id",
    },
    "debate_judgments": {
        "order": 6,
        "pk_type": "serial",
        "dedup_key": "session_id",
        "fk_remaps": {
            "session_id": "debate_sessions",
            "judge_participant_id": "debate_participants",
            "best_debater_id": "debate_participants",
        },
    },
    "evaluation_datasets": {
        "order": 6,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users", "space_id": "knowledge_spaces"},
    },
    "user_topic_preferences": {
        "order": 6,
        "pk_type": "serial",
        "dedup_columns": ("user_id", "topic_id"),
        "fk_remaps": {"user_id": "users", "topic_id": "chat_topics"},
    },
    # ── Tier 7 ──
    "message_reactions": {
        "order": 7,
        "pk_type": "serial",
        "dedup_columns": ("message_id", "user_id", "emoji_name"),
        "fk_remaps": {"message_id": "chat_messages", "user_id": "users"},
    },
    "starred_messages": {
        "order": 7,
        "pk_type": "serial",
        "dedup_columns": ("message_id", "user_id"),
        "fk_remaps": {"message_id": "chat_messages", "user_id": "users"},
    },
    "file_attachments": {
        "order": 7,
        "pk_type": "serial",
        "fk_remaps": {
            "message_id": "chat_messages",
            "dm_id": "direct_messages",
            "uploader_id": "users",
        },
    },
    "child_chunks": {
        "order": 7,
        "pk_type": "serial",
        "fk_remaps": {"parent_chunk_id": "document_chunks"},
    },
    "chunk_attachments": {
        "order": 7,
        "pk_type": "serial",
        "fk_remaps": {"chunk_id": "document_chunks"},
    },
    "embeddings": {
        "order": 7,
        "pk_type": "serial",
        "dedup_columns": ("model_name", "provider_name", "hash"),
        "fk_remaps": {},
    },
    "knowledge_queries": {
        "order": 7,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users", "space_id": "knowledge_spaces"},
    },
    "chunk_test_results": {
        "order": 7,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users"},
    },
    "chunk_test_documents": {
        "order": 7,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users"},
    },
    # ── Tier 8 ──
    "evaluation_results": {
        "order": 8,
        "pk_type": "serial",
        "fk_remaps": {
            "dataset_id": "evaluation_datasets",
            "query_id": "knowledge_queries",
        },
    },
    "query_feedback": {
        "order": 8,
        "pk_type": "serial",
        "fk_remaps": {
            "query_id": "knowledge_queries",
            "user_id": "users",
            "space_id": "knowledge_spaces",
        },
    },
    "query_templates": {
        "order": 8,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users", "space_id": "knowledge_spaces"},
    },
    "chunk_test_document_chunks": {
        "order": 8,
        "pk_type": "serial",
        "fk_remaps": {"document_id": "chunk_test_documents"},
    },
}


def ordered_table_names() -> List[str]:
    """Return table names sorted by merge order."""
    return sorted(
        TABLE_MERGE_CONFIG,
        key=lambda t: TABLE_MERGE_CONFIG[t]["order"],
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_for_orm_table(table: Table, values: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only keys that exist on the model table (drops staging-only columns)."""
    return {k: v for k, v in values.items() if k in table.c}


def _build_dedup_lookup(
    live_engine: Engine,
    table_name: str,
    pk_col: str,
    dedup_key: Optional[str],
    dedup_columns: Optional[Tuple[str, ...]],
) -> Dict[Any, Any]:
    """Pre-fetch natural-key → live PK mapping for dedup checking."""
    if dedup_key:
        with live_engine.connect() as conn:
            rows = conn.execute(text(f'SELECT "{dedup_key}", "{pk_col}" FROM "{table_name}"'))
            return {r[0]: r[1] for r in rows}

    if dedup_columns:
        cols_sql = ", ".join(f'"{c}"' for c in dedup_columns)
        with live_engine.connect() as conn:
            rows = conn.execute(text(f'SELECT {cols_sql}, "{pk_col}" FROM "{table_name}"'))
            return {tuple(r[:-1]): r[-1] for r in rows}

    return {}


def _fetch_nullable_fk_cols(
    live_engine: Engine,
    table_name: str,
    fk_columns: List[str],
) -> Set[str]:
    """Return the subset of *fk_columns* that are nullable in the live DB."""
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


def _remap_fk_values(
    values: Dict[str, Any],
    fk_remaps: Dict[str, str],
    id_maps: Dict[str, Dict],
    nullable_fk_cols: Set[str],
) -> bool:
    """Remap FK columns using accumulated id_maps.

    Returns True if a non-nullable FK is broken (row should be skipped).
    """
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
                except Exception as exc:
                    sp.rollback()
                    logger.debug(
                        "[PGMerge] Self-ref update failed for %s pk=%s: %s",
                        table_name,
                        params["pk"],
                        exc,
                    )
            txn.commit()
        except Exception:
            txn.rollback()
            raise

    if applied:
        logger.info(
            "[PGMerge] %s: applied %d self-ref updates for %s",
            table_name,
            applied,
            self_ref_col,
        )


# ---------------------------------------------------------------------------
# Generic merge for one table
# ---------------------------------------------------------------------------


def merge_table(
    table_name: str,
    staging_engine: Engine,
    live_engine: Engine,
    id_maps: Dict[str, Dict],
) -> Dict[str, int]:
    """Merge a single table from the staging DB into the live DB.

    Reads all rows from *staging_engine*, remaps FK columns via *id_maps*,
    deduplicates against live data, inserts new rows, and records
    old-PK → new-PK mappings back into *id_maps[table_name]*.

    Returns ``{"inserted": N, "skipped": N, "orphaned": N}``.
    """
    config = TABLE_MERGE_CONFIG[table_name]
    pk_col = config.get("pk_column", "id")
    pk_type = config.get("pk_type", "serial")
    dedup_key: Optional[str] = config.get("dedup_key")
    dedup_columns: Optional[Tuple[str, ...]] = config.get("dedup_columns")
    fk_remaps: Dict[str, str] = config.get("fk_remaps", {})
    self_ref: Optional[str] = config.get("self_ref")
    singleton = config.get("singleton_user", False)

    with staging_engine.connect() as conn:
        rows = conn.execute(text(f'SELECT * FROM "{table_name}"')).mappings().all()

    if not rows:
        id_maps[table_name] = {}
        return {"inserted": 0, "skipped": 0, "orphaned": 0}

    dedup_lookup = _build_dedup_lookup(
        live_engine,
        table_name,
        pk_col,
        dedup_key,
        dedup_columns,
    )

    nullable_fk_cols = _fetch_nullable_fk_cols(
        live_engine,
        table_name,
        list(fk_remaps.keys()),
    )

    singleton_map: Dict[int, int] = {}
    if singleton:
        with live_engine.connect() as conn:
            result = conn.execute(text(f'SELECT "user_id", "{pk_col}" FROM "{table_name}"'))
            singleton_map = {r[0]: r[1] for r in result}

    existing_uuids: Set[str] = set()
    if pk_type == "uuid":
        with live_engine.connect() as conn:
            result = conn.execute(text(f'SELECT "{pk_col}" FROM "{table_name}"'))
            existing_uuids = {r[0] for r in result}

    table_id_map: Dict[Any, Any] = {}
    inserted = 0
    skipped = 0
    orphaned = 0
    self_ref_updates: List[Tuple[Any, Any]] = []

    pending_inserts: List[Tuple[Any, Dict[str, Any], Optional[Any]]] = []

    for row in rows:
        values = dict(row)
        old_pk = values[pk_col]

        broken = _remap_fk_values(values, fk_remaps, id_maps, nullable_fk_cols)
        if broken:
            orphaned += 1
            continue

        if singleton:
            live_uid = values.get("user_id")
            if live_uid is not None and live_uid in singleton_map:
                table_id_map[old_pk] = singleton_map[live_uid]
                skipped += 1
                continue

        if dedup_key:
            key_val = values.get(dedup_key)
            if key_val in dedup_lookup:
                table_id_map[old_pk] = dedup_lookup[key_val]
                skipped += 1
                continue
        elif dedup_columns:
            key_tuple = tuple(values.get(c) for c in dedup_columns)
            if key_tuple in dedup_lookup:
                table_id_map[old_pk] = dedup_lookup[key_tuple]
                skipped += 1
                continue

        if pk_type == "uuid" and old_pk in existing_uuids:
            table_id_map[old_pk] = old_pk
            skipped += 1
            continue

        old_self_ref = None
        if self_ref and values.get(self_ref) is not None:
            old_self_ref = values[self_ref]
            values[self_ref] = None

        if pk_type == "serial":
            values.pop(pk_col, None)

        pending_inserts.append((old_pk, values, old_self_ref))

    if pending_inserts:
        try:
            orm_table = Base.metadata.tables[table_name]
        except KeyError as err:
            raise KeyError(
                f"Table {table_name!r} is not on Base.metadata — register the model in "
                "models/domain/registry.py"
            ) from err

        with live_engine.connect() as conn:
            txn = conn.begin()
            try:
                for old_pk, values, old_self_ref in pending_inserts:
                    savepoint = conn.begin_nested()
                    try:
                        row = _row_for_orm_table(orm_table, values)
                        stmt = insert(orm_table).values(**row)
                        if pk_type == "serial":
                            stmt = stmt.returning(orm_table.c[pk_col])
                        result = conn.execute(stmt)
                        new_pk = result.scalar() if pk_type == "serial" else old_pk
                        table_id_map[old_pk] = new_pk
                        savepoint.commit()
                        inserted += 1
                        if old_self_ref is not None:
                            self_ref_updates.append((new_pk, old_self_ref))
                    except Exception as exc:
                        savepoint.rollback()
                        logger.debug(
                            "[PGMerge] Insert failed %s pk=%s: %s",
                            table_name,
                            old_pk,
                            exc,
                        )
                        orphaned += 1
                txn.commit()
            except Exception:
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
    return {"inserted": inserted, "skipped": skipped, "orphaned": orphaned}


# ---------------------------------------------------------------------------
# Sequence reset
# ---------------------------------------------------------------------------


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
                except Exception as exc:
                    sp.rollback()
                    logger.debug(
                        "[PGMerge] Sequence reset skipped for %s: %s",
                        table_name,
                        exc,
                    )
            txn.commit()
        except Exception:
            txn.rollback()
            raise
