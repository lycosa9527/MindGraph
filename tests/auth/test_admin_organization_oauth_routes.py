"""Admin OAuth config is served on the organizations admin path."""

from __future__ import annotations

from fastapi.routing import APIRoute

from routers.auth.admin.organization_oauth import router


def test_oauth_config_is_under_admin_organizations() -> None:
    """Edit-org calls GET/PUT /api/auth/admin/organizations/{id}/oauth-config."""
    methods_by_path: dict[str, set[str]] = {}
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.endswith("/oauth-config"):
            continue
        methods_by_path.setdefault(route.path, set()).update(route.methods or set())
    assert methods_by_path == {
        "/admin/organizations/{org_id}/oauth-config": {"GET", "PUT"},
    }
