"""Shared no-LLM prompt prep for gallery, DingTalk/PNG, and Kitty.

Compose learning-sheet cleanup, 专业程度 detection, and instruction merge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from agents.core.learning_sheet import (
    clean_prompt_for_learning_sheet,
    detect_learning_sheet_from_prompt,
)
from agents.core.prompt_topic_seed import (
    extract_topic_seed_from_prompt,
    primary_topic_seed,
    resolve_diagram_type_from_prompt,
)
from prompts.ai_content_level import merge_generation_instructions
from prompts.mind_map_audience import resolve_prompt_audience
from services.utils.ai_content_level import DEFAULT_AI_CONTENT_LEVEL


@dataclass(frozen=True)
class PreparedGenerationPrompt:
    """Normalized prompt fields after shared prep."""

    raw_prompt: str
    topic_prompt: str
    language: str
    ai_content_level: str
    generation_instructions: Optional[str]
    is_learning_sheet: bool
    topic_seed: str
    diagram_type_hint: Optional[str]

    def merged_prompt(self) -> str:
        """Topic plus locale-marked generation_instructions."""
        return merge_generation_instructions(
            self.topic_prompt,
            self.generation_instructions or "",
            self.language,
        )


def prepare_generation_prompt(
    prompt: str,
    language: str,
    *,
    explicit_instructions: Optional[str] = None,
) -> PreparedGenerationPrompt:
    """Detect learning sheet and 专业程度; explicit canvas instructions win."""
    raw = (prompt or "").strip()
    lang = (language or "zh").strip() or "zh"
    is_sheet = detect_learning_sheet_from_prompt(raw, lang) if raw else False
    working = clean_prompt_for_learning_sheet(raw) if is_sheet else raw
    topic, level, detected_block = resolve_prompt_audience(working, lang)
    explicit = (explicit_instructions or "").strip() or None
    instructions = explicit or detected_block
    type_hint = resolve_diagram_type_from_prompt(topic)
    seed = extract_topic_seed_from_prompt(topic, type_hint or "mindmap")
    topic_seed = primary_topic_seed(seed)
    return PreparedGenerationPrompt(
        raw_prompt=raw,
        topic_prompt=topic or raw,
        language=lang,
        ai_content_level=level or DEFAULT_AI_CONTENT_LEVEL,
        generation_instructions=instructions,
        is_learning_sheet=is_sheet,
        topic_seed=topic_seed,
        diagram_type_hint=type_hint,
    )
