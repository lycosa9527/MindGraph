# Main Agent Comprehensive Analysis

**Date:** 2024-12-19  
**Version:** 1.0  
**Status:** Analysis Complete - Awaiting Implementation Approval

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture](#current-architecture)
3. [Prompt System Analysis](#prompt-system-analysis)
4. [Four User Scenarios](#four-user-scenarios)
5. [ReAct Pattern Analysis](#react-pattern-analysis)
6. [LLM Call Count & Cost Analysis](#llm-call-count--cost-analysis)
7. [Implementation Recommendations](#implementation-recommendations)
8. [Code Locations Reference](#code-locations-reference)

---

## Executive Summary

### Current State

The main agent (`agents/main_agent.py`) is the entry point for diagram generation, handling:
- **Topic Extraction**: Extracting main topic/subject from user prompts
- **Diagram Type Classification**: Determining which of 9 diagram types (8 thinking maps + 1 mindmap) the user wants
- **Workflow Orchestration**: Coordinating between specialized agents
- **Concept Map Generation**: Special handling for concept maps

**Current Framework:** Prompt Engineering + Sequential LLM Calls (NOT ReAct)

**Key Findings:**
- ✅ Centralized prompt system covering all 9 diagram types
- ✅ Well-structured prompt templates with comprehensive examples
- ⚠️ Uses rule-based routing (if/else) instead of intent reasoning
- ⚠️ No ReAct pattern - decisions are parameter-driven, not reasoning-based
- ⚠️ Double bubble map prompts are hardcoded (not centralized)

### Proposed Improvements

1. **Implement Hybrid ReAct Pattern**
   - Combine REASON + Classification in single LLM call
   - Intent-based decision making
   - Better understanding of user intentions

2. **Workflow Enhancement**
   - After topic extraction and diagram selection → jump to canvas
   - Auto-complete triggers automatically
   - Seamless user experience

3. **Centralize All Prompts**
   - Move double bubble map prompts to centralized system
   - Consistent prompt management

---

## Current Architecture

### Framework Classification

**Pattern:** Prompt Engineering + Sequential LLM Calls  
**Decision Making:** Rule-based (if/else logic)  
**Intent Detection:** None (uses parameters)  
**Reasoning:** None (sequential steps)

### Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    MAIN AGENT WORKFLOW                      │
│           (Prompt Engineering + Sequential LLM Calls)        │
└─────────────────────────────────────────────────────────────┘

User Prompt
    │
    ├─→ [Step 1: Classification] (if not forced_diagram_type)
    │   └─→ LLM Call with Classification Prompt
    │       └─→ Returns: diagram_type
    │
    ├─→ [Step 2: Topic Extraction] (if not forced_diagram_type)
    │   └─→ LLM Call with Topic Extraction Prompt
    │       └─→ Returns: extracted_topic
    │       └─→ Return: {diagram_type, extracted_topic, use_default_template: True}
    │
    └─→ [Step 3: Generation] (if forced_diagram_type)
        └─→ Route to Specialized Agent
            └─→ LLM Call with Generation Prompt
                └─→ Returns: diagram_spec
```

### Key Characteristics

1. **Prompt Engineering**
   - Centralized prompts in `prompts/` directory
   - Each step has dedicated prompt template
   - Prompts guide LLM through examples and instructions

2. **Sequential LLM Calls**
   - Step-by-step: Classification → Extraction → Generation
   - Each step is separate LLM call
   - No reasoning loop or iterative refinement

3. **Rule-Based Routing**
   - Simple if/else based on `forced_diagram_type` parameter
   - No intent reasoning
   - Parameter-driven decisions

### Comparison: Main Agent vs Thinking Mode Agents

| Aspect | Main Agent (Current) | Thinking Mode Agents |
|--------|---------------------|---------------------|
| **Pattern** | Prompt Engineering | ReAct |
| **Decision Making** | Rule-based (if/else) | Intent-based |
| **Intent Detection** | ❌ None | ✅ LLM-based |
| **Reasoning** | ❌ Sequential steps | ✅ REASON step |
| **Adaptability** | ⚠️ Limited | ✅ High |

---

## Prompt System Analysis

### Prompt System Structure

```
prompts/
├── main_agent.py          # Classification + Topic Extraction
├── thinking_maps.py       # 8 Thinking Maps generation prompts
└── mind_maps.py           # 1 Mind Map generation prompt
```

### Classification Prompts

**Location:** `prompts/main_agent.py` lines 38-118

**Coverage:** All 9 diagram types
- ✅ circle_map (Circle Map)
- ✅ bubble_map (Bubble Map)
- ✅ double_bubble_map (Double Bubble Map)
- ✅ brace_map (Brace Map)
- ✅ bridge_map (Bridge Map)
- ✅ tree_map (Tree Map)
- ✅ flow_map (Flow Map)
- ✅ multi_flow_map (Multi-Flow Map)
- ✅ mind_map (Mind Map)

**Quality:** Excellent
- Comprehensive examples for each type
- Edge case handling (diagram type vs topic confusion)
- Returns "unclear" for ambiguous prompts (fallback to mind_map)

### Topic Extraction Prompts

**Location:** `prompts/main_agent.py` lines 120-172

**Quality:** Good
- Clear examples showing correct vs incorrect extraction
- Handles diagram type words in prompt
- Language-specific (EN/ZH)

**Issue:** Could be enhanced for Scenario 2 (when diagram type is already known)

### Generation Prompts

**Location:** `prompts/thinking_maps.py` and `prompts/mind_maps.py`

**Coverage:** All 9 diagrams have comprehensive generation prompts

**Quality Assessment:**

| Diagram Type | Prompt Quality | Special Features |
|-------------|---------------|------------------|
| Circle Map | ✅ Excellent | Handles quoted topics |
| Bubble Map | ✅ Excellent | Handles quoted topics |
| Double Bubble Map | ⚠️ Good | Uses hardcoded prompts (not centralized) |
| Tree Map | ✅ Excellent | Dimension concept, alternative dimensions, fixed dimension mode |
| Brace Map | ✅ Excellent | Dimension concept, alternative dimensions, fixed dimension mode |
| Flow Map | ✅ Excellent | Handles quoted topics, step/substep structure |
| Multi-Flow Map | ✅ Excellent | Simple structure |
| Bridge Map | ✅ Excellent | Multiple modes (identify, fixed, relationship-only), alternative dimensions |
| Mind Map | ✅ Excellent | Educational frameworks, MECE principle, even branches |

### Prompt Template Conflicts

**Issue:** Two sets of prompt templates

**Set 1: Hardcoded Prompts** (`agents/main_agent.py` lines 357-507)
- Topic extraction prompts (for double bubble maps - extract two topics)
- Characteristics generation prompts (for double bubble maps)
- Used by `create_topic_extraction_chain()` and `create_characteristics_chain()`

**Set 2: Centralized Prompts** (`prompts/main_agent.py`)
- General topic extraction (single topic)
- Classification prompts
- Used by main workflow

**Impact:**
- ⚠️ Naming confusion (both called "topic extraction" but different purposes)
- ⚠️ Maintenance burden (two systems to update)
- ⚠️ Inconsistency (double bubble prompts not centralized)

---

## Four User Scenarios

### Scenario 1: User Provides Prompt → System Picks Diagram

**User Input:** Natural language prompt
```
"生成关于光合作用的气泡图"
"create a mind map about machine learning"
```

**Current Flow:**
```
User Prompt
  → _detect_diagram_type_from_prompt()
    → Classification Prompt (centralized)
    → Returns: {diagram_type, clarity, has_topic}
  → Extract Topic
    → Topic Extraction Prompt (centralized)
    → Returns: extracted_topic
  → Return: {diagram_type, extracted_topic, use_default_template: True}
```

**Status:** ✅ Working Well
- Uses centralized classification prompt
- Handles all 9 diagram types
- Good edge case handling
- Returns clarity indicators for frontend

**LLM Calls:** 2 calls (Classification + Topic Extraction)

### Scenario 2: User Knows Diagram Type → System Fills Topic

**User Input:** Diagram type specified + minimal prompt (just topic)
```
diagram_type="bubble_map", prompt="光合作用"
diagram_type="tree_map", prompt="动物分类"
```

**Current Flow:**
```
User provides diagram_type + prompt
  → forced_diagram_type is set
  → Checks: if not forced_diagram_type (line 1774)
    → SKIPS topic extraction return
  → Goes directly to full generation (line 1805)
```

**Issue:** ⚠️ **Scenario 2 is currently treated the same as Scenario 3**

**Expected Behavior:**
- Extract topic from prompt
- Return `use_default_template: True`
- Frontend loads default template with extracted topic
- Auto-complete triggers automatically

**LLM Calls:** 1 call (Topic Extraction) - not currently implemented

### Scenario 3: User Provides Topic + Diagram + Instructions → System Builds Diagram

**User Input:** Diagram type + prompt with explicit instructions
```
diagram_type="bubble_map", prompt="光合作用，包含8个特征，重点描述能量转换"
diagram_type="tree_map", prompt="动物分类，按栖息地分类，包含4个主要类别"
```

**Current Flow:**
```
User provides diagram_type + prompt with instructions
  → forced_diagram_type is set
  → Full agent workflow
    → Specialized agent (e.g., BubbleMapAgent)
    → Generation prompt (centralized)
    → Generate complete spec
  → Return: {success, spec, diagram_type, ...}
```

**Status:** ✅ Working Well
- Uses specialized agents for each diagram type
- Handles learning sheet detection
- Supports dimension preferences
- Supports auto-complete modes

**LLM Calls:** 1 call (Generation)

### Scenario 4: No Diagram Type Selected → Default to Mindmap

**User Input:** Natural language prompt without specifying diagram type, or empty/unclear prompt
```
"光合作用"
"machine learning"
"help me organize my thoughts"
```

**Current Flow:**
```
User Prompt (no diagram type specified)
  → _detect_diagram_type_from_prompt()
    → Classification Prompt
    → If unclear/ambiguous → Returns: "unclear" or "mind_map"
  → Extract Topic
    → Topic Extraction Prompt
    → Returns: extracted_topic
  → Return: {diagram_type: "mind_map", extracted_topic, use_default_template: True}
```

**Status:** ✅ Partially Working
- Currently falls back to mind_map for unclear prompts
- Should explicitly default to mind_map when no diagram type is detected
- Should handle minimal prompts gracefully

**Expected Behavior:**
- If classification returns "unclear" or confidence is low → default to mind_map
- Extract topic from prompt
- Return mind_map with extracted topic
- Frontend loads mindmap template
- Auto-complete triggers automatically

**LLM Calls:** 2 calls (Classification + Topic Extraction) - same as Scenario 1, but with explicit mind_map default

**ReAct Intent:** `"default_to_mindmap"` or `"detect_and_extract"` with low confidence → default to mind_map

---

## ReAct Pattern Analysis

### Why ReAct?

**Current Limitations:**
- ⚠️ Rule-based decisions (if/else logic)
- ⚠️ Parameter-driven (relies on `forced_diagram_type`)
- ⚠️ No intent understanding
- ⚠️ Cannot adapt to nuanced requests

**ReAct Benefits:**
- ✅ Intent reasoning (understands user's actual intent)
- ✅ Flexible decision making (handles edge cases)
- ✅ Consistency with thinking mode agents
- ✅ Better user experience

### ReAct Pattern Structure

```
REASON Step: Understand user intent
    ↓
ACT Step: Execute action based on intent
    ↓
OBSERVE Step: Return appropriate response
```

### Proposed Hybrid ReAct Approach

**Combine REASON + Classification in Single LLM Call**

**Benefits:**
- No cost increase for Scenario 1 (most common)
- Enables Scenario 2 support
- Better intent understanding
- Minimal increase for Scenario 3

**Flow:**
```
1. REASON+CLASSIFY: Single LLM call
   → Analyze user prompt
   → Detect intent + diagram_type
   → If unclear/low confidence → Default to mind_map
   → Returns: {intent, diagram_type, confidence, reasoning}

2. ACT: Execute based on intent
   → If intent == "detect_and_extract": Extract topic
   → If intent == "extract_topic_only": Extract topic
   → If intent == "generate_full_spec": Generate spec
   → If intent == "default_to_mindmap": Extract topic, use mind_map

3. OBSERVE: Return response
   → Jump to canvas
   → Trigger auto-complete
```

---

## LLM Call Count & Cost Analysis

### Current Approach

| Scenario | LLM Calls | Breakdown |
|----------|-----------|-----------|
| Scenario 1 | **2 calls** | Classification + Topic Extraction |
| Scenario 2 | **1 call** | Topic Extraction (not implemented) |
| Scenario 3 | **1 call** | Generation |
| Scenario 4 | **2 calls** | Classification + Topic Extraction (defaults to mind_map) |

**Average:** ~1.5 calls per request

### Pure ReAct Approach

| Scenario | LLM Calls | Breakdown |
|----------|-----------|-----------|
| Scenario 1 | **3 calls** | REASON (intent) + Classification + Topic Extraction |
| Scenario 2 | **2 calls** | REASON (intent) + Topic Extraction |
| Scenario 3 | **2 calls** | REASON (intent) + Generation |

**Cost Impact:** +50-100% increase (+1 call per scenario)

### Hybrid ReAct Approach (Recommended)

| Scenario | Current | Hybrid ReAct | Increase |
|----------|---------|--------------|----------|
| Scenario 1 | 2 calls | **2 calls** | **0%** ✅ |
| Scenario 2 | N/A | **2 calls** | **New capability** ✅ |
| Scenario 3 | 1 call | **2 calls** | **+100%** ⚠️ |
| Scenario 4 | 2 calls | **2 calls** | **0%** ✅ (explicit mind_map default) |

**How It Works:**
- REASON+CLASSIFY: Combined in single LLM call
- ACT: 1 additional call based on intent
- Total: 2 calls for all scenarios

**Token Usage Estimate:**
- Current Scenario 1: ~400 tokens
- Hybrid ReAct Scenario 1: ~550 tokens (+37% increase)
- Pure ReAct Scenario 1: ~800 tokens (+100% increase)

---

## Logic Review & Improvements

### Critical Edge Cases to Handle

#### Edge Case 1: Empty or Very Short Prompts
**Example:** `""`, `"test"`, `"a"`
**Handling:**
- If prompt is empty → Return error
- If prompt is 1 word → Default to mind_map, use word as topic
- If prompt is 2-3 words → Use REASON+CLASSIFY, likely default to mind_map

#### Edge Case 2: Prompts with Only Diagram Type Mentioned
**Example:** `"bubble map"`, `"思维导图"`
**Handling:**
- Detect diagram type from prompt
- Extract topic from prompt (might be empty or use diagram type as topic)
- Return template with detected diagram type

#### Edge Case 3: Prompts with Multiple Diagram Types Mentioned
**Example:** `"create a bubble map about mind maps"`
**Handling:**
- First diagram type mentioned is the type to CREATE
- Second diagram type is the TOPIC content
- REASON+CLASSIFY should handle this correctly

#### Edge Case 4: Prompts with Quoted Topics
**Example:** `"create a bubble map about 'Photosynthesis'"`
**Handling:**
- Preserve exact quoted text as topic
- Don't modify or translate quoted content
- Pass to generation prompts as-is

#### Edge Case 5: Mixed Language Prompts
**Example:** `"生成一个bubble map关于photosynthesis"`
**Handling:**
- Detect primary language from prompt
- Use appropriate language prompts
- Handle mixed content gracefully

### Additional Considerations

#### Consideration 1: Topic Extraction Fallback
**Current:** If topic extraction fails, uses original prompt  
**Proposed:** Multi-level fallback:
1. Try LLM extraction
2. If fails → Try simple keyword extraction (remove action words)
3. If fails → Use original prompt as topic

#### Consideration 2: Confidence Threshold Tuning
**Current:** Fixed 0.6 threshold  
**Proposed:** Make threshold configurable and monitor:
- Track success rates by confidence level
- Adjust threshold based on real usage data
- Different thresholds for different diagram types

#### Consideration 3: Caching Strategy
**Proposed:** Cache REASON+CLASSIFY results for similar prompts:
- Hash prompt + diagram_type_provided
- Cache for 1 hour
- Reduces LLM calls for repeated requests

#### Consideration 4: Response Time Optimization
**Proposed:** Parallel execution where possible:
- REASON+CLASSIFY and topic extraction could potentially run in parallel
- But topic extraction depends on diagram_type, so sequential is better
- Consider pre-warming common diagram types

#### Consideration 5: Frontend Integration Points
**Critical:** Ensure frontend properly handles:
- `use_default_template: True` → Load template immediately
- `trigger_auto_complete: True` → Auto-trigger after template loads
- `extracted_topic` → Populate topic field in template
- `diagram_type` → Set correct diagram type in editor

---

### Key Improvements Identified

#### Improvement 1: Simplify Intent Types
**Current:** 4 intents (`detect_and_extract`, `extract_topic_only`, `generate_full_spec`, `default_to_mindmap`)  
**Issue:** `detect_and_extract` and `default_to_mindmap` have identical ACT flow - only difference is diagram_type  
**Proposed:** Merge into 3 intents:
- `extract_and_detect`: Extract topic + detect/assign diagram type (covers Scenario 1 & 4)
- `extract_topic_only`: Extract topic only (Scenario 2)
- `generate_full_spec`: Full generation (Scenario 3)

**Benefit:** Cleaner logic, less code duplication

#### Improvement 2: Optimize REASON+CLASSIFY Prompt
**Current:** Prompt tries to do both intent detection and classification  
**Issue:** Could be more specific about instruction keywords  
**Proposed:** Add explicit instruction keyword detection:
- Keywords for `generate_full_spec`: "包含", "include", "with", "按", "by", "分类", "分类", "步骤", "步骤"
- Keywords for `extract_topic_only`: Just topic words, no instructions
- Keywords for `extract_and_detect`: Natural language describing diagram type

**Benefit:** More accurate intent detection

#### Improvement 3: Early Exit Optimization
**Current:** Always calls REASON+CLASSIFY  
**Proposed:** Skip REASON+CLASSIFY if:
- `forced_diagram_type` is provided AND
- Prompt is very minimal (1-3 words, no instruction keywords) AND
- No explicit instructions detected

**Benefit:** Saves 1 LLM call for obvious Scenario 2 cases

#### Improvement 4: Better Confidence Handling
**Current:** Fixed threshold (0.6) for defaulting to mind_map  
**Proposed:** Adaptive thresholds:
- High confidence (>0.8): Use detected diagram type
- Medium confidence (0.6-0.8): Use detected type but mark as 'unclear'
- Low confidence (<0.6): Default to mind_map

**Benefit:** More nuanced handling of edge cases

#### Improvement 5: Consolidate Topic Extraction Logic
**Current:** Scenario 1 and 4 have duplicate code  
**Proposed:** Single function `_extract_topic_and_return_template()` used by both

**Benefit:** DRY principle, easier maintenance

#### Improvement 6: Enhanced Error Recovery
**Current:** Basic fallback heuristics  
**Proposed:** Multi-level fallback:
1. Try REASON+CLASSIFY
2. If fails → Try simple classification only
3. If fails → Use heuristics based on prompt length/keywords
4. If all fail → Default to mind_map with original prompt as topic

**Benefit:** More robust error handling

#### Improvement 7: Prompt Length Analysis
**Current:** No prompt length consideration  
**Proposed:** Add prompt length heuristics:
- Very short (1-2 words): Likely just topic → `extract_topic_only` or `extract_and_detect`
- Short (3-10 words): Could be topic or instructions → Use REASON+CLASSIFY
- Long (10+ words): Likely has instructions → Check for instruction keywords

**Benefit:** Better initial intent estimation

---

## Implementation Recommendations

### Priority 1: Implement Hybrid ReAct Pattern (Improved)

#### Step 1: Add REASON+CLASSIFY Prompt

**File:** `prompts/main_agent.py`

```python
REASON_CLASSIFY_EN = """Analyze the user's prompt to determine their intent AND detect the diagram type.

User prompt: "{user_prompt}"
Diagram type provided: {diagram_type_provided}
Prompt length: {prompt_length} words

=== INTENT DETECTION ===

Detect user intent based on these criteria:

1. "extract_and_detect" (Scenario 1 & 4):
   - User provides natural language describing what they want
   - Prompt mentions diagram type OR describes content
   - Examples: "create a bubble map about photosynthesis", "mind map for machine learning", "光合作用"
   - If diagram type cannot be determined → use "mind_map" as default

2. "extract_topic_only" (Scenario 2):
   - Diagram type is already provided (diagram_type_provided is NOT "None")
   - Prompt is minimal (1-4 words, just topic)
   - NO instruction keywords present (see list below)
   - Examples: "photosynthesis" (with diagram_type="bubble_map"), "动物分类" (with diagram_type="tree_map")

3. "generate_full_spec" (Scenario 3):
   - Diagram type is already provided (diagram_type_provided is NOT "None")
   - Prompt contains INSTRUCTION KEYWORDS:
     * English: "include", "with", "by", "contain", "steps", "categories", "features", "dimensions"
     * Chinese: "包含", "按", "分类", "步骤", "特征", "维度", "类别"
   - Examples: "photosynthesis with 8 features", "动物分类，按栖息地分类，包含4个主要类别"

=== DIAGRAM TYPE DETECTION ===

If diagram_type_provided is "None":
- Detect from prompt using these indicators:
  * "bubble map", "bubble_map", "气泡图" → bubble_map
  * "mind map", "mind_map", "思维导图" → mind_map
  * "tree map", "tree_map", "树形图" → tree_map
  * "flow map", "flow_map", "流程图" → flow_map
  * "circle map", "circle_map", "圆圈图" → circle_map
  * "double bubble", "双气泡图" → double_bubble_map
  * "brace map", "括号图" → brace_map
  * "bridge map", "桥形图" → bridge_map
  * "multi-flow", "复流程图" → multi_flow_map
- If no diagram type detected → default to "mind_map"
- If confidence < 0.6 → default to "mind_map"

If diagram_type_provided is set:
- Use the provided diagram type
- Still analyze intent to determine if user wants topic extraction or full generation

=== CONFIDENCE SCORING ===

- High confidence (0.8-1.0): Clear intent and diagram type
- Medium confidence (0.6-0.8): Reasonable detection but some ambiguity
- Low confidence (<0.6): Unclear → default to mind_map

Return JSON:
{
  "intent": "extract_and_detect" | "extract_topic_only" | "generate_full_spec",
  "diagram_type": "bubble_map" | "tree_map" | ... | "mind_map",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation of decision"
}

Valid diagram types:
circle_map, bubble_map, double_bubble_map, brace_map, bridge_map, 
tree_map, flow_map, multi_flow_map, mind_map

IMPORTANT RULES:
- If uncertain about diagram type → default to "mind_map"
- If prompt is just a topic word/phrase → intent is "extract_and_detect", diagram_type is "mind_map"
- If instruction keywords present → intent is "generate_full_spec"
- If no instruction keywords and diagram_type provided → intent is "extract_topic_only"

Return only valid JSON, no other text."""

REASON_CLASSIFY_ZH = """分析用户的提示以确定意图并检测图表类型。

用户提示："{user_prompt}"
是否提供图表类型：{diagram_type_provided}
提示长度：{prompt_length} 个词

=== 意图检测 ===

根据以下标准检测用户意图：

1. "extract_and_detect"（场景1和4）：
   - 用户提供描述需求的自然语言
   - 提示提到图表类型或描述内容
   - 示例："创建一个关于光合作用的气泡图"、"机器学习的思维导图"、"光合作用"
   - 如果无法确定图表类型 → 默认使用"mind_map"

2. "extract_topic_only"（场景2）：
   - 图表类型已提供（diagram_type_provided不是"None"）
   - 提示最小（1-4个词，仅主题）
   - 没有指令关键词（见下方列表）
   - 示例："光合作用"（diagram_type="bubble_map"时）、"动物分类"（diagram_type="tree_map"时）

3. "generate_full_spec"（场景3）：
   - 图表类型已提供（diagram_type_provided不是"None"）
   - 提示包含指令关键词：
     * 中文：包含、按、分类、步骤、特征、维度、类别、包含、包含
     * 英文：include, with, by, contain, steps, categories, features, dimensions
   - 示例："光合作用，包含8个特征"、"动物分类，按栖息地分类，包含4个主要类别"

=== 图表类型检测 ===

如果diagram_type_provided为"None"：
- 从提示中检测，使用以下指标：
  * "气泡图"、"bubble map" → bubble_map
  * "思维导图"、"mind map" → mind_map
  * "树形图"、"tree map" → tree_map
  * "流程图"、"flow map" → flow_map
  * "圆圈图"、"circle map" → circle_map
  * "双气泡图"、"double bubble" → double_bubble_map
  * "括号图"、"brace map" → brace_map
  * "桥形图"、"bridge map" → bridge_map
  * "复流程图"、"multi-flow" → multi_flow_map
- 如果未检测到图表类型 → 默认使用"mind_map"
- 如果置信度 < 0.6 → 默认使用"mind_map"

如果diagram_type_provided已设置：
- 使用提供的图表类型
- 仍分析意图以确定用户想要主题提取还是完整生成

=== 置信度评分 ===

- 高置信度（0.8-1.0）：意图和图表类型明确
- 中等置信度（0.6-0.8）：合理检测但存在一些模糊性
- 低置信度（<0.6）：不明确 → 默认使用mind_map

返回JSON：
{{
  "intent": "extract_and_detect" | "extract_topic_only" | "generate_full_spec",
  "diagram_type": "bubble_map" | "tree_map" | ... | "mind_map",
  "confidence": 0.0-1.0,
  "reasoning": "决策的简要说明"
}}

有效图表类型：
circle_map, bubble_map, double_bubble_map, brace_map, bridge_map,
tree_map, flow_map, multi_flow_map, mind_map

重要规则：
- 如果不确定图表类型 → 默认使用"mind_map"
- 如果提示只是主题词/短语 → 意图是"extract_and_detect"，图表类型是"mind_map"
- 如果存在指令关键词 → 意图是"generate_full_spec"
- 如果没有指令关键词且提供了图表类型 → 意图是"extract_topic_only"

只返回有效JSON，不要其他文字。"""
```

#### Step 2: Implement _reason_and_classify() Function

**File:** `agents/main_agent.py`

```python
async def _reason_and_classify(
    user_prompt: str,
    language: str,
    forced_diagram_type: Optional[str] = None,
    model: str = 'qwen',
    user_id=None,
    organization_id=None,
    request_type='diagram_generation',
    endpoint_path=None
) -> dict:
    """
    ReAct Step 1: REASON + CLASSIFY (Combined)
    
    Analyze user intent AND detect diagram type in single LLM call.
    
    Returns:
        dict: {
            'intent': 'detect_and_extract' | 'extract_topic_only' | 'generate_full_spec',
            'diagram_type': str,
            'confidence': float,
            'reasoning': str,
            'clarity': str,
            'has_topic': bool
        }
    """
    from services.llm_service import llm_service
    from prompts import get_prompt
    import json
    
    # Early exit optimization: Skip REASON+CLASSIFY for obvious Scenario 2 cases
    if forced_diagram_type:
        prompt_words = user_prompt.strip().split()
        prompt_length = len(prompt_words)
        
        # Check for instruction keywords
        instruction_keywords = {
            'zh': ['包含', '按', '分类', '步骤', '特征', '维度', '类别'],
            'en': ['include', 'with', 'by', 'contain', 'steps', 'categories', 'features', 'dimensions']
        }
        keywords = instruction_keywords.get(language, instruction_keywords['en'])
        has_instructions = any(keyword in user_prompt.lower() for keyword in keywords)
        
        # If minimal prompt (1-4 words) with no instructions → likely Scenario 2
        if prompt_length <= 4 and not has_instructions:
            logger.info(f"Early exit: Minimal prompt with diagram_type → Scenario 2 (extract_topic_only)")
            return {
                'intent': 'extract_topic_only',
                'diagram_type': forced_diagram_type,
                'confidence': 0.9,
                'reasoning': 'Early exit: minimal prompt with diagram type, no instructions',
                'clarity': 'clear',
                'has_topic': True
            }
    
    # Get REASON+CLASSIFY prompt
    prompt_words = user_prompt.strip().split()
    prompt_length = len(prompt_words)
    
    reason_classify_prompt = get_prompt("reason_classify", language, "generation")
    reason_classify_prompt = reason_classify_prompt.format(
        user_prompt=user_prompt,
        diagram_type_provided=forced_diagram_type or "None",
        prompt_length=prompt_length
    )
    
    try:
        response = await llm_service.chat(
            prompt=reason_classify_prompt,
            model=model,
            max_tokens=300,
            temperature=0.3,
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path=endpoint_path
        )
        
        # Parse JSON response
        response = response.strip()
        if '```json' in response:
            response = response.split('```json')[1].split('```')[0].strip()
        elif '```' in response:
            response = response.split('```')[1].split('```')[0].strip()
        
        result = json.loads(response)
        
        # Validate diagram type
        valid_types = {
            'circle_map', 'bubble_map', 'double_bubble_map', 
            'brace_map', 'bridge_map', 'tree_map', 
            'flow_map', 'multi_flow_map', 'mind_map'
        }
        
        diagram_type = result.get('diagram_type', 'mind_map').lower()
        confidence = result.get('confidence', 0.5)
        
        # Default to mind_map if invalid type or low confidence
        if diagram_type not in valid_types:
            diagram_type = 'mind_map'
            result['intent'] = 'extract_and_detect'  # Simplified intent
            result['clarity'] = 'very_unclear'
            result['has_topic'] = False
            result['confidence'] = 0.5
        elif confidence < 0.6:
            # Low confidence → default to mind_map
            if not forced_diagram_type:  # Only override if not forced
                diagram_type = 'mind_map'
            result['intent'] = 'extract_and_detect'  # Simplified intent
            result['clarity'] = 'unclear'
            result['has_topic'] = True
        else:
            # Normalize intent: merge detect_and_extract and default_to_mindmap
            if result.get('intent') in ['detect_and_extract', 'default_to_mindmap']:
                result['intent'] = 'extract_and_detect'
            result['clarity'] = 'clear' if confidence > 0.8 else 'unclear'
            result['has_topic'] = True
        
        result['diagram_type'] = diagram_type
        
        logger.info(f"REASON+CLASSIFY → Intent: {result.get('intent')}, Diagram: {diagram_type}, Confidence: {result.get('confidence')}")
        return result
        
    except Exception as e:
        logger.error(f"REASON+CLASSIFY failed: {e}")
        # Fallback: use heuristics
        if forced_diagram_type:
            has_instructions = any(word in user_prompt.lower() for word in ['包含', 'include', 'with', '按', 'by'])
            return {
                'intent': 'generate_full_spec' if has_instructions else 'extract_topic_only',
                'diagram_type': forced_diagram_type,
                'confidence': 0.7,
                'reasoning': 'Fallback heuristic',
                'clarity': 'clear',
                'has_topic': True
            }
        else:
            # Multi-level fallback
            # Level 1: Try simple classification
            try:
                from prompts import get_prompt
                simple_classify_prompt = get_prompt("classification", language, "generation")
                simple_classify_prompt = simple_classify_prompt.format(user_prompt=user_prompt)
                simple_response = await llm_service.chat(
                    prompt=simple_classify_prompt,
                    model=model,
                    max_tokens=50,
                    temperature=0.3,
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path
                )
                detected_type = simple_response.strip().lower()
                valid_types = {'circle_map', 'bubble_map', 'double_bubble_map', 'brace_map', 
                              'bridge_map', 'tree_map', 'flow_map', 'multi_flow_map', 'mind_map'}
                if detected_type in valid_types:
                    return {
                        'intent': 'extract_and_detect',
                        'diagram_type': detected_type,
                        'confidence': 0.7,
                        'reasoning': 'Fallback: simple classification succeeded',
                        'clarity': 'unclear',
                        'has_topic': True
                    }
            except Exception as e2:
                logger.debug(f"Simple classification fallback also failed: {e2}")
            
            # Level 2: Use heuristics
            prompt_words = user_prompt.strip().split()
            if len(prompt_words) <= 3:
                # Very short → likely just topic
                return {
                    'intent': 'extract_and_detect',
                    'diagram_type': 'mind_map',
                    'confidence': 0.6,
                    'reasoning': 'Fallback: short prompt heuristic',
                    'clarity': 'unclear',
                    'has_topic': True
                }
            else:
                # Use original prompt as topic, default to mind_map
                return {
                    'intent': 'extract_and_detect',
                    'diagram_type': 'mind_map',
                    'confidence': 0.5,
                    'reasoning': 'Fallback: all methods failed, using mind_map default',
                    'clarity': 'very_unclear',
                    'has_topic': False
                }
```

#### Step 3: Refactor Workflow to Use ReAct

**File:** `agents/main_agent.py`

```python
async def agent_graph_workflow_with_styles(
    user_prompt,
    language='zh',
    forced_diagram_type=None,
    dimension_preference=None,
    model='qwen',
    ...
):
    """
    ReAct-based workflow: REASON → ACT → OBSERVE
    """
    logger.info("Starting ReAct-based graph workflow")
    
    try:
        validate_inputs(user_prompt, language)
        
        # REACT STEP 1: REASON + CLASSIFY (Combined)
        reasoning_result = await _reason_and_classify(
            user_prompt,
            language,
            forced_diagram_type,
            model,
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path=endpoint_path
        )
        
        intent = reasoning_result.get('intent', 'detect_and_extract')
        diagram_type = reasoning_result.get('diagram_type', 'mind_map')
        clarity = reasoning_result.get('clarity', 'clear')
        
        logger.info(f"REASON → Intent: {intent}, Diagram: {diagram_type}, Clarity: {clarity}")
        
        # Handle unclear prompts
        if clarity == 'very_unclear' and not reasoning_result.get('has_topic'):
            return {
                'success': False,
                'error_type': 'prompt_too_complex',
                'error': 'Unable to understand the request',
                'diagram_type': 'mind_map',
                'show_guidance': True
            }
        
        # REACT STEP 2: ACT - Execute based on intent
        from services.llm_service import llm_service
        
        # Helper function to extract topic and return template (used by Scenario 1, 2, 4)
        async def _extract_topic_and_return_template(diagram_type: str, intent_description: str):
            """Extract topic and return template response - used by extract_and_detect and extract_topic_only"""
            topic_extraction_prompt = get_prompt("topic_extraction", language, "generation")
            topic_extraction_prompt = topic_extraction_prompt.format(user_prompt=user_prompt)
            
            main_topic = await llm_service.chat(
                prompt=topic_extraction_prompt,
                model=model,
                max_tokens=50,
                temperature=0.1,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )
            main_topic = main_topic.strip().strip('"\'')
            
            logger.info(f"ACT → {intent_description}, extracted topic: '{main_topic}', diagram: {diagram_type}")
            
            # REACT STEP 3: OBSERVE - Return response, jump to canvas, trigger auto-complete
            return {
                'success': True,
                'diagram_type': diagram_type,
                'extracted_topic': main_topic,
                'language': language,
                'use_default_template': True,  # Signal frontend to load template
                'trigger_auto_complete': True  # Signal frontend to trigger auto-complete
            }
        
        if intent == 'extract_and_detect':
            # Scenario 1 & 4: Extract topic (diagram type detected or defaulted to mind_map)
            # Ensure mind_map default if confidence was low
            if clarity == 'unclear' and confidence < 0.6:
                diagram_type = 'mind_map'
            return await _extract_topic_and_return_template(
                diagram_type, 
                f"Scenario 1/4: Extract and detect (diagram: {diagram_type})"
            )
        
        elif intent == 'extract_topic_only':
            # Scenario 2: Extract topic only (diagram type already known)
            return await _extract_topic_and_return_template(
                diagram_type,
                f"Scenario 2: Extract topic only (diagram: {diagram_type})"
            )
        
        elif intent == 'generate_full_spec':
            # Scenario 3: Full generation with instructions
            is_learning_sheet = _detect_learning_sheet_from_prompt(user_prompt, language)
            generation_prompt = _clean_prompt_for_learning_sheet(user_prompt) if is_learning_sheet else user_prompt
            
            spec = await _generate_spec_with_agent(
                generation_prompt,
                diagram_type,
                language,
                dimension_preference,
                model,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type_for_tracking=diagram_type,
                existing_analogies=existing_analogies,
                fixed_dimension=fixed_dimension
            )
            
            if not spec or (isinstance(spec, dict) and spec.get('error')):
                return {
                    'success': False,
                    'spec': spec or create_error_response('Failed to generate specification', 'generation'),
                    'diagram_type': diagram_type,
                    ...
                }
            
            hidden_percentage = 0.2 if is_learning_sheet else 0
            
            # REACT STEP 3: OBSERVE - Return complete spec
            return {
                'success': True,
                'spec': spec,
                'diagram_type': diagram_type,
                'language': language,
                'is_learning_sheet': is_learning_sheet,
                'hidden_node_percentage': hidden_percentage
            }
        
    except Exception as e:
        logger.error(f"ReAct workflow failed: {e}")
        return {
            'success': False,
            'spec': create_error_response(f'Generation failed: {str(e)}', 'workflow'),
            'diagram_type': 'bubble_map',
            ...
        }
```

### Priority 2: Centralize Double Bubble Map Prompts

**File:** `prompts/main_agent.py`

```python
# Add new prompts
DOUBLE_BUBBLE_TOPIC_EXTRACTION_EN = """..."""
DOUBLE_BUBBLE_TOPIC_EXTRACTION_ZH = """..."""
CHARACTERISTICS_GENERATION_EN = """..."""
CHARACTERISTICS_GENERATION_ZH = """..."""

# Register in MAIN_AGENT_PROMPTS
MAIN_AGENT_PROMPTS = {
    ...
    "double_bubble_topic_extraction_generation_en": DOUBLE_BUBBLE_TOPIC_EXTRACTION_EN,
    "double_bubble_topic_extraction_generation_zh": DOUBLE_BUBBLE_TOPIC_EXTRACTION_ZH,
    "characteristics_generation_en": CHARACTERISTICS_GENERATION_EN,
    "characteristics_generation_zh": CHARACTERISTICS_GENERATION_ZH,
    "reason_classify_generation_en": REASON_CLASSIFY_EN,
    "reason_classify_generation_zh": REASON_CLASSIFY_ZH,
}
```

### Priority 3: Frontend Integration

**Ensure frontend handles:**
- `use_default_template: True` → Load default template with extracted topic
- `trigger_auto_complete: True` → Automatically trigger auto-complete
- Jump to canvas immediately after receiving response

---

## Code Locations Reference

### Prompt Definitions

- **Hardcoded Topic Extraction**: `agents/main_agent.py` lines 357-399
- **Hardcoded Characteristics**: `agents/main_agent.py` lines 402-507
- **Centralized Prompts**: `prompts/main_agent.py` lines 38-173
- **Prompt Registry**: `prompts/__init__.py` lines 17-23

### Function Locations

- `extract_central_topic_llm()`: `agents/main_agent.py` lines 85-109
- `extract_double_bubble_topics_llm()`: `agents/main_agent.py` lines 111-163
- `create_topic_extraction_chain()`: `agents/main_agent.py` lines 514-528
- `create_characteristics_chain()`: `agents/main_agent.py` lines 531-545
- `_detect_diagram_type_from_prompt()`: `agents/main_agent.py` lines 722-818
- `agent_graph_workflow_with_styles()`: `agents/main_agent.py` lines 1696-1883

### Usage Locations

- **Double Bubble Map**: `agents/core/agent_utils.py` lines 374-406
- **Main Workflow**: `routers/api.py` line 199
- **Frontend Auto-Complete**: `static/js/managers/toolbar/llm-autocomplete-manager.js`

---

## Summary

### Current State
- ✅ Well-architected prompt system
- ✅ Comprehensive coverage of all 9 diagram types
- ⚠️ Rule-based routing (not ReAct)
- ⚠️ Double bubble prompts not centralized

### Proposed State
- ✅ Hybrid ReAct pattern (REASON+CLASSIFY combined)
- ✅ Intent-based decision making
- ✅ All prompts centralized
- ✅ Seamless canvas + auto-complete flow

### Implementation Impact
- **LLM Calls**: No increase for Scenario 1, +1 for Scenario 3
- **Cost**: ~37% increase for Scenario 1, acceptable trade-off
- **User Experience**: Better intent understanding, seamless flow
- **Maintainability**: Consistent architecture, centralized prompts

---

---

## Logic Improvements Summary

### Key Optimizations

1. **Simplified Intent Types**: 3 intents instead of 4 (merged `detect_and_extract` and `default_to_mindmap`)
2. **Early Exit Optimization**: Skip REASON+CLASSIFY for obvious Scenario 2 cases (saves 1 LLM call)
3. **Enhanced Prompt**: More specific instruction keyword detection
4. **Consolidated Code**: Single `_extract_topic_and_return_template()` function for Scenarios 1, 2, 4
5. **Multi-Level Fallback**: Better error recovery with 3 fallback levels
6. **Adaptive Confidence**: More nuanced handling based on confidence thresholds
7. **Prompt Length Analysis**: Added prompt length consideration for better intent estimation

### Improved LLM Call Count

| Scenario | Current | Improved ReAct | Optimization |
|----------|---------|---------------|--------------|
| Scenario 1 | 2 calls | **2 calls** | No change |
| Scenario 2 | N/A | **1-2 calls** | Early exit saves 1 call for obvious cases |
| Scenario 3 | 1 call | **2 calls** | +1 call for better intent understanding |
| Scenario 4 | 2 calls | **2 calls** | No change |

**Average:** ~1.8 calls per request (vs 1.5 current, but enables Scenario 2)

---

**Next Steps:**
1. Review and approve this improved analysis
2. Implement Improved Hybrid ReAct pattern
3. Add early exit optimization
4. Centralize double bubble map prompts
5. Test all four scenarios with improved logic
6. Update frontend to handle auto-complete trigger
7. Monitor confidence thresholds and adjust based on real usage

