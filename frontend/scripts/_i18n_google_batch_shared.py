"""Shared helpers for Google (deep_translator) batch scripts."""

from __future__ import annotations

import re
import time
from collections.abc import Callable

import requests
from deep_translator import GoogleTranslator
from deep_translator.exceptions import RequestError, TooManyRequests, TranslationNotFound

GOOGLE_TARGET = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
}

_PLACEHOLDER = re.compile(r"\{[^{}]+\}")


def shield_placeholders(text: str) -> tuple[str, list[str]]:
    found: list[str] = []

    def _sub(match: re.Match[str]) -> str:
        found.append(match.group(0))
        return f"ZZ__PH__{len(found) - 1}__ZZ"

    return _PLACEHOLDER.sub(_sub, text), found


def unshield_placeholders(text: str, found: list[str]) -> str:
    out = text
    for index, token in enumerate(found):
        out = out.replace(f"ZZ__PH__{index}__ZZ", token)
    return out


def google_target(locale: str, override: str | None) -> str:
    if override:
        return override
    key = locale.lower().replace("_", "-")
    return GOOGLE_TARGET.get(key, locale)


def patch_requests_timeout(connect: float, read: float) -> Callable[[], None]:
    original = requests.get

    def wrapped(*args, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = (connect, read)
        return original(*args, **kwargs)

    requests.get = wrapped

    def restore() -> None:
        requests.get = original

    return restore


def translate_with_retries(
    translator: GoogleTranslator,
    text: str,
    *,
    retries: int,
    retry_base_delay: float,
) -> str:
    if retries < 1:
        raise ValueError("retries must be at least 1")
    for attempt in range(retries):
        try:
            return translator.translate(text)
        except TranslationNotFound:
            return text
        except (requests.RequestException, TooManyRequests, RequestError):
            if attempt + 1 >= retries:
                raise
            time.sleep(retry_base_delay * (2**attempt))
