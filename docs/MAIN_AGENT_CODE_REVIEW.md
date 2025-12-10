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

