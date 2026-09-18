"""
Pure helpers for diagram persistence error messages (no DB imports).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

STALE_ACCOUNT_SAVE_ERROR = "Account is out of date. Please sign out and sign in again."


def describe_diagram_db_error(exc: Exception) -> str:
    """Map database exceptions to API-safe diagram save error messages."""
    message = str(exc).lower()
    if "row-level security" in message or "violates row-level security policy" in message:
        return "Diagram save blocked by access policy"
    if "diagrams_user_id_fkey" in message or ("foreign key constraint" in message and "user_id" in message):
        return STALE_ACCOUNT_SAVE_ERROR
    if "undefinedcolumn" in message or "does not exist" in message or "字段不存在" in message:
        return "Database schema is missing a required diagram column"
    if "value too long" in message:
        return "Diagram field exceeds maximum length"
    if "null value in column" in message and '"id"' in message:
        return "Failed to assign diagram id"
    return "Failed to save diagram to database"
