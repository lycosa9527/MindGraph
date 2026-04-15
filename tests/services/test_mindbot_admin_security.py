"""MindBot admin API: organization isolation for school managers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from routers.api.mindbot import _callback_metrics_snapshot_for_user
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.telemetry.metrics import mindbot_metrics


def test_callback_metrics_snapshot_admin_sees_all() -> None:
    admin = SimpleNamespace(id=1, role="admin", organization_id=None, phone="")
    with patch.object(mindbot_metrics, "snapshot", return_value={"by_error_code": {"OK": 1}}):
        out = _callback_metrics_snapshot_for_user(admin)
    assert out == {"by_error_code": {"OK": 1}}


def test_callback_metrics_snapshot_manager_only_own_org() -> None:
    mgr = SimpleNamespace(id=10, role="manager", organization_id=5, phone="")
    full = {
        "by_error_code": {"OK": 100},
        "by_organization_id": {
            5: {MindbotErrorCode.OK.value: 3},
            99: {MindbotErrorCode.OK.value: 50},
        },
        "by_robot_code": {"r1": {MindbotErrorCode.OK.value: 1}},
    }
    with patch.object(mindbot_metrics, "snapshot", return_value=full):
        out = _callback_metrics_snapshot_for_user(mgr)
    assert out["by_error_code"] == {}
    assert out["by_robot_code"] == {}
    assert out["by_organization_id"] == {5: {MindbotErrorCode.OK.value: 3}}
    assert 99 not in out["by_organization_id"]


def test_callback_metrics_snapshot_manager_no_org_empty() -> None:
    mgr = SimpleNamespace(id=10, role="manager", organization_id=None, phone="")
    with patch.object(
        mindbot_metrics,
        "snapshot",
        return_value={"by_organization_id": {1: {"OK": 1}}},
    ):
        out = _callback_metrics_snapshot_for_user(mgr)
    assert out["by_organization_id"] == {}
