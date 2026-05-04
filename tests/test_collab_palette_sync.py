"""
Test: backend and frontend collab palettes must stay byte-identical.

The colors and emoji lists drive the user-avatar rail and the node-editing
overlay. If the two lists drift, a user can appear as blue on their own
screen and red on a peer's, which wreaks havoc on the collaboration UX. This
test parses the shared TypeScript mirror at
``frontend/src/shared/collabPalette.ts`` and diffs it against the Python
source of truth at ``services/workshop/collab_palette.py``.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from pathlib import Path

from services.online_collab.common.collab_palette import USER_COLORS, USER_EMOJIS

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TS_PATH = _REPO_ROOT / "frontend" / "src" / "shared" / "collabPalette.ts"


def _decode_js_string(literal: str) -> str:
    """
    Decode a JavaScript-style single-quoted string body into a Python ``str``.

    Handles ``\\uXXXX`` escapes and, crucially, *combines* UTF-16 surrogate
    pairs (e.g. ``\\uD83D\\uDD8A`` → ``U+1F58A``) into a single code point.
    Python's ``unicode_escape`` codec does not recombine surrogates on its
    own, which previously caused the emoji palette parity test to report a
    spurious drift between ``\\uD83D\\uDD8A`` and ``U+1F58A`` even though the
    two lists were identical.
    """
    raw = literal.encode("latin-1", errors="strict").decode(
        "raw_unicode_escape"
    )
    return raw.encode("utf-16", errors="surrogatepass").decode(
        "utf-16", errors="strict"
    )


def _extract_list_from_ts(source: str, name: str) -> list[str]:
    """Extract ``const NAME: readonly string[] = Object.freeze([...])`` entries."""
    pattern = (
        rf"export const {re.escape(name)}: readonly string\[] = Object\.freeze\("
        r"\[(?P<body>.*?)\]\s*\)"
    )
    match = re.search(pattern, source, re.DOTALL)
    if not match:
        raise AssertionError(
            f"[palette-sync] cannot locate {name} in {_TS_PATH} - "
            "did the TS mirror's shape change?"
        )
    body = match.group("body")
    items = re.findall(r"'((?:\\[\"'\\/bfnrtv]|\\u[0-9a-fA-F]{4}|[^'\\])*)'", body)
    return [_decode_js_string(item) for item in items]


def test_user_colors_match_frontend() -> None:
    """USER_COLORS must be byte-identical on both sides."""
    ts_source = _TS_PATH.read_text(encoding="utf-8")
    ts_colors = _extract_list_from_ts(ts_source, "USER_COLORS")
    assert ts_colors == USER_COLORS, (
        "Backend/frontend USER_COLORS drift:\n"
        f"  backend: {USER_COLORS}\n"
        f"  frontend: {ts_colors}"
    )


def test_user_emojis_match_frontend() -> None:
    """USER_EMOJIS must be byte-identical on both sides."""
    ts_source = _TS_PATH.read_text(encoding="utf-8")
    ts_emojis = _extract_list_from_ts(ts_source, "USER_EMOJIS")
    assert ts_emojis == USER_EMOJIS, (
        "Backend/frontend USER_EMOJIS drift:\n"
        f"  backend: {USER_EMOJIS}\n"
        f"  frontend: {ts_emojis}"
    )
