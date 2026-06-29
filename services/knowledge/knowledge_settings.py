"""Knowledge Space user settings — server defaults, per-user overrides, and merge logic.

User-editable retrieval and chunking preferences live in ``KnowledgeSpace.processing_rules``
under ``settings``. Chunking values are mirrored into ``rules.segmentation`` so the existing
document pipeline picks them up without duplicate logic.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import config
from models.domain.knowledge_space import KnowledgeSpace

RETRIEVAL_METHODS = frozenset({"semantic", "keyword", "hybrid"})
MIN_CHUNK_SIZE = 100
MAX_CHUNK_SIZE = 2000
MIN_CHUNK_OVERLAP = 0
MAX_CHUNK_OVERLAP = 200
MIN_TOP_K = 1
MAX_TOP_K = 20


@dataclass(frozen=True)
class EffectiveKnowledgeSettings:
    """Resolved settings used by retrieval and chunking."""

    default_method: str
    top_k: int
    score_threshold: float
    chunk_size: int
    chunk_overlap: int
    vector_weight: float
    keyword_weight: float
    reranking_mode: str
    wiki_compile_enabled: bool
    chunking_engine: str
    has_user_overrides: bool


@dataclass(frozen=True)
class SettingsUpdateResult:
    """Outcome of persisting user settings."""

    settings: EffectiveKnowledgeSettings
    reindex_required: bool


def server_defaults() -> Dict[str, Any]:
    """Deployment defaults from environment / config."""
    return {
        "default_method": config.DEFAULT_RETRIEVAL_METHOD,
        "top_k": 5,
        "score_threshold": config.RERANK_SCORE_THRESHOLD,
        "chunk_size": config.CHUNK_SIZE,
        "chunk_overlap": config.CHUNK_OVERLAP,
        "vector_weight": config.HYBRID_VECTOR_WEIGHT,
        "keyword_weight": config.HYBRID_KEYWORD_WEIGHT,
        "reranking_mode": config.RERANKING_MODE,
        "wiki_compile_enabled": config.FILE_CENTER_WIKI_COMPILE,
        "chunking_engine": (
            "mindchunk" if os.getenv("CHUNKING_ENGINE", "semchunk").lower() == "mindchunk" else "semchunk"
        ),
    }


def _user_settings(processing_rules: Optional[dict]) -> Dict[str, Any]:
    raw = (processing_rules or {}).get("settings")
    return raw if isinstance(raw, dict) else {}


def _coerce_int(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, parsed))


def _coerce_float(value: Any, fallback: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, parsed))


def effective_settings(processing_rules: Optional[dict]) -> EffectiveKnowledgeSettings:
    """Merge server defaults with stored user overrides."""
    defaults = server_defaults()
    stored = _user_settings(processing_rules)
    raw_retrieval = stored.get("retrieval")
    raw_chunking = stored.get("chunking")
    retrieval: Dict[str, Any] = raw_retrieval if isinstance(raw_retrieval, dict) else {}
    chunking: Dict[str, Any] = raw_chunking if isinstance(raw_chunking, dict) else {}

    method = str(retrieval.get("default_method") or defaults["default_method"])
    if method not in RETRIEVAL_METHODS:
        method = defaults["default_method"]

    has_overrides = bool(retrieval or chunking)
    return EffectiveKnowledgeSettings(
        default_method=method,
        top_k=_coerce_int(retrieval.get("top_k"), defaults["top_k"], MIN_TOP_K, MAX_TOP_K),
        score_threshold=_coerce_float(
            retrieval.get("score_threshold"),
            defaults["score_threshold"],
            0.0,
            1.0,
        ),
        chunk_size=_coerce_int(
            chunking.get("chunk_size"),
            defaults["chunk_size"],
            MIN_CHUNK_SIZE,
            MAX_CHUNK_SIZE,
        ),
        chunk_overlap=_coerce_int(
            chunking.get("chunk_overlap"),
            defaults["chunk_overlap"],
            MIN_CHUNK_OVERLAP,
            MAX_CHUNK_OVERLAP,
        ),
        vector_weight=float(defaults["vector_weight"]),
        keyword_weight=float(defaults["keyword_weight"]),
        reranking_mode=str(defaults["reranking_mode"]),
        wiki_compile_enabled=bool(defaults["wiki_compile_enabled"]),
        chunking_engine=str(defaults["chunking_engine"]),
        has_user_overrides=has_overrides,
    )


def segmentation_from_rules(processing_rules: Optional[dict]) -> Tuple[int, int]:
    """Return (chunk_size_tokens, chunk_overlap_tokens) for the chunking pipeline."""
    effective = effective_settings(processing_rules)
    return effective.chunk_size, effective.chunk_overlap


def apply_settings_update(
    processing_rules: Optional[dict],
    *,
    default_method: str,
    top_k: int,
    score_threshold: float,
    chunk_size: int,
    chunk_overlap: int,
) -> Tuple[dict, bool]:
    """Persist user settings into processing_rules; return (new_rules, reindex_required)."""
    if default_method not in RETRIEVAL_METHODS:
        raise ValueError(f"Invalid retrieval method: {default_method}")

    top_k = _coerce_int(top_k, 5, MIN_TOP_K, MAX_TOP_K)
    score_threshold = _coerce_float(score_threshold, config.RERANK_SCORE_THRESHOLD, 0.0, 1.0)
    chunk_size = _coerce_int(chunk_size, config.CHUNK_SIZE, MIN_CHUNK_SIZE, MAX_CHUNK_SIZE)
    chunk_overlap = _coerce_int(chunk_overlap, config.CHUNK_OVERLAP, MIN_CHUNK_OVERLAP, MAX_CHUNK_OVERLAP)

    before = effective_settings(processing_rules)
    reindex_required = chunk_size != before.chunk_size or chunk_overlap != before.chunk_overlap

    base = dict(processing_rules or {})
    settings = {
        "retrieval": {
            "default_method": default_method,
            "top_k": top_k,
            "score_threshold": score_threshold,
        },
        "chunking": {
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        },
    }
    base["settings"] = settings

    rules = dict(base.get("rules") or {})
    segmentation = dict(rules.get("segmentation") or {})
    segmentation["max_tokens"] = chunk_size
    segmentation["chunk_overlap"] = chunk_overlap
    rules["segmentation"] = segmentation
    base["rules"] = rules
    return base, reindex_required


async def get_space_settings(db: AsyncSession, user_id: int) -> EffectiveKnowledgeSettings:
    """Load effective settings for a user (empty overrides when no space yet)."""
    result = await db.execute(select(KnowledgeSpace).where(KnowledgeSpace.user_id == user_id))
    space = result.scalar_one_or_none()
    return effective_settings(space.processing_rules if space else None)


async def update_space_settings(
    db: AsyncSession,
    user_id: int,
    *,
    default_method: str,
    top_k: int,
    score_threshold: float,
    chunk_size: int,
    chunk_overlap: int,
) -> SettingsUpdateResult:
    """Create or update the user's knowledge space settings."""
    result = await db.execute(select(KnowledgeSpace).where(KnowledgeSpace.user_id == user_id))
    space = result.scalar_one_or_none()
    if space is None:
        space = KnowledgeSpace(user_id=user_id)
        db.add(space)
        await db.flush()

    new_rules, reindex_required = apply_settings_update(
        space.processing_rules,
        default_method=default_method,
        top_k=top_k,
        score_threshold=score_threshold,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    space.processing_rules = new_rules
    await db.commit()
    await db.refresh(space)
    return SettingsUpdateResult(
        settings=effective_settings(space.processing_rules),
        reindex_required=reindex_required,
    )


async def resolve_retrieval_params(
    db: AsyncSession,
    user_id: int,
    method: Optional[str] = None,
    top_k: Optional[int] = None,
    score_threshold: Optional[float] = None,
) -> Tuple[str, int, float]:
    """Fill missing retrieval parameters from the user's effective settings."""
    prefs = await get_space_settings(db, user_id)
    resolved_method = method or prefs.default_method
    if resolved_method not in RETRIEVAL_METHODS:
        resolved_method = prefs.default_method
    resolved_top_k = top_k if top_k is not None else prefs.top_k
    resolved_threshold = score_threshold if score_threshold is not None else prefs.score_threshold
    return resolved_method, resolved_top_k, resolved_threshold
