"""
Registry of API generation language codes and English display names for LLM instructions.

Single source: data/prompt_language_registry.json (emit via scripts/build_prompt_language_registry.py).

Templates remain zh+en in prompts/; any code here maps to English-keyed templates plus
output_language_instruction() footer text.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "data" / "prompt_language_registry.json"


def _load_registry() -> tuple[frozenset[str], dict[str, str]]:
    if not _REGISTRY_PATH.is_file():
        raise FileNotFoundError(
            f"Missing prompt language registry: {_REGISTRY_PATH}. "
            "Run: python scripts/build_prompt_language_registry.py"
        )
    with _REGISTRY_PATH.open(encoding="utf-8") as handle:
        rows = json.load(handle)
    codes: set[str] = set()
    names: dict[str, str] = {}
    for row in rows:
        code = str(row["code"]).lower().strip()
        codes.add(code)
        names[code] = str(row["englishName"])
    return frozenset(codes), names


PROMPT_OUTPUT_LANGUAGE_CODES: frozenset[str]
OUTPUT_LANGUAGE_ENGLISH_NAMES: dict[str, str]
PROMPT_OUTPUT_LANGUAGE_CODES, OUTPUT_LANGUAGE_ENGLISH_NAMES = _load_registry()


def is_prompt_output_language(code: str) -> bool:
    """Return True if code is a supported generation language."""
    if not isinstance(code, str):
        return False
    normalized = code.lower().strip()
    return normalized in PROMPT_OUTPUT_LANGUAGE_CODES
