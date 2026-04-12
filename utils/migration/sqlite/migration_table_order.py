"""
SQLite Migration Table Order

Table migration order respecting foreign key dependencies.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import List


def get_table_migration_order() -> List[str]:
    """
    Get list of tables in migration order (respecting foreign key dependencies).

    Returns:
        List of table names in correct migration order
    """
    # Order matters: parent tables before child tables
    # Tables are ordered by foreign key dependencies to ensure referential integrity
    return [
        # ========================================================================
        # TIER 1: Core tables with no foreign key dependencies
        # ========================================================================
        "organizations",
        "organization_mindbot_configs",
        "users",
        "mindbot_usage_events",
        "api_keys",
        # ========================================================================
        # TIER 2: Tables that depend on Tier 1
        # ========================================================================
        # Knowledge space tables (depend on users/organizations)
        "knowledge_spaces",  # May reference users/organizations
        "knowledge_documents",  # References knowledge_spaces, users
        "document_chunks",  # References knowledge_documents
        "embeddings",  # References document_chunks
        "child_chunks",  # References document_chunks
        "chunk_attachments",  # References document_chunks
        "document_batches",  # References knowledge_documents
        "document_versions",  # References knowledge_documents
        "document_relationships",  # References knowledge_documents
        "knowledge_queries",  # References knowledge_spaces, users
        "query_feedback",  # References knowledge_queries
        "query_templates",  # References knowledge_spaces
        "evaluation_datasets",  # References knowledge_spaces
        "evaluation_results",  # References evaluation_datasets
        # Diagram tables (depend on users)
        "diagrams",  # References users
        # Market (市场) — catalog and orders
        "market_listings",
        "market_orders",  # References users, market_listings
        "market_payments",  # References market_orders
        "market_entitlements",  # References users, market_listings, market_orders
        "market_subscriptions",  # References users, market_listings
        # Token usage (depends on users)
        "token_usage",  # References users
        # Debate tables (depend on users)
        "debate_sessions",  # References users
        "debate_participants",  # References debate_sessions, users
        "debate_messages",  # References debate_sessions, debate_participants
        "debate_judgments",  # References debate_sessions
        # School zone tables (depend on diagrams, users)
        "shared_diagrams",  # References diagrams, users
        "shared_diagram_likes",  # References shared_diagrams, users
        "shared_diagram_comments",  # References shared_diagrams, users
        # Community tables (depend on users)
        "community_posts",  # References users
        "community_post_likes",  # References community_posts, users
        "community_post_comments",  # References community_posts, users
        # Other tables (depend on users)
        "pinned_conversations",  # References users
        "dashboard_activities",  # References users
        "update_notifications",  # References organizations (optional)
        "update_notification_dismissed",  # References update_notifications, users
        # Library tables (depend on users)
        "library_documents",  # References users
        "library_danmaku",  # References library_documents, users
        "library_danmaku_likes",  # References library_danmaku, users
        "library_danmaku_replies",  # References library_danmaku, users (self-ref parent)
        "library_bookmarks",  # References library_documents, users
        # User activity and usage (depend on users)
        "user_activity_log",  # References users
        "user_usage_stats",  # References users
        "teacher_usage_config",  # No foreign keys
        # Gewe/WeChat tables (standalone, no FK to users)
        "gewe_messages",
        "gewe_contacts",
        "gewe_group_members",
        # Workshop Chat tables (depend on users, chat_channels, chat_messages, direct_messages)
        "chat_channels",
        "channel_members",
        "chat_topics",
        "chat_messages",
        "direct_messages",
        "message_reactions",
        "starred_messages",
        "file_attachments",
        "user_topic_preferences",
        # ========================================================================
        # TIER 3: Chunk test tables (depend on knowledge space tables)
        # ========================================================================
        "chunk_test_documents",  # References knowledge_spaces
        "chunk_test_document_chunks",  # References chunk_test_documents
        "chunk_test_results",  # References chunk_test_documents, chunk_test_document_chunks
    ]
