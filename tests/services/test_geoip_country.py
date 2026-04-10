"""Tests for GeoIP country helpers and email login CN policy."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.auth.geoip_country import (
    evaluate_email_login_geoip,
    overseas_email_registration_allowed,
    resolve_country_iso_from_request,
)


@pytest.mark.parametrize(
    ("code", "whitelisted", "must_deny", "key_suffix"),
    (
        ("CN", False, True, "email_login_blocked_in_mainland_china"),
        ("CN", True, False, ""),
        ("US", False, False, ""),
        (None, False, True, "login_email_geoip_unavailable"),
    ),
)
def test_evaluate_email_login_geoip(
    code: str | None,
    whitelisted: bool,
    must_deny: bool,
    key_suffix: str,
) -> None:
    with patch("services.auth.geoip_country.lookup_country_iso_code", return_value=code):
        deny, msg_key = evaluate_email_login_geoip("203.0.113.1", whitelisted)
    assert deny is must_deny
    if must_deny:
        assert msg_key == key_suffix
    else:
        assert msg_key == ""


def test_overseas_registration_uses_lookup() -> None:
    with patch("services.auth.geoip_country.lookup_country_iso_code", return_value="CN"):
        allowed, err = overseas_email_registration_allowed("203.0.113.1")
    assert allowed is False
    assert err == "registration_email_not_available_in_region"


def test_overseas_registration_none_allows_with_domain_check_elsewhere() -> None:
    with patch("services.auth.geoip_country.lookup_country_iso_code", return_value=None):
        allowed, err = overseas_email_registration_allowed("203.0.113.1")
    assert allowed is True
    assert err == ""


def test_resolve_country_iso_from_request_prefers_cf_header() -> None:
    request = MagicMock()
    request.headers = {"CF-IPCountry": "us"}
    assert resolve_country_iso_from_request(request) == "US"


def test_resolve_country_iso_from_request_falls_back_to_lookup() -> None:
    request = MagicMock()
    request.headers = {}
    request.client.host = "203.0.113.1"
    with patch("services.auth.geoip_country.lookup_country_iso_code", return_value="CN"):
        assert resolve_country_iso_from_request(request) == "CN"
