"""MindBot: opaque public_callback_token for per-school DingTalk URL without org id.

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-13

Baseline ``0001`` may already define ``public_callback_token`` and the unique
constraint (see ORM). Skip ``add_column`` and constraint when present; still
backfill any NULL tokens when the column is nullable.
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

_TABLE = "organization_mindbot_configs"
_COL = "public_callback_token"
_UQ = "uq_mindbot_config_public_callback_token"


def _uq_names(conn) -> set[str]:
    return {u["name"] for u in sa.inspect(conn).get_unique_constraints(_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    col_names = {c["name"] for c in insp.get_columns(_TABLE)}

    if _COL not in col_names:
        op.add_column(
            _TABLE,
            sa.Column(_COL, sa.String(length=64), nullable=True),
        )

    rows = list(
        bind.execute(text(f"SELECT id, {_COL} FROM {_TABLE}")).mappings().all()
    )
    used: set[str] = set()
    for row in rows:
        tok = row.get(_COL)
        if tok is not None and str(tok).strip() != "":
            used.add(str(tok)[:64])
    for row in rows:
        tok = row.get(_COL)
        if tok is None or (isinstance(tok, str) and tok.strip() == ""):
            rid = row["id"]
            while True:
                t = secrets.token_urlsafe(16)
                if len(t) > 64:
                    t = t[:64]
                if t not in used:
                    used.add(t)
                    break
            bind.execute(
                text(f"UPDATE {_TABLE} SET {_COL} = :t WHERE id = :id"),
                {"t": t, "id": rid},
            )

    for c in sa.inspect(bind).get_columns(_TABLE):
        if c["name"] == _COL and c.get("nullable", True):
            op.alter_column(
                _TABLE,
                _COL,
                existing_type=sa.String(length=64),
                nullable=False,
            )
            break

    if _UQ not in _uq_names(bind):
        op.create_unique_constraint(
            _UQ,
            _TABLE,
            [_COL],
        )


def downgrade() -> None:
    bind = op.get_bind()
    uqs = _uq_names(bind)
    if _UQ in uqs:
        op.drop_constraint(
            _UQ,
            _TABLE,
            type_="unique",
        )
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}
    if _COL in cols:
        op.drop_column(_TABLE, _COL)
