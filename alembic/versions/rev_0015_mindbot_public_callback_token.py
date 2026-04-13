"""MindBot: opaque public_callback_token for per-school DingTalk URL without org id.

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-13
"""

from __future__ import annotations

import secrets
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_mindbot_configs",
        sa.Column("public_callback_token", sa.String(length=64), nullable=True),
    )
    conn = op.get_bind()
    rows = conn.execute(text("SELECT id FROM organization_mindbot_configs")).fetchall()
    used: set[str] = set()
    for row in rows:
        rid = row[0]
        while True:
            tok = secrets.token_urlsafe(16)
            if len(tok) > 64:
                tok = tok[:64]
            if tok not in used:
                used.add(tok)
                break
        conn.execute(
            text(
                "UPDATE organization_mindbot_configs SET public_callback_token = :t "
                "WHERE id = :id"
            ),
            {"t": tok, "id": rid},
        )
    op.alter_column(
        "organization_mindbot_configs",
        "public_callback_token",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_mindbot_config_public_callback_token",
        "organization_mindbot_configs",
        ["public_callback_token"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_mindbot_config_public_callback_token",
        "organization_mindbot_configs",
        type_="unique",
    )
    op.drop_column("organization_mindbot_configs", "public_callback_token")
