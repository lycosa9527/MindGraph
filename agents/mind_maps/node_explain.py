"""
Mind map node explain — Kitty educational helper on cognitive conflict and inquiry.

Helps learners reflect on why a selected node may spark questions, tension, or
misconceptions within their diagram.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Literal, Optional

from services.llm import llm_service
from utils.prompt_locale import is_chinese_prompt_shell_language, output_language_instruction

_MAX_BRANCHES = 16
_MAX_TOKENS = 520
PromptShell = Literal["zh", "en", "az"]

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


def _build_zh_prompt(
    *,
    diagram_label: str,
    topic: str,
    node_label: str,
    branches_text: str,
    path_line: str,
    siblings_text: str,
    children_text: str,
    language: str,
) -> str:
    return (
        "你是 Kitty，面向课堂与自主学习的思维图示助教。学习者正在绘制一张"
        f"{diagram_label}，请你以温和、启发式口吻帮助其反思所选节点。\n"
        f"{output_language_instruction(language)}\n"
        "【图示情境】\n"
        f"- 中心主题：{topic}\n"
        f"- 主要分支：{branches_text}\n"
        f"- 学习者选中的节点：{node_label}\n"
        f"{path_line}"
        f"- 同层相关节点：{siblings_text}\n"
        f"- 该节点下的子节点：{children_text}\n\n"
        "【你的任务】\n"
        "说明这个节点为什么值得停下来想一想：它可能引发哪些认知冲突、疑问、"
        "与主题或其他分支的张力，或学习者常见的误解？\n"
        "请自然写成一段对话式辅导（可分 2–3 短段，不要堆很多条列点），并涵盖：\n"
        "1. 该节点在整张图中的位置与含义；\n"
        "2. 至少 1–2 个可能引发认知冲突或追问的具体角度（可点名与哪些分支形成对比或张力）；\n"
        "3. 1–2 条简短的后续思考建议（如何继续完善、讨论或验证）。\n\n"
        "【文风与长度】\n"
        "亲切、专业、面向学习者；总长约 120–220 字；不要 Markdown 标题；"
        "结尾可用一句简短问句邀请学习者继续思考。"
    )


def _build_en_prompt(
    *,
    diagram_label: str,
    topic: str,
    node_label: str,
    branches_text: str,
    path_line: str,
    siblings_text: str,
    children_text: str,
    language: str,
) -> str:
    return (
        "You are Kitty, a classroom-friendly diagram learning coach. "
        f"The learner is building a {diagram_label}. "
        "Help them reflect on the node they selected.\n"
        f"{output_language_instruction(language)}\n"
        "【Diagram context】\n"
        f"- Central topic: {topic}\n"
        f"- Main branches: {branches_text}\n"
        f"- Selected node: {node_label}\n"
        f"{path_line}"
        f"- Sibling / related nodes: {siblings_text}\n"
        f"- Child nodes under selection: {children_text}\n\n"
        "【Your task】\n"
        "Explain why this node is worth pausing on: what cognitive conflict, open questions, "
        "tension with the topic or other branches, or common misconceptions might it trigger?\n"
        "Write as a warm coaching reply in 2–3 short paragraphs (not a long bullet list), covering:\n"
        "1. What this node means and where it sits in the diagram;\n"
        "2. At least 1–2 specific angles of conflict or inquiry (name branches it may tension with);\n"
        "3. 1–2 brief next-step suggestions (how to refine, discuss, or verify).\n\n"
        "【Tone & length】\n"
        "Supportive and educational; about 80–150 words; no Markdown headings; "
        "you may end with one short question inviting further thought."
    )


def _build_az_prompt(
    *,
    diagram_label: str,
    topic: str,
    node_label: str,
    branches_text: str,
    path_line: str,
    siblings_text: str,
    children_text: str,
    language: str,
) -> str:
    return (
        "Siz Kitty-siniz — sinif və müstəqil öyrənmə üçün diaqram köməkçisi. "
        f"Öyrənən bir {diagram_label} qurur; seçdiyi düyün haqqında düşünməsinə "
        "səmimi və açıq şəkildə kömək edin.\n"
        f"{output_language_instruction(language)}\n"
        "【Diaqram konteksti】\n"
        f"- Mərkəz mövzu: {topic}\n"
        f"- Əsas budaqlar: {branches_text}\n"
        f"- Seçilmiş düyün: {node_label}\n"
        f"{path_line}"
        f"- Eyni səviyyəli / əlaqəli düyünlər: {siblings_text}\n"
        f"- Seçim altındakı alt düyünlər: {children_text}\n\n"
        "【Tapşırığınız】\n"
        "Bu düyünün niyə dayanıb düşünməyə dəyər olduğunu izah edin: hansı "
        "koqnitiv konflikt, açıq suallar, mövzu və ya digər budaqlarla gərginlik "
        "və ya ümumi səhv anlayışlar yarana bilər?\n"
        "Cavabı 2–3 qısa abzasda, söhbət tərzində yazın (uzun siyahı yox), və bunları əhatə edin:\n"
        "1. Bu düyünün diaqramdakı yeri və mənası;\n"
        "2. Ən azı 1–2 konkret konflikt və ya sorğu bucağı (hansı budaqlarla ziddiyyət "
        "və ya gərginlik yarada biləcəyini adlandırın);\n"
        "3. 1–2 qısa növbəti addım təklifi (necə təkmilləşdirmək, müzakirə etmək və ya yoxlamaq).\n\n"
        "【Ton və həcm】\n"
        "Dəstəkləyici və təhsil yönümlü; təxminən 80–150 söz; Markdown başlıqları olmasın; "
        "sonda daha çox düşünməyə dəvət edən qısa bir sualla bitirə bilərsiniz."
    )


def _build_follow_up_system_prompt(
    *,
    diagram_label: str,
    topic: str,
    node_label: str,
    branches_text: str,
    path_line: str,
    siblings_text: str,
    children_text: str,
    language: str,
) -> str:
    """System context for follow-up turns in the node explain chat."""
    shell = _prompt_shell_key(language)
    if shell == "zh":
        return (
            "你是 Kitty，面向课堂与自主学习的思维图示助教。学习者正在一张"
            f"{diagram_label}上讨论节点「{node_label}」。"
            f"{output_language_instruction(language)}\n"
            "【图示情境】\n"
            f"- 中心主题：{topic}\n"
            f"- 主要分支：{branches_text}\n"
            f"{path_line}"
            f"- 同层相关节点：{siblings_text}\n"
            f"- 该节点下的子节点：{children_text}\n\n"
            "继续以温和、启发式口吻回答学习者的追问，帮助其反思认知冲突、"
            "疑问与后续思考；保持对话式短段，约 80–150 字，不要 Markdown 标题。"
        )
    if shell == "az":
        return (
            "Siz Kitty-siniz — sinif və müstəqil öyrənmə üçün diaqram köməkçisi. "
            f"Öyrənən «{node_label}» düyünü haqqında {diagram_label} üzərində "
            "söhbəti davam etdirir.\n"
            f"{output_language_instruction(language)}\n"
            "【Diaqram konteksti】\n"
            f"- Mərkəz mövzu: {topic}\n"
            f"- Əsas budaqlar: {branches_text}\n"
            f"{path_line}"
            f"- Eyni səviyyəli düyünlər: {siblings_text}\n"
            f"- Alt düyünlər: {children_text}\n\n"
            "Öyrənənin suallarına səmimi, açıq şəkildə cavab verin; koqnitif konflikt "
            "və növbəti addımlara kömək edin. 2–3 qısa abzas, Markdown başlıqları olmasın."
        )
    return (
        "You are Kitty, a classroom-friendly diagram learning coach. "
        f"The learner is continuing a conversation about node «{node_label}» "
        f"on a {diagram_label}.\n"
        f"{output_language_instruction(language)}\n"
        "【Diagram context】\n"
        f"- Central topic: {topic}\n"
        f"- Main branches: {branches_text}\n"
        f"{path_line}"
        f"- Sibling / related nodes: {siblings_text}\n"
        f"- Child nodes: {children_text}\n\n"
        "Answer follow-up questions warmly and educationally; help reflect on "
        "cognitive conflict and next steps. Keep replies conversational, about "
        "60–120 words, no Markdown headings."
    )


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
        "language": language,
    }


def _build_explain_prompt(
    *,
    node_label: str,
    topic: str,
    diagram_type: str,
    top_level_branches: List[str],
    ancestor_path: List[str],
    sibling_branches: List[str],
    child_branches: List[str],
    language: str,
) -> str:
    """Build an education-focused cognitive-conflict explain prompt."""
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

    if shell == "zh":
        return _build_zh_prompt(**fields)
    if shell == "az":
        return _build_az_prompt(**fields)
    return _build_en_prompt(**fields)


def _build_follow_up_messages(
    *,
    node_label: str,
    topic: str,
    diagram_type: str,
    top_level_branches: List[str],
    ancestor_path: List[str],
    sibling_branches: List[str],
    child_branches: List[str],
    language: str,
    history: List[Dict[str, str]],
    user_message: str,
) -> List[Dict[str, str]]:
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
    system_prompt = _build_follow_up_system_prompt(**fields)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in history:
        role = turn.get("role", "").strip()
        content = (turn.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message.strip()})
    return messages


class _GeneratorHolder:
    """Holds singleton instance to avoid global mutable state."""

    instance: Optional["MindMapNodeExplainGenerator"] = None


class MindMapNodeExplainGenerator:
    """Streams an educational node reflection from a single LLM."""

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
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        endpoint_path: str = "/thinking_mode/mindmap/explain_node",
        diagram_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        user_message: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield SSE-friendly event dicts: token chunks and end."""
        branches = top_level_branches or []
        ancestors = ancestor_path or []
        siblings = sibling_branches or []
        children = child_branches or []
        follow_up_text = (user_message or "").strip()
        session_id = f"explain_{diagram_id or 'anon'}"
        saw_token = False

        if follow_up_text:
            chat_messages = _build_follow_up_messages(
                node_label=node_label,
                topic=topic,
                diagram_type=diagram_type,
                top_level_branches=branches,
                ancestor_path=ancestors,
                sibling_branches=siblings,
                child_branches=children,
                language=language,
                history=history or [],
                user_message=follow_up_text,
            )
            stream_kwargs: Dict[str, Any] = {"messages": chat_messages}
        else:
            prompt = _build_explain_prompt(
                node_label=node_label,
                topic=topic,
                diagram_type=diagram_type,
                top_level_branches=branches,
                ancestor_path=ancestors,
                sibling_branches=siblings,
                child_branches=children,
                language=language,
            )
            stream_kwargs = {"prompt": prompt}

        async for chunk in self.llm_service.chat_stream(
            **stream_kwargs,
            model="qwen",
            max_tokens=_MAX_TOKENS,
            temperature=0.6,
            user_id=user_id,
            organization_id=organization_id,
            request_type="diagram_generation",
            diagram_type=diagram_type or "mindmap",
            endpoint_path=endpoint_path,
            session_id=session_id,
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
            yield {"event": "token", "text": content}

        if not saw_token:
            yield {"event": "error", "message": "No response"}
            return
        yield {"event": "end"}


def get_mind_map_node_explain_generator() -> MindMapNodeExplainGenerator:
    """Return shared generator instance."""
    if _GeneratorHolder.instance is None:
        _GeneratorHolder.instance = MindMapNodeExplainGenerator()
    return _GeneratorHolder.instance
