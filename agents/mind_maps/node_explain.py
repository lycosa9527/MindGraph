"""
Mind map node explain — three focused educational panels for one node.

Streams meaning, cognitive conflict, and inquiry questions as separate facets.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Literal, Optional

from prompts.ai_content_level import append_audience_instructions
from services.llm import llm_service
from utils.prompt_locale import is_chinese_prompt_shell_language, output_language_instruction

_MAX_BRANCHES = 16
_MAX_TOKENS = 320
PromptShell = Literal["zh", "en", "az"]
ExplainFacet = Literal["meaning", "conflict", "questions"]

_DIAGRAM_TYPE_LABELS: Dict[str, Dict[str, str]] = {
    "zh": {
        "mindmap": "思维导图",
        "mind_map": "思维导图",
        "circle_map": "圆圈图",
        "bubble_map": "气泡图",
        "double_bubble_map": "双气泡图",
        "tree_map": "树形图",
        "brace_map": "括号图",
        "flow_map": "流程图",
        "multi_flow_map": "复流程图",
        "bridge_map": "桥形图",
        "concept_map": "概念图",
    },
    "en": {
        "mindmap": "mind map",
        "mind_map": "mind map",
        "circle_map": "circle map",
        "bubble_map": "bubble map",
        "double_bubble_map": "double bubble map",
        "tree_map": "tree map",
        "brace_map": "brace map",
        "flow_map": "flow map",
        "multi_flow_map": "multi-flow map",
        "bridge_map": "bridge map",
        "concept_map": "concept map",
    },
    "az": {
        "mindmap": "Ağıl xəritəsi",
        "mind_map": "Ağıl xəritəsi",
        "circle_map": "Dairə xəritəsi",
        "bubble_map": "Bubble xəritəsi",
        "double_bubble_map": "Double Bubble xəritəsi",
        "tree_map": "Ağac xəritəsi",
        "brace_map": "Brace xəritəsi",
        "flow_map": "Axın xəritəsi",
        "multi_flow_map": "Çox axınlı xəritə",
        "bridge_map": "Körpü xəritəsi",
        "concept_map": "Konsepsiya xəritəsi",
    },
}

_EMPTY_LABELS = {
    "zh": "（无）",
    "en": "(none)",
    "az": "(yoxdur)",
}

_UNTITLED_LABELS = {
    "zh": "（未命名）",
    "en": "(untitled)",
    "az": "(adsız)",
}

_FACET_TASKS: Dict[PromptShell, Dict[ExplainFacet, str]] = {
    "zh": {
        "meaning": (
            "直接给出该节点的清晰定义与解释：站在中心主题的视角，说明它是什么、指什么。"
            "先答本质（像短释义），必要时再用一两句点明它在本主题下的具体含义；"
            "不要讲层级位置，不要寒暄铺垫，不要写认知冲突，不要列问题。"
            "写成 1–2 段短文，约 60–120 字，干净直给。"
        ),
        "conflict": (
            "只讨论该节点可能引发的认知冲突、张力或常见误解：可点名与主题或其他分支的对比。"
            "不要做完整释义，不要列启发问题。写成 1–2 段短文，约 80–140 字。"
        ),
        "questions": (
            "只给出 3 条简短、有趣、可继续探究的问题，帮助学习者围绕该节点深入思考。"
            "用编号列表（1. 2. 3.），每条一行；不要解释节点含义，不要展开长篇分析。"
        ),
    },
    "en": {
        "meaning": (
            "Give a clear, direct definition of this node from the central topic's perspective: "
            "what it is and what it means here. Lead with the essence (short glossary style); "
            "add at most one or two sentences on its meaning under this topic if needed. "
            "No hierarchy lecture, no soft opener, no cognitive conflict, no questions. "
            "1–2 short paragraphs, about 50–100 words — clean and straight."
        ),
        "conflict": (
            "Only discuss cognitive conflicts, tensions, or common misconceptions this node may spark "
            "(you may name contrasts with the topic or other branches). "
            "Do not give a full definition or list inquiry questions. "
            "Write 1–2 short paragraphs, about 60–110 words."
        ),
        "questions": (
            "Only provide 3 short, interesting inquiry questions that help the learner dig deeper "
            "into this node. Use a numbered list (1. 2. 3.), one line each. "
            "Do not explain the node or write long analysis."
        ),
    },
    "az": {
        "meaning": (
            "Mərkəz mövzunun perspektivindən bu düyünün aydın, birbaşa tərifini verin: "
            "nədir və burada nə deməkdir. Əvvəlcə mahiyyəti (qısa lüğət üslubu); "
            "lazım gələrsə mövzu altındakı mənasına 1–2 cümlə əlavə edin. "
            "İerarxiya izahı, giriş salamı, koqnitiv konflikt və suallar olmasın. "
            "1–2 qısa abzas, təxminən 50–100 söz — təmiz və birbaşa."
        ),
        "conflict": (
            "Yalnız bu düyünün yarada biləcəyi koqnitiv konflikt, gərginlik və ya ümumi səhv "
            "anlayışları müzakirə edin. Tam izah və sual siyahısı verməyin. "
            "1–2 qısa abzas, təxminən 60–110 söz."
        ),
        "questions": (
            "Yalnız bu düyün haqqında dərin düşünməyə kömək edən 3 qısa, maraqlı sual verin. "
            "Nömrələnmiş siyahı (1. 2. 3.), hər sətirdə bir sual. Uzun izah yazmayın."
        ),
    },
}

_ROLE_LINES: Dict[PromptShell, str] = {
    "zh": "你是面向课堂与自主学习的思维图示助教。",
    "en": "You are a classroom-friendly diagram learning coach.",
    "az": "Siz sinif və müstəqil öyrənmə üçün diaqram köməkçisisiniz.",
}

_STYLE_LINES: Dict[PromptShell, str] = {
    "zh": "亲切、专业；不要 Markdown 标题；不要寒暄开场。",
    "en": "Supportive and educational; no Markdown headings; no small-talk opener.",
    "az": "Dəstəkləyici və təhsil yönümlü; Markdown başlıqları və giriş salamı olmasın.",
}


def _prompt_shell_key(language: str) -> PromptShell:
    normalized = (language or "en").strip().lower().replace("_", "-")
    if is_chinese_prompt_shell_language(normalized):
        return "zh"
    if normalized == "az":
        return "az"
    return "en"


def _diagram_type_label(diagram_type: str, shell: PromptShell) -> str:
    normalized = (diagram_type or "mindmap").strip().lower().replace("-", "_")
    labels = _DIAGRAM_TYPE_LABELS[shell]
    return labels.get(normalized, labels["mindmap"])


def _join_labels(labels: List[str], shell: PromptShell) -> str:
    cleaned = [label.strip() for label in labels if label and label.strip()]
    if not cleaned:
        return _EMPTY_LABELS[shell]
    separator = "、" if shell == "zh" else ", "
    return separator.join(cleaned[:_MAX_BRANCHES])


def _path_line(path: List[str], shell: PromptShell) -> str:
    if not path:
        return ""
    joined = " → ".join(path)
    if shell == "zh":
        return f"节点层级路径：主题 → {joined}\n"
    if shell == "az":
        return f"Düyün yolu: mövzu → {joined}\n"
    return f"Node path: topic → {joined}\n"


def _normalize_facet(facet: str) -> ExplainFacet:
    normalized = (facet or "meaning").strip().lower()
    if normalized == "conflict":
        return "conflict"
    if normalized == "questions":
        return "questions"
    return "meaning"


def _diagram_context_fields(
    *,
    node_label: str,
    topic: str,
    diagram_type: str,
    top_level_branches: List[str],
    ancestor_path: List[str],
    sibling_branches: List[str],
    child_branches: List[str],
    language: str,
) -> Dict[str, str]:
    shell = _prompt_shell_key(language)
    topic_text = topic.strip() or _UNTITLED_LABELS[shell]
    return {
        "diagram_label": _diagram_type_label(diagram_type, shell),
        "topic": topic_text,
        "node_label": node_label.strip(),
        "branches_text": _join_labels(top_level_branches, shell),
        "siblings_text": _join_labels(sibling_branches, shell),
        "children_text": _join_labels(child_branches, shell),
        "path_line": _path_line(ancestor_path, shell),
    }


def _build_context_block(fields: Dict[str, str], shell: PromptShell) -> str:
    if shell == "zh":
        return (
            "【图示情境】\n"
            f"- 图示类型：{fields['diagram_label']}\n"
            f"- 中心主题：{fields['topic']}\n"
            f"- 主要分支：{fields['branches_text']}\n"
            f"- 学习者选中的节点：{fields['node_label']}\n"
            f"{fields['path_line']}"
            f"- 同层相关节点：{fields['siblings_text']}\n"
            f"- 该节点下的子节点：{fields['children_text']}\n"
        )
    if shell == "az":
        return (
            "【Diaqram konteksti】\n"
            f"- Diaqram növü: {fields['diagram_label']}\n"
            f"- Mərkəz mövzu: {fields['topic']}\n"
            f"- Əsas budaqlar: {fields['branches_text']}\n"
            f"- Seçilmiş düyün: {fields['node_label']}\n"
            f"{fields['path_line']}"
            f"- Eyni səviyyəli düyünlər: {fields['siblings_text']}\n"
            f"- Alt düyünlər: {fields['children_text']}\n"
        )
    return (
        "【Diagram context】\n"
        f"- Diagram type: {fields['diagram_label']}\n"
        f"- Central topic: {fields['topic']}\n"
        f"- Main branches: {fields['branches_text']}\n"
        f"- Selected node: {fields['node_label']}\n"
        f"{fields['path_line']}"
        f"- Sibling / related nodes: {fields['siblings_text']}\n"
        f"- Child nodes: {fields['children_text']}\n"
    )


def _build_facet_prompt(
    *,
    facet: ExplainFacet,
    node_label: str,
    topic: str,
    diagram_type: str,
    top_level_branches: List[str],
    ancestor_path: List[str],
    sibling_branches: List[str],
    child_branches: List[str],
    language: str,
    generation_instructions: Optional[str] = None,
) -> str:
    """Build a single-facet educational prompt for one panel."""
    fields = _diagram_context_fields(
        node_label=node_label,
        topic=topic,
        diagram_type=diagram_type,
        top_level_branches=top_level_branches,
        ancestor_path=ancestor_path,
        sibling_branches=sibling_branches,
        child_branches=child_branches,
        language=language,
    )
    shell = _prompt_shell_key(language)
    task = _FACET_TASKS[shell][facet]
    if shell == "zh":
        task_header = "【你的任务】"
        style_header = "【文风】"
    elif shell == "az":
        task_header = "【Tapşırığınız】"
        style_header = "【Ton】"
    else:
        task_header = "【Your task】"
        style_header = "【Tone】"

    return append_audience_instructions(
        (
            f"{_ROLE_LINES[shell]}\n"
            f"{output_language_instruction(language)}\n"
            f"{_build_context_block(fields, shell)}\n"
            f"{task_header}\n"
            f"{task}\n\n"
            f"{style_header}\n"
            f"{_STYLE_LINES[shell]}"
        ),
        generation_instructions,
    )


class _GeneratorHolder:
    """Holds singleton instance to avoid global mutable state."""

    instance: Optional["MindMapNodeExplainGenerator"] = None


class MindMapNodeExplainGenerator:
    """Streams one educational facet for a selected diagram node."""

    def __init__(self) -> None:
        self.llm_service = llm_service

    async def stream_explain(
        self,
        *,
        node_label: str,
        topic: str,
        diagram_type: str = "mindmap",
        top_level_branches: Optional[List[str]] = None,
        ancestor_path: Optional[List[str]] = None,
        sibling_branches: Optional[List[str]] = None,
        child_branches: Optional[List[str]] = None,
        language: str = "en",
        facet: str = "meaning",
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        endpoint_path: str = "/thinking_mode/mindmap/explain_node",
        diagram_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_token: Optional[str] = None,
        generation_instructions: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield SSE-friendly event dicts: token chunks and end."""
        resolved_facet = _normalize_facet(facet)
        branches = top_level_branches or []
        ancestors = ancestor_path or []
        siblings = sibling_branches or []
        children = child_branches or []
        token = (request_token or "req").strip() or "req"
        user_part = str(user_id) if user_id is not None else "anon"
        base_session = (session_id or "").strip() or f"explain_{diagram_id or 'anon'}_{user_part}"
        # Per-facet stream id keeps token rows distinct while sharing the client session prefix.
        stream_session_id = f"{base_session}:{resolved_facet}:{token}"
        saw_token = False

        prompt = _build_facet_prompt(
            facet=resolved_facet,
            node_label=node_label,
            topic=topic,
            diagram_type=diagram_type,
            top_level_branches=branches,
            ancestor_path=ancestors,
            sibling_branches=siblings,
            child_branches=children,
            language=language,
            generation_instructions=generation_instructions,
        )

        async for chunk in self.llm_service.chat_stream(
            prompt=prompt,
            model="qwen",
            max_tokens=_MAX_TOKENS,
            temperature=0.6,
            user_id=user_id,
            organization_id=organization_id,
            request_type="mindmap_node_explain",
            diagram_type=diagram_type or "mindmap",
            endpoint_path=endpoint_path,
            session_id=stream_session_id,
            use_knowledge_base=False,
            yield_structured=True,
        ):
            if not isinstance(chunk, dict):
                continue
            if chunk.get("type") != "token":
                continue
            content = chunk.get("content") or ""
            if not content:
                continue
            saw_token = True
            yield {"event": "token", "text": content, "facet": resolved_facet}

        if not saw_token:
            # Router emits a localized empty-response error when no chunks arrive.
            return
        yield {"event": "end", "facet": resolved_facet}


def get_mind_map_node_explain_generator() -> MindMapNodeExplainGenerator:
    """Return shared generator instance."""
    if _GeneratorHolder.instance is None:
        _GeneratorHolder.instance = MindMapNodeExplainGenerator()
    return _GeneratorHolder.instance
