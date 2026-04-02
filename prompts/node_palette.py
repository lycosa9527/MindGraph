"""
Node Palette Prompts - Aligned with Auto-Complete (thinking_maps.py)

Centralized prompt templates for node palette incremental generation.
Content requirements (dimension types, MECE, conciseness) are aligned with
prompts/thinking_maps.py to ensure consistent content generation across
auto-complete (full JSON) and node palette (line-by-line) flows.

Two-stage generation remains flexible: each diagram type defines its own
stages (dimensions → parts → subparts, etc.).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional


# ---------------------------------------------------------------------------
# BRACE MAP - Aligned with BRACE_MAP_GENERATION
# ---------------------------------------------------------------------------

BRACE_DIMENSION_TYPES_ZH = """常见拆解维度类型（参考）：
- 物理部件（按实体组成）
- 功能模块（按功能划分）
- 时间阶段（按时间顺序）
- 空间区域（按空间位置）
- 类型分类（按种类划分）
- 属性特征（按特性划分）
- 层次结构（按层级划分）"""

BRACE_DIMENSION_TYPES_EN = """Common dimension types (reference):
- Physical Components (by physical parts)
- Functional Modules (by function)
- Time Stages (by temporal sequence)
- Spatial Regions (by location)
- Type Classification (by category)
- Attribute Features (by characteristics)
- Hierarchical Structure (by levels)"""


def get_brace_dimensions_prompt(center_topic: str, context_desc: str, language: str, count: int, batch_num: int) -> str:
    """Stage 1: Generate decomposition dimension options."""
    dim_types = BRACE_DIMENSION_TYPES_ZH if language == "zh" else BRACE_DIMENSION_TYPES_EN
    if language == "zh":
        prompt = f"""为主题"{center_topic}"生成{count}个可能的拆解维度。

教学背景：{context_desc}

括号图可以使用不同的维度来拆解整体。请思考这个整体可以用哪些维度进行拆解。

{dim_types}

要求：
1. 每个维度要简洁明了，2-6个字
2. 维度要互不重叠、各具特色
3. 每个维度都应该能有效地拆解这个整体
4. 只输出维度名称，每行一个，不要编号

生成{count}个拆解维度："""
    else:
        prompt = f"""Generate {count} possible decomposition dimensions for: {center_topic}

Educational Context: {context_desc}

A brace map can decompose a whole using DIFFERENT DIMENSIONS. Think about what dimensions could be used to break down this whole.

{dim_types}

Requirements:
1. Each dimension should be concise, 2-6 words
2. Dimensions should be distinct and non-overlapping
3. Each dimension should be valid for decomposing this whole
4. Output only dimension names, one per line, no numbering

Generate {count} dimensions:"""

    if batch_num > 1:
        prompt += (
            "\n\n注意：这是第{batch_num}批。确保提供不同角度的维度，避免重复。"
            if language == "zh"
            else f"\n\nNote: Batch {batch_num}. Provide different perspectives, avoid repetition."
        )
    return prompt


def get_brace_parts_prompt(
    center_topic: str, dimension: str, context_desc: str, language: str, count: int, batch_num: int
) -> str:
    """Stage 2: Generate parts using selected dimension."""
    if language == "zh":
        if dimension:
            prompt = f"""需要从"{dimension}"这个视角来拆解整体"{center_topic}"。

教学背景：{context_desc}
用户选择的拆解视角：{dimension}

核心任务：从"{dimension}"这个视角，将"{center_topic}"拆解成{count}个组成部分。

核心要求：
1. 始终从"{dimension}"视角拆解"{center_topic}"
2. 部分要清晰、互不重叠、完全穷尽（MECE原则）
3. 生成3-6个部分（理想数量）
4. 使用名词或名词短语，2-8个字
5. 只输出部分名称，每行一个，不要编号，不要解释

从"{dimension}"视角拆解"{center_topic}"，生成{count}个组成部分："""
        else:
            prompt = f"""为以下整体生成{count}个组成部分：{center_topic}

教学背景：{context_desc}

你能够绘制括号图，对整体进行拆解，展示整体与部分的关系。
思维方式：拆解、分解
1. 从同一个拆解维度进行拆解
2. 部分要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语
4. 每个部分要简洁明了

要求：每个部分要简洁明了，可以超过4个字，但不要太长，避免完整句子。只输出部分文本，每行一个，不要编号。

生成{count}个组成部分："""
    else:
        if dimension:
            prompt = f"""Decompose the whole "{center_topic}" from the "{dimension}" perspective.

Educational Context: {context_desc}
User-selected decomposition perspective: {dimension}

Core Task: From the "{dimension}" perspective, break down "{center_topic}" into {count} component parts.

Core Requirements:
1. ALWAYS decompose "{center_topic}" from the "{dimension}" perspective
2. Parts should be clear, mutually exclusive, and collectively exhaustive (MECE principle)
3. Generate 3-6 parts (ideal range)
4. Use nouns or noun phrases, 2-8 words
5. Output only part names, one per line, no numbering, no explanations

Decompose "{center_topic}" from the "{dimension}" perspective, generate {count} component parts:"""
        else:
            prompt = f"""Generate {count} component parts for the whole: {center_topic}

Educational Context: {context_desc}

You can draw a brace map to decompose a whole and show whole-part relationships.
Thinking approach: Decomposition, Breakdown
1. Decompose from the same dimension
2. Parts should be clear, mutually exclusive, and collectively exhaustive (MECE)
3. Use nouns or noun phrases
4. Each part should be concise

Requirements: Each part concise, 2-8 words allowed, avoid full sentences. Output only part names, one per line, no numbering.

Generate {count} component parts:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保提供不同角度的部分，避免重复。"
            if language == "zh"
            else f"\n\nNote: Batch {batch_num}. Provide different perspectives, avoid repetition."
        )
    return prompt


def get_brace_subparts_prompt(
    center_topic: str, part_name: str, dimension: str, context_desc: str, language: str, count: int, batch_num: int
) -> str:
    """Stage 3: Generate subparts for a selected part."""
    dim_effective = (dimension or "").strip()
    part_effective = (part_name or "").strip()
    if language == "zh":
        if dim_effective:
            prompt = f"""为以下部分生成{count}个子部分：{part_effective}

整体：{center_topic}
拆解维度：{dim_effective}
教学背景：{context_desc}

你能够绘制括号图，对部分进行细分。
思维方式：细化、分解
1. 子部分必须属于"{part_effective}"，且属于"{dim_effective}"的拆解视角
2. 子部分要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语，2-8个字
4. 只输出子部分名称，每行一个，不要编号

生成{count}个子部分："""
        else:
            prompt = f"""为以下部分生成{count}个子部分：{part_effective}

整体：{center_topic}
教学背景：{context_desc}

你能够绘制括号图，对部分进行细分。
思维方式：细化、分解
1. 子部分必须属于"{part_effective}"，从任一合理拆解视角细分
2. 子部分要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语，2-8个字
4. 只输出子部分名称，每行一个，不要编号

生成{count}个子部分："""
    else:
        if dim_effective:
            prompt = f"""Generate {count} subparts for: {part_effective}

Whole: {center_topic}
Decomposition dimension: {dim_effective}
Educational Context: {context_desc}

You can draw a brace map to break down parts into subparts.
Thinking approach: Refinement, Decomposition
1. Subparts must belong to "{part_effective}" and follow the "{dim_effective}" perspective
2. Subparts should be clear, mutually exclusive, and collectively exhaustive (MECE)
3. Use nouns or noun phrases, 2-8 words
4. Output only subpart names, one per line, no numbering

Generate {count} subparts:"""
        else:
            prompt = f"""Generate {count} subparts for: {part_effective}

Whole: {center_topic}
Educational Context: {context_desc}

You can draw a brace map to break down parts into subparts.
Thinking approach: Refinement, Decomposition
1. Subparts must belong to "{part_effective}" from any reasonable decomposition perspective
2. Subparts should be clear, mutually exclusive, and collectively exhaustive (MECE)
3. Use nouns or noun phrases, 2-8 words
4. Output only subpart names, one per line, no numbering

Generate {count} subparts:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保提供不同角度的子部分，避免重复。"
            if language == "zh"
            else f"\n\nNote: Batch {batch_num}. Provide different perspectives, avoid repetition."
        )
    return prompt


# ---------------------------------------------------------------------------
# TREE MAP - Aligned with TREE_MAP_GENERATION
# ---------------------------------------------------------------------------

TREE_DIMENSION_TYPES_ZH = """常见分类维度类型（参考）：
- 生物分类（科学性）
- 栖息地（环境性）
- 食性（营养性）
- 体型（物理性）
- 功能（功能性）
- 时间阶段（时间性）
- 地理区域（空间性）"""

TREE_DIMENSION_TYPES_EN = """Common dimension types (reference):
- Biological Taxonomy (Scientific)
- Habitat (Environmental)
- Diet (Nutritional)
- Size (Physical)
- Function (Functional)
- Time Stages (Temporal)
- Geographic Region (Spatial)"""


def get_tree_dimensions_prompt(center_topic: str, context_desc: str, language: str, count: int, batch_num: int) -> str:
    """Stage 1: Generate classification dimension options."""
    dim_types = TREE_DIMENSION_TYPES_ZH if language == "zh" else TREE_DIMENSION_TYPES_EN
    if language == "zh":
        prompt = f"""为主题"{center_topic}"生成{count}个可能的分类维度。

教学背景：{context_desc}

树状图可以使用不同的维度来分类主题。请思考这个主题可以用哪些维度进行分类。

{dim_types}

要求：
1. 每个维度要简洁明了，2-6个字
2. 维度要互不重叠、各具特色
3. 每个维度都应该能有效地分类这个主题
4. 只输出维度名称，每行一个，不要编号

生成{count}个分类维度："""
    else:
        prompt = f"""Generate {count} possible classification dimensions for topic: {center_topic}

Educational Context: {context_desc}

A tree map can classify a topic using DIFFERENT DIMENSIONS. Think about what dimensions could be used to classify this topic.

{dim_types}

Requirements:
1. Each dimension should be concise, 2-6 words
2. Dimensions should be distinct and non-overlapping
3. Each dimension should be valid for classifying this topic
4. Output only dimension names, one per line, no numbering

Generate {count} dimensions:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保提供不同角度的维度，避免重复。"
            if language == "zh"
            else f"\n\nNote: Batch {batch_num}. Provide different perspectives, avoid repetition."
        )
    return prompt


def get_tree_categories_prompt(
    center_topic: str, dimension: str, context_desc: str, language: str, count: int, batch_num: int
) -> str:
    """Stage 2: Generate categories using selected dimension."""
    if language == "zh":
        if dimension:
            prompt = f"""为主题"{center_topic}"生成{count}个分类类别，使用分类维度：{dimension}

教学背景：{context_desc}

要求：
1. 所有类别必须遵循"{dimension}"这个分类维度
2. 类别要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语，2-8个字
4. 只输出类别名称，每行一个，不要编号
5. 不要生成具体的子项目，只生成类别名称

生成{count}个类别："""
        else:
            prompt = f"""为主题"{center_topic}"生成{count}个树状图分类类别

教学背景：{context_desc}

要求：
1. 从同一个分类维度进行分类
2. 类别要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语，2-8个字
4. 只输出类别名称，每行一个，不要编号
5. 不要生成具体的子项目，只生成类别名称

生成{count}个类别："""
    else:
        if dimension:
            header = f"Generate {count} classification categories for: {center_topic}, using dimension: {dimension}"
            req1 = f'1. ALL categories MUST follow the "{dimension}" dimension'
        else:
            header = f"Generate {count} classification categories for: {center_topic}"
            req1 = "1. Classify using a consistent dimension"
        prompt = f"""{header}

Educational Context: {context_desc}

Requirements:
{req1}
2. Categories should be clear, mutually exclusive, and collectively exhaustive (MECE)
3. Use nouns or noun phrases, 2-8 words
4. Output only category names, one per line, no numbering
5. Do NOT generate sub-items, only category names

Generate {count} categories:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保提供不同角度的类别，避免重复。"
            if language == "zh"
            else f"\n\nNote: Batch {batch_num}. Provide different perspectives, avoid repetition."
        )
    return prompt


def get_tree_items_prompt(
    center_topic: str, category_name: str, dimension: str, context_desc: str, language: str, count: int, batch_num: int
) -> str:
    """Stage 3: Generate items for a selected category."""
    if language == "zh":
        prompt = f"""为类别"{category_name}"生成{count}个具体条目

主题：{center_topic}
分类维度：{dimension}
教学背景：{context_desc}

要求：
1. 所有条目必须属于"{category_name}"且遵循"{dimension}"维度
2. 条目要清晰、互不重叠
3. 使用名词或名词短语，2-8个字
4. 只输出条目名称，每行一个，不要编号

生成{count}个条目："""
    else:
        prompt = f"""Generate {count} items for category: {category_name}

Topic: {center_topic}
Classification dimension: {dimension}
Educational Context: {context_desc}

Requirements:
1. ALL items must belong to "{category_name}" and follow the "{dimension}" dimension
2. Items should be clear and non-overlapping
3. Use nouns or noun phrases, 2-8 words
4. Output only item names, one per line, no numbering

Generate {count} items:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保提供不同角度的条目，避免重复。"
            if language == "zh"
            else f"\n\nNote: Batch {batch_num}. Provide different perspectives, avoid repetition."
        )
    return prompt


# ---------------------------------------------------------------------------
# FLOW MAP - Aligned with FLOW_MAP_GENERATION
# ---------------------------------------------------------------------------

FLOW_DIMENSION_TYPES_ZH = """常见拆解维度类型（参考）：
- 时间阶段（按时间顺序）
- 功能模块（按功能划分）
- 层次结构（按层级划分）
- 空间位置（按位置划分）
- 角色视角（按参与者划分）
- 类型分类（按种类划分）"""

FLOW_DIMENSION_TYPES_EN = """Common dimension types (reference):
- Time phases (chronological order)
- Functional modules (by function)
- Hierarchical structure (by level)
- Spatial location (by position)
- Role perspective (by participant)
- Type classification (by category)"""


def get_flow_dimensions_prompt(center_topic: str, context_desc: str, language: str, count: int, batch_num: int) -> str:
    """Stage 1: Generate flow decomposition dimensions."""
    dim_types = FLOW_DIMENSION_TYPES_ZH if language == "zh" else FLOW_DIMENSION_TYPES_EN
    if language == "zh":
        prompt = f"""为主题"{center_topic}"生成{count}个可能的拆解维度。

教学背景：{context_desc}

流程图可以使用不同的维度来拆解流程。请思考这个流程可以用哪些维度进行拆解。

{dim_types}

要求：
1. 每个维度要简洁明了，2-6个字
2. 维度要互不重叠、各具特色
3. 每个维度都应该能有效地拆解这个流程
4. 只输出维度名称，每行一个，不要编号

生成{count}个拆解维度："""
    else:
        prompt = f"""Generate {count} possible decomposition dimensions for: {center_topic}

Educational Context: {context_desc}

Flow maps can use different dimensions to break down a process. Think about what dimensions can be used to decompose this flow.

{dim_types}

Requirements:
1. Each dimension should be concise, 2-6 words
2. Dimensions should be distinct and non-overlapping
3. Each dimension should effectively decompose this flow
4. Output only the dimension name, one per line, no numbering

Generate {count} decomposition dimensions:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保提供不同角度的维度，避免重复。"
            if language == "zh"
            else f"\n\nNote: Batch {batch_num}. Ensure different perspectives, avoid duplication."
        )
    return prompt


def get_flow_steps_prompt(center_topic: str, context_desc: str, language: str, count: int, batch_num: int) -> str:
    """Stage 1: Generate major steps (chronological)."""
    if language == "zh":
        prompt = f"""为流程"{center_topic}"生成{count}个按时间顺序排列的步骤

教学背景：{context_desc}

你能够绘制流程图，展示过程的各个步骤。
思维方式：顺序、流程
1. 步骤要按时间顺序排列（从早到晚，从开始到结束）
2. 每个步骤要简洁明了，不要使用完整句子
3. 使用动宾短语或名词短语描述步骤
4. 步骤之间要有逻辑关联

要求：每个步骤要简洁明了（1-6个词），不要标点符号，不要编号前缀。只输出步骤文本，每行一个。**请按照时间顺序从早到晚排列步骤**。

生成{count}个按顺序的步骤："""
    else:
        prompt = f"""Generate {count} chronologically ordered steps for: {center_topic}

Educational Context: {context_desc}

You can draw a flow map to show the steps of a process.
Thinking approach: Sequential, Procedural
1. Steps should be in chronological order (from beginning to end)
2. Each step should be concise and clear, avoid full sentences
3. Use action phrases or noun phrases to describe steps
4. Steps should be logically connected

Requirements: Each step concise (1-6 words), no punctuation, no numbering prefixes. Output only step text, one per line. **Arrange steps in chronological order from earliest to latest.**

Generate {count} ordered steps:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保提供不同角度的步骤，避免重复。"
            if language == "zh"
            else f"\n\nNote: Batch {batch_num}. Provide different perspectives, avoid repetition."
        )
    return prompt


def get_flow_substeps_prompt(
    center_topic: str, step_name: str, context_desc: str, language: str, count: int, batch_num: int
) -> str:
    """Stage 2: Generate substeps for a selected step."""
    if language == "zh":
        prompt = f"""为步骤"{step_name}"生成{count}个子步骤

流程：{center_topic}
教学背景：{context_desc}

你能够绘制流程图，展示过程的子步骤。
思维方式：细化、展开
1. 子步骤必须属于"{step_name}"，是具体执行动作
2. 每个子步骤要简洁明了（1-7个词），不要重复主要步骤
3. 使用动宾短语或名词短语
4. 只输出子步骤文本，每行一个，不要编号

生成{count}个子步骤："""
    else:
        prompt = f"""Generate {count} substeps for step: {step_name}

Flow: {center_topic}
Educational Context: {context_desc}

You can draw a flow map to show substeps of a process.
Thinking approach: Refinement, Expansion
1. Substeps must belong to "{step_name}", concrete actions
2. Each substep concise (1-7 words), avoid repeating the step text
3. Use action phrases or noun phrases
4. Output only substep text, one per line, no numbering

Generate {count} substeps:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保提供不同角度的子步骤，避免重复。"
            if language == "zh"
            else f"\n\nNote: Batch {batch_num}. Provide different perspectives, avoid repetition."
        )
    return prompt


# ---------------------------------------------------------------------------
# BRIDGE MAP - Aligned with BRIDGE_MAP_GENERATION
# ---------------------------------------------------------------------------

BRIDGE_RELATIONSHIP_TYPES_ZH = """常见类比关系参考：
- 首都到国家：巴黎 | 法国 | 首都关系
- 作者到作品：莎士比亚 | 哈姆雷特 | 创作关系
- 功能到对象：飞 | 鸟 | 功能关系
- 部分到整体：轮子 | 汽车 | 组成关系
- 工具到工作者：锤子 | 木匠 | 工具关系
- 因到果：雨 | 洪水 | 因果关系"""

BRIDGE_RELATIONSHIP_TYPES_EN = """Common analogy relationships reference:
- Capital to Country: Paris | France | Capital Relationship
- Author to Work: Shakespeare | Hamlet | Creation Relationship
- Function to Object: Fly | Bird | Function Relationship
- Part to Whole: Wheel | Car | Composition Relationship
- Tool to Worker: Hammer | Carpenter | Tool Relationship
- Cause to Effect: Rain | Flood | Causal Relationship"""


def get_bridge_pairs_prompt(
    center_topic: str, dimension: Optional[str], context_desc: str, language: str, count: int, batch_num: int
) -> str:
    """Generate analogy pairs (with or without fixed dimension)."""
    rel_types = BRIDGE_RELATIONSHIP_TYPES_ZH if language == "zh" else BRIDGE_RELATIONSHIP_TYPES_EN
    is_specific = dimension and dimension.strip()
    topic_hint = ""
    if center_topic and center_topic.strip():
        topic_hint = (
            f"（若用户指定了主题「{center_topic}」，可结合该主题思考）"
            if language == "zh"
            else f" (If user specified topic '{center_topic}', consider it)"
        )

    if language == "zh":
        if is_specific:
            focus = f"""
⚠️ 重要：用户在桥形图的"关系维度"字段中指定了「{dimension}」
- 所有{count}组类比必须遵循完全相同的关系维度
- 关系维度统一为：{dimension}
- 只改变左项和右项的具体内容，关系保持一致

例如，如果关系是「首都到国家」，所有类比都应该是：
巴黎 | 法国 | 首都关系
柏林 | 德国 | 首都关系
东京 | 日本 | 首都关系
（所有类比都是首都→国家，不要混入其他关系）
"""
            topic_text = f"{dimension}{topic_hint}"
        else:
            focus = """
💡 用户未指定关系维度（字段为空），请生成多样化的类比：
- 从多个不同的关系维度思考
- 每2-3组类比可以换一个新的关系维度
- 展示丰富的思维角度和关系类型

例如，可以包含多种关系：
巴黎 | 法国 | 首都关系
锤子 | 木匠 | 工具关系
雨 | 洪水 | 因果关系
轮子 | 汽车 | 组成关系
（混合多种不同的关系维度）
"""
            topic_text = f"多种关系的类比{topic_hint}"

        prompt = f"""为以下生成{count}组类比对：{topic_text}

教学背景：{context_desc}

你能够绘制桥形图，通过类比帮助理解抽象概念。
思维方式：类比、联想
1. 找出符合相同关系模式的事物对
2. 类比要清晰易懂，帮助学生理解
3. 使用简洁的名词或名词短语
4. 每组类比包含左项、右项和关系维度
{focus}

{rel_types}

输出格式：每行一组类比，用 | 分隔，格式如下：
左项 | 右项 | 关系维度

要求：每个项要简洁明了（2-8个字），关系维度要简洁（2-6个字），每行一对，用竖线分隔，不要编号。

生成{count}组类比："""
    else:
        if is_specific:
            focus = f"""
⚠️ IMPORTANT: User specified a relationship in the bridge map's "dimension" field: "{dimension}"
- ALL {count} analogies MUST follow the EXACT SAME relationship dimension
- Relationship dimension should be: {dimension}
- Only vary the left and right items, keep the relationship consistent

For example, if the relationship is "Capital to Country", all analogies should be:
Paris | France | Capital Relationship
Berlin | Germany | Capital Relationship
Tokyo | Japan | Capital Relationship
(All analogies are capital→country, don't mix other relationships)
"""
            topic_text = f"{dimension}{topic_hint}"
        else:
            focus = """
💡 User left the dimension field EMPTY, generate DIVERSE analogies:
- Think from multiple DIFFERENT relationship dimensions
- Switch to a new relationship dimension every 2-3 analogies
- Show rich perspectives and relationship types

For example, include multiple relationships:
Paris | France | Capital Relationship
Hammer | Carpenter | Tool Relationship
Rain | Flood | Causal Relationship
Wheel | Car | Component Relationship
(Mix multiple different relationship dimensions)
"""
            topic_text = f"various relationships{topic_hint}"

        prompt = f"""Generate {count} Bridge Map analogy pairs for: {topic_text}

Educational Context: {context_desc}

You can draw a bridge map to help understand abstract concepts through analogies.
Thinking approach: Analogy, Association
1. Find pairs of things that follow the same relationship pattern
2. Analogies should be clear and help students understand
3. Use concise nouns or noun phrases
4. Each analogy contains left item, right item, and relationship dimension
{focus}

{rel_types}

Output format: One analogy per line, separated by |, format:
left item | right item | relationship dimension

Requirements: Each item should be concise (2-8 words). Dimension concise (2-6 words).
One pair per line, separated by pipe character, no numbering.

Generate {count} analogies:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，从新的领域和角度寻找类比，避免与之前批次重复。"
            if language == "zh"
            else (
                f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity "
                "from new domains and angles, avoid any repetition from previous "
                "batches."
            )
        )
    return prompt


def get_bridge_dimensions_prompt(
    center_topic: str,
    context_desc: str,
    language: str,
    count: int,
    batch_num: int,
    existing_pairs: Optional[list] = None,
) -> str:
    """Stage 1: Generate relationship dimension options.

    When existing_pairs is provided (user has fixed item A and B), infer the
    relationship dimension that fits those pairs.
    When existing_pairs is empty, suggest diverse dimension options.
    """
    rel_types = BRIDGE_RELATIONSHIP_TYPES_ZH if language == "zh" else BRIDGE_RELATIONSHIP_TYPES_EN
    pairs = existing_pairs or []

    if pairs:
        pairs_text = "\n".join(f"- {p.get('left', '')} | {p.get('right', '')}" for p in pairs[:10])
        infer_count = min(count, 5)
        if language == "zh":
            prompt = f"""用户已在桥形图中填写了以下类比对（左项 | 右项）：
{pairs_text}

请根据这些已有的类比对，推断它们共同遵循的关系维度。找出左项与右项之间的规律（如：首都→国家、工具→使用者、部分→整体等）。

教学背景：{context_desc}

{rel_types}

要求：
1. 推断出最能概括上述类比对的关系维度
2. 维度要简洁明了，2-6个字
3. 可以给出1-5个可能的维度（若存在多种解读）
4. 只输出维度名称，每行一个，不要编号

生成{infer_count}个关系维度："""
        else:
            prompt = f"""User has filled in these analogy pairs (left | right) in the bridge map:
{pairs_text}

Infer the common relationship dimension that these pairs follow. Find the pattern between left and right items (e.g., capital→country, tool→user, part→whole).

Educational Context: {context_desc}

{rel_types}

Requirements:
1. Infer the relationship dimension that best describes these pairs
2. Dimension should be concise, 2-6 words
3. May give 1-5 possible dimensions if multiple interpretations exist
4. Output only dimension names, one per line, no numbering

Generate {infer_count} relationship dimensions:"""
    else:
        topic_hint = (
            f"（若用户指定了主题「{center_topic}」，可结合该主题思考）" if center_topic and center_topic.strip() else ""
        )
        if language == "zh":
            prompt = f"""为桥形图生成{count}个可能的类比关系维度。{topic_hint}

教学背景：{context_desc}

桥形图可以展示不同的类比关系。请思考可以用哪些关系维度来类比。

{rel_types}

要求：
1. 每个维度要简洁明了，2-6个字
2. 维度要互不重叠、各具特色
3. 只输出维度名称，每行一个，不要编号

生成{count}个关系维度："""
        else:
            topic_hint_en = (
                f" (If user specified topic '{center_topic}', consider it)"
                if center_topic and center_topic.strip()
                else ""
            )
            prompt = f"""Generate {count} possible analogy relationship dimensions for bridge map.{topic_hint_en}

Educational Context: {context_desc}

A bridge map can show different analogy relationships. Think about what relationship dimensions could be used.

{rel_types}

Requirements:
1. Each dimension should be concise, 2-6 words
2. Dimensions should be distinct and non-overlapping
3. Output only dimension names, one per line, no numbering

Generate {count} relationship dimensions:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保提供不同角度的维度，避免重复。"
            if language == "zh"
            else f"\n\nNote: Batch {batch_num}. Provide different perspectives, avoid repetition."
        )
    return prompt


# ---------------------------------------------------------------------------
# MIND MAP - Aligned with MIND_MAP_AGENT_GENERATION
# ---------------------------------------------------------------------------


def get_mindmap_branches_prompt(center_topic: str, context_desc: str, language: str, count: int, batch_num: int) -> str:
    """Stage 1: Generate main branch ideas."""
    if language == "zh":
        prompt = f"""为以下主题生成{count}个思维导图分支想法：{center_topic}

教学背景：{context_desc}

你能够绘制思维导图，进行发散思维和头脑风暴。
思维方式：发散、联想、创造
1. 从多个角度对中心主题进行联想
2. 分支要覆盖不同的维度和方面
3. 每个分支要简洁明了，使用名词或名词短语
4. 鼓励创造性和多样性思考

要求：每个分支想法要简洁明了（1-5个词），不要使用完整句子，不要编号。
只输出分支文本，每行一个。

生成{count}个分支想法："""
    else:
        prompt = f"""Generate {count} Mind Map branch ideas for: {center_topic}

Educational Context: {context_desc}

You can draw a mind map for divergent thinking and brainstorming.
Thinking approach: Divergent, Associative, Creative
1. Associate from multiple angles around the central topic
2. Branches should cover different dimensions and aspects
3. Each branch should be concise, using nouns or noun phrases
4. Encourage creative and diverse thinking

Requirements: Each branch idea should be concise (1-5 words), avoid full sentences, no numbering. Output only the branch text, one per line.

Generate {count} branch ideas:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性和创造性，\n从新的维度和角度思考，避免与之前批次重复。"
            if language == "zh"
            else (
                f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity "
                "and creativity from new dimensions and angles,\n"
                "avoid any repetition from previous batches."
            )
        )
    return prompt


def get_mindmap_children_prompt(
    center_topic: str, branch_name: str, context_desc: str, language: str, count: int, batch_num: int
) -> str:
    """Stage 2: Generate sub-branches for a selected branch."""
    if language == "zh":
        prompt = f"""为思维导图分支"{branch_name}"生成{count}个子分支想法：

主题：{center_topic}
上级分支：{branch_name}
教学背景：{context_desc}

你能够为思维导图分支生成子想法，进一步细化和展开这个分支。
思维方式：深入、细化、展开
1. 围绕"{branch_name}"这个分支进行更深入的思考
2. 子分支应该是该分支的具体展开或细节
3. 每个子分支要简洁明了，使用名词或名词短语
4. 保持与上级分支的逻辑关联性

要求：每个子分支想法要简洁明了（1-5个词），不要使用完整句子，不要编号。
只输出子分支文本，每行一个。

生成{count}个子分支想法："""
    else:
        prompt = f"""Generate {count} sub-branch ideas for mind map branch: {branch_name}

Topic: {center_topic}
Parent branch: {branch_name}
Educational Context: {context_desc}

You can generate sub-ideas for mind map branches to refine and expand.
Thinking approach: In-depth, Refinement, Expansion
1. Think more deeply around the branch "{branch_name}"
2. Sub-branches should be concrete expansions or details of this branch
3. Each sub-branch should be concise, using nouns or noun phrases
4. Maintain logical connection with the parent branch

Requirements: Each sub-branch idea should be concise (1-5 words), avoid full sentences, no numbering. Output only sub-branch text, one per line.

Generate {count} sub-branch ideas:"""

    if batch_num > 1:
        prompt += (
            f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性和创造性，避免与之前批次重复。"
            if language == "zh"
            else (
                f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity "
                "and creativity, avoid repetition from previous batches."
            )
        )
    return prompt
