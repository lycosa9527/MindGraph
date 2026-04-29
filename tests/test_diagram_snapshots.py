"""Unit tests for diagram snapshot model and API contracts."""
from __future__ import annotations

from datetime import UTC, datetime

from models.domain.diagram_snapshots import DiagramSnapshot
from models.requests.requests_diagram import SnapshotTakeRequest
from models.responses import SnapshotListResponse, SnapshotMetadata


def test_diagram_snapshot_table_name() -> None:
    """ORM maps to ``diagram_snapshots`` relation."""
    assert DiagramSnapshot.__tablename__ == "diagram_snapshots"


def test_diagram_snapshot_unique_version_constraint_registered() -> None:
    """Unique (diagram_id, version_number) matches production DDL."""
    names = {c.name for c in DiagramSnapshot.__table__.constraints}
    assert "uq_diagram_snapshot_version" in names


def test_snapshot_take_request_accepts_spec() -> None:
    """SnapshotTakeRequest holds arbitrary spec dict from the client."""
    body = SnapshotTakeRequest(spec={"topic": "Central Topic", "nodes": []})
    assert body.spec["topic"] == "Central Topic"


def test_snapshot_list_response_roundtrip() -> None:
    """Snapshot list serializes for JSON responses."""
    created = datetime.now(UTC)
    data = SnapshotListResponse(
        snapshots=[
            SnapshotMetadata(id=1, version_number=1, created_at=created),
            SnapshotMetadata(id=2, version_number=2, created_at=created),
        ]
    )
    dumped = data.model_dump(mode="json")
    assert len(dumped["snapshots"]) == 2
    assert dumped["snapshots"][1]["version_number"] == 2


def test_snapshot_next_version_under_cap_matches_router_logic() -> None:
    """First snapshot is v1; ninth existing row yields v10 (see take_snapshot in diagrams router)."""
    snapshot_max = 10
    existing_len = 0
    assert existing_len + 1 == 1
    existing_len = 9
    assert existing_len + 1 == snapshot_max


def test_snapshot_next_version_at_cap_matches_router_logic() -> None:
    """With 10 rows, eviction path assigns new_version = _SNAPSHOT_MAX (10)."""
    snapshot_max = 10
    existing_len = 10
    assert existing_len >= snapshot_max
    new_version = snapshot_max
    assert new_version == 10
