"""API locale resolution and message fallback (tier-27)."""
from __future__ import annotations

import pytest

from models.domain.api_locale import (
    API_MESSAGE_LOCALE_SET,
    resolve_request_locale,
)
from models.domain.messages import Messages, get_request_language


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
    assert resolve_request_locale(header) == expected


def test_get_request_language_defaults_to_en() -> None:
    assert get_request_language(None, None) == "en"


def test_get_request_language_x_language_fr() -> None:
    assert get_request_language("fr", None) == "fr"


def test_messages_error_falls_back_en_for_generated_locales() -> None:
    """Locales whose catalog values were filled from ``en`` return English for this key."""
    msg_en = Messages.error("invalid_request", lang="en")
    for code in sorted(API_MESSAGE_LOCALE_SET - {"zh", "zh-tw", "az"}):
        got = Messages.error("invalid_request", lang=code)
        assert got == msg_en


def test_messages_error_preserves_az_translation() -> None:
    az = Messages.error("invalid_request", lang="az")
    en = Messages.error("invalid_request", lang="en")
    assert az != en


def test_messages_get_positional_lang_kwarg() -> None:
    out = Messages.get("ERRORS", "invalid_request", "de", lang="en")
    assert out == Messages.error("invalid_request", lang="de")
