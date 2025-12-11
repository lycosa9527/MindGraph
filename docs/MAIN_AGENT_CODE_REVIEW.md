# Main Agent Code Review

**Date:** 2024-12-19  
**Reviewer:** AI Assistant  
**Scope:** Complete code review of `agents/main_agent.py` focusing on prompt template conflicts and architecture

---

## Executive Summary

The main agent (`agents/main_agent.py`) is responsible for accepting user prompts, extracting topics, and classifying diagram types. The review identified **two conflicting sets of prompt templates** that serve similar purposes but are used in different parts of the codebase, creating potential inconsistencies and maintenance issues.

---

## 1. Architecture Overview

### 1.1 Main Agent Responsibilities

The main agent (`agents/main_agent.py`) serves as the entry point for diagram generation and handles:

1. **Topic Extraction**: Extracting the main topic/subject from user prompts
2. **Diagram Type Classification**: Determining which diagram type (bubble_map, mind_map, etc.) the user wants
3. **Workflow Orchestration**: Coordinating between specialized agents for different diagram types
4. **Concept Map Generation**: Special handling for concept maps with multiple generation strategies

### 1.2 Key Functions

- `agent_graph_workflow_with_styles()`: Main workflow function called from API endpoints
- `_detect_diagram_type_from_prompt()`: LLM-based diagram type classification
- `extract_central_topic_llm()`: LLM-based topic extraction
- `generate_concept_map_*()`: Multiple concept map generation strategies
- `_generate_spec_with_agent()`: Delegates to specialized agents

---

## 2. Prompt Template Conflicts

### 2.1 Two Sets of Prompt Templates Identified

#### Set 1: Hardcoded Prompts in `agents/main_agent.py`

**Location:** Lines 357-507

```python
# Topic extraction prompts (PromptTemplate objects)
topic_extraction_prompt_en = PromptTemplate(...)
topic_extraction_prompt_zh = PromptTemplate(...)

# Characteristics generation prompts (for double bubble maps)
characteristics_prompt_en = PromptTemplate(...)
characteristics_prompt_zh = PromptTemplate(...)
```

**Usage:**
- Used by `create_topic_extraction_chain()` (line 514-528)
- Used by `create_characteristics_chain()` (line 531-545)
- Called from `agents/core/agent_utils.py` for double bubble map generation

**Content Analysis:**
- Topic extraction prompts focus on extracting **exactly two topics** for comparison
- Characteristics prompts generate similarities and differences for double bubble maps

#### Set 2: Centralized Prompts in `prompts/main_agent.py`

**Location:** `prompts/main_agent.py` lines 38-173

```python
# Registered in MAIN_AGENT_PROMPTS dictionary
CLASSIFICATION_EN/ZH: Diagram type classification
TOPIC_EXTRACTION_EN/ZH: General topic extraction
CONCEPT_30_EN/ZH: Concept generation for concept maps
```

**Usage:**
- `get_prompt("classification", language, "generation")` → Line 754 in `_detect_diagram_type_from_prompt()`
- `get_prompt("topic_extraction", language, "generation")` → Line 1779 in `agent_graph_workflow_with_styles()`
- `get_prompt("concept_30", language, "generation")` → Line 1197 in `generate_concept_map_enhanced_30()`

**Content Analysis:**
- Topic extraction prompt focuses on extracting **the main topic/subject** (single topic, not two)
- More comprehensive examples and instructions
- Different purpose than hardcoded prompts

### 2.2 Conflict Analysis

#### Conflict 1: Topic Extraction Prompts

**Hardcoded Prompts (lines 357-399):**
- Purpose: Extract **exactly two topics** for comparison
- Target: Double bubble map generation
- Format: "topic1 and topic2"

**Centralized Prompts (`TOPIC_EXTRACTION_*`):**
- Purpose: Extract **the main topic/subject** (single topic)
- Target: General topic extraction for all diagram types
- Format: Single topic string

**Impact:** 
- ✅ **No direct conflict** - They serve different purposes
- ⚠️ **Naming confusion** - Both are called "topic extraction" but serve different use cases
- ⚠️ **Maintenance risk** - Two separate prompt systems to maintain

#### Conflict 2: Characteristics Prompts

**Hardcoded Prompts (lines 402-507):**
- Purpose: Generate similarities and differences for double bubble maps
- Content: Detailed YAML format with similarities, left_differences, right_differences
- **No centralized equivalent exists**

**Impact:**
- ⚠️ **Missing from centralized system** - Characteristics prompts are only hardcoded
- ⚠️ **Inconsistency** - Other prompts are centralized, but these are not

---

## 3. Detailed Code Analysis

### 3.1 Topic Extraction Functions

#### Function 1: `extract_central_topic_llm()` (lines 85-109)

```python
def extract_central_topic_llm(user_prompt: str, language: str = 'zh') -> str:
    """Extract central topic using LLM instead of hardcoded string manipulation."""
    if language == 'zh':
        prompt = f"从以下用户输入中提取核心主题，只返回主题内容，不要其他文字：\n{user_prompt}"
    else:
        prompt = f"Extract the central topic from this user input, return only the topic:\n{user_prompt}"
    
    result = llm_classification._call(prompt)
    # ...
```

**Issues:**
- ⚠️ **Hardcoded prompt strings** - Not using centralized prompts
- ⚠️ **Simple prompt** - Less comprehensive than centralized `TOPIC_EXTRACTION_*` prompts
- ⚠️ **Inconsistent** - Different from the centralized prompt used in `agent_graph_workflow_with_styles()`

#### Function 2: `extract_double_bubble_topics_llm()` (lines 111-163)

```python
async def extract_double_bubble_topics_llm(user_prompt: str, language: str = 'zh', model: str = 'qwen') -> str:
    """Extract two topics for double bubble map comparison using LLM."""
    if language == 'zh':
        prompt = f"""从以下用户输入中提取两个要比较的主题，只返回两个主题，用"和"连接，不要其他文字：
        {user_prompt}
        ...
        """
    # ...
```

**Issues:**
- ⚠️ **Hardcoded prompt strings** - Not using centralized prompts
- ⚠️ **Specialized function** - Purpose-built for double bubble maps
- ✅ **Appropriate** - Different from general topic extraction

#### Function 3: `create_topic_extraction_chain()` (lines 514-528)

```python
def create_topic_extraction_chain(language='zh'):
    """Create a simple chain for topic extraction"""
    prompt = topic_extraction_prompt_zh if language == 'zh' else topic_extraction_prompt_en
    
    def extract_topics(user_prompt):
        """Extract topics using the classification model"""
        return llm_classification._call(prompt.format(user_prompt=user_prompt))
    
    return extract_topics
```

**Issues:**
- ⚠️ **Uses hardcoded prompts** - Not using centralized system
- ⚠️ **Legacy LangChain pattern** - Uses PromptTemplate objects
- ⚠️ **Called from agent_utils.py** - Used for double bubble map generation

### 3.2 Diagram Classification

#### Function: `_detect_diagram_type_from_prompt()` (lines 722-818)

```python
async def _detect_diagram_type_from_prompt(...) -> dict:
    """LLM-based diagram type detection using semantic understanding."""
    # Get classification prompt from centralized system
    classification_prompt = get_prompt("classification", language, "generation")
    classification_prompt = classification_prompt.format(user_prompt=user_prompt)
    
    # Use middleware directly
    from services.llm_service import llm_service
    response = await llm_service.chat(
        prompt=classification_prompt,
        model=model,
        max_tokens=50,
        temperature=0.3,
        # ...
    )
```

**Status:**
- ✅ **Uses centralized prompts** - Correctly uses `get_prompt("classification", ...)`
- ✅ **Modern async pattern** - Uses `llm_service.chat()` directly
- ✅ **Well-structured** - Clean implementation

### 3.3 Main Workflow

#### Function: `agent_graph_workflow_with_styles()` (lines 1696-1883)

**Topic Extraction Section (lines 1773-1803):**

```python
# Extract main topic from prompt using LLM (only if not forced diagram type)
if not forced_diagram_type:
    # Use centralized topic extraction prompt
    topic_extraction_prompt = get_prompt("topic_extraction", language, "generation")
    topic_extraction_prompt = topic_extraction_prompt.format(user_prompt=user_prompt)
    
    main_topic = await llm_service.chat(
        prompt=topic_extraction_prompt,
        model=model,
        max_tokens=50,
        temperature=0.1,
        # ...
    )
```

**Status:**
- ✅ **Uses centralized prompts** - Correctly uses `get_prompt("topic_extraction", ...)`
- ✅ **Modern async pattern** - Uses `llm_service.chat()` directly
- ⚠️ **Different from `extract_central_topic_llm()`** - Two different implementations for similar purpose

---

## 4. Issues and Recommendations

### 4.1 Critical Issues

#### Issue 1: Duplicate Topic Extraction Implementations

**Problem:**
- `extract_central_topic_llm()` uses hardcoded simple prompts
- `agent_graph_workflow_with_styles()` uses centralized comprehensive prompts
- Both extract a single topic but use different prompts

**Recommendation:**
- Consolidate to use centralized `TOPIC_EXTRACTION_*` prompts everywhere
- Update `extract_central_topic_llm()` to use `get_prompt("topic_extraction", ...)`
- Remove hardcoded prompt strings

#### Issue 2: Characteristics Prompts Not Centralized

**Problem:**
- Characteristics prompts (for double bubble maps) are only hardcoded
- Not registered in `prompts/main_agent.py`
- Inconsistent with other prompts

**Recommendation:**
- Move characteristics prompts to `prompts/main_agent.py`
- Register as `CHARACTERISTICS_GENERATION_EN/ZH`
- Update `create_characteristics_chain()` to use centralized prompts

#### Issue 3: Naming Confusion

**Problem:**
- Hardcoded prompts called "topic_extraction" but extract two topics
- Centralized prompts called "topic_extraction" but extract one topic
- Same name, different purposes

**Recommendation:**
- Rename hardcoded prompts to `double_bubble_topic_extraction_*`
- Or create separate centralized prompts: `double_bubble_topic_extraction_*` and `topic_extraction_*`

### 4.2 Medium Priority Issues

#### Issue 4: Legacy LangChain Pattern

**Problem:**
- `create_topic_extraction_chain()` and `create_characteristics_chain()` use LangChain `PromptTemplate`
- Other code uses direct string prompts with `get_prompt()`
- Inconsistent patterns

**Recommendation:**
- Migrate to centralized prompt system
- Remove LangChain dependency if not needed elsewhere
- Use consistent async/await pattern

#### Issue 5: Mixed Sync/Async Patterns

**Problem:**
- `extract_central_topic_llm()` is synchronous but uses async LLM service internally
- `extract_double_bubble_topics_llm()` is async
- `agent_graph_workflow_with_styles()` is async

**Recommendation:**
- Make all LLM calls consistently async
- Remove sync wrappers where possible
- Use `llm_service.chat()` directly

### 4.3 Low Priority Issues

#### Issue 6: Code Organization

**Problem:**
- Prompt templates scattered throughout the file
- Some prompts defined at module level, some in functions
- Hard to find all prompts

**Recommendation:**
- Move all prompt-related code to use centralized system
- Remove hardcoded prompts from `main_agent.py`
- Keep only business logic in `main_agent.py`

---

## 5. Prompt Content Comparison

### 5.1 Topic Extraction Prompts

#### Hardcoded Prompt (Simple):
```
"从以下用户输入中提取核心主题，只返回主题内容，不要其他文字：\n{user_prompt}"
```

#### Centralized Prompt (Comprehensive):
```
从用户输入中提取核心主题词。

**核心原则：主题是图表的内容，不是图表本身的类型！**

正确示例：
输入："生成一个关于树形图的气泡图" 
分析：用户要创建气泡图（图表类型），内容是关于"树形图"（主题）
输出："树形图"
...
```

**Analysis:**
- Centralized prompt is **more comprehensive** with examples
- Centralized prompt **better handles edge cases** (diagram type vs topic)
- Centralized prompt should be used everywhere

### 5.2 Double Bubble Topic Extraction

#### Hardcoded Prompt (Two Topics):
```
从以下用户输入中提取两个要比较的主题，只返回两个主题，用"和"连接，不要其他文字：
{user_prompt}

重要：忽略动作词如"生成"、"创建"、"比较"、"制作"等，只提取实际要比较的两个主题。
...
```

**Analysis:**
- This prompt is **specialized** for double bubble maps
- Should be **separate** from general topic extraction
- Should be **centralized** but with different name

---

## 6. Call Flow Analysis

### 6.1 Topic Extraction Call Flow

```
API Endpoint (/api/generate_graph)
  └─> agent_graph_workflow_with_styles()
       └─> get_prompt("topic_extraction", ...)  [CENTRALIZED]
            └─> llm_service.chat()

Double Bubble Map Generation
  └─> agent_utils.extract_topics_with_agent()
       └─> create_topic_extraction_chain()
            └─> topic_extraction_prompt_zh/en  [HARDCODED]
                 └─> llm_classification._call()

Concept Map Generation
  └─> extract_central_topic_llm()
       └─> Hardcoded simple prompt  [HARDCODED]
            └─> llm_classification._call()
```

**Issues:**
- Three different code paths for topic extraction
- Two different prompt systems
- Inconsistent LLM service usage

### 6.2 Diagram Classification Call Flow

```
API Endpoint (/api/generate_graph)
  └─> agent_graph_workflow_with_styles()
       └─> _detect_diagram_type_from_prompt()
            └─> get_prompt("classification", ...)  [CENTRALIZED]
                 └─> llm_service.chat()
```

**Status:**
- ✅ Single code path
- ✅ Uses centralized prompts
- ✅ Consistent pattern

---

## 7. Recommendations Summary

### 7.1 Immediate Actions

1. **Consolidate Topic Extraction**
   - Update `extract_central_topic_llm()` to use `get_prompt("topic_extraction", ...)`
   - Remove hardcoded prompt strings

2. **Centralize Characteristics Prompts**
   - Move to `prompts/main_agent.py`
   - Register as `CHARACTERISTICS_GENERATION_EN/ZH`
   - Update `create_characteristics_chain()` to use centralized prompts

3. **Rename Double Bubble Prompts**
   - Create `DOUBLE_BUBBLE_TOPIC_EXTRACTION_EN/ZH` in centralized system
   - Update `create_topic_extraction_chain()` to use new name
   - Clarify purpose vs general topic extraction

### 7.2 Medium-Term Improvements

4. **Remove LangChain Dependencies**
   - Migrate `create_topic_extraction_chain()` to use centralized prompts
   - Use direct `llm_service.chat()` calls
   - Remove `PromptTemplate` imports if not needed

5. **Standardize Async Pattern**
   - Make all LLM calls async
   - Remove sync wrappers
   - Use consistent error handling

### 7.3 Long-Term Architecture

6. **Unified Prompt System**
   - All prompts in `prompts/` directory
   - No hardcoded prompts in agent files
   - Single source of truth

7. **Consistent LLM Service Usage**
   - Always use `llm_service.chat()` directly
   - Remove legacy `llm_classification._call()` wrappers
   - Standardize token tracking parameters

---

## 8. Testing Recommendations

### 8.1 Test Cases Needed

1. **Topic Extraction Consistency**
   - Test that `extract_central_topic_llm()` and centralized prompts produce similar results
   - Test edge cases (diagram type in prompt, etc.)

2. **Double Bubble Topic Extraction**
   - Test that two-topic extraction works correctly
   - Test with various input formats

3. **Prompt Template Loading**
   - Test that all centralized prompts load correctly
   - Test fallback behavior if prompt missing

### 8.2 Integration Tests

1. **End-to-End Workflow**
   - Test full workflow from API to diagram generation
   - Verify prompt consistency throughout

2. **Multi-Diagram Type Support**
   - Test all diagram types use correct prompts
   - Verify no hardcoded prompts in specialized agents

---

## 9. Conclusion

The main agent has **two conflicting prompt systems** that serve overlapping but distinct purposes:

1. **Hardcoded prompts** in `agents/main_agent.py` - Used for double bubble maps and legacy code
2. **Centralized prompts** in `prompts/main_agent.py` - Used for general topic extraction and classification

**Key Findings:**
- ✅ Classification prompts are properly centralized
- ⚠️ Topic extraction has duplicate implementations
- ⚠️ Characteristics prompts are not centralized
- ⚠️ Naming confusion between similar prompts

**Priority Actions:**
1. Consolidate topic extraction to use centralized prompts
2. Centralize characteristics prompts
3. Rename double bubble prompts for clarity
4. Remove hardcoded prompts from `main_agent.py`

**Impact:**
- Low risk of bugs (different code paths)
- Medium maintenance burden (two systems to update)
- High improvement potential (consistency and clarity)

---

## 10. ReAct Pattern Analysis: Should Main Agent Use ReAct?

### 10.1 Current Implementation: Rule-Based Logic

**Current Approach:**
The main agent (`agents/main_agent.py`) uses simple if/else logic based on parameters:

```python
if forced_diagram_type:
    # Use forced diagram type
    if not forced_diagram_type:  # Line 1774
        # Extract topic only
    else:
        # Full generation
else:
    # Detect diagram type + extract topic
```

**Issues:**
- ⚠️ **No intent reasoning** - Decisions are rule-based, not reasoning-based
- ⚠️ **Parameter-driven** - Relies on `forced_diagram_type` parameter instead of understanding user intent
- ⚠️ **Inflexible** - Cannot adapt to nuanced user requests

### 10.2 Comparison: Thinking Mode Agents Use ReAct

**Thinking Mode Agents** (`agents/thinking_modes/base_thinking_agent.py`):
- ✅ Use ReAct pattern: REASON → ACT → OBSERVE
- ✅ Intent detection via `_detect_user_intent()`
- ✅ Actions executed based on detected intent
- ✅ More flexible and adaptive

**Example from Circle Map Agent:**
```python
# REASON: Detect user intent
intent = await self._detect_user_intent(session, message, current_state)
# ACT: Execute action based on intent
async for event in self._act(session, intent, message, current_state):
    yield event
```

### 10.3 Proposed ReAct Pattern for Main Agent

**ReAct Step 1: REASON**
- Analyze user prompt to understand intent
- Determine which scenario applies:
  - Scenario 1: User wants system to detect diagram type
  - Scenario 2: User knows diagram type, just wants topic
  - Scenario 3: User wants full generation with instructions

**ReAct Step 2: ACT**
- Execute appropriate action based on detected intent
- Not based on parameters, but on reasoning

**ReAct Step 3: OBSERVE**
- Return appropriate response
- Can include confidence scores and reasoning

### 10.4 Benefits of ReAct Pattern

1. **Better Intent Understanding**
   - Analyzes user prompt semantically
   - Understands context and nuance
   - More accurate scenario detection

2. **Flexible Decision Making**
   - Not limited to parameter-based rules
   - Can handle edge cases and ambiguous requests
   - Adapts to user's actual intent

3. **Consistency with Architecture**
   - Matches thinking mode agents' pattern
   - Unified approach across codebase
   - Easier to maintain and extend

### 10.5 Implementation Recommendation

**Add Intent Detection Function:**
```python
async def _detect_user_intent(
    user_prompt: str,
    language: str,
    forced_diagram_type: Optional[str] = None,
    ...
) -> dict:
    """
    ReAct Step 1: REASON
    Detect user intent for diagram generation workflow.
    """
    # Use LLM to analyze prompt and determine intent
    # Return: {'intent': 'detect_and_extract' | 'extract_topic_only' | 'generate_full_spec', ...}
```

**Refactor Workflow:**
```python
async def agent_graph_workflow_with_styles(...):
    # REASON: Detect intent
    intent = await _detect_user_intent(...)
    
    # ACT: Execute based on intent
    if intent['intent'] == 'detect_and_extract':
        # Scenario 1
    elif intent['intent'] == 'extract_topic_only':
        # Scenario 2
    elif intent['intent'] == 'generate_full_spec':
        # Scenario 3
    
    # OBSERVE: Return response
```

---

## 11. Three-Scenario Analysis: Topic Extraction and Diagram Selection

### 10.1 Current System Overview

The main agent handles three distinct user scenarios for diagram generation:

1. **Scenario 1: User provides prompt → System picks diagram**
   - User input: Natural language prompt (e.g., "生成关于光合作用的气泡图")
   - System action: Detects diagram type + extracts topic
   - Current implementation: ✅ Working (lines 1734-1803 in `agent_graph_workflow_with_styles()`)

2. **Scenario 2: User knows diagram type → System fills topic**
   - User input: Diagram type specified + prompt (e.g., diagram_type="bubble_map", prompt="光合作用")
   - System action: Extracts topic, uses specified diagram type
   - Current implementation: ⚠️ Partially working (needs refinement)

3. **Scenario 3: User provides topic + diagram + instructions → System builds diagram**
   - User input: Diagram type + topic + explicit instructions (e.g., diagram_type="bubble_map", prompt="光合作用，包含8个特征")
   - System action: Full generation with user's explicit instructions
   - Current implementation: ✅ Working (lines 1805-1862 in `agent_graph_workflow_with_styles()`)

### 10.2 Scenario 1: Prompt-Based Diagram Selection

**Current Flow:**
```
User Prompt → _detect_diagram_type_from_prompt() → Classification Prompt
           → extract topic → Return {diagram_type, extracted_topic, use_default_template: True}
```

**Classification Prompt Analysis:**
- Location: `prompts/main_agent.py` lines 38-118
- Covers all 9 diagram types (8 thinking maps + 1 mindmap)
- Uses comprehensive examples and edge case handling
- Returns "unclear" for ambiguous prompts (fallback to mind_map)

**Status:** ✅ Well-implemented
- Uses centralized `CLASSIFICATION_EN/ZH` prompts
- Handles edge cases (diagram type vs topic confusion)
- Returns clarity indicators for frontend guidance

### 10.3 Scenario 2: Diagram Type Known, Topic Extraction Needed

**Current Flow:**
```
User provides diagram_type + prompt → forced_diagram_type is set
                                    → Still extracts topic (line 1774 check)
                                    → But then goes to full generation (line 1805)
```

**Issue Identified:**
- When `forced_diagram_type` is provided, the system skips topic extraction return (line 1774)
- Goes directly to full generation workflow
- This means Scenario 2 is currently treated the same as Scenario 3

**Expected Behavior for Scenario 2:**
- User provides diagram type + minimal prompt (just topic)
- System should extract topic and return `use_default_template: True`
- Frontend loads default template with extracted topic
- User can then use auto-complete to fill in details

**Recommendation:**
Add a new parameter `extract_topic_only: bool` to distinguish:
- Scenario 2: `forced_diagram_type` + `extract_topic_only=True` → Extract topic, return template
- Scenario 3: `forced_diagram_type` + `extract_topic_only=False` → Full generation

### 10.4 Scenario 3: Full Generation with Instructions

**Current Flow:**
```
User provides diagram_type + prompt with instructions → forced_diagram_type is set
                                                    → Full agent workflow
                                                    → Generate complete spec
```

**Status:** ✅ Well-implemented
- Uses specialized agents for each diagram type
- Handles learning sheet detection
- Supports dimension preferences (brace_map, tree_map, bridge_map)
- Supports auto-complete modes (bridge_map with existing_analogies)

### 10.5 Prompt System Analysis for All 9 Diagrams

#### 10.5.1 Classification Prompts (Scenario 1)

**Location:** `prompts/main_agent.py` lines 38-118

**Coverage:**
- ✅ All 9 diagram types covered
- ✅ Comprehensive examples for each type
- ✅ Edge case handling (diagram type vs topic confusion)
- ✅ Clear decision logic for ambiguous cases

**Quality Assessment:**
- **Excellent**: Clear instructions, good examples
- **Comprehensive**: Covers all valid diagram types
- **Robust**: Handles edge cases and returns "unclear" when needed

#### 10.5.2 Topic Extraction Prompts (All Scenarios)

**Location:** `prompts/main_agent.py` lines 120-172

**Coverage:**
- ✅ Single topic extraction (general use)
- ✅ Handles diagram type confusion
- ✅ Language-specific (EN/ZH)

**Quality Assessment:**
- **Good**: Clear examples showing correct vs incorrect extraction
- **Comprehensive**: Handles edge cases (diagram type words in prompt)
- **Needs Improvement**: Could add examples for Scenario 2 (when diagram type is already known)

#### 10.5.3 Generation Prompts (Scenario 3)

**Location:** `prompts/thinking_maps.py` and `prompts/mind_maps.py`

**Coverage by Diagram Type:**

1. **Circle Map** (`CIRCLE_MAP_GENERATION_EN/ZH`)
   - ✅ Clear structure (topic + context array)
   - ✅ Handles quoted topics
   - ✅ Concise requirements

2. **Bubble Map** (`BUBBLE_MAP_GENERATION_EN/ZH`)
   - ✅ Clear structure (topic + attributes array)
   - ✅ Handles quoted topics
   - ✅ Adjective-focused instructions

3. **Double Bubble Map** (`DOUBLE_BUBBLE_MAP_GENERATION_EN/ZH`)
   - ✅ Clear structure (left, right, similarities, differences)
   - ✅ Parallel differences requirement
   - ⚠️ Uses hardcoded prompts in `main_agent.py` (lines 402-507) instead of centralized

4. **Tree Map** (`TREE_MAP_GENERATION_EN/ZH`)
   - ✅ Clear structure (topic, dimension, children hierarchy)
   - ✅ Dimension concept explained
   - ✅ Alternative dimensions support
   - ✅ Fixed dimension mode for auto-complete

5. **Brace Map** (`BRACE_MAP_GENERATION_EN/ZH`)
   - ✅ Clear structure (whole, dimension, parts hierarchy)
   - ✅ Dimension concept explained
   - ✅ Alternative dimensions support
   - ✅ Fixed dimension mode for auto-complete

6. **Flow Map** (`FLOW_MAP_GENERATION_EN/ZH`)
   - ✅ Clear structure (title, steps, substeps)
   - ✅ Handles quoted topics
   - ✅ Step/substep relationship explained

7. **Multi-Flow Map** (`MULTI_FLOW_MAP_GENERATION_EN/ZH`)
   - ✅ Clear structure (event, causes, effects)
   - ✅ Concise requirements

8. **Bridge Map** (`BRIDGE_MAP_GENERATION_EN/ZH`)
   - ✅ Complex but well-structured
   - ✅ Relationship pattern analysis
   - ✅ Multiple modes (identify relationship, fixed dimension, relationship-only)
   - ✅ Alternative dimensions support

9. **Mind Map** (`MIND_MAP_AGENT_GENERATION_EN/ZH`)
   - ✅ Clear structure (topic, children hierarchy)
   - ✅ Educational framework integration
   - ✅ MECE principle requirement
   - ✅ Even number branches (4, 6, or 8)

**Quality Assessment:**
- **Overall**: Excellent coverage and quality
- **Consistency**: All prompts follow similar structure
- **Completeness**: All 9 diagrams have generation prompts
- **Issue**: Double bubble map uses hardcoded prompts instead of centralized system

### 10.6 Recommendations for Three-Scenario Support

#### Recommendation 1: Add `extract_topic_only` Parameter

**Purpose:** Distinguish Scenario 2 from Scenario 3

**Implementation:**
```python
async def agent_graph_workflow_with_styles(
    user_prompt,
    language='zh',
    forced_diagram_type=None,
    extract_topic_only=False,  # NEW: For Scenario 2
    dimension_preference=None,
    ...
):
    # If forced diagram type + extract_topic_only, return topic + template
    if forced_diagram_type and extract_topic_only:
        # Extract topic using centralized prompt
        topic_extraction_prompt = get_prompt("topic_extraction", language, "generation")
        main_topic = await llm_service.chat(...)
        return {
            'success': True,
            'diagram_type': forced_diagram_type,
            'extracted_topic': main_topic,
            'use_default_template': True
        }
```

#### Recommendation 2: Enhance Topic Extraction Prompt for Scenario 2

**Current:** Prompt assumes diagram type needs to be ignored
**Enhancement:** Add examples for when diagram type is already known

```python
TOPIC_EXTRACTION_EN = """
...
Scenario 2 Examples (diagram type already known):
- diagram_type="bubble_map", prompt="光合作用" → "photosynthesis"
- diagram_type="tree_map", prompt="动物分类" → "animals"
- diagram_type="flow_map", prompt="制作咖啡" → "coffee making"
"""
```

#### Recommendation 3: Centralize Double Bubble Map Prompts

**Current:** Hardcoded in `agents/main_agent.py` lines 402-507
**Action:** Move to `prompts/main_agent.py` as `DOUBLE_BUBBLE_TOPIC_EXTRACTION_EN/ZH` and `CHARACTERISTICS_GENERATION_EN/ZH`

#### Recommendation 4: Document Three Scenarios in API

**Action:** Update `GenerateRequest` model documentation to explain three scenarios:
- Scenario 1: `diagram_type=None` → Auto-detect + extract topic
- Scenario 2: `diagram_type=X` + `extract_topic_only=True` → Extract topic, use template
- Scenario 3: `diagram_type=X` + `extract_topic_only=False` → Full generation

### 10.7 Testing Recommendations

1. **Scenario 1 Tests:**
   - Test all 9 diagram types are correctly detected
   - Test edge cases (diagram type in prompt)
   - Test ambiguous prompts return "unclear"

2. **Scenario 2 Tests:**
   - Test topic extraction when diagram type is known
   - Test that template is returned correctly
   - Test with minimal prompts (just topic words)

3. **Scenario 3 Tests:**
   - Test full generation for all 9 diagram types
   - Test with explicit instructions
   - Test dimension preferences
   - Test auto-complete modes

---

## Appendix: Code Locations

### Prompt Definitions

- Hardcoded Topic Extraction: `agents/main_agent.py` lines 357-399
- Hardcoded Characteristics: `agents/main_agent.py` lines 402-507
- Centralized Prompts: `prompts/main_agent.py` lines 38-173
- Prompt Registry: `prompts/__init__.py` lines 17-23

### Function Locations

- `extract_central_topic_llm()`: `agents/main_agent.py` lines 85-109
- `extract_double_bubble_topics_llm()`: `agents/main_agent.py` lines 111-163
- `create_topic_extraction_chain()`: `agents/main_agent.py` lines 514-528
- `create_characteristics_chain()`: `agents/main_agent.py` lines 531-545
- `_detect_diagram_type_from_prompt()`: `agents/main_agent.py` lines 722-818
- `agent_graph_workflow_with_styles()`: `agents/main_agent.py` lines 1696-1883

### Usage Locations

- Double Bubble Map: `agents/core/agent_utils.py` lines 374-406
- Main Workflow: `routers/api.py` line 199

