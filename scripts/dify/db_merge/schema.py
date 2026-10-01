"""
Read the Dify columns this merge is allowed to touch.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from scripts.dify.db_merge.models import SchemaError

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
_UDT = re.compile(r"^[a-z0-9_]+$")

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "apps": ("id", "name"),
    "end_users": ("id", "app_id", "tenant_id", "session_id", "type"),
    "conversations": ("id", "app_id", "from_end_user_id", "inputs"),
    "messages": ("id", "app_id", "conversation_id", "from_end_user_id"),
}

CATALOG_SQL = """
COPY (
  SELECT table_name, column_name, udt_name
  FROM information_schema.columns
  WHERE table_schema = 'public'
    AND table_name IN (
      'apps',
      'end_users',
      'conversations',
      'messages',
      'message_feedbacks',
      'message_annotations'
    )
  ORDER BY table_name, ordinal_position
) TO STDOUT WITH (FORMAT csv, HEADER true);
""".strip()


@dataclass(frozen=True)
class SchemaFacts:
    """Columns that change how the merge SQL is written."""

    apps_created_at: bool
    apps_mode: bool
    end_user_created_at: bool
    inputs_udt: str
    feedback_app_id: bool
    feedback_end_user: bool
    feedback_conversation: bool
    feedback_message: bool
    annotation_app_id: bool
    annotation_conversation: bool

    @classmethod
    def from_catalog(cls, tables: dict[str, dict[str, str]]) -> SchemaFacts:
        """Build facts or raise when a required column is missing."""
        missing: list[str] = []
        for table, columns in REQUIRED_COLUMNS.items():
            have = tables.get(table, {})
            for column in columns:
                if column not in have:
                    missing.append(f"{table}.{column}")
        if missing:
            raise SchemaError("Dify schema is missing: " + ", ".join(missing))
        inputs_udt = tables["conversations"]["inputs"]
        if inputs_udt not in {"json", "jsonb"}:
            raise SchemaError(f"conversations.inputs type {inputs_udt} is not json")
        feedback = tables.get("message_feedbacks", {})
        annotations = tables.get("message_annotations", {})
        return cls(
            apps_created_at="created_at" in tables["apps"],
            apps_mode="mode" in tables["apps"],
            end_user_created_at="created_at" in tables["end_users"],
            inputs_udt=inputs_udt,
            feedback_app_id="app_id" in feedback,
            feedback_end_user="from_end_user_id" in feedback,
            feedback_conversation="conversation_id" in feedback,
            feedback_message="message_id" in feedback,
            annotation_app_id="app_id" in annotations,
            annotation_conversation="conversation_id" in annotations,
        )


def parse_column_csv(text: str) -> dict[str, dict[str, str]]:
    """Parse the catalog COPY output into table → column → udt."""
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    needed = {"table_name", "column_name", "udt_name"}
    if not needed.issubset(set(fieldnames)):
        raise SchemaError("column catalog is missing a header")
    tables: dict[str, dict[str, str]] = {}
    for row in reader:
        table = (row.get("table_name") or "").strip()
        column = (row.get("column_name") or "").strip()
        udt = (row.get("udt_name") or "").strip()
        if not (_IDENT.match(table) and _IDENT.match(column) and _UDT.match(udt)):
            continue
        tables.setdefault(table, {})[column] = udt
    if not tables:
        raise SchemaError("column catalog was empty")
    return tables
