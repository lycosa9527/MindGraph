"""Rename seminar tables off the collab prefix.

Revisions through 0158 create mindmate_collab_*. This revision renames them
and rebuilds policies whose SQL still names the old tables.

Revision ID: 0159
Revises: 0158
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import (
    MINDMATE_COLLAB_LEGACY_FILE_CHECK,
    MINDMATE_COLLAB_LEGACY_FILE_EXPR,
    MINDMATE_COLLAB_LEGACY_TABLES,
    MINDMATE_COLLAB_MEMBER_CHECK,
    MINDMATE_COLLAB_MEMBER_EXPR,
    MINDMATE_SEMINAR_FILE_CHECK_BEFORE_VISIBILITY,
    MINDMATE_SEMINAR_FILE_EXPR_BEFORE_VISIBILITY,
    MINDMATE_SEMINAR_TABLES_BEFORE_VISIBILITY,
    _create_all_policy,
    downgrade_policies_for_tables,
)

revision: str = "0159"
down_revision: Union[str, None] = "0158"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "mindmate_collab_sessions",
    "mindmate_collab_messages",
    "mindmate_collab_members",
    "mindmate_collab_background_files",
    "mindmate_collab_read_cursors",
)


def _rename_pair(old: str, new: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(old) and not inspector.has_table(new):
        op.rename_table(old, new)


def _rename_indexes(source: str, target: str, short_source: str, short_target: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
            "AND (indexname LIKE :token OR indexname LIKE :short)"
        ).bindparams(token=f"%{source}%", short=f"%{short_source}%")
    ).fetchall()
    for row in rows:
        old_name = str(row[0])
        new_name = old_name.replace(source, target).replace(short_source, short_target)
        if old_name == new_name:
            continue
        op.execute(sa.text(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'))


def _policy_specs(seminar_names: bool) -> list[tuple[str, str, str]]:
    if seminar_names:
        specs = list(MINDMATE_SEMINAR_TABLES_BEFORE_VISIBILITY)
        specs.append(("mindmate_seminar_members", MINDMATE_COLLAB_MEMBER_EXPR, MINDMATE_COLLAB_MEMBER_CHECK))
        specs.append(
            (
                "mindmate_seminar_background_files",
                MINDMATE_SEMINAR_FILE_EXPR_BEFORE_VISIBILITY,
                MINDMATE_SEMINAR_FILE_CHECK_BEFORE_VISIBILITY,
            )
        )
        return specs
    specs = list(MINDMATE_COLLAB_LEGACY_TABLES)
    specs.append(("mindmate_collab_members", MINDMATE_COLLAB_MEMBER_EXPR, MINDMATE_COLLAB_MEMBER_CHECK))
    specs.append(
        (
            "mindmate_collab_background_files",
            MINDMATE_COLLAB_LEGACY_FILE_EXPR,
            MINDMATE_COLLAB_LEGACY_FILE_CHECK,
        )
    )
    return specs


def _reapply_policies(seminar_names: bool) -> None:
    specs = _policy_specs(seminar_names)
    inspector = sa.inspect(op.get_bind())
    for table, using_expr, check_expr in specs:
        if not inspector.has_table(table):
            continue
        downgrade_policies_for_tables([table])
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        _create_all_policy(table, f"{table}_tenant", using_expr, check_expr)


def _rename_feature_key(old: str, new: str) -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("feature_access_rules"):
        return
    op.execute(
        sa.text(
            "INSERT INTO feature_access_rules (feature_key, restrict, updated_at) "
            "SELECT :new_key, restrict, updated_at FROM feature_access_rules "
            "WHERE feature_key = :old_key "
            "ON CONFLICT (feature_key) DO NOTHING"
        ).bindparams(old_key=old, new_key=new)
    )
    for table in ("feature_access_org_grants", "feature_access_user_grants"):
        if sa.inspect(bind).has_table(table):
            op.execute(
                sa.text(f'UPDATE "{table}" SET feature_key = :new_key WHERE feature_key = :old_key').bindparams(
                    old_key=old,
                    new_key=new,
                )
            )
    op.execute(sa.text("DELETE FROM feature_access_rules WHERE feature_key = :old_key").bindparams(old_key=old))


def upgrade() -> None:
    for old in _TABLES:
        _rename_pair(old, old.replace("mindmate_collab_", "mindmate_seminar_"))
    _rename_indexes("mindmate_collab", "mindmate_seminar", "mm_collab", "mm_seminar")
    _reapply_policies(True)
    op.execute(sa.text("SELECT set_config('app.rls_mode', 'system', true)"))
    _rename_feature_key("feature_mindmate_collab", "feature_mindmate_seminar")


def downgrade() -> None:
    for old in reversed(_TABLES):
        _rename_pair(old.replace("mindmate_collab_", "mindmate_seminar_"), old)
    _rename_indexes("mindmate_seminar", "mindmate_collab", "mm_seminar", "mm_collab")
    _reapply_policies(False)
    op.execute(sa.text("SELECT set_config('app.rls_mode', 'system', true)"))
    _rename_feature_key("feature_mindmate_seminar", "feature_mindmate_collab")
