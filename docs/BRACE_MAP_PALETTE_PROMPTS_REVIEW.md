# Brace Map Palette Prompt Templates Review

**Location:** `agents/thinking_modes/node_palette/brace_map_palette.py`

## Current Prompt Templates

### Stage 1: Dimensions Prompt (Lines 156-222)

**Chinese Version:**
```python
为主题"{center_topic}"生成{count}个可能的拆解维度。

教学背景：{context_desc}

括号图可以使用不同的维度来拆解整体。请思考这个整体可以用哪些维度进行拆解。

常见拆解维度类型（参考）：
- 物理部件（按实体组成）
- 功能模块（按功能划分）
- 时间阶段（按时间顺序）
- 空间区域（按空间位置）
- 类型分类（按种类划分）
- 属性特征（按特性划分）
- 层次结构（按层级划分）

要求：
1. 每个维度要简洁明了，2-6个字
2. 维度要互不重叠、各具特色
3. 每个维度都应该能有效地拆解这个整体
4. 只输出维度名称，每行一个，不要编号
```

**English Version:**
```python
Generate {count} possible decomposition dimensions for: {center_topic}

Educational Context: {context_desc}

A brace map can decompose a whole using DIFFERENT DIMENSIONS. Think about what dimensions could be used to break down this whole.

Common dimension types (reference):
- Physical Components (by physical parts)
- Functional Modules (by function)
- Time Stages (by temporal sequence)
- Spatial Regions (by location)
- Type Classification (by category)
- Attribute Features (by characteristics)
- Hierarchical Structure (by levels)

Requirements:
1. Each dimension should be concise, 2-6 words
2. Dimensions should be distinct and non-overlapping
3. Each dimension should be valid for decomposing this whole
4. Output only dimension names, one per line, no numbering
```

**Status:** ✅ Good - Clear, comprehensive dimension examples

---

### Stage 2: Parts Prompt (Lines 224-311)

**Chinese Version (with dimension):**
```python
为以下整体生成{count}个组成部分：{center_topic}

教学背景：{context_desc}
拆解维度：{dimension}

你能够绘制括号图，对整体进行拆解，展示整体与部分的关系。
思维方式：拆解、分解
1. 必须按照"{dimension}"这个维度进行拆解
2. 部分要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语
4. 每个部分要简洁明了

要求：每个部分要简洁明了，可以超过4个字，但不要太长，避免完整句子。只输出部分文本，每行一个，不要编号。

按照"{dimension}"维度生成{count}个组成部分：
```

**English Version (with dimension):**
```python
Generate {count} Brace Map parts/components for: {center_topic}

Educational Context: {context_desc}
Decomposition Dimension: {dimension}

You can draw a brace map to decompose the whole and show the relationship between whole and parts.
Thinking approach: Decomposition, Breaking down
1. MUST decompose using the "{dimension}" dimension
2. Parts should be clear, mutually exclusive, and collectively exhaustive (MECE principle)
3. Use nouns or noun phrases
4. Each part should be concise and clear

Requirements: Each part should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences. Output only the part text, one per line, no numbering.

Generate {count} parts using "{dimension}" dimension:
```

**Potential Issues:**
- ⚠️ **Missing dimension-specific examples** - Could provide examples based on dimension type
- ⚠️ **Vague "MECE principle"** - Could be more explicit about what makes parts distinct
- ⚠️ **No guidance on quantity** - Doesn't specify ideal number of parts (should be 3-6 for brace maps)
- ⚠️ **No examples** - Could include concrete examples based on dimension type

---

### Stage 3: Subparts Prompt (Lines 313-362)

**Chinese Version:**
```python
为整体"{center_topic}"的部分"{part_name}"生成{count}个子部件或组成成分

教学背景：{context_desc}

你能够绘制括号图，进一步分解"{part_name}"这个部分，展示它的更细致的组成。

要求：
1. 所有子部件必须属于"{part_name}"这个部分
2. 子部件要具体、清晰、有代表性
3. 使用名词或名词短语，2-8个字
4. 只输出子部件名称，每行一个，不要编号

为"{part_name}"生成{count}个子部件：
```

**English Version:**
```python
Generate {count} sub-components for part "{part_name}" of whole: {center_topic}

Educational Context: {context_desc}

You can draw a brace map to further decompose the part "{part_name}" and show its finer components.

Requirements:
1. All sub-components MUST belong to the part "{part_name}"
2. Sub-components should be specific, clear, and representative
3. Use nouns or noun phrases, 2-8 words
4. Output only sub-component names, one per line, no numbering

Generate {count} sub-components for "{part_name}":
```

**Potential Issues:**
- ⚠️ **Missing dimension context** - Subparts prompt doesn't mention the dimension, so LLM might forget the consistency requirement
- ⚠️ **No examples** - Could provide concrete examples based on part type
- ⚠️ **Vague "specific, clear, representative"** - Could be more explicit
- ⚠️ **Missing part-to-subpart relationship clarity** - Could emphasize logical decomposition

---

## Recommendations for Improvement

### 1. **Parts Prompt Improvements** (Most Critical)

**Issues to Address:**
- Add dimension-specific examples
- Clarify MECE principle with concrete examples
- Specify ideal quantity (3-6 parts)
- Provide examples based on dimension type

**Suggested Enhancement:**
```python
# Add dimension-specific guidance
if dimension:
    # Add examples based on dimension type
    dimension_examples = {
        "物理部件": "例如：发动机、底盘、变速箱（对于汽车）",
        "功能模块": "例如：动力系统、安全系统、舒适系统（对于汽车）",
        # ... more examples
    }
    prompt += f"\n\n拆解示例（基于{dimension}维度）："
    prompt += f"\n{dimension_examples.get(dimension, '请根据整体特点进行拆解')}"
```

### 2. **Subparts Prompt Improvements** (High Priority)

**Issues to Address:**
- Include dimension context to maintain consistency
- Add examples showing proper part-to-subpart relationship
- Clarify what "belongs to" means with examples

**Suggested Enhancement:**
```python
# Add dimension context
dimension = stage_data.get('dimension', '')
if dimension:
    prompt += f"\n\n重要提示：拆解维度为"{dimension}"，所有子部件必须符合此维度。"
    prompt += f"\n例如：如果部分"发动机"是按物理部件维度，子部件应该是：气缸、活塞、曲轴（具体的物理零件）"
    prompt += f"\n而不是功能性的：动力输出、能量转换等（这些属于功能模块维度）"
```

### 3. **Add Dimension Context to Subparts**

The subparts prompt currently doesn't receive dimension information, which could cause inconsistency.

**Current Issue:**
- Subparts prompt only gets `part_name` and `center_topic`
- Doesn't know the dimension being used
- Could generate subparts that don't match the dimension

**Fix Needed:**
- Pass dimension to `_build_subparts_prompt()`
- Include dimension in the prompt to maintain consistency

---

## File Locations

- **Main Prompt File:** `agents/thinking_modes/node_palette/brace_map_palette.py`
  - `_build_dimensions_prompt()` - Lines 156-222
  - `_build_parts_prompt()` - Lines 224-311
  - `_build_subparts_prompt()` - Lines 313-362

- **System Message:** Lines 364-378
  - Simple: "You are a helpful K12 education assistant."

---

## Specific Accuracy Issues to Address

### Parts Generation:
1. **Dimension Consistency**: Ensure all parts strictly follow the selected dimension
2. **MECE Clarity**: Make "mutually exclusive, collectively exhaustive" more concrete
3. **Examples**: Add dimension-specific examples
4. **Quantity Guidance**: Specify 3-6 parts ideal range

### Subparts Generation:
1. **Dimension Context**: Subparts prompt needs dimension to maintain consistency
2. **Logical Decomposition**: Emphasize part-to-subpart logical relationship
3. **Concreteness**: Ensure subparts are specific components, not abstract concepts
4. **Examples**: Show what good subparts look like

---

## Next Steps

1. Review the prompts above
2. Identify specific accuracy issues you're seeing
3. Propose improved prompt wording
4. Test improved prompts

**Would you like me to:**
- Enhance the prompts with the improvements above?
- Show you specific examples of what the improved prompts would look like?
- Focus on a particular aspect (parts vs subparts)?

