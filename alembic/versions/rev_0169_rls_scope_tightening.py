"""Tighten row-level security scope.

- Platform-admin tables need a superadmin or global panel session, not any panel.
- A panel session no longer sees every school that has no inviter, and the
  unused ``rls_panel_legacy_org_visible`` helper is dropped.
- Teacher sessions see their own personal rows, not schoolmates'. Diagrams
  stay readable by share recipients and workshop participants.
- Direct messages are visible to sender and recipient only.
- MindBot and OAuth config rows (school secrets) are hidden from teachers.
- Danmaku moderation, embeddings and teacher usage thresholds get separate
  read and write rules.

Revision ID: 0169
Revises: 0168
"""

from typing import Sequence, Union

from utils.db_rls.catalog_reapply import reapply_current_rls_policies

revision: str = "0169"
down_revision: Union[str, None] = "0168"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace the helper functions and every catalog policy."""
    reapply_current_rls_policies()


def downgrade() -> None:
    """Leave the tightened catalog in place.

    The previous rules let a school admin read other schools and let teachers
    read school secrets. Restore a backup taken before 0169 to go back.
    """
