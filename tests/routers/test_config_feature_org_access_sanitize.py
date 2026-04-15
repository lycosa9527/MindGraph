"""Feature flags API: do not leak full org/user allowlists to non-admins."""

from __future__ import annotations

from types import SimpleNamespace

from models.domain.feature_org_access import FeatureOrgAccessEntry
from routers.api.config import _sanitize_feature_org_access_map


def test_sanitize_keeps_only_calling_users_ids_for_non_admin() -> None:
    user = SimpleNamespace(id=7, role="user", organization_id=5, phone="")
    full = {
        "feature_mindbot": FeatureOrgAccessEntry(
            restrict=True,
            organization_ids=[5, 99, 100],
            user_ids=[7, 42],
        ),
    }
    out = _sanitize_feature_org_access_map(user, full)
    assert out["feature_mindbot"].restrict is True
    assert out["feature_mindbot"].organization_ids == [5]
    assert out["feature_mindbot"].user_ids == [7]


def test_sanitize_empty_when_user_not_in_allowlists() -> None:
    user = SimpleNamespace(id=1, role="user", organization_id=2, phone="")
    full = {
        "feature_mindbot": FeatureOrgAccessEntry(
            restrict=True,
            organization_ids=[99],
            user_ids=[42],
        ),
    }
    out = _sanitize_feature_org_access_map(user, full)
    assert out["feature_mindbot"].organization_ids == []
    assert out["feature_mindbot"].user_ids == []


def test_sanitize_preserves_full_map_for_admin() -> None:
    admin = SimpleNamespace(id=1, role="admin", organization_id=None, phone="")
    full = {
        "feature_mindbot": FeatureOrgAccessEntry(
            restrict=True,
            organization_ids=[5, 99],
            user_ids=[1, 2],
        ),
    }
    out = _sanitize_feature_org_access_map(admin, full)
    assert out == full
