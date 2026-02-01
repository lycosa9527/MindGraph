"""
SQLite Migration Table Helper Functions

Helper functions for table migration operations extracted from migration_tables.py
to reduce file size and improve maintainability.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import re
import logging
from typing import List, Dict, Tuple, Any, Optional

logger = logging.getLogger(__name__)


def build_insert_sql(
    table_name: str,
    common_columns: List[str],
    pk_column_names: List[str],
    conflict_columns: List[str]
) -> str:
    """
    Build INSERT SQL statement with ON CONFLICT handling.

    Args:
        table_name: Name of the table
        common_columns: Columns that exist in both databases
        pk_column_names: Primary key column names
        conflict_columns: PK columns that exist in common_columns

    Returns:
        INSERT SQL statement string
    """
    columns_str = ", ".join([f'"{col}"' for col in common_columns])

    if pk_column_names and conflict_columns:
        update_columns = [col for col in common_columns if col not in conflict_columns]
        if update_columns:
            has_updated_at = 'updated_at' in common_columns
            has_created_at = 'created_at' in common_columns

            update_clause = ", ".join(
                [f'"{col}" = EXCLUDED."{col}"' for col in update_columns]
            )
            conflict_target = ", ".join([f'"{col}"' for col in conflict_columns])

            where_clause = ""
            if has_updated_at:
                where_clause = (
                    f" WHERE \"{table_name}\".\"updated_at\" IS NULL "
                    f"OR \"{table_name}\".\"updated_at\" < EXCLUDED.\"updated_at\""
                )
                logger.debug(
                    "[Migration] Table %s: Using timestamp-aware updates "
                    "(updated_at column found)",
                    table_name
                )
            elif has_created_at:
                where_clause = (
                    f" WHERE \"{table_name}\".\"created_at\" IS NULL "
                    f"OR \"{table_name}\".\"created_at\" < EXCLUDED.\"created_at\""
                )
                logger.debug(
                    "[Migration] Table %s: Using created_at for timestamp-aware updates "
                    "(updated_at not found)",
                    table_name
                )
            else:
                logger.debug(
                    "[Migration] Table %s: No timestamp column found, "
                    "updating all records on conflict",
                    table_name
                )

            return (
                f'INSERT INTO "{table_name}" ({columns_str}) '
                f"VALUES %s "
                f"ON CONFLICT ({conflict_target}) "
                f"DO UPDATE SET {update_clause}{where_clause}"
            )
        else:
            conflict_target = ", ".join([f'"{col}"' for col in conflict_columns])
            return (
                f'INSERT INTO "{table_name}" ({columns_str}) '
                f"VALUES %s "
                f"ON CONFLICT ({conflict_target}) DO NOTHING"
            )
    else:
        return (
            f'INSERT INTO "{table_name}" ({columns_str}) '
            f"VALUES %s "
            f"ON CONFLICT DO NOTHING"
        )


def convert_row_data(
    row: Tuple,
    columns: List[str],
    common_columns: List[str],
    pg_column_types: Dict[str, str],
    table_name: str
) -> List[Any]:
    """
    Convert row data types from SQLite to PostgreSQL format.

    Args:
        row: Raw row tuple from SQLite
        columns: Column names from SQLite
        common_columns: Columns that exist in both databases
        pg_column_types: Mapping of column names to PostgreSQL types
        table_name: Name of the table (for logging)

    Returns:
        List of converted values ready for PostgreSQL insertion
    """
    row_dict = dict(zip(columns, row))
    filtered_row = []
    for col in common_columns:
        value = row_dict.get(col)
        pg_type = pg_column_types.get(col, '')

        # Convert SQLite INTEGER booleans (0/1) to PostgreSQL BOOLEAN
        if 'BOOLEAN' in pg_type:
            if value is not None:
                if isinstance(value, (int, float)):
                    value = bool(value)
                elif isinstance(value, str):
                    value = value.lower() in ('1', 'true', 'yes', 'on')
                elif not isinstance(value, bool):
                    value = bool(value)

        # Handle VARCHAR length limits (truncate if too long)
        elif 'VARCHAR' in pg_type or 'CHARACTER VARYING' in pg_type:
            if value is not None and isinstance(value, str):
                match = re.search(r'\((\d+)\)', pg_type)
                if match:
                    max_length = int(match.group(1))
                    if len(value) > max_length:
                        logger.warning(
                            "[Migration] Truncating value in column %s.%s: "
                            "length %d exceeds VARCHAR(%d)",
                            table_name, col, len(value), max_length
                        )
                        value = value[:max_length]

        filtered_row.append(value)
    return filtered_row


def handle_foreign_key_violations(
    pg_cursor: Any,
    pg_conn: Any,
    batch_data: List[List[Any]],
    batch_num: int,
    table_name: str,
    common_columns: List[str],
    insert_sql: str,
    fk_columns: Dict[str, bool],
    fk_parent_info: Dict[str, Tuple[str, str]],
    savepoint_name: str,
    progress_tracker: Optional[Any]
) -> Tuple[int, int, int, List[int], List[str]]:
    """
    Handle foreign key violations by inserting records individually.

    Args:
        pg_cursor: PostgreSQL cursor
        pg_conn: PostgreSQL connection
        batch_data: List of row data to insert
        batch_num: Batch number for logging
        table_name: Name of the table
        common_columns: Columns that exist in both databases
        insert_sql: INSERT SQL statement
        fk_columns: Mapping of FK column names to nullable status
        fk_parent_info: Mapping of FK column names to (parent_table, parent_column)
        savepoint_name: Name of the savepoint
        progress_tracker: Optional progress tracker

    Returns:
        Tuple of (success_count, nullified_count, skipped_count,
                 failed_batches, batch_errors)
    """
    num_placeholders = len(common_columns)
    placeholders = ", ".join(["%s"] * num_placeholders)
    single_insert_sql = insert_sql.replace(
        "VALUES %s", f"VALUES ({placeholders})"
    )

    individual_sp_name = f"{savepoint_name}_individual"
    batch_success_count = 0
    batch_nullified_count = 0
    batch_skipped_count = 0
    nullified_fks = {}
    failed_batches = []
    batch_errors = []

    for row_idx, row_data in enumerate(batch_data):
        row_inserted = False
        is_orphaned_record = False
        max_retries = 3

        for retry_attempt in range(max_retries):
            try:
                pg_cursor.execute(f"SAVEPOINT {individual_sp_name}")

                if retry_attempt > 0:
                    modified_row_data = list(row_data)
                    for fk_col_name, is_nullable in fk_columns.items():
                        if is_nullable:
                            try:
                                fk_col_idx = common_columns.index(fk_col_name)
                                if modified_row_data[fk_col_idx] is not None:
                                    modified_row_data[fk_col_idx] = None
                                    nullified_fks[fk_col_name] = (
                                        nullified_fks.get(fk_col_name, 0) + 1
                                    )
                            except (ValueError, IndexError):
                                pass
                    row_data_to_use = modified_row_data
                else:
                    row_data_to_use = row_data

                pg_cursor.execute(single_insert_sql, row_data_to_use)
                pg_cursor.execute(f"RELEASE SAVEPOINT {individual_sp_name}")
                batch_success_count += 1
                row_inserted = True

                if retry_attempt > 0:
                    batch_nullified_count += 1

                break

            except Exception as row_error:
                try:
                    pg_cursor.execute(
                        f"ROLLBACK TO SAVEPOINT {individual_sp_name}"
                    )
                except Exception:
                    pass

                row_error_msg = str(row_error)
                row_error_msg_lower = row_error_msg.lower()
                if "violates foreign key constraint" in row_error_msg_lower:
                    fk_column_name = None
                    fk_value = None

                    key_match = re.search(
                        r'Key\s+\(([^)]+)\)\s*=\s*\(([^)]+)\)',
                        row_error_msg,
                        re.IGNORECASE
                    )
                    if key_match:
                        fk_column_name = key_match.group(1).strip().strip('"')
                        fk_value = key_match.group(2).strip()

                    if fk_column_name:
                        parent_info = fk_parent_info.get(
                            fk_column_name,
                            ('unknown', 'unknown')
                        )
                        logger.info(
                            "[Migration] Skipping orphaned record %d "
                            "in batch %d: %s.%s=%s references "
                            "non-existent %s.%s",
                            row_idx + 1,
                            batch_num,
                            table_name,
                            fk_column_name,
                            fk_value,
                            parent_info[0],
                            parent_info[1]
                        )
                    else:
                        logger.info(
                            "[Migration] Skipping orphaned record %d "
                            "in batch %d: FK violation (parent record "
                            "doesn't exist)",
                            row_idx + 1,
                            batch_num
                        )
                    is_orphaned_record = True
                    break
                else:
                    if retry_attempt < max_retries - 1:
                        logger.debug(
                            "[Migration] Record %d in batch %d failed "
                            "with non-FK error, retrying: %s",
                            row_idx + 1, batch_num, row_error
                        )
                        continue

                    logger.error(
                        "[Migration] CRITICAL: Record %d in batch %d "
                        "cannot be migrated after %d retries: %s",
                        row_idx + 1, batch_num, max_retries, row_error
                    )
                    break

        if not row_inserted:
            batch_skipped_count += 1
            if is_orphaned_record:
                logger.warning(
                    "[Migration] Skipped orphaned record %d in batch %d "
                    "(foreign key violation - parent record doesn't exist). "
                    "This is expected for orphaned data.",
                    row_idx + 1, batch_num
                )
            else:
                logger.error(
                    "[Migration] CRITICAL: Could not insert record %d in "
                    "batch %d after %d retries. This record will be lost.",
                    row_idx + 1, batch_num, max_retries
                )

    if batch_success_count > 0:
        pg_conn.commit()
        if progress_tracker is not None:
            progress_tracker.update_table_records(batch_success_count)

        if batch_nullified_count > 0:
            logger.info(
                "[Migration] Batch %d for table %s: inserted %d "
                "records, nullified FK columns in %d records to "
                "preserve data. FK columns nullified: %s",
                batch_num, table_name, batch_success_count,
                batch_nullified_count,
                dict(nullified_fks)
            )

        if batch_skipped_count > 0:
            logger.error(
                "[Migration] CRITICAL: Batch %d for table %s: %d "
                "records could not be migrated after all retry "
                "attempts. These records will be lost unless FK "
                "constraints are disabled or parent records are "
                "created manually.",
                batch_num, table_name, batch_skipped_count
            )
            failed_batches.append(batch_num)
            batch_errors.append(
                f"Batch {batch_num}: {batch_skipped_count} records "
                f"could not be migrated (FK violations or other errors)"
            )
    else:
        failed_batches.append(batch_num)
        batch_errors.append(
            f"Batch {batch_num}: All {len(batch_data)} records had "
            f"FK violations or errors that could not be resolved"
        )
        logger.error(
            "[Migration] CRITICAL: Batch %d failed for table %s: "
            "all %d records had unresolvable FK violations or errors. "
            "These records will be lost unless FK constraints are "
            "disabled.",
            batch_num, table_name, len(batch_data)
        )

    return (
        batch_success_count,
        batch_nullified_count,
        batch_skipped_count,
        failed_batches,
        batch_errors
    )
