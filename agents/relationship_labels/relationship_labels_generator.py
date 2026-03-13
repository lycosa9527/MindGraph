"""
Relationship Labels Generator - Catapult-style multi-LLM streaming.

Fires 3 LLMs (qwen, deepseek, doubao) concurrently to generate relationship labels
between two concepts. Streams labels progressively, deduplicates across LLMs.
Used by concept map label picker (IME-style) with pagination (- and = keys).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import asyncio
import logging
import re
import time
from difflib import SequenceMatcher
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

from langchain_core.prompts import PromptTemplate

from prompts.concept_maps import CONCEPT_MAP_PROMPTS
from services.llm import llm_service

logger = logging.getLogger(__name__)


class _GeneratorHolder:
    """Holds singleton instance to avoid global mutable state."""

    instance: Optional['RelationshipLabelsGenerator'] = None


def _strip_parenthetical(text: str) -> str:
    """Remove parenthetical notes (Chinese （） or English ())."""
    if not text:
        return text
    for sep in ("（", "("):
        idx = text.find(sep)
        if idx >= 0:
            text = text[:idx]
    return text.strip()


def _get_direction_instruction(link_direction: str | None, language: str) -> str:
    """Return direction-specific instruction for relationship generation."""
    direction = (link_direction or "").strip().lower()
    instructions: Dict[str, Dict[str, str]] = {
        "zh": {
            "source_to_target": (
                "该连线有箭头，从概念A指向概念B。请生成 3–5 个不同的动词/短语，描述 A 如何导致、引导或指向 B。"
                "类型宜多样：如因果、组成、依赖等。"
            ),
            "target_to_source": (
                "该连线有箭头，从概念B指向概念A。请生成 3–5 个不同的动词/短语，描述 B 如何导致、引导或指向 A。"
                "类型宜多样。"
            ),
            "both": (
                "该连线两端均有箭头（双向）。请生成 3–5 个不同的动词/短语，描述 A 与 B 如何相互关联或影响。"
            ),
            "none": (
                "该连线无箭头。这两个概念是平行或对称相关的。"
                "请生成 3–5 个不同的标签（对称、非方向性），可以是名词、形容词或短语。"
                "示例类型：相似、对比、同类、互补、对应、并列。"
            ),
        },
        "en": {
            "source_to_target": (
                "The link has an arrow from A to B. "
                "Generate 3–5 different verb phrases describing how A leads to, causes, or directs to B. "
                "Vary the relationship types (causal, compositional, dependency, etc.)."
            ),
            "target_to_source": (
                "The link has an arrow from B to A. "
                "Generate 3–5 different verb phrases describing how B leads to, causes, or directs to A. "
                "Vary the relationship types."
            ),
            "both": (
                "The link has arrows on both ends (bidirectional). "
                "Generate 3–5 different phrases describing how A and B relate or influence each other."
            ),
            "none": (
                "The link has no arrow. These concepts are in parallel or symmetrically related. "
                "Generate 3–5 different symmetric labels (noun, adjective, or phrase). "
                "Examples: similar to, contrasts with, complementary, analogous to, parallel."
            ),
        },
    }
    lang = "zh" if language == "zh" else "en"
    key = direction if direction in instructions[lang] else "none"
    return instructions[lang][key]


class RelationshipLabelsGenerator:
    """
    Catapult-style generator for concept map relationship labels.

    Fires 3 LLMs concurrently, streams labels as they arrive, deduplicates.
    """

    def __init__(self) -> None:
        self.llm_service = llm_service
        self.llm_models = ['qwen', 'deepseek', 'doubao']
        self.seen_labels: Dict[str, Set[str]] = {}
        self.generated_labels: Dict[str, list] = {}
        self.batch_counts: Dict[str, int] = {}
        self.session_start_times: Dict[str, float] = {}

    def _build_prompt(
        self,
        concept_a: str,
        concept_b: str,
        topic: str,
        link_direction: str | None,
        language: str,
        batch_num: int = 1,
        existing_labels: Optional[List[str]] = None,
    ) -> str:
        """Build prompt from concept map relationship template."""
        if language == "zh":
            topic_context = f"主题是：{topic}" if topic else "此图尚未设置主主题。"
        else:
            topic_context = (
                f"The topic is about: {topic}"
                if topic
                else "No main topic has been set for this map."
            )
        direction_instruction = _get_direction_instruction(link_direction, language)
        prompt_key = f"concept_map_relationship_only_{language}"
        template = CONCEPT_MAP_PROMPTS.get(prompt_key)
        if not template:
            return ""
        prompt_template = PromptTemplate.from_template(template)
        prompt = prompt_template.invoke(
            {
                "concept_a": concept_a,
                "concept_b": concept_b,
                "topic_context": topic_context,
                "direction_instruction": direction_instruction,
            }
        ).to_string()
        prev = existing_labels or []
        if batch_num > 1 and prev:
            if language == "zh":
                prompt += (
                    f"\n\n已生成的关系标签：{', '.join(prev[:20])}\n"
                    "请生成全新的、与上述不同的关系标签。不要重复或改写已有标签。"
                )
            else:
                prompt += (
                    f"\n\nAlready generated labels: {', '.join(prev[:20])}\n"
                    "Generate NEW labels that are different from the above. "
                    "Do not repeat or paraphrase existing labels."
                )
        elif batch_num > 1:
            if language == "zh":
                prompt += (
                    f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，"
                    "从新的关系类型和角度思考，避免与之前批次重复。"
                )
            else:
                prompt += (
                    f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity, "
                    "think from new relationship types and angles, "
                    "avoid repetition from previous batches."
                )
        return prompt

    def _normalize_label(self, text: str) -> str:
        """Normalize label for deduplication."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _deduplicate_label(
        self, label: str, session_id: str
    ) -> Tuple[bool, str, float]:
        """Check if label is unique. Returns (is_unique, match_type, similarity)."""
        normalized = self._normalize_label(label)
        if session_id not in self.seen_labels:
            self.seen_labels[session_id] = set()
        seen = self.seen_labels[session_id]
        if normalized in seen:
            return (False, 'exact', 1.0)
        for seen_text in seen:
            similarity = SequenceMatcher(None, normalized, seen_text).ratio()
            if similarity > 0.85:
                return (False, 'fuzzy', similarity)
        seen.add(normalized)
        return (True, 'unique', 0.0)

    def _try_parse_label(self, line: str, session_id: str) -> Optional[str]:
        """Parse and deduplicate a line into a label. Returns label if unique else None."""
        line = line.strip().lstrip('0123456789.-、）) ').strip()
        if not line or len(line) < 2:
            return None
        cleaned = _strip_parenthetical(line)
        if not cleaned:
            return None
        is_unique, _, _ = self._deduplicate_label(cleaned, session_id)
        return cleaned if is_unique else None

    def _store_label(self, session_id: str, label: str, llm_name: str) -> Dict[str, Any]:
        """Store label and return event dict for yielding."""
        if session_id not in self.generated_labels:
            self.generated_labels[session_id] = []
        self.generated_labels[session_id].append(label)
        return {'event': 'label_generated', 'label': label, 'source_llm': llm_name}

    def _parse_lines_to_events(
        self, lines: List[str], session_id: str, llm_name: str
    ) -> List[Dict[str, Any]]:
        """Parse lines into label events. Returns list of event dicts."""
        events: List[Dict[str, Any]] = []
        for line in lines:
            label = self._try_parse_label(line, session_id)
            if label:
                events.append(self._store_label(session_id, label, llm_name))
        return events

    def _prepare_batch(
        self,
        session_id: str,
        concept_a: str,
        concept_b: str,
        topic: str,
        link_direction: str | None,
        language: str,
    ) -> Optional[Dict[str, Any]]:
        """Prepare batch: init session, build prompt. Returns None if prompt fails."""
        if session_id not in self.session_start_times:
            self.session_start_times[session_id] = time.time()
            self.batch_counts[session_id] = 0
        batch_num = self.batch_counts[session_id] + 1
        self.batch_counts[session_id] = batch_num
        total_before = len(self.generated_labels.get(session_id, []))
        logger.debug(
            "[RelLabels] Batch %d | Session: %s | %s ↔ %s",
            batch_num, session_id[:8], concept_a[:20], concept_b[:20]
        )
        existing = self.generated_labels.get(session_id, [])
        prompt = self._build_prompt(
            concept_a, concept_b, topic, link_direction, language,
            batch_num=batch_num, existing_labels=existing
        )
        if not prompt:
            return None
        return {
            'batch_num': batch_num,
            'total_before': total_before,
            'prompt': prompt,
            'batch_start_evt': {
                'event': 'batch_start',
                'batch_number': batch_num,
                'llm_count': len(self.llm_models),
            },
        }

    async def _process_stream_chunk(
        self,
        chunk: Dict[str, Any],
        session_id: str,
        state: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process one stream chunk, yield label events."""
        evt_type = chunk.get('event')
        llm = chunk.get('llm', '')
        curr = state['current_lines']
        pend = state['pending']
        uniq = state['llm_unique']
        order = state['llm_order']
        nidx = state['next_idx']

        if evt_type == 'token':
            curr[llm] += chunk.get('token', '')
            if '\n' in curr[llm]:
                parts = curr[llm].split('\n')
                curr[llm] = parts[-1]
                for evt in self._parse_lines_to_events(
                    parts[:-1], session_id, llm
                ):
                    pend[llm].append(evt)
                    uniq[llm] += 1
                    for _ in range(len(self.llm_models)):
                        mdl = order[nidx % len(order)]
                        nidx += 1
                        if pend[mdl]:
                            yield pend[mdl].pop(0)
                            await asyncio.sleep(0)
                state['next_idx'] = nidx

        elif evt_type == 'complete':
            remainder = curr[llm].lstrip('0123456789.-、）) ')
            for evt in self._parse_lines_to_events([remainder], session_id, llm):
                pend[llm].append(evt)
                uniq[llm] += 1
            while pend[llm]:
                yield pend[llm].pop(0)
                await asyncio.sleep(0)

    async def _stream_labels(
        self,
        session_id: str,
        prompt: str,
        language: str,
        batch_num: int,
        user_id: Optional[int],
        organization_id: Optional[int],
        endpoint_path: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream labels from 3 LLMs. Yields label_generated events."""
        state: Dict[str, Any] = {
            'current_lines': {m: "" for m in self.llm_models},
            'llm_unique': {m: 0 for m in self.llm_models},
            'pending': {m: [] for m in self.llm_models},
            'llm_order': self.llm_models.copy(),
            'next_idx': 0,
        }
        async for chunk in self.llm_service.stream_progressive(
            prompt=prompt,
            models=self.llm_models,
            temperature=min(0.7 + (batch_num - 1) * 0.1, 1.0),
            max_tokens=300,
            timeout=15.0,
            system_message=(
                '你是一个有帮助的K12教育助手。'
                if language == 'zh'
                else 'You are a helpful K12 education assistant.'
            ),
            user_id=user_id,
            organization_id=organization_id,
            request_type='relationship_labels',
            diagram_type='concept_map',
            endpoint_path=endpoint_path or '/thinking_mode/relationship_labels/start',
            session_id=session_id,
        ):
            async for evt in self._process_stream_chunk(
                chunk, session_id, state
            ):
                yield evt

    async def generate_batch(
        self,
        session_id: str,
        concept_a: str,
        concept_b: str,
        topic: str = "",
        link_direction: str | None = None,
        language: str = "en",
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        endpoint_path: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate batch of relationship labels using 3 LLMs concurrently.

        Yields:
            - {'event': 'batch_start', 'batch_number': N, 'llm_count': 3}
            - {'event': 'label_generated', 'label': str, 'source_llm': str}
            - {'event': 'batch_complete', 'total_unique': N}
            - {'event': 'error', 'message': str}
        """
        prep = self._prepare_batch(
            session_id, concept_a, concept_b, topic, link_direction, language
        )
        if prep is None:
            yield {'event': 'error', 'message': 'Failed to build prompt'}
            return

        yield prep['batch_start_evt']
        batch_start = time.time()
        async for evt in self._stream_labels(
            session_id=session_id,
            prompt=prep['prompt'],
            language=language,
            batch_num=prep['batch_num'],
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
        ):
            yield evt

        total_after = len(self.generated_labels.get(session_id, []))
        yield {
            'event': 'batch_complete',
            'batch_number': prep['batch_num'],
            'batch_duration': round(time.time() - batch_start, 2),
            'new_unique_labels': total_after - prep['total_before'],
            'total_labels': total_after,
        }

    def end_session(self, session_id: str, reason: str = "complete") -> None:
        """Clean up session state."""
        logger.debug(
            "[RelLabels] Session ended: %s (reason: %s)", session_id[:8], reason
        )
        self.session_start_times.pop(session_id, None)
        self.generated_labels.pop(session_id, None)
        self.seen_labels.pop(session_id, None)
        self.batch_counts.pop(session_id, None)


def get_relationship_labels_generator() -> RelationshipLabelsGenerator:
    """Return singleton relationship labels generator."""
    if _GeneratorHolder.instance is None:
        _GeneratorHolder.instance = RelationshipLabelsGenerator()
    return _GeneratorHolder.instance
