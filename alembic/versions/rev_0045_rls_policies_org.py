"""RLS policies — group B (organization_id + workshop chat).

Revision ID: 0045
Revises: 0044
"""

from typing import Sequence, Union

from db_rls.policy_builder import downgrade_policies_for_tables, upgrade_group_b

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GROUP_B_TABLES = [
    "token_usage",
    "mindbot_usage_events",
    "organization_mindbot_configs",
    "shared_diagrams",
    "shared_diagram_likes",
    "shared_diagram_comments",
    "feature_access_org_grants",
    "chat_channels",
    "channel_members",
    "chat_topics",
    "chat_messages",
    "direct_messages",
    "message_reactions",
    "starred_messages",
    "file_attachments",
    "user_topic_preferences",
]


def upgrade() -> None:
    upgrade_group_b()


def downgrade() -> None:
    downgrade_policies_for_tables(_GROUP_B_TABLES)
