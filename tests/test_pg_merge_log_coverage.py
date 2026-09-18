"""PG merge config covers every Unique/FK class from the 2026-09-18 dump log."""

from __future__ import annotations

from services.admin.pg_merge_config import (
    TABLE_MERGE_CONFIG,
    ordered_table_names,
    table_has_merge_identity,
)
from services.admin.pg_merge_dedup import chat_channel_fingerprint
from services.admin.pg_merge_table_ops import (
    _apply_mapped_parent,
    _is_duplicate,
    _staging_rows_parents_first,
)


def test_merge_order_covers_folder_and_activity_fks() -> None:
    """Folders and batches land before diagrams; activities land after diagrams."""
    names = ordered_table_names()
    assert names.index("diagram_folders") < names.index("diagrams")
    assert names.index("document_batches") < names.index("diagrams")
    assert names.index("diagrams") < names.index("user_usage_activities")
    assert names.index("diagrams") < names.index("chat_channels")


def test_users_dedup_by_email_when_phone_missing() -> None:
    """Overseas email-only users collide on uq_users_email, not phone."""
    config = TABLE_MERGE_CONFIG["users"]
    assert config["dedup_key"] == "phone"
    assert config["skip_dedup_key_when_null"] is True
    assert config["alt_dedup_keys"] == ("email",)

    table_id_map: dict[int, int] = {}
    assert _is_duplicate(
        {"phone": None, "email": "roy.wang@live.com"},
        config,
        {},
        table_id_map,
        4573,
        "phone",
        None,
        None,
        {"email": {"roy.wang@live.com": 88}},
    )
    assert table_id_map[4573] == 88


def test_diagrams_remap_nullable_folder_and_package() -> None:
    """Missing archive folders must null folder_id instead of aborting the diagram."""
    remaps = TABLE_MERGE_CONFIG["diagrams"]["fk_remaps"]
    assert remaps["folder_id"] == "diagram_folders"
    assert remaps["knowledge_package_id"] == "document_batches"
    assert remaps["user_id"] == "users"
    assert TABLE_MERGE_CONFIG["diagram_folders"]["pk_type"] == "uuid"


def test_chat_channel_fingerprint_matches_live_unique_indexes() -> None:
    """Announce is a singleton; live groups share (org, parent, name)."""
    assert TABLE_MERGE_CONFIG["chat_channels"]["dedup_fingerprint"] == "chat_channel"
    assert chat_channel_fingerprint({"channel_type": "announce", "is_archived": False, "name": "公告"}) == ("announce",)
    assert chat_channel_fingerprint(
        {
            "channel_type": "public",
            "is_archived": False,
            "organization_id": 5,
            "parent_id": None,
            "name": "STEM教研组",
        }
    ) == (5, None, "STEM教研组", False, None)
    archived = chat_channel_fingerprint(
        {
            "channel_type": "public",
            "is_archived": True,
            "organization_id": 5,
            "parent_id": None,
            "name": "旧教研组",
            "created_at": None,
        }
    )
    assert archived == (5, None, "旧教研组", True, None)


def test_every_merge_table_has_identity() -> None:
    """Serial event tables must skip on re-merge so tokens/activities never double."""
    missing = [name for name, config in TABLE_MERGE_CONFIG.items() if not table_has_merge_identity(config)]
    assert missing == []


def test_usage_tables_dedup_on_event_identity() -> None:
    """Token and activity rows match on event fields, not serial id."""
    token_cols = TABLE_MERGE_CONFIG["token_usage"]["dedup_columns"]
    assert "user_id" in token_cols
    assert "created_at" in token_cols
    assert "total_tokens" in token_cols
    assert "session_id" in token_cols

    activity_cols = TABLE_MERGE_CONFIG["user_usage_activities"]["dedup_columns"]
    assert "user_id" in activity_cols
    assert "created_at" in activity_cols
    assert "title" in activity_cols
    assert "diagram_id" not in activity_cols

    assert TABLE_MERGE_CONFIG["user_activity_log"]["dedup_columns"] == (
        "user_id",
        "activity_type",
        "created_at",
    )
    assert TABLE_MERGE_CONFIG["mindbot_usage_events"]["dedup_fingerprint"] == ("mindbot_usage_event")


def test_users_with_phone_still_dedup_on_phone() -> None:
    """skip_dedup_key_when_null only skips empty phones, not populated ones."""
    config = TABLE_MERGE_CONFIG["users"]
    table_id_map: dict[int, int] = {}
    assert _is_duplicate(
        {"phone": "13800000000", "email": "a@b.c"},
        config,
        {"13800000000": 3},
        table_id_map,
        10,
        "phone",
        None,
        None,
        {"email": {}},
    )
    assert table_id_map[10] == 3


def test_self_ref_parents_merge_before_children() -> None:
    """Child parent_id remaps only after the parent row has a live PK."""
    rows = [
        {"id": 2, "parent_id": 1, "name": "child"},
        {"id": 1, "parent_id": None, "name": "root"},
    ]
    ordered = _staging_rows_parents_first(rows, "parent_id", "id")
    assert [row["id"] for row in ordered] == [1, 2]

    child = {"parent_id": 1}
    assert _apply_mapped_parent(child, "parent_id", {}) == 1
    assert child["parent_id"] == 1
    assert _apply_mapped_parent(child, "parent_id", {1: 88}) is None
    assert child["parent_id"] == 88


def test_child_channel_dedup_uses_remapped_parent() -> None:
    """Live unique is (org, parent, name); dump parent ids must remap first."""
    config = TABLE_MERGE_CONFIG["chat_channels"]
    table_id_map: dict[int, int] = {}
    assert _is_duplicate(
        {
            "channel_type": "public",
            "is_archived": False,
            "organization_id": 5,
            "parent_id": 88,
            "name": "勾股定理",
        },
        config,
        {(5, 88, "勾股定理", False, None): 12},
        table_id_map,
        99,
        None,
        None,
        "chat_channel",
    )
    assert table_id_map[99] == 12


def test_library_bookmarks_dedup_by_uuid() -> None:
    """Same bookmark uuid must map even when document_id was remapped."""
    config = TABLE_MERGE_CONFIG["library_bookmarks"]
    assert config["alt_dedup_keys"] == ("uuid",)
    table_id_map: dict[int, int] = {}
    bookmark_uuid = "323e8de6-5351-4517-a724-64191d6a6784"
    assert _is_duplicate(
        {"document_id": 88, "user_id": 3634, "page_number": 1, "uuid": bookmark_uuid},
        config,
        {},
        table_id_map,
        1,
        None,
        ("document_id", "user_id", "page_number"),
        None,
        {"uuid": {bookmark_uuid: 9}},
    )
    assert table_id_map[1] == 9
