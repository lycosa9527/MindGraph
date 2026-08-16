"""讲解语气 briefs for classroom lecture scripts.

课堂 / 讲故事 / 对话追问 / 苏格拉底 / 速讲 / 精读 / 举例丰富 / 考点提纲
must produce different spoken cadence, not a single classroom voice with a label.
"""

from __future__ import annotations

from typing import Any

TONE_IDS = frozenset(
    {
        "classroom",
        "story",
        "dialogue",
        "socratic",
        "fast",
        "close_read",
        "examples",
        "exam_outline",
    }
)

TONE_TABLE_HEADER_ZH = "━━━ 语气配置表 ━━━"
TONE_TABLE_HEADER_EN = "━━━ Tone table ━━━"

_LABELS = {
    "classroom": {"zh": "课堂", "en": "Classroom"},
    "story": {"zh": "讲故事", "en": "Storytelling"},
    "dialogue": {"zh": "对话追问", "en": "Dialogue"},
    "socratic": {"zh": "苏格拉底", "en": "Socratic"},
    "fast": {"zh": "速讲", "en": "Fast talk"},
    "close_read": {"zh": "精读", "en": "Close reading"},
    "examples": {"zh": "举例丰富", "en": "Rich examples"},
    "exam_outline": {"zh": "考点提纲", "en": "Exam outline"},
}

_SECTIONS_ZH: dict[str, tuple[str, tuple[str, ...]]] = {
    "classroom": (
        "课堂",
        (
            "风格：沉稳、清楚，像老师在课堂上带读导图。",
            "每支先给一句话定调（概括这一支的核心问题），再拆解子节点。",
            "句与句之间用“首先”“另外”“还有”衔接，节奏均匀。",
            "禁止提问、反问、卖关子。",
            "示例口吻：“我们先看右上角这一支，地理区位。它主要回答昌平在哪、怎么去、地形如何……”",
        ),
    ),
    "story": (
        "讲故事",
        (
            "风格：叙事感强，像在讲一个地方的故事。",
            "开场多用时间线或场景感句子，如“几百年前……”“如果你开车进昌平……”“这里曾经是……”。",
            "把信息点串成“画面”而不是“条目”，比如讲交通时不说"
            "“有高速和地铁”，而说“过去靠古道翻山，现在一脚油门走京藏就能到”。",
            "允许适当加入感官描写（山势、花海、城墙），但不要虚构历史事实。",
            "禁止用“第一、第二”或“包含以下”这类结构化用语。",
        ),
    ),
    "dialogue": (
        "对话追问",
        (
            "风格：亲切、口语化，像和一个刚认识的朋友边聊边看。",
            "可以穿插自然的“无声提问”并用导图信息回答，比如"
            "“你可能会好奇，为什么昌平有那么多陵墓？"
            "其实是因为明代皇室选定了这片风水宝地。”",
            "允许用“你看啊”“其实呢”“换句话说”这类口头衔接词。",
            "不要真的向用户抛出一个开放式问题（因为用户是初识，答不上来），而是“自问自答”式引导。",
            "禁止考试式提问（“知道是什么吗？”）。",
        ),
    ),
    "socratic": (
        "苏格拉底",
        (
            "风格：用“为什么”和“逻辑推理”串联知识点，而不是平铺。",
            "每支围绕一个核心追问展开，比如讲地理时问“山各半对昌平意味着什么？”，然后从位置、交通、区划中找答案回扣。",
            "下一支的开头可以用上一个问题的余波衔接，比如"
            "“刚才说山挡住了北边，那历史上这里自然就成了关口——正好接上人文历史。”",
            "每支结尾给一个小推论（“所以昌平的发展轨迹，其实是被这座山和这道关决定的”）。",
            "禁止只丢问题不解答；禁止评价“这个问题问得好”。",
        ),
    ),
    "fast": (
        "速讲",
        (
            "风格：极简、快节奏，像画重点。",
            "每支只讲 3～4 句，每句只给一个关键信息。",
            "不加修饰语、不举例子、不铺垫、不重复。",
            "子节点之间用顿号或短斜杠串联，不用完整长句。",
            "示例口吻：“右上：地理区位。北京西北，邻海淀顺义。山平各半，军都山居中。交通：京藏高速、昌平线。”",
        ),
    ),
    "close_read": (
        "精读",
        (
            "风格：慢、深、注重子节点之间的内在联系。",
            "每支不讲满所有子节点，而是挑 2～3 个关系密切的节点展开“关系分析”。",
            "例如讲“人文历史”时，把“历史沿革”和“文化遗产”串起来讲"
            "“军事要塞如何变成皇陵区”；讲“经济产业”时把“高新产业”和“产业园区”串起来。",
            "允许在一支内反复回扣同一子节点，进行交叉解读。",
            "每支结尾用一句话总结该支的“内在逻辑”（如“人文历史这一支的逻辑是：过去守关→后来葬皇→现在办教育”）。",
            "禁止平均用力（不要每个子节点都讲同样字数）。",
        ),
    ),
    "examples": (
        "举例丰富",
        (
            "风格：每一个抽象概念必须搭配一个具体、可感知的例子。",
            "“高新技术”要说出一个具体领域（如生物医药、芯片设计），"
            "“温泉度假”要说出一个具体地名或场景（如小汤山温泉），"
            "“高教园”要说出其中一所大学名字。",
            "允许适当补充导图上没有但普遍常识中的具体案例"
            "（如提到昌平草莓时可以说“每年三四月采摘季，很多人专程去兴寿镇”）。",
            "例子要简短，每支 2～4 个例子即可，不要变成堆砌。",
            "禁止只说概念不举例（如只说“有特色农业”而不说是什么）。",
        ),
    ),
    "exam_outline": (
        "考点提纲",
        (
            "风格：像考前复习提纲，结构化、关键词突出。",
            "每支用“核心词 + 要点”的方式组织，例如：“📍 经济产业 · 核心词：高新、农业、文旅”。",
            "对容易出填空或选择题的信息点，用“【记】”标注，如“地形：山平各半【记】”。",
            "子节点之间用“①②③”或“·”分条，但不要用完整叙述句，用短语即可。",
            "每支结尾给一个“可能考法”，如“可能问：昌平的主导产业有哪些？答：高新技术、新能源、生命健康。”",
            "禁止长篇叙述、禁止讲故事、禁止口语化过渡。",
        ),
    ),
}

_SECTIONS_EN: dict[str, tuple[str, tuple[str, ...]]] = {
    "classroom": (
        "Classroom",
        (
            "Style: steady and clear, like a teacher walking the class through the map.",
            "Each branch starts with one framing sentence (the core question of this "
            "branch), then unpacks the child nodes.",
            "Connect sentences with “first”, “also”, and “and”; keep an even rhythm.",
            "No questions, rhetorical questions, or cliffhangers.",
            "Sample: “Let’s look at the upper-right branch, geographic location. "
            "It mainly answers where this place is, how you get there, and what "
            "the terrain is like…”",
        ),
    ),
    "story": (
        "Storytelling",
        (
            "Style: narrative, like telling the story of a place.",
            "Open with a timeline or a scene: “centuries ago…”, “if you drive in…”, “this used to be…”.",
            "String facts into pictures, not lists. Traffic is not "
            "“there is a highway and a metro”, but “you used to cross the mountains "
            "on old roads; now one stretch of expressway gets you there.”",
            "Sensory detail (ridges, flower fields, walls) is fine; do not invent historical facts.",
            "No “first, second” or “includes the following”.",
        ),
    ),
    "dialogue": (
        "Dialogue",
        (
            "Style: warm and spoken, like chatting with a new friend while looking at the map.",
            "You may weave a silent question and answer it with map facts, e.g. "
            "“You might wonder why there are so many tombs here — the court chose "
            "this ground.”",
            "Spoken glue is fine: “look”, “actually”, “in other words”.",
            "Do not pose a real open question (a first-look listener cannot answer); use self-Q&A guidance.",
            "No exam questions (“do you know what this is?”).",
        ),
    ),
    "socratic": (
        "Socratic",
        (
            "Style: chain facts with “why” and reasoning, not a flat list.",
            "Each branch orbits one core question, then answers it from location, "
            "links, and child nodes on this branch.",
            "The next branch may pick up the leftover of the last question.",
            "End each branch with a small inference that ties the children together.",
            "Do not leave questions unanswered; do not praise “good question”.",
        ),
    ),
    "fast": (
        "Fast talk",
        (
            "Style: minimal and fast, like highlighting.",
            "Each branch is 3–4 sentences; one key fact per sentence.",
            "No modifiers, examples, setup, or repetition.",
            "Join child nodes with commas or slashes, not long sentences.",
            "Sample: “Upper right: geography. Northwest of the city, next to two "
            "neighbors. Half mountain, half plain. Transport: expressway, metro.”",
        ),
    ),
    "close_read": (
        "Close reading",
        (
            "Style: slow and deep; focus on links between child nodes.",
            "Do not cover every child. Pick 2–3 tightly related nodes and analyze the relationship.",
            "You may return to the same child inside a branch for cross-reading.",
            "End each branch with one sentence on its inner logic.",
            "Do not spend the same word count on every child.",
        ),
    ),
    "examples": (
        "Rich examples",
        (
            "Style: every abstract idea needs one concrete, perceptible example.",
            "Name a real field, place, or institution instead of a category alone.",
            "Short, well-known examples not printed on the map are allowed when they are common knowledge.",
            "2–4 examples per branch; do not pile them on.",
            "Do not leave a concept without an example.",
        ),
    ),
    "exam_outline": (
        "Exam outline",
        (
            "Style: a pre-exam outline; structured; keywords first.",
            "Organize each branch as “core words + points”, e.g. "
            "“📍 Economy · keywords: high-tech, farming, culture-tourism”.",
            "Mark fill-in or multiple-choice facts with [MEM].",
            "List children as ①②③ or · phrases, not full narrative sentences.",
            "End each branch with a likely exam ask and a short answer.",
            "No long narration, no story, no spoken transitions.",
        ),
    ),
}


def normalize_tone(raw: Any) -> str:
    """Return a valid tone id, defaulting to classroom."""
    value = str(raw or "").strip()
    return value if value in TONE_IDS else "classroom"


def tone_label(tone: str, language: str) -> str:
    """UI label for a 讲解语气 id."""
    lang = "zh" if str(language or "zh").startswith("zh") else "en"
    return _LABELS[normalize_tone(tone)][lang]


def _format_tone_table(header: str, title: str, bullets: tuple[str, ...]) -> str:
    """One selected row of the tone table, plus a stay-in-lane closer."""
    lines = [header, "", f"【{title}】"]
    lines.extend(f"- {item}" for item in bullets)
    if header == TONE_TABLE_HEADER_ZH:
        lines.append("- 只按本栏执行，不要混用其他语气。")
    else:
        lines.append("- Follow this row only; do not mix other tones.")
    return "\n".join(lines)


def tone_brief(tone: str, language: str) -> str:
    """Instruction block so the LLM speaks in the chosen lecture tone."""
    key = normalize_tone(tone)
    if str(language or "zh").startswith("zh"):
        title, bullets = _SECTIONS_ZH[key]
        return _format_tone_table(TONE_TABLE_HEADER_ZH, title, bullets)
    title, bullets = _SECTIONS_EN[key]
    return _format_tone_table(TONE_TABLE_HEADER_EN, title, bullets)
