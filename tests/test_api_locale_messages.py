"""API locale resolution and message fallback (tier-27)."""

from __future__ import annotations

from typing import cast

import pytest

from models.domain.api_locale import (
    API_MESSAGE_LOCALE_SET,
    resolve_request_locale,
)
from models.domain.messages import Language, Messages, get_request_language


@pytest.mark.parametrize(
    "header,expected",
    [
        ("de", "de"),
        ("DE-at", "de"),
        ("zh-TW", "zh-tw"),
        ("zh-tw", "zh-tw"),
        ("zh_cn", "zh"),
        ("zh", "zh"),
        ("en-GB", "en"),
        ("pt-BR", "pt"),
        ("xx-YY", None),
    ],
)
def test_resolve_request_locale(header: str, expected: str | None) -> None:
    """Test resolve request locale."""
    assert resolve_request_locale(header) == expected


def test_get_request_language_defaults_to_en() -> None:
    """Test get request language defaults to en."""
    assert get_request_language(None, None) == "en"


def test_get_request_language_x_language_fr() -> None:
    """Test get request language x language fr."""
    assert get_request_language("fr", None) == "fr"


def test_messages_error_falls_back_en_for_generated_locales() -> None:
    """Locales whose catalog values were filled from ``en`` return English for this key."""
    msg_en = Messages.error("invalid_request", lang="en")
    for code in sorted(API_MESSAGE_LOCALE_SET - {"zh", "zh-tw", "az"}):
        got = Messages.error("invalid_request", lang=cast(Language, code))
        assert got == msg_en


def test_messages_error_preserves_az_translation() -> None:
    """Test messages error preserves az translation."""
    az = Messages.error("invalid_request", lang="az")
    en = Messages.error("invalid_request", lang="en")
    assert az != en


def test_messages_get_positional_lang_kwarg() -> None:
    """Test messages get positional lang kwarg."""
    out = Messages.get("ERRORS", "invalid_request", "de", lang="en")
    assert out == Messages.error("invalid_request", lang="de")
