"""Load personal-knowledge markdown for a mind-map branch.

Every branch runs both channels. The outline channel pins a numbered section
and its children. The vector channel asks the VibeFlow index. Reciprocal rank
fusion (k=60) orders the two lists. No DashScope rerank model is called.
A full outline already uses the prompt budget. A short outline, or none,
keeps the fused vector sections in the remaining room.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from services.knowledge.section_query import parse_section_hint
from services.knowledge.vibeflow_rrf import reciprocal_rank_fusion
from services.knowledge.vibeflow_store import load_package_manifest, read_object_text
from services.knowledge.vibeflow_vectors import embed_branch_query, query_similar_keys

logger = logging.getLogger(__name__)

MAX_PERSONAL_CONTEXT_CHARS = 12000
VECTOR_EXTRA = 4
OPEN_HITS = 6
_CLIP_MARKER = "\n\n[...]\n\n"
_CONTEXT_HEADER = "Relevant Context (from user's knowledge base):\n"
_CONTEXT_FOOTER = (
    "\n\nWrite the diagram from this source. Keep its numbers, dates, and proper names "
    "in the node text. Do not replace them with a teaching framework or a summary that drops those facts."
    "\n用这份资料画图。节点里保留原文的数字、日期和专名，不要改成丢掉这些事实的教学框架或空泛概括。"
)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def _parent_number(query: str, entries: List[Dict[str, Any]]) -> str:
    hint = parse_section_hint(query)
    if hint and hint.section_number:
        return hint.section_number
    folded = _normalize(query)
    for entry in entries:
        number = str(entry.get("section_number") or "")
        if number and number != "document" and _normalize(number) == folded:
            return number
    best = ""
    best_len = 0
    for entry in entries:
        title = _normalize(str(entry.get("title") or ""))
        number = str(entry.get("section_number") or "")
        if not title or number in {"", "document"}:
            continue
        if folded == title or (len(title) >= 8 and (title in folded or folded in title)):
            if len(title) > best_len:
                best = number
                best_len = len(title)
    return best


def _belongs(parent: str, number: str) -> bool:
    return number == parent or number.startswith(f"{parent}.")


def _outline_entries(query: str, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    parent = _parent_number(query, entries)
    if not parent:
        return []
    chosen = [entry for entry in entries if _belongs(parent, str(entry.get("section_number") or ""))]
    chosen.sort(key=lambda entry: (str(entry.get("section_number")), int(entry.get("index") or 0)))
    return chosen


def vector_section_entries(
    user_id: int,
    package_id: int,
    query: str,
    entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Manifest rows for the nearest vectors in this folder, in index order."""
    vector = embed_branch_query(query)
    if not vector:
        return []
    by_key = {str(entry.get("key") or ""): entry for entry in entries}
    found: List[Dict[str, Any]] = []
    for key in query_similar_keys(user_id, package_id, vector):
        entry = by_key.get(key)
        if entry is not None:
            found.append(entry)
    return found


def clip_head_tail(text: str, budget: int) -> str:
    """Keep the start and the end of a section that does not fit."""
    if budget <= 0:
        return ""
    if len(text) <= budget:
        return text
    if budget <= len(_CLIP_MARKER) + 2:
        return text[:budget]
    room = budget - len(_CLIP_MARKER)
    head = room // 2
    tail = room - head
    return text[:head] + _CLIP_MARKER + text[-tail:]


def pack_texts(texts: List[str], budget: int) -> str:
    """Join sections. When they overflow, each truncated section keeps its start and end."""
    usable = [text for text in texts if text]
    if not usable or budget <= 0:
        return ""
    if sum(len(text) for text in usable) <= budget:
        return "\n\n".join(usable)
    count = len(usable)
    shares = [budget // count] * count
    for index in range(budget - sum(shares)):
        shares[index] += 1
    surplus = 0
    needy: List[int] = []
    kept = [""] * count
    for index, text in enumerate(usable):
        if len(text) <= shares[index]:
            kept[index] = text
            surplus += shares[index] - len(text)
        else:
            needy.append(index)
    if needy and surplus:
        extra = surplus // len(needy)
        remainder = surplus % len(needy)
        for offset, index in enumerate(needy):
            shares[index] += extra + (1 if offset < remainder else 0)
    parts: List[str] = []
    for index, text in enumerate(usable):
        parts.append(kept[index] or clip_head_tail(text, shares[index]))
    return "\n\n".join(part for part in parts if part)


def _entry_text(entry: Dict[str, Any]) -> str:
    return read_object_text(str(entry.get("key") or "")).strip()


def _vector_extra_texts(
    outline_keys: List[str],
    fused: List[str],
    by_key: Dict[str, Dict[str, Any]],
    room: int,
) -> List[str]:
    texts: List[str] = []
    used = 0
    seen = set(outline_keys)
    for key in fused:
        if key in seen or key not in by_key:
            continue
        text = _entry_text(by_key[key])
        seen.add(key)
        if not text:
            continue
        texts.append(text)
        used += len(text)
        if len(texts) >= VECTOR_EXTRA or used >= room:
            break
    return texts


def personal_context_block(user_id: int, package_id: int, query: str) -> str:
    """Return outline text plus fused vector sections for one branch label."""
    entries = load_package_manifest(user_id, package_id)
    outline = _outline_entries(query, entries)
    vector = vector_section_entries(user_id, package_id, query, entries)
    outline_keys = [str(entry.get("key") or "") for entry in outline if entry.get("key")]
    vector_keys = [str(entry.get("key") or "") for entry in vector if entry.get("key")]
    rankings = [keys for keys in (outline_keys, vector_keys) if keys]
    fused = reciprocal_rank_fusion(rankings) if rankings else []
    by_key = {str(entry.get("key") or ""): entry for entry in entries}
    outline_texts = [text for text in (_entry_text(entry) for entry in outline) if text]
    if outline_texts:
        outline_block = "\n\n".join(outline_texts)
        if len(outline_block) >= MAX_PERSONAL_CONTEXT_CHARS:
            body = pack_texts(outline_texts, MAX_PERSONAL_CONTEXT_CHARS)
        else:
            gap = MAX_PERSONAL_CONTEXT_CHARS - len(outline_block) - 2
            extras = _vector_extra_texts(outline_keys, fused, by_key, gap)
            extra_block = pack_texts(extras, gap)
            body = f"{outline_block}\n\n{extra_block}" if extra_block else outline_block
    else:
        open_texts = [_entry_text(by_key[key]) for key in fused if key in by_key]
        body = pack_texts([text for text in open_texts if text][:OPEN_HITS], MAX_PERSONAL_CONTEXT_CHARS)
    if not body:
        logger.info(
            "[PersonalKnowledge] vibeflow context empty user=%s package=%s outline=%s vectors=%s query=%r",
            user_id,
            package_id,
            len(outline),
            len(vector),
            (query or "")[:80],
        )
        return ""
    logger.info(
        "[PersonalKnowledge] vibeflow context user=%s package=%s outline=%s vectors=%s chars=%s query=%r",
        user_id,
        package_id,
        len(outline),
        len(vector),
        len(body),
        (query or "")[:80],
    )
    return _CONTEXT_HEADER + body + _CONTEXT_FOOTER
