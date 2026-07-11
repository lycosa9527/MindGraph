"""Load multi-variant Kitty ack phrase pools from JSON."""

from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

_POOLS_PATH = Path(__file__).with_name("ack_phrase_pools.json")
_LAST_PICKED: Dict[str, str] = {}


@lru_cache(maxsize=1)
def load_ack_phrase_pools() -> Dict[str, Dict[str, List[str]]]:
    """Load phrase pools once (zh/en lists per ack key)."""
    with _POOLS_PATH.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        return {}
    pools: Dict[str, Dict[str, List[str]]] = {}
    for key, row in raw.items():
        if not isinstance(key, str) or not isinstance(row, dict):
            continue
        langs: Dict[str, List[str]] = {}
        for lang, lines in row.items():
            if not isinstance(lang, str) or not isinstance(lines, list):
                continue
            cleaned = [str(item) for item in lines if str(item).strip()]
            if cleaned:
                langs[lang] = cleaned
        if langs:
            pools[key] = langs
    return pools


def pick_ack_template(
    key: str,
    lang: str,
    fallback: str,
    *,
    variant_index: Optional[int] = None,
) -> str:
    """
    Pick a template string for ``key``/``lang``.

    When ``variant_index`` is set, selection is deterministic (tests).
    Otherwise pick randomly and avoid repeating the previous line for the
    same key+lang when possible.
    """
    pools = load_ack_phrase_pools()
    row = pools.get(key)
    if not row:
        return fallback
    lines = row.get(lang) or row.get("zh") or []
    if not lines:
        return fallback
    if variant_index is not None:
        return lines[variant_index % len(lines)]
    cache_key = f"{key}:{lang}"
    previous = _LAST_PICKED.get(cache_key)
    choices = [line for line in lines if line != previous] or list(lines)
    picked = random.choice(choices)
    _LAST_PICKED[cache_key] = picked
    return picked


def ack_pool_lines(key: str, lang: str = "zh") -> List[str]:
    """Return pool lines for tests (empty if missing)."""
    row = load_ack_phrase_pools().get(key) or {}
    return list(row.get(lang) or row.get("zh") or [])
