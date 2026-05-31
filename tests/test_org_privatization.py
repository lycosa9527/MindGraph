"""Unit tests for derived organization privatization state."""

from __future__ import annotations

from types import SimpleNamespace

from utils.auth.org_privatization import organization_is_privatized, org_privatization_list_field


def _org(**fields: object) -> SimpleNamespace:
    defaults = {
        "mindmate_agent_name": None,
        "mindmate_agent_avatar_url": None,
        "dify_api_base_url": None,
        "dify_api_key": None,
    }
    defaults.update(fields)
    return SimpleNamespace(**defaults)


def test_not_privatized_when_all_empty() -> None:
    org = _org()
    assert organization_is_privatized(org) is False
    assert org_privatization_list_field(org) == {"is_privatized": False}


def test_not_privatized_with_agent_name_only() -> None:
    org = _org(mindmate_agent_name="小助手")
    assert organization_is_privatized(org) is False


def test_not_privatized_with_avatar_only() -> None:
    org = _org(mindmate_agent_avatar_url="/static/org_mindmate_avatars/1/avatar.png")
    assert organization_is_privatized(org) is False


def test_not_privatized_with_dify_key_only() -> None:
    org = _org(dify_api_key="app-secret-key")
    assert organization_is_privatized(org) is False


def test_not_privatized_with_dify_url_and_key_missing_pair() -> None:
    org = _org(
        mindmate_agent_name="Mind",
        mindmate_agent_avatar_url="/static/org_mindmate_avatars/2/avatar.gif",
        dify_api_key="key",
    )
    assert organization_is_privatized(org) is False
    org_with_url_only = _org(
        mindmate_agent_name="Mind",
        mindmate_agent_avatar_url="/static/org_mindmate_avatars/2/avatar.gif",
        dify_api_base_url="https://dify.example.com/v1",
    )
    assert organization_is_privatized(org_with_url_only) is False


def test_not_privatized_with_two_of_three_criteria() -> None:
    org = _org(
        mindmate_agent_name="Mind",
        mindmate_agent_avatar_url="/static/org_mindmate_avatars/2/avatar.gif",
    )
    assert organization_is_privatized(org) is False


def test_whitespace_only_fields_are_not_privatized() -> None:
    org = _org(
        mindmate_agent_name="   ",
        mindmate_agent_avatar_url="  ",
        dify_api_key="\t",
    )
    assert organization_is_privatized(org) is False


def test_privatized_when_all_three_criteria_met() -> None:
    org = _org(
        mindmate_agent_name="Mind",
        mindmate_agent_avatar_url="/static/org_mindmate_avatars/2/avatar.gif",
        dify_api_base_url="https://dify.example.com/v1",
        dify_api_key="key",
    )
    assert organization_is_privatized(org) is True
    assert org_privatization_list_field(org) == {"is_privatized": True}


def test_admin_list_payload_marks_privatized_after_superadmin_configures_all_three() -> None:
    """Mirrors GET /admin/organizations field assembly for one fully configured school."""
    from routers.auth.admin.organization_dify import dify_list_fields
    from routers.auth.admin.organization_mindmate_branding import mindmate_branding_list_fields

    org = _org(
        mindmate_agent_name="SchoolBot",
        mindmate_agent_avatar_url="/static/org_mindmate_avatars/5/avatar.png",
        dify_api_base_url="https://dify.example.com/v1",
        dify_api_key="app-secret",
    )
    payload = {
        **dify_list_fields(org),
        **mindmate_branding_list_fields(org),
        **org_privatization_list_field(org),
    }
    assert payload["is_privatized"] is True
    assert payload["mindmate_agent_name"] == "SchoolBot"
    assert payload["mindmate_agent_avatar_url"] == "/static/org_mindmate_avatars/5/avatar.png"
    assert payload["dify_api_base_url"] == "https://dify.example.com/v1"
    assert payload["dify_api_key_masked"] is not None
