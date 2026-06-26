"""
PG-to-PG merge table configuration (FK order, dedup keys, remaps).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List

SKIP_TABLES: FrozenSet[str] = frozenset(
    {
        "alembic_version",
        "gewe_contacts",
        "gewe_group_members",
        "gewe_messages",
    }
)

STATS_RECOMPUTE_TABLES: FrozenSet[str] = frozenset(
    {
        "token_usage",
        "user_activity_log",
        "user_usage_activities",
    }
)

# Config keys:
#   order, pk_type, pk_column, dedup_key, dedup_columns, dedup_fingerprint,
#   fk_remaps, self_ref, singleton_user, incremental_watermark,
#   preserve_staging_pk, skip_dedup_key_when_null

TABLE_MERGE_CONFIG: Dict[str, Dict[str, Any]] = {
    "organizations": {
        "order": 0,
        "pk_type": "serial",
        "dedup_key": "code",
        "fk_remaps": {},
    },
    "feature_access_rules": {
        "order": 0,
        "pk_type": "string_pk",
        "pk_column": "feature_key",
        "dedup_key": "feature_key",
        "fk_remaps": {},
    },
    "teacher_usage_config": {
        "order": 0,
        "pk_type": "serial",
        "dedup_key": "config_key",
        "fk_remaps": {},
    },
    "error_groups": {
        "order": 0,
        "pk_type": "serial",
        "dedup_key": "fingerprint",
        "fk_remaps": {},
    },
    "market_listings": {
        "order": 0,
        "pk_type": "serial",
        "dedup_key": "slug",
        "fk_remaps": {},
    },
    "users": {
        "order": 1,
        "pk_type": "serial",
        "dedup_key": "phone",
        "fk_remaps": {"organization_id": "organizations"},
    },
    "api_keys": {
        "order": 1,
        "pk_type": "serial",
        "dedup_key": "key",
        "fk_remaps": {"organization_id": "organizations"},
    },
    "update_notifications": {
        "order": 1,
        "pk_type": "serial",
        "preserve_staging_pk": True,
        "fk_remaps": {"organization_id": "organizations"},
    },
    "organization_mindbot_configs": {
        "order": 1,
        "pk_type": "serial",
        "dedup_key": "dingtalk_robot_code",
        "fk_remaps": {"organization_id": "organizations"},
    },
    "feature_access_org_grants": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("feature_key", "organization_id"),
        "fk_remaps": {"organization_id": "organizations"},
    },
    "feature_access_user_grants": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("feature_key", "user_id"),
        "fk_remaps": {"user_id": "users"},
    },
    "update_notification_dismissed": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("user_id", "version"),
        "fk_remaps": {"user_id": "users"},
    },
    "user_usage_stats": {
        "order": 2,
        "pk_type": "serial",
        "singleton_user": True,
        "fk_remaps": {"user_id": "users"},
    },
    "knowledge_spaces": {
        "order": 2,
        "pk_type": "serial",
        "singleton_user": True,
        "fk_remaps": {"user_id": "users"},
    },
    "pinned_conversations": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("user_id", "conversation_id"),
        "fk_remaps": {"user_id": "users"},
    },
    "devices": {
        "order": 2,
        "pk_type": "serial",
        "dedup_key": "watch_id",
        "fk_remaps": {"student_id": "users"},
    },
    "user_activity_log": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("user_id", "activity_type", "created_at"),
        "fk_remaps": {"user_id": "users"},
    },
    "user_usage_activities": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("user_id", "source", "action", "created_at", "conversation_id"),
        "fk_remaps": {"user_id": "users", "organization_id": "organizations"},
    },
    "dashboard_activities": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("user_id", "action", "diagram_type", "created_at", "topic"),
        "fk_remaps": {"user_id": "users"},
    },
    "direct_messages": {
        "order": 2,
        "pk_type": "serial",
        "incremental_watermark": "created_at",
        "fk_remaps": {"sender_id": "users", "recipient_id": "users"},
    },
    "user_api_tokens": {
        "order": 2,
        "pk_type": "serial",
        "singleton_user": True,
        "fk_remaps": {"user_id": "users"},
    },
    "dingtalk_staff_links": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("organization_id", "dingtalk_staff_id"),
        "fk_remaps": {"organization_id": "organizations", "user_id": "users"},
    },
    "error_events": {
        "order": 2,
        "pk_type": "serial",
        "dedup_columns": ("fingerprint", "created_at", "request_id"),
        "fk_remaps": {"group_id": "error_groups", "user_id": "users"},
    },
    "market_subscriptions": {
        "order": 2,
        "pk_type": "serial",
        "dedup_key": "external_agreement_no",
        "skip_dedup_key_when_null": True,
        "fk_remaps": {"user_id": "users", "listing_id": "market_listings"},
    },
    "diagrams": {
        "order": 3,
        "pk_type": "uuid",
        "fk_remaps": {"user_id": "users"},
    },
    "document_batches": {
        "order": 3,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users"},
    },
    "token_usage": {
        "order": 3,
        "pk_type": "serial",
        "dedup_columns": ("user_id", "session_id", "created_at"),
        "backfill_org_from_user": True,
        "fk_remaps": {
            "user_id": "users",
            "organization_id": "organizations",
            "api_key_id": "api_keys",
        },
    },
    "community_posts": {
        "order": 3,
        "pk_type": "uuid",
        "fk_remaps": {"author_id": "users"},
    },
    "shared_diagrams": {
        "order": 3,
        "pk_type": "uuid",
        "fk_remaps": {"organization_id": "organizations", "author_id": "users"},
    },
    "debate_sessions": {
        "order": 3,
        "pk_type": "uuid",
        "fk_remaps": {"user_id": "users"},
    },
    "library_documents": {
        "order": 3,
        "pk_type": "serial",
        "fk_remaps": {"uploader_id": "users"},
    },
    "mindbot_usage_events": {
        "order": 3,
        "pk_type": "serial",
        "dedup_fingerprint": "mindbot_usage_event",
        "backfill_org_from_user": True,
        "fk_remaps": {
            "organization_id": "organizations",
            "mindbot_config_id": "organization_mindbot_configs",
            "linked_user_id": "users",
        },
    },
    "generation_preview_links": {
        "order": 3,
        "pk_type": "string_pk",
        "pk_column": "preview_id",
        "fk_remaps": {
            "diagram_id": "diagrams",
            "user_id": "users",
            "organization_id": "organizations",
        },
    },
    "mindmate_export_jobs": {
        "order": 3,
        "pk_type": "serial",
        "incremental_watermark": "created_at",
        "fk_remaps": {"created_by_user_id": "users", "organization_id": "organizations"},
    },
    "market_orders": {
        "order": 3,
        "pk_type": "serial",
        "dedup_key": "out_trade_no",
        "fk_remaps": {
            "user_id": "users",
            "listing_id": "market_listings",
            "subscription_id": "market_subscriptions",
        },
    },
    "market_entitlements": {
        "order": 3,
        "pk_type": "serial",
        "dedup_columns": ("user_id", "listing_id"),
        "fk_remaps": {
            "user_id": "users",
            "listing_id": "market_listings",
            "order_id": "market_orders",
            "subscription_id": "market_subscriptions",
        },
    },
    "chat_channels": {
        "order": 4,
        "pk_type": "serial",
        "fk_remaps": {
            "organization_id": "organizations",
            "created_by": "users",
            "diagram_id": "diagrams",
        },
        "self_ref": "parent_id",
    },
    "diagram_snapshots": {
        "order": 4,
        "pk_type": "serial",
        "dedup_columns": ("diagram_id", "version_number"),
        "fk_remaps": {"user_id": "users", "diagram_id": "diagrams"},
    },
    "knowledge_documents": {
        "order": 4,
        "pk_type": "serial",
        "dedup_columns": ("space_id", "file_name"),
        "fk_remaps": {"space_id": "knowledge_spaces", "batch_id": "document_batches"},
    },
    "community_post_likes": {
        "order": 4,
        "pk_type": "serial",
        "dedup_columns": ("post_id", "user_id"),
        "fk_remaps": {"user_id": "users", "post_id": "community_posts"},
    },
    "community_post_comments": {
        "order": 4,
        "pk_type": "serial",
        "incremental_watermark": "created_at",
        "fk_remaps": {"user_id": "users", "post_id": "community_posts"},
    },
    "shared_diagram_likes": {
        "order": 4,
        "pk_type": "serial",
        "dedup_columns": ("diagram_id", "user_id"),
        "fk_remaps": {"user_id": "users", "diagram_id": "shared_diagrams"},
    },
    "shared_diagram_comments": {
        "order": 4,
        "pk_type": "serial",
        "incremental_watermark": "created_at",
        "fk_remaps": {"user_id": "users", "diagram_id": "shared_diagrams"},
    },
    "debate_participants": {
        "order": 4,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users", "session_id": "debate_sessions"},
    },
    "library_danmaku": {
        "order": 4,
        "pk_type": "serial",
        "incremental_watermark": "created_at",
        "fk_remaps": {"document_id": "library_documents", "user_id": "users"},
    },
    "library_bookmarks": {
        "order": 4,
        "pk_type": "serial",
        "dedup_columns": ("document_id", "user_id", "page_number"),
        "fk_remaps": {"document_id": "library_documents", "user_id": "users"},
    },
    "chat_topics": {
        "order": 5,
        "pk_type": "serial",
        "fk_remaps": {"channel_id": "chat_channels", "created_by": "users"},
    },
    "channel_members": {
        "order": 5,
        "pk_type": "serial",
        "dedup_columns": ("channel_id", "user_id"),
        "fk_remaps": {"channel_id": "chat_channels", "user_id": "users"},
    },
    "document_chunks": {
        "order": 6,
        "pk_type": "serial",
        "fk_remaps": {"document_id": "knowledge_documents"},
    },
    "document_versions": {
        "order": 6,
        "pk_type": "serial",
        "dedup_columns": ("document_id", "version_number"),
        "fk_remaps": {"document_id": "knowledge_documents", "created_by": "users"},
    },
    "document_relationships": {
        "order": 6,
        "pk_type": "serial",
        "dedup_columns": (
            "source_document_id",
            "target_document_id",
            "relationship_type",
        ),
        "fk_remaps": {
            "source_document_id": "knowledge_documents",
            "target_document_id": "knowledge_documents",
            "created_by": "users",
        },
    },
    "chat_messages": {
        "order": 6,
        "pk_type": "serial",
        "incremental_watermark": "created_at",
        "fk_remaps": {
            "channel_id": "chat_channels",
            "topic_id": "chat_topics",
            "sender_id": "users",
        },
        "self_ref": "parent_id",
    },
    "library_danmaku_likes": {
        "order": 6,
        "pk_type": "serial",
        "dedup_columns": ("danmaku_id", "user_id"),
        "fk_remaps": {"danmaku_id": "library_danmaku", "user_id": "users"},
    },
    "library_danmaku_replies": {
        "order": 6,
        "pk_type": "serial",
        "incremental_watermark": "created_at",
        "fk_remaps": {"danmaku_id": "library_danmaku", "user_id": "users"},
        "self_ref": "parent_reply_id",
    },
    "debate_messages": {
        "order": 6,
        "pk_type": "serial",
        "incremental_watermark": "created_at",
        "fk_remaps": {
            "session_id": "debate_sessions",
            "participant_id": "debate_participants",
        },
        "self_ref": "parent_message_id",
    },
    "debate_judgments": {
        "order": 6,
        "pk_type": "serial",
        "dedup_key": "session_id",
        "fk_remaps": {
            "session_id": "debate_sessions",
            "judge_participant_id": "debate_participants",
            "best_debater_id": "debate_participants",
        },
    },
    "evaluation_datasets": {
        "order": 6,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users", "space_id": "knowledge_spaces"},
    },
    "user_topic_preferences": {
        "order": 6,
        "pk_type": "serial",
        "dedup_columns": ("user_id", "topic_id"),
        "fk_remaps": {"user_id": "users", "topic_id": "chat_topics"},
    },
    "market_payments": {
        "order": 6,
        "pk_type": "serial",
        "dedup_columns": ("order_id",),
        "fk_remaps": {"order_id": "market_orders"},
    },
    "message_reactions": {
        "order": 7,
        "pk_type": "serial",
        "dedup_columns": ("message_id", "user_id", "emoji_name"),
        "fk_remaps": {"message_id": "chat_messages", "user_id": "users"},
    },
    "starred_messages": {
        "order": 7,
        "pk_type": "serial",
        "dedup_columns": ("message_id", "user_id"),
        "fk_remaps": {"message_id": "chat_messages", "user_id": "users"},
    },
    "file_attachments": {
        "order": 7,
        "pk_type": "serial",
        "fk_remaps": {
            "message_id": "chat_messages",
            "dm_id": "direct_messages",
            "uploader_id": "users",
        },
    },
    "child_chunks": {
        "order": 7,
        "pk_type": "serial",
        "fk_remaps": {"parent_chunk_id": "document_chunks"},
    },
    "chunk_attachments": {
        "order": 7,
        "pk_type": "serial",
        "fk_remaps": {"chunk_id": "document_chunks"},
    },
    "embeddings": {
        "order": 7,
        "pk_type": "serial",
        "dedup_columns": ("model_name", "provider_name", "hash"),
        "fk_remaps": {},
    },
    "knowledge_queries": {
        "order": 7,
        "pk_type": "serial",
        "incremental_watermark": "created_at",
        "fk_remaps": {"user_id": "users", "space_id": "knowledge_spaces"},
    },
    "chunk_test_results": {
        "order": 7,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users"},
    },
    "chunk_test_documents": {
        "order": 7,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users"},
    },
    "evaluation_results": {
        "order": 8,
        "pk_type": "serial",
        "fk_remaps": {
            "dataset_id": "evaluation_datasets",
            "query_id": "knowledge_queries",
        },
    },
    "query_feedback": {
        "order": 8,
        "pk_type": "serial",
        "fk_remaps": {
            "query_id": "knowledge_queries",
            "user_id": "users",
            "space_id": "knowledge_spaces",
        },
    },
    "query_templates": {
        "order": 8,
        "pk_type": "serial",
        "fk_remaps": {"user_id": "users", "space_id": "knowledge_spaces"},
    },
    "chunk_test_document_chunks": {
        "order": 8,
        "pk_type": "serial",
        "fk_remaps": {"document_id": "chunk_test_documents"},
    },
}


def ordered_table_names() -> List[str]:
    """Return table names sorted by merge order."""
    return sorted(
        TABLE_MERGE_CONFIG,
        key=lambda t: TABLE_MERGE_CONFIG[t]["order"],
    )
