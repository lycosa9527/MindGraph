"""Showcase tables must remappable by phone for test↔prod MG id mismatches."""

from __future__ import annotations

from services.admin.pg_merge_config import TABLE_MERGE_CONFIG, ordered_table_names


def test_showcase_tables_registered_for_phone_user_remap() -> None:
    """case_square_* join merge after users so author_id remaps by phone."""
    names = ordered_table_names()
    assert names.index("users") < names.index("case_square_posts")
    assert names.index("case_square_posts") < names.index("case_square_post_likes")
    assert names.index("case_square_posts") < names.index("case_square_post_favorites")
    assert names.index("case_square_posts") < names.index("case_square_audit_log")

    posts = TABLE_MERGE_CONFIG["case_square_posts"]
    assert posts["fk_remaps"]["author_id"] == "users"
    assert posts["fk_remaps"]["submitted_by_id"] == "users"
    assert posts["fk_remaps"]["reviewed_by"] == "users"
    assert posts["fk_remaps"]["expert_recommended_by"] == "users"

    likes = TABLE_MERGE_CONFIG["case_square_post_likes"]
    assert likes["fk_remaps"]["user_id"] == "users"
    assert likes["fk_remaps"]["post_id"] == "case_square_posts"

    grants = TABLE_MERGE_CONFIG["case_square_staff_grants"]
    assert grants.get("singleton_user") is True
    assert grants["fk_remaps"]["user_id"] == "users"
