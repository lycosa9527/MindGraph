"""
Node-explain prompt builder — 专业程度 selects voice, length, and depth.

Meaning copy is level-specific so kids get everyday glosses and
professional / audit readers get peer language. Conflict and questions
keep a shared shape; audience_brief still steers their voice.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from prompts.ai_content_level import append_audience_instructions
from services.mind_classroom.prompts.audience_prompts import (
    audience_brief,
    normalize_audience_level,
)
from utils.prompt_locale import is_chinese_prompt_shell_language, output_language_instruction

_MAX_BRANCHES = 16
PromptShell = Literal["zh", "en", "az"]
ExplainFacet = Literal["meaning", "conflict", "questions"]
StyleBand = Literal["kid", "school", "pro", "general"]

_MAX_TOKENS_BY_LEVEL: Dict[str, int] = {
    "primary": 512,
    "junior": 640,
    "general": 640,
    "senior": 768,
    "university": 768,
    "adult": 768,
    "expert": 768,
}

RESEARCH_MAX_OUTPUT_TOKENS = 8192
RESEARCH_IMAGE_MAX_OUTPUT_TOKENS = 1024
RESEARCH_IMAGE_MAX = 24
RESEARCH_TOOLS = ("web_search",)
RESEARCH_IMAGE_TOOLS = ("web_search_image",)

_RESEARCH_BLOCKS: Dict[PromptShell, str] = {
    "zh": (
        "【联网研究】\n"
        "必须调用 web_search。"
        "搜索一返回就根据标题和摘要写释义，不要打开网页，不要再搜一轮。"
        "正文不少于 250 字，目标 250–400 字。"
        "句末用 [1][2] 标注依据，编号与搜索结果顺序一致（第一条为 [1]）。"
        "不要在释义里列出网址或标题。标注不算扩写。"
        "最终回复只写这段释义加标注，不要写检索过程，不要列提纲。"
    ),
    "en": (
        "【Web research】\n"
        "You must run web_search. "
        "Write the gloss from search titles and snippets as soon as search returns — "
        "do not open pages or start another search. "
        "Write at least 160 words, target 160–260 words. "
        "Cite sources as [1][2] in search order (first result is [1]). "
        "Do not list URLs or titles in the gloss. Marks are not extra prose. "
        "The final reply is that paragraph plus citations only — no search diary."
    ),
    "az": (
        "【Veb tədqiqat】\n"
        "Alət: web_search. "
        "Axtarış gələndən dərhal başlıq və qısa mətndən izah yazın. "
        "Ən azı 160 söz, hədəf 160–260 söz. "
        "Mənbələri [1][2] ilə işarələyin. Səhifə açmayın. Hesabat olmasın."
    ),
}

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

_EMPTY_LABELS = {"zh": "（无）", "en": "(none)", "az": "(yoxdur)"}
_UNTITLED_LABELS = {"zh": "（未命名）", "en": "(untitled)", "az": "(adsız)"}

_ROLE_LINES: Dict[PromptShell, str] = {
    "zh": "你是面向课堂、职场与专业审阅的思维图示助教。",
    "en": "You are a diagram coach for classrooms, workplaces, and professional review.",
    "az": "Siz sinif, iş və peşəkar baxış üçün diaqram köməkçisisiniz.",
}

_STYLE_LINES: Dict[PromptShell, Dict[StyleBand, str]] = {
    "zh": {
        "kid": "亲切，像讲给小朋友听；不要 Markdown 标题；不要寒暄开场。",
        "school": "清楚、适合该学段；不要 Markdown 标题；不要寒暄开场。",
        "pro": "专业、克制；禁止科普开场与课堂口吻；不要 Markdown 标题。",
        "general": "清楚、自然；不要故意小学化，也不要专家腔；不要 Markdown 标题；不要寒暄开场。",
    },
    "en": {
        "kid": "Warm and easy for a child; no Markdown headings; no small-talk opener.",
        "school": "Clear for this school stage; no Markdown headings; no small-talk opener.",
        "pro": "Professional and restrained; no popular-science opening or classroom tone; no Markdown headings.",
        "general": "Clear and natural; neither primary-school nor expert-peer voice; no Markdown headings; no opener.",
    },
    "az": {
        "kid": "Uşağa danışır kimi isti; Markdown başlığı və giriş salamı olmasın.",
        "school": "Bu məktəb səviyyəsinə uyğun; Markdown başlığı və giriş salamı olmasın.",
        "pro": "Peşəkar və yığcam; populyar-elm açılışı və sinif tonu olmasın; Markdown başlığı olmasın.",
        "general": "Aydın və təbii; nə ibtidai, nə ekspert səsi; Markdown başlığı və giriş salamı olmasın.",
    },
}

_MEANING_TASKS: Dict[PromptShell, Dict[str, str]] = {
    "zh": {
        "general": (
            "用一段完整说明把这个节点在中心主题里是什么、指什么讲清楚。"
            "正文不少于 250 字，目标 250–400 字。不要讲层级位置，不要寒暄，不要写认知冲突，不要列问题，不要分点。"
            "不要故意小学化，也不要专家腔。"
        ),
        "primary": (
            "用一段日常口语说明这个节点是什么，像给小朋友解释「苹果」："
            "苹果是长在树上的红色水果。"
            "站在中心主题的视角，只说它是什么、指什么；正文不少于 250 字，目标 250–400 字。"
            "不要讲层级位置，不要寒暄，不要写认知冲突，不要列问题，不要分点。"
        ),
        "junior": (
            "用一段适合初中生的话说明这个节点是什么。可用一个学科词，首次用生活说法带过。"
            "正文不少于 250 字，目标 250–400 字。不要讲层级位置，不要寒暄，不要写认知冲突，不要列问题，不要分点。"
        ),
        "senior": (
            "用一段规范学科用语说明这个节点在主题中的含义与关系。少科普铺垫。"
            "正文不少于 250 字，目标 250–400 字。不要讲层级位置，不要寒暄，不要写认知冲突，不要列问题，不要分点。"
        ),
        "university": (
            "用一段学科术语说明这个节点的机制或理论位置，不必解释入门词。"
            "正文不少于 250 字，目标 250–400 字。不要中小学教案口吻，不要讲层级位置，不要寒暄，不要列问题。"
        ),
        "adult": (
            "用一段专业、面向做事的话说明这个节点是什么、在实务上意味着什么。"
            "正文不少于 250 字，目标 250–400 字。少课堂口吻。不要讲层级位置，不要寒暄，不要列问题。"
        ),
        "expert": (
            "用一段领域术语给出同行级、可审阅的释义：机制、边界或争议即可。"
            "禁止科普开场与类比故事。正文不少于 250 字，目标 250–400 字，密、准。"
            "不要讲层级位置，不要寒暄，不要列问题。"
        ),
    },
    "en": {
        "general": (
            "In one paragraph, say what this node is in the central topic. "
            "At least 160 words, target 160–260. "
            "No hierarchy lecture, no opener, no cognitive conflict, no questions, no lists. "
            "Neither a child's gloss nor an expert-peer note."
        ),
        "primary": (
            "In one everyday paragraph, say what this node is — like explaining apple: "
            "a red fruit that grows on trees. From the central topic's perspective, only what it is "
            "and what it means here. At least 160 words, target 160–260. "
            "No hierarchy lecture, no soft opener, no cognitive conflict, no questions, no lists."
        ),
        "junior": (
            "In one middle-school paragraph, say what this node is. "
            "One subject word is fine if you gloss it. At least 160 words, target 160–260. "
            "No hierarchy lecture, no opener, no cognitive conflict, no questions, no lists."
        ),
        "senior": (
            "In one high-school paragraph, name what this node is and how it relates to the topic. "
            "Subject terms are fine; skip popular-science padding. At least 160 words, target 160–260. "
            "No hierarchy lecture, no opener, no questions, no lists."
        ),
        "university": (
            "In one disciplinary paragraph, place this node in its mechanism or theoretical frame. "
            "Do not define introductory words. At least 160 words, target 160–260. "
            "No K–12 lesson tone, no opener, no lists."
        ),
        "adult": (
            "In one professional paragraph, say what this node is and what it means in practice. "
            "Little classroom tone. At least 160 words, target 160–260. "
            "No hierarchy lecture, no opener, no lists."
        ),
        "expert": (
            "In one dense peer paragraph, give an audit-ready gloss: mechanism, bound, or disagreement. "
            "Domain terminology. No popular-science opening or analogy story. "
            "At least 160 words, target 160–260. "
            "No hierarchy lecture, no opener, no questions, no lists."
        ),
    },
    "az": {
        "general": (
            "Qısa bir abzasla bu düyünün mərkəz mövzuda nə olduğunu deyin. "
            "Təxminən 160–260 söz. İerarxiya, salam, konflikt, sual və siyahı olmasın."
        ),
        "primary": (
            "Qısa gündəlik abzasla bu düyünün nə olduğunu deyin — alma kimi: "
            "ağacda bitən qırmızı meyvə. Təxminən 160–260 söz. "
            "İerarxiya, giriş salamı, koqnitiv konflikt, sual və siyahı olmasın."
        ),
        "junior": (
            "Orta məktəb səviyyəsində qısa abzasla bu düyünün nə olduğunu deyin. "
            "Təxminən 160–260 söz. İerarxiya, salam, sual və siyahı olmasın."
        ),
        "senior": (
            "Lisey səviyyəsində bu düyünün mövzu ilə əlaqəsini deyin. "
            "Təxminən 160–260 söz. Populyar-elm dolğusu olmasın."
        ),
        "university": (
            "Akademik abzasla bu düyünün mexanizm və ya nəzəri yerini deyin. "
            "Təxminən 160–260 söz. Məktəb dərs tonu olmasın."
        ),
        "adult": ("Peşəkar, işə yönəlmiş qısa abzasla bu düyünün praktik mənasını deyin. Təxminən 160–260 söz."),
        "expert": (
            "Həmkar üçün sıx, dəqiq, yoxlanıla bilən izah: mexanizm, sərhəd və ya mübahisə. "
            "Populyar-elm açılışı olmasın. Təxminən 160–260 söz."
        ),
    },
}

_SHARED_FACET_TASKS: Dict[PromptShell, Dict[str, str]] = {
    "zh": {
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


def prompt_shell_key(language: str) -> PromptShell:
    """Map a UI / generation language to the prompt-shell locale."""
    normalized = (language or "en").strip().lower().replace("_", "-")
    if is_chinese_prompt_shell_language(normalized):
        return "zh"
    if normalized == "az":
        return "az"
    return "en"


def style_band_for_level(level: str) -> StyleBand:
    """Collapse 专业程度 ids into kid / school / professional / general bands."""
    resolved = normalize_audience_level(level)
    if resolved == "primary":
        return "kid"
    if resolved in {"university", "adult", "expert"}:
        return "pro"
    if resolved in {"junior", "senior"}:
        return "school"
    return "general"


def max_tokens_for_audience(level: str) -> int:
    """Token budget so a 250–400 character gloss is not cut off."""
    return _MAX_TOKENS_BY_LEVEL[normalize_audience_level(level)]


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


def normalize_facet(facet: str) -> ExplainFacet:
    """Unknown facet values fall back to meaning."""
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
    shell = prompt_shell_key(language)
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


_MEANING_LENGTH_GUARD: Dict[PromptShell, str] = {
    "zh": "正文不少于 250 字，目标 250–400 字。",
    "en": "Write at least 160 words, target 160–260 words.",
    "az": "Ən azı 160 söz, hədəf 160–260 söz.",
}


def _facet_task(facet: ExplainFacet, shell: PromptShell, level: str) -> str:
    if facet == "meaning":
        task = _MEANING_TASKS[shell][normalize_audience_level(level)]
        return f"{_MEANING_LENGTH_GUARD[shell]}{task}"
    return _SHARED_FACET_TASKS[shell][facet]


def _section_headers(shell: PromptShell) -> tuple[str, str, str]:
    if shell == "zh":
        return "【你的任务】", "【文风】", "【专业程度】"
    if shell == "az":
        return "【Tapşırığınız】", "【Ton】", "【Peşəkarlıq】"
    return "【Your task】", "【Tone】", "【Expertise】"


def build_facet_prompt(
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
    audience_level: Optional[str] = None,
    generation_instructions: Optional[str] = None,
) -> str:
    """Build a single-facet prompt whose meaning task follows 专业程度."""
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
    shell = prompt_shell_key(language)
    level = normalize_audience_level(audience_level)
    task = _facet_task(facet, shell, level)
    task_header, style_header, audience_header = _section_headers(shell)
    brief = audience_brief(level, "zh" if shell == "zh" else "en")
    return append_audience_instructions(
        (
            f"{_ROLE_LINES[shell]}\n"
            f"{output_language_instruction(language)}\n"
            f"{_build_context_block(fields, shell)}\n"
            f"{task_header}\n"
            f"{task}\n\n"
            f"{style_header}\n"
            f"{_STYLE_LINES[shell][style_band_for_level(level)]}\n\n"
            f"{audience_header}\n"
            f"{brief}"
        ),
        generation_instructions,
    )


def build_research_meaning_prompt(
    *,
    node_label: str,
    topic: str,
    diagram_type: str,
    top_level_branches: List[str],
    ancestor_path: List[str],
    sibling_branches: List[str],
    child_branches: List[str],
    language: str,
    audience_level: Optional[str] = None,
    generation_instructions: Optional[str] = None,
) -> str:
    """Meaning prompt plus search-then-write research instructions."""
    base = build_facet_prompt(
        facet="meaning",
        node_label=node_label,
        topic=topic,
        diagram_type=diagram_type,
        top_level_branches=top_level_branches,
        ancestor_path=ancestor_path,
        sibling_branches=sibling_branches,
        child_branches=child_branches,
        language=language,
        audience_level=audience_level,
        generation_instructions=generation_instructions,
    )
    shell = prompt_shell_key(language)
    return f"{base}\n\n{_RESEARCH_BLOCKS[shell]}"


def build_research_image_prompt(
    *,
    node_label: str,
    topic: str,
    language: str,
) -> str:
    """Short prompt that only asks for image search, never a gloss."""
    shell = prompt_shell_key(language)
    node_text = node_label.strip() or _UNTITLED_LABELS[shell]
    topic_text = topic.strip() or _UNTITLED_LABELS[shell]
    if shell == "zh":
        return (
            f"{output_language_instruction(language)}\n"
            f"只调用一次 web_search_image，为节点「{node_text}」（主题：{topic_text}）检索约 "
            f"{RESEARCH_IMAGE_MAX} 张配图，最多 30 张。"
            "不要写释义，不要调用 web_search，不要打开网页，不要再搜一轮。"
        )
    if shell == "az":
        return (
            f"{output_language_instruction(language)}\n"
            f"Bir dəfə web_search_image: düyün «{node_text}» (mövzu: {topic_text}), "
            f"təxminən {RESEARCH_IMAGE_MAX} şəkil, 30-dan çox olmasın. "
            "İzah yazmayın, web_search və səhifə açmayın."
        )
    return (
        f"{output_language_instruction(language)}\n"
        f'Call web_search_image once for node "{node_text}" (topic: {topic_text}). '
        f"About {RESEARCH_IMAGE_MAX} images, never more than 30. "
        "Do not write a gloss, call web_search, open pages, or search again."
    )
