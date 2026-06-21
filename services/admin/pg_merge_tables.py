"""
PG-to-PG Merge: re-exports for backward compatibility.

See pg_merge_config.py and pg_merge_table_ops.py for implementation.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from services.admin.pg_merge_config import (
    SKIP_TABLES,
    STATS_RECOMPUTE_TABLES,
    TABLE_MERGE_CONFIG,
    ordered_table_names,
)
from services.admin.pg_merge_table_ops import merge_table, preview_table, reset_all_sequences

__all__ = [
    "SKIP_TABLES",
    "STATS_RECOMPUTE_TABLES",
    "TABLE_MERGE_CONFIG",
    "merge_table",
    "ordered_table_names",
    "preview_table",
    "reset_all_sequences",
]
