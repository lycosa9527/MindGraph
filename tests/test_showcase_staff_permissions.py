"""Showcase staff permission → admin panel capability mapping."""

from __future__ import annotations

from services.showcase.staff_permissions import (
    ALL_SHOWCASE_PERMS,
    PERM_DASHBOARD,
    PERM_DELETE,
    PERM_FIELDS,
    PERM_PERMISSIONS,
    PERM_PUBLISH_PROXY,
    PERM_RECOMMEND,
    PERM_REVIEW,
    PLATFORM_BD_DEFAULT,
    showcase_panel_capabilities,
)


def test_recommend_only_emits_no_panel_capabilities() -> None:
    """Recommend is a gallery action — it must not map to any admin panel caps."""
    assert showcase_panel_capabilities(frozenset({PERM_RECOMMEND})) == frozenset()
    assert showcase_panel_capabilities(frozenset()) == frozenset()


def test_management_perms_unlock_showcase_admin_tab() -> None:
    """Review/delete/proxy/fields/dashboard unlock the admin Showcase tab."""
    for perm in (PERM_REVIEW, PERM_DELETE, PERM_PUBLISH_PROXY, PERM_FIELDS, PERM_DASHBOARD):
        caps = showcase_panel_capabilities(frozenset({perm}))
        assert "tab.showcase.view" in caps, perm


def test_recommend_with_management_maps_recommend_cap() -> None:
    """Recommend panel cap only when paired with management access."""
    caps = showcase_panel_capabilities(frozenset({PERM_RECOMMEND, PERM_REVIEW}))
    assert "tab.showcase.view" in caps
    assert "tab.showcase.recommend" in caps
    assert "tab.showcase.edit" in caps


def test_platform_bd_default_maps_to_management_caps() -> None:
    """Platform BD default perms include Showcase management UI caps."""
    caps = showcase_panel_capabilities(PLATFORM_BD_DEFAULT)
    assert "tab.showcase.view" in caps
    assert "tab.showcase.edit" in caps
    assert "tab.showcase.recommend" in caps
    assert "tab.showcase.fields" in caps
    assert "tab.showcase.dashboard" in caps
    assert "tab.showcase.permissions" not in caps


def test_all_perms_include_permissions_cap() -> None:
    """Full Showcase perm set maps to permissions management."""
    caps = showcase_panel_capabilities(ALL_SHOWCASE_PERMS)
    assert "tab.showcase.permissions" in caps
    assert PERM_PERMISSIONS in ALL_SHOWCASE_PERMS
