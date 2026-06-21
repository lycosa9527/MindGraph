"""
Reset PostgreSQL serial sequences after bulk import or merge.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import inspect, text

from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)


def _integer_max_for_serial_setval(max_id: object) -> Optional[int]:
    """Return a positive int max for setval, or None if PK is not integer serial."""
    if max_id is None or isinstance(max_id, str):
        return None
    if isinstance(max_id, bool):
        return None
    try:
        if isinstance(max_id, int):
            val = max_id
        elif isinstance(max_id, (int, float, Decimal)):
            val = int(max_id)
        else:
            val = int(str(max_id))
    except (TypeError, ValueError, OverflowError):
        return None
    return val if val > 0 else None


def reset_postgresql_sequences(pg_engine: Any) -> None:
    """Reset PostgreSQL sequences to match current MAX(pk) values."""
    try:
        engine_inspector = inspect(pg_engine)
        tables = engine_inspector.get_table_names()
        sequences_reset = 0
        sequences_failed: list[str] = []

        with pg_engine.connect() as conn:
            for table_name in tables:
                try:
                    pk_cols = engine_inspector.get_pk_constraint(table_name)
                    if not pk_cols.get("constrained_columns"):
                        continue

                    pk_col = pk_cols["constrained_columns"][0]
                    result = conn.execute(text(f'SELECT MAX("{pk_col}") FROM "{table_name}"'))
                    max_id = result.scalar()
                    int_max = _integer_max_for_serial_setval(max_id)
                    if int_max is None:
                        continue

                    seq_result = conn.execute(
                        text(f"SELECT pg_get_serial_sequence('{table_name}', '{pk_col}')")
                    )
                    sequence_name = seq_result.scalar()
                    if not sequence_name:
                        continue

                    if "." in sequence_name:
                        sequence_name = sequence_name.split(".")[-1]

                    try:
                        next_val = int_max + 1
                        conn.execute(
                            text(f"SELECT setval('{sequence_name}', {next_val}, false)"),
                        )
                        conn.commit()
                        sequences_reset += 1
                    except DATABASE_ERRORS as seq_error:
                        logger.warning(
                            "[PGSequenceReset] Failed to reset sequence %s for table %s: %s",
                            sequence_name,
                            table_name,
                            seq_error,
                        )
                        sequences_failed.append(f"{table_name}.{pk_col}")
                except DATABASE_ERRORS as exc:
                    logger.warning(
                        "[PGSequenceReset] Could not reset sequence for %s: %s",
                        table_name,
                        exc,
                    )
                    sequences_failed.append(table_name)

        if sequences_failed:
            logger.warning(
                "[PGSequenceReset] %d succeeded, %d failed: %s",
                sequences_reset,
                len(sequences_failed),
                ", ".join(sequences_failed),
            )
        else:
            logger.info("[PGSequenceReset] Reset %d sequences", sequences_reset)
    except DATABASE_ERRORS as exc:
        logger.warning("[PGSequenceReset] Failed to reset sequences: %s", exc)
