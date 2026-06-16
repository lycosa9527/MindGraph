"""RLS policies — groups C–E (users, orgs, community, platform admin, dashboard).

Revision ID: 0046
Revises: 0045
"""

from typing import Sequence, Union

from db_rls.policy_builder import downgrade_policies_for_tables, upgrade_group_cde

revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GROUP_CDE_TABLES = [
    "users",
    "organizations",
    "community_posts",
    "community_post_likes",
    "community_post_comments",
    "library_documents",
    "library_danmaku",
    "library_danmaku_likes",
    "library_danmaku_replies",
    "api_keys",
    "update_notifications",
    "update_notification_dismissed",
    "feature_access_rules",
    "feature_access_user_grants",
    "teacher_usage_config",
    "dashboard_activities",
    "market_listings",
]


def upgrade() -> None:
    upgrade_group_cde()


def downgrade() -> None:
    downgrade_policies_for_tables(_GROUP_CDE_TABLES)
