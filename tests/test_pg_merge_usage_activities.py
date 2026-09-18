"""user_usage_activities must merge after diagrams so diagram_id can remap."""

from __future__ import annotations

from services.admin.pg_merge_config import TABLE_MERGE_CONFIG, ordered_table_names
from services.admin.pg_merge_table_ops import _remap_fk_values


def test_usage_activities_merge_after_diagrams() -> None:
    """Activities join after diagrams and remap the nullable diagram FK."""
    names = ordered_table_names()
    assert names.index("users") < names.index("user_usage_activities")
    assert names.index("organizations") < names.index("user_usage_activities")
    assert names.index("diagrams") < names.index("user_usage_activities")

    config = TABLE_MERGE_CONFIG["user_usage_activities"]
    assert config["order"] == 4
    assert config["fk_remaps"]["user_id"] == "users"
    assert config["fk_remaps"]["organization_id"] == "organizations"
    assert config["fk_remaps"]["diagram_id"] == "diagrams"


def test_remap_keeps_merged_diagram_id() -> None:
    """Known dump diagram UUIDs stay linked after remap."""
    diagram_id = "a60a3d87-f35e-4635-8a74-6d17a33c8ca1"
    values = {"user_id": 10, "organization_id": 20, "diagram_id": diagram_id}
    broken = _remap_fk_values(
        values,
        TABLE_MERGE_CONFIG["user_usage_activities"]["fk_remaps"],
        {
            "users": {10: 3},
            "organizations": {20: 7},
            "diagrams": {diagram_id: diagram_id},
        },
        {"organization_id", "diagram_id"},
    )
    assert broken is False
    assert values["user_id"] == 3
    assert values["organization_id"] == 7
    assert values["diagram_id"] == diagram_id


def test_remap_nulls_missing_diagram_id() -> None:
    """Missing diagram UUIDs become NULL so the activity row still inserts."""
    values = {
        "user_id": 10,
        "organization_id": 20,
        "diagram_id": "02e9332b-f73d-4d63-bb54-f4a3d83fd3f4",
    }
    broken = _remap_fk_values(
        values,
        TABLE_MERGE_CONFIG["user_usage_activities"]["fk_remaps"],
        {
            "users": {10: 3},
            "organizations": {20: 7},
            "diagrams": {},
        },
        {"organization_id", "diagram_id"},
    )
    assert broken is False
    assert values["diagram_id"] is None
    assert values["user_id"] == 3
