"""Regression: Showcase field options catalog must be readable by publishers.

Admin Fields CRUD is panel-scoped; publish/filter dropdowns use
GET /api/showcase/meta under authenticated RLS. Panel-only SELECT on
case_square_field_options hid DB rows and forced hardcoded fallbacks.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_field_options_create_migration_uses_catalog_read() -> None:
    """Greenfield 0085 must community-read field options (not panel-only SELECT)."""
    text = _read("alembic/versions/rev_0085_case_square_admin.py")
    assert "def _catalog_rls" in text
    assert '_catalog_rls("case_square_field_options")' in text
    assert '_panel_rls("case_square_field_options")' not in text
    assert 'CATALOG_READ = "rls_community_read_allowed()"' in text
    assert '_panel_rls("case_square_staff_grants")' in text
    assert '_panel_rls("case_square_audit_log")' in text


def test_field_options_repair_migration_opens_select() -> None:
    """0094 repairs existing DBs that still have panel-only SELECT."""
    text = _read("alembic/versions/rev_0094_case_square_field_options_community_read.py")
    assert 'down_revision: Union[str, None] = "0093"' in text
    assert '_CATALOG_READ = "rls_community_read_allowed()"' in text
    assert "FOR SELECT USING ({_CATALOG_READ})" in text
    assert '_PANEL_ONLY = "rls_is_panel_mode()"' in text
    assert "FOR INSERT" not in text
    assert "FOR UPDATE" not in text
    assert "FOR DELETE" not in text


def test_meta_route_and_service_are_db_backed() -> None:
    """Public meta must load subjects/grades/tags from field_options service."""
    feed = _read("routers/features/showcase/routes_feed.py")
    service = _read("services/showcase/field_options.py")
    assert "load_meta_payload" in feed
    assert '@router.get("/meta")' in feed
    assert 'load_active_values(db, "subject")' in service
    assert 'load_active_values(db, "grade")' in service
    assert 'load_active_values(db, "recommended_tag")' in service
    assert "invalidate_field_options_cache_async" in service


def test_frontend_publish_and_filters_consume_showcase_meta() -> None:
    """Upload modal and filter UIs must use useShowcaseMeta (not admin-only API)."""
    meta_hook = _read("frontend/src/composables/showcase/useShowcaseMeta.ts")
    publish = _read("frontend/src/composables/showcase/usePublishShowcaseModal.ts")
    fields_admin = _read("frontend/src/components/admin/AdminShowcaseFields.vue")
    api = _read("frontend/src/utils/apiClient.ts")

    assert "getShowcaseMeta" in meta_hook
    assert "recommended_tags" in meta_hook
    assert "useShowcaseMeta" in publish
    assert "queryKey: ['showcaseMeta']" in fields_admin
    assert "invalidateQueries" in fields_admin
    assert "/api/showcase/meta" in api
    assert "/api/auth/admin/showcase/field-options" in api
