"""Bayi SSO accounts keep the shared default name until the teacher sets one."""

from utils.auth import bayi_mode


def test_bayi_placeholder_needs_a_real_name(monkeypatch) -> None:
    """The default label and a blank name both ask for a real name."""
    monkeypatch.setattr(bayi_mode, "AUTH_MODE", "bayi")
    monkeypatch.setattr(bayi_mode, "BAYI_SSO_DEFAULT_DISPLAY_NAME", "八一用户")

    assert bayi_mode.user_needs_display_name("八一用户") is True
    assert bayi_mode.user_needs_display_name("  ") is True
    assert bayi_mode.user_needs_display_name(None) is True
    assert bayi_mode.is_bayi_placeholder_display_name("八一用户") is True
    assert bayi_mode.user_needs_display_name("王老师") is False
    assert bayi_mode.is_bayi_placeholder_display_name("王老师") is False


def test_uuid_user_id_is_stored_in_one_form(monkeypatch) -> None:
    """Uppercase and braced UUIDs become the same lowercase id."""
    monkeypatch.setattr(bayi_mode, "AUTH_MODE", "bayi")
    raw = "A1B2C3D4-E5F6-4789-A012-3456789ABCDE"
    canonical = bayi_mode.canonical_bayi_subject("{" + raw + "}")
    assert canonical == raw.lower()
    assert bayi_mode.canonical_bayi_subject(canonical) == canonical
    assert bayi_mode.canonical_bayi_subject("teacher-42") == "teacher-42"
    assert bayi_mode.is_bayi_sso_phone(canonical) is True
    assert bayi_mode.same_account_key(raw, canonical) is True
    assert bayi_mode.same_account_key("13800138000", "13800138001") is False
    assert bayi_mode.is_bayi_sso_phone("bayi@system.com") is False


def test_sso_phone_flag_is_bayi_only(monkeypatch) -> None:
    """A UUID phone is a normal phone outside Bayi mode."""
    monkeypatch.setattr(bayi_mode, "AUTH_MODE", "standard")
    assert bayi_mode.is_bayi_sso_phone("a1b2c3d4-e5f6-4789-a012-3456789abcde") is False
    assert bayi_mode.is_admin_account_phone("ed2d998e-495e-46cc-ab7d-2d64ccba4b92") is False
    assert bayi_mode.is_admin_account_phone("13800138000") is True


def test_admin_account_phone_accepts_xiaozhi_uuid_in_bayi(monkeypatch) -> None:
    """Bayi stores 小致 userId in the phone column, so role edits must keep it."""
    monkeypatch.setattr(bayi_mode, "AUTH_MODE", "bayi")
    uuid_phone = "ed2d998e-495e-46cc-ab7d-2d64ccba4b92"
    assert bayi_mode.is_admin_account_phone(uuid_phone) is True
    assert bayi_mode.is_admin_account_phone("13800138000") is True
    assert bayi_mode.is_admin_account_phone("not-a-phone") is False


def test_other_auth_modes_skip_the_name_prompt(monkeypatch) -> None:
    """Standard accounts may keep any display name, including the Bayi default."""
    monkeypatch.setattr(bayi_mode, "AUTH_MODE", "standard")
    monkeypatch.setattr(bayi_mode, "BAYI_SSO_DEFAULT_DISPLAY_NAME", "八一用户")

    assert bayi_mode.user_needs_display_name("八一用户") is False
    assert bayi_mode.is_bayi_placeholder_display_name("八一用户") is False
