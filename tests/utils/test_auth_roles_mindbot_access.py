"""Tests for MindBot feature access: managers respect feature_org_access grants."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from utils.auth.roles import user_has_feature_access


def _sample_manager() -> SimpleNamespace:
    return SimpleNamespace(id=100, role="manager", organization_id=5, phone="")


def _sample_admin() -> SimpleNamespace:
    return SimpleNamespace(id=1, role="admin", organization_id=None, phone="")


@patch("utils.auth.roles._global_feature_flag_enabled", return_value=True)
@patch("utils.auth.roles._get_feature_access_map_cached", return_value={})
def test_manager_mindbot_allowed_when_no_db_rule(
    _mock_cache: object,
    _mock_flag: object,
) -> None:
    assert user_has_feature_access(_sample_manager(), "feature_mindbot") is True


@patch("utils.auth.roles._global_feature_flag_enabled", return_value=True)
@patch(
    "utils.auth.roles._get_feature_access_map_cached",
    return_value={
        "feature_mindbot": SimpleNamespace(
            restrict=True,
            organization_ids=[5],
            user_ids=[],
        ),
    },
)
def test_manager_mindbot_allowed_when_org_granted(
    _mock_cache: object,
    _mock_flag: object,
) -> None:
    assert user_has_feature_access(_sample_manager(), "feature_mindbot") is True


@patch("utils.auth.roles._global_feature_flag_enabled", return_value=True)
@patch(
    "utils.auth.roles._get_feature_access_map_cached",
    return_value={
        "feature_mindbot": SimpleNamespace(
            restrict=True,
            organization_ids=[99],
            user_ids=[],
        ),
    },
)
def test_manager_mindbot_denied_when_org_not_granted(
    _mock_cache: object,
    _mock_flag: object,
) -> None:
    assert user_has_feature_access(_sample_manager(), "feature_mindbot") is False


@patch("utils.auth.roles._global_feature_flag_enabled", return_value=True)
@patch(
    "utils.auth.roles._get_feature_access_map_cached",
    return_value={
        "feature_mindbot": SimpleNamespace(
            restrict=True,
            organization_ids=[],
            user_ids=[100],
        ),
    },
)
def test_manager_mindbot_allowed_when_user_granted(
    _mock_cache: object,
    _mock_flag: object,
) -> None:
    assert user_has_feature_access(_sample_manager(), "feature_mindbot") is True


@patch("utils.auth.roles._global_feature_flag_enabled", return_value=True)
def test_admin_mindbot_always_allowed_with_restrictive_map(
    _mock_flag: object,
) -> None:
    with patch(
        "utils.auth.roles._get_feature_access_map_cached",
        return_value={
            "feature_mindbot": SimpleNamespace(
                restrict=True,
                organization_ids=[],
                user_ids=[],
            ),
        },
    ):
        assert user_has_feature_access(_sample_admin(), "feature_mindbot") is True


@patch("utils.auth.roles._global_feature_flag_enabled", return_value=True)
@patch(
    "utils.auth.roles._get_feature_access_map_cached",
    return_value={
        "feature_library": SimpleNamespace(
            restrict=True,
            organization_ids=[],
            user_ids=[],
        ),
    },
)
def test_manager_non_mindbot_still_bypasses_restrictive_rule(
    _mock_cache: object,
    _mock_flag: object,
) -> None:
    assert user_has_feature_access(_sample_manager(), "feature_library") is True
