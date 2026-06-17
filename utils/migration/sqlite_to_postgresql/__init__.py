"""
SQLite to PostgreSQL Data Migration

This package handles the one-time migration of data from SQLite to PostgreSQL.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from .data_migration import migrate_sqlite_to_postgresql

__all__ = [
    "migrate_sqlite_to_postgresql",
]
