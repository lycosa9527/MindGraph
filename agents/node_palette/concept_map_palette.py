"""
Concept map palette module.

Concept Map specific node palette generator.
Supports multi-domain tabs (Novak-style branches), root-anchored concepts per domain,
and one-shot domain-label bootstrap via LLM chat.
"""
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

from agents.node_palette.base_palette_generator import BasePaletteGenerator
from utils.prompt_locale import output_language_instruction

logger = logging.getLogger(__name__)


class ConceptMapPaletteGenerator(BasePaletteGenerator):
    """Concept Map palette generator for concept node generation from topic."""

    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        """
        Build Concept Map prompt for concept generation.

        When educational_context contains palette_domain_label, the prompt focuses
        on that knowledge branch only (multi-tab domain mode).
        """
        domain_label = ''
        if educational_context:
            domain_label = str(
                educational_context.get('palette_domain_label') or ''
            ).strip()
        if domain_label:
            return self._build_domain_focused_prompt(
                center_topic, educational_context, count, batch_num, domain_label
            )

        language = self._detect_language(center_topic, educational_context)

        context_desc = (
            educational_context.get('raw_message', 'General K12 teaching')
            if educational_context
            else 'General K12 teaching'
        )

        focus_q = ''
        root_concept = ''
        if educational_context:
            focus_q = str(educational_context.get('focus_question') or '').strip()
            root_concept = str(educational_context.get('root_concept') or '').strip()

        if language == 'zh':
            fq_line = (
                focus_q
                if focus_q
                else '（未填写：请结合当前锚点与教学背景推断，并保持概念聚焦）'
            )
            rc_line = (
                root_concept
                if root_concept
                else '（未填写：请根据焦点问题与锚点推断上位概念）'
            )
            prompt = (
                f"""为概念图生成{count}个**可放入画布**的相关概念（名词或名词短语）。

【必须遵守的上下文】
1. **焦点问题**（用于约束概念范围）：{fq_line}
2. **根概念**（概念图的上位总括节点；概念应能与之及焦点问题形成有意义的关联）：{rc_line}
3. **当前生成锚点**（本批概念围绕展开的中心；可能是焦点问题节点或你选中的某概念）："{center_topic}"

教学背景：{context_desc}

要求：
1. 概念必须**聚焦**焦点问题与根概念；若根概念未填，仍须与焦点问题及锚点强相关。
2. 优先学科内主要概念与关键概念；可少量跨学科连接词。
3. 每个概念 2–4 个汉字为宜，名词或名词短语；避免整句与重复。
4. 概念应能在图中与根概念或彼此建立命题关系。

只输出概念文本，每行一个，不要编号。

生成{count}个概念："""
            )
        else:
            fq_line = (
                focus_q
                if focus_q
                else (
                    '(Not provided: infer from anchor and context only; '
                    'still align to a clear focus question.)'
                )
            )
            rc_line = (
                root_concept
                if root_concept
                else '(Not filled: infer from the focus question and anchor only.)'
            )
            prompt = (
                f"""Generate {count} **distinct** concept labels """
                f"""(nouns or short noun phrases) for a Novak-style concept map.

【Required context — use all of these】
1. **Focus question** (scopes what the map should answer): {fq_line}
2. **Root concept** (top inclusive node; relate to it and the focus question): {rc_line}
3. **Current anchor** (this batch’s center — focus node or selected concept): "{center_topic}"

Educational context: {context_desc}

Rules:
1. Each label must be strongly tied to the **focus question** and **root concept** (or clearly inferred if missing).
2. Prefer core in-subject concepts; a few cross-disciplinary links are OK.
3. Each label: 1–4 words, noun or noun phrase; no full sentences; avoid duplicates.
4. Labels should support propositional links to the root concept and/or each other.

Output only concept text, one per line, no numbering.

Generate {count} concepts:"""
            )

        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，避免与之前批次重复。"
            else:
                prompt += (
                    f"\n\nNote: This is batch {batch_num}. "
                    "Ensure MAXIMUM diversity and avoid any repetition from previous batches."
                )

        return prompt

    @staticmethod
    def _split_concept_tab_relationship(line: str) -> tuple[str, str]:
        """
        Parse ``concept<TAB>linking_phrase`` from one streamed line.

        If there is no tab, the whole line is the concept and the link is empty.
        """
        stripped = line.strip()
        if '\t' not in stripped:
            return stripped, ''
        left, right = stripped.split('\t', 1)
        return left.strip(), right.strip()

    def _build_domain_focused_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int,
        domain_label: str,
    ) -> str:
        """Novak-style: concepts within one knowledge branch / domain tab."""
        language = self._detect_language(center_topic, educational_context)
        context_desc = (
            educational_context.get('raw_message', 'General K12 teaching')
            if educational_context
            else 'General K12 teaching'
        )
        focus_q = ''
        root_concept = ''
        if educational_context:
            focus_q = str(educational_context.get('focus_question') or '').strip()
            root_concept = str(educational_context.get('root_concept') or '').strip()

        if language == 'zh':
            fq_line = (
                focus_q
                if focus_q
                else '（未结合：请据主题与教学背景推断）'
            )
            rc_line = (
                root_concept
                if root_concept
                else '（未填写：请据焦点问题推断上位概念）'
            )
            prompt = (
                f"""请根据诺瓦克概念图理论，在**单一知识分支**内为概念图生成{count}个可放入画布的概念（名词或名词短语）。

【结构化任务】
1. **当前分支（标签页）**："{domain_label}" — 本批概念必须属于该分支所代表的学科视角或子系统，边界清晰。
2. **焦点问题**：{fq_line}
3. **根概念**：{rc_line}
4. **主题锚点**："{center_topic}"
5. **教学背景**：{context_desc}

【跨分支说明】概念图允许交叉连接；请优先产出**本分支内**可形成命题的核心概念，便于日后与其他分支节点建立有意义的联系。

**输出格式（必须）**：每行一条，制表符（Tab）分隔为两列——
第1列：概念（名词或名词短语，2–8 个汉字为宜）；
第2列：将该概念与**根概念**连成可读命题的**连接词或短语**（如「是」「包括」「导致」等，勿写整句）。
若无法写出合理连接词，第2列可留空，但仍须保留 Tab 后的位置（即行末可为 Tab 后无字）。
不要编号，不要引号包裹整行。

生成{count}行："""
            )
        else:
            fq_line = (
                focus_q
                if focus_q
                else '(Infer from the map topic and context.)'
            )
            rc_line = (
                root_concept
                if root_concept
                else '(Infer from the focus question.)'
            )
            prompt = (
                f"""Following Novak’s concept mapping theory, generate {count} concept labels """
                f"""(nouns or short noun phrases) that belong to **one knowledge branch only**.

**Branch (this tab)**: "{domain_label}" — labels must fit this disciplinary lens or subsystem.
**Focus question**: {fq_line}
**Root concept**: {rc_line}
**Topic anchor**: "{center_topic}"
**Context**: {context_desc}

Cross-links between branches are allowed on the map; prioritize **within-branch** core concepts that can later form propositions with other branches.

**Required format — one row per line, TAB-separated:**
1) concept label (noun or short noun phrase);
2) a **linking phrase** that connects **the root concept** to that concept in a readable proposition (e.g. \"is\", \"includes\", \"leads to\"). No full sentences.
If no sensible phrase exists, column 2 may be empty after the TAB.

Generate {count} lines:"""
            )

        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。避免与之前批次重复。"
            else:
                prompt += (
                    f"\n\nNote: Batch {batch_num}. Avoid repetition from earlier batches."
                )
        return prompt

    def _get_system_message(
        self,
        educational_context: Optional[Dict[str, Any]],
        center_topic: str = "",
    ) -> str:
        """Richer system hint when generating domain-scoped concepts."""
        domain = ''
        if educational_context:
            domain = str(
                educational_context.get('palette_domain_label') or ''
            ).strip()
        language = self._detect_language(center_topic, educational_context)
        if domain:
            if language == 'zh':
                return (
                    '你是K12教育助手，熟悉诺瓦克概念图：先区分知识分支，再在分支内列出可构成命题的概念；'
                    '每行用制表符（Tab）分为两列：概念、以及将该概念与根概念连成命题的连接词或短语；'
                    '第一列为名词或名词短语。'
                )
            return (
                'You are a K12 assistant trained in Novak concept maps. '
                'Each line: concept, TAB, short linking phrase from root concept to '
                'that concept (proposition-style). First column: noun or noun phrase only.'
            )
        return super()._get_system_message(educational_context, center_topic)

    def _build_domain_label_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        existing_labels: List[str],
        language: str,
    ) -> str:
        """Prompt for one-shot domain / branch name generation."""
        context_desc = (
            educational_context.get('raw_message', 'General K12 teaching')
            if educational_context
            else 'General K12 teaching'
        )
        focus_q = ''
        root_concept = ''
        if educational_context:
            focus_q = str(educational_context.get('focus_question') or '').strip()
            root_concept = str(educational_context.get('root_concept') or '').strip()

        existing_text = ''
        if existing_labels:
            joined = '、'.join(existing_labels[:40])
            if language == 'zh':
                existing_text = f"\n【已有分支名称，禁止重复或同义改写】{joined}"
            else:
                existing_text = f"\n【Existing branch names — do not repeat】{joined}"

        if language == 'zh':
            fq_line = focus_q or '（可据主题推断）'
            rc_line = root_concept or '（可据焦点问题推断）'
            return (
                f"""请根据诺瓦克概念图理论，为以下概念图主题确定知识分支名称。
主题锚点："{center_topic}"
焦点问题：{fq_line}
根概念：{rc_line}
教学背景：{context_desc}
{existing_text}

任务：拆解为**恰好 {count} 个**有明确边界的知识分支（每个分支对应一个标签页），每个分支代表相对独立的学科视角或子系统。
只输出分支名称，每行一个，不要编号、不要解释、不要前缀符号。共 {count} 行。"""
            )
        fq_line = focus_q or '(Infer if needed.)'
        rc_line = root_concept or '(Infer if needed.)'
        return (
            f"""Using Novak concept-mapping ideas, propose exactly {count} distinct knowledge-branch """
            f"""names (one tab each) for this map.
Topic anchor: "{center_topic}"
Focus question: {fq_line}
Root concept: {rc_line}
Context: {context_desc}
{existing_text}

Output one branch name per line, no numbering, no extra text. Exactly {count} lines."""
        )

    def _finalize_domain_label_list(
        self,
        raw_llm: str,
        count: int,
        existing_labels: List[str],
        language: str,
    ) -> List[str]:
        """Parse LLM output lines; pad with generic labels if needed."""
        lines = [ln.strip() for ln in str(raw_llm).splitlines() if ln.strip()]
        cleaned: List[str] = []
        seen_norm: set[str] = set()
        existing_norm = {self._normalize_text(x) for x in existing_labels}

        for line in lines:
            text = re.sub(r'^[\d.\s、）)]*', '', line).strip()
            if len(text) < 2:
                continue
            norm = self._normalize_text(text)
            if norm in existing_norm or norm in seen_norm:
                continue
            seen_norm.add(norm)
            cleaned.append(text)
            if len(cleaned) >= count:
                break

        if len(cleaned) < count:
            for i in range(len(cleaned), count):
                label = f'分支{i + 1}' if language == 'zh' else f'Branch {i + 1}'
                cleaned.append(label)

        return cleaned[:count]

    async def _generate_domain_labels(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        existing_labels: List[str],
        language: str,
        user_id: Optional[int],
        organization_id: Optional[int],
        diagram_type: Optional[str],
        endpoint_path: Optional[str],
        session_id: str,
    ) -> List[str]:
        """One-shot chat: return `count` distinct domain/branch names."""
        prompt = self._build_domain_label_prompt(
            center_topic, educational_context, count, existing_labels, language
        )
        prompt = prompt + output_language_instruction(language)
        raw = await self.llm_service.chat(
            prompt=prompt,
            model='qwen',
            temperature=0.75,
            max_tokens=400,
            system_message=(
                '你是K12教育助手，只输出分支名称，每行一个。'
                if language == 'zh'
                else 'You are a K12 assistant. Output branch names only, one per line.'
            ),
            timeout=45.0,
            user_id=user_id,
            organization_id=organization_id,
            request_type='node_palette',
            diagram_type=diagram_type,
            endpoint_path=endpoint_path or '/thinking_mode/node_palette/start',
            session_id=session_id,
        )
        return self._finalize_domain_label_list(raw, count, existing_labels, language)

    async def _iter_domain_bootstrap(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        stage: Dict[str, Any],
        user_id: Optional[int],
        organization_id: Optional[int],
        diagram_type: Optional[str],
        endpoint_path: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """SSE: batch_start + concept_map_domains + batch_complete."""
        count = max(1, min(int(stage.get('domain_count') or 3), 12))
        raw_existing = stage.get('existing_domain_labels')
        existing: List[str] = []
        if isinstance(raw_existing, list):
            existing = [str(x).strip() for x in raw_existing if str(x).strip()]
        language = self._detect_language(center_topic, educational_context)
        domains = await self._generate_domain_labels(
            center_topic=center_topic,
            educational_context=educational_context,
            count=count,
            existing_labels=existing,
            language=language,
            user_id=user_id,
            organization_id=organization_id,
            diagram_type=diagram_type,
            endpoint_path=endpoint_path,
            session_id=session_id,
        )
        yield {
            'event': 'batch_start',
            'batch_number': 1,
            'llm_count': 1,
            'nodes_per_llm': 0,
        }
        yield {'event': 'concept_map_domains', 'domains': domains}
        yield {'event': 'batch_complete', 'total_unique': 0}

    def _parent_id_and_merged_edu(
        self,
        stage: Dict[str, Any],
        _mode: Optional[str],
        educational_context: Optional[Dict[str, Any]],
    ) -> tuple[Optional[str], Dict[str, Any]]:
        """Resolve tab routing parent id and merge domain label into educational context."""
        merged: Dict[str, Any] = dict(educational_context or {})
        parent_id: Optional[str] = None
        if stage.get('parent_id'):
            parent_id = str(stage['parent_id'])
        elif _mode and _mode != 'topic':
            parent_id = str(_mode)
        domain_label = str(stage.get('domain_label') or '').strip()
        if domain_label:
            merged['palette_domain_label'] = domain_label
        return parent_id, merged

    def _decorate_concept_map_node_generated(
        self,
        node: Dict[str, Any],
        merged_edu: Dict[str, Any],
        parent_id: Optional[str],
    ) -> None:
        """Attach relationship label (domain tab) and palette parent routing."""
        if merged_edu.get('palette_domain_label'):
            raw_text = str(node.get('text') or '')
            concept, rel = self._split_concept_tab_relationship(raw_text)
            node['text'] = concept
            if rel:
                node['relationship_label'] = rel
        if parent_id:
            node['parent_id'] = parent_id
            node['mode'] = parent_id

    async def _async_iter_concept_stream(
        self,
        session_id: str,
        center_topic: str,
        stage: Dict[str, Any],
        educational_context: Optional[Dict[str, Any]],
        nodes_per_llm: int,
        _mode: Optional[str],
        _stage: Optional[str],
        _stage_data: Optional[Dict[str, Any]],
        user_id: Optional[int],
        organization_id: Optional[int],
        diagram_type: Optional[str],
        endpoint_path: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream concept nodes with per-tab parent_id and dedup scope."""
        parent_id, merged_edu = self._parent_id_and_merged_edu(
            stage, _mode, educational_context
        )
        dedup = f"{session_id}_{parent_id}" if parent_id else session_id
        async for chunk in super().generate_batch(
            session_id=dedup,
            center_topic=center_topic,
            educational_context=merged_edu,
            nodes_per_llm=nodes_per_llm,
            _mode=_mode,
            _stage=_stage,
            _stage_data=_stage_data,
            user_id=user_id,
            organization_id=organization_id,
            diagram_type=diagram_type,
            endpoint_path=endpoint_path,
        ):
            if chunk.get('event') == 'node_generated':
                node = chunk.get('node')
                if node and isinstance(node, dict):
                    self._decorate_concept_map_node_generated(
                        node, merged_edu, parent_id
                    )
            yield chunk

    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        _mode: Optional[str] = None,
        _stage: Optional[str] = None,
        _stage_data: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        **_kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Bootstrap domain names or stream concepts with per-tab dedup scope."""
        stage = _stage_data if isinstance(_stage_data, dict) else {}

        if stage.get('bootstrap_domains'):
            async for ev in self._iter_domain_bootstrap(
                session_id,
                center_topic,
                educational_context,
                stage,
                user_id,
                organization_id,
                diagram_type,
                endpoint_path,
            ):
                yield ev
            return

        async for chunk in self._async_iter_concept_stream(
            session_id,
            center_topic,
            stage,
            educational_context,
            nodes_per_llm,
            _mode,
            _stage,
            _stage_data,
            user_id,
            organization_id,
            diagram_type,
            endpoint_path,
        ):
            yield chunk


_PALETTE_GENERATOR_CACHE: list[Optional[ConceptMapPaletteGenerator]] = [None]


def get_concept_map_palette_generator() -> ConceptMapPaletteGenerator:
    """Get singleton instance of Concept Map palette generator."""
    if _PALETTE_GENERATOR_CACHE[0] is None:
        _PALETTE_GENERATOR_CACHE[0] = ConceptMapPaletteGenerator()
    return _PALETTE_GENERATOR_CACHE[0]
