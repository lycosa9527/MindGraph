"""Resolve section keys from indexed chunks (exact + fuzzy fallback)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, List, Optional


def _normalize_key(value: str) -> str:
    return re.sub(r"[\s_]+", "-", (value or "").lower().strip())


def _chapter_number(key: str) -> Optional[str]:
    match = re.match(r"^chapter-(\d+)$", _normalize_key(key))
    return match.group(1) if match else None


def score_section_key_match(candidate: str, target: str) -> float:
    """Score how well *candidate* matches desired *target* (higher is better)."""
    cand = _normalize_key(candidate)
    want = _normalize_key(target)
    if not cand or not want:
        return 0.0
    if cand == want:
        return 1.0
    if cand.startswith(f"{want}-") or want.startswith(f"{cand}-"):
        return 0.92

    cand_chapter = _chapter_number(cand)
    want_chapter = _chapter_number(want)
    if cand_chapter is not None and want_chapter is not None:
        if cand_chapter == want_chapter:
            return 1.0
        return SequenceMatcher(None, cand_chapter, want_chapter).ratio() * 0.4

    if want in cand or cand in want:
        return 0.85
    return SequenceMatcher(None, cand, want).ratio()


def best_section_key_match(target: str, candidates: Iterable[str]) -> Optional[str]:
    """Pick the best section_key from *candidates* for *target*."""
    best_key: Optional[str] = None
    best_score = 0.0
    for candidate in candidates:
        if not candidate:
            continue
        score = score_section_key_match(candidate, target)
        if score > best_score:
            best_score = score
            best_key = candidate
    if best_score >= 0.72:
        return best_key
    return None


def section_title_matches_hint(title: str, section_number: str, label: str) -> bool:
    """True when a chunk section_title plausibly belongs to the requested chapter."""
    haystack = (title or "").lower()
    if not haystack:
        return False
    if section_number and section_number in haystack:
        return True
    if label and label.lower() in haystack:
        return True
    chapter_match = re.search(r"chapter\s+(\d+)", label or "", re.IGNORECASE)
    if chapter_match and chapter_match.group(1) in haystack:
        return True
    zh_match = re.search(r"第(\d+)章", label or "")
    if zh_match and zh_match.group(1) in haystack:
        return True
    return False


def collect_distinct_section_keys(payloads: Iterable[dict]) -> List[str]:
    """Unique non-empty section_key values from Qdrant payloads."""
    keys: List[str] = []
    seen: set[str] = set()
    for payload in payloads:
        key = str(payload.get("section_key") or "").strip()
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys
