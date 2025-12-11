# Topic Extraction and Diagram Selection Analysis

**Date:** 2024-12-19  
**Focus:** Centralized prompt system analysis for all 9 diagrams (8 thinking maps + 1 mindmap)

---

## Executive Summary

The main agent's topic extraction and diagram selection system is **well-architected** with centralized prompts covering all 9 diagram types. However, the main agent should use **ReAct pattern** (Reason → Act → Observe) to reason about user intentions before deciding what action to take.

Currently, the main agent uses simple if/else logic instead of ReAct:
- If `forced_diagram_type` is None → detect + extract topic → return template
- If `forced_diagram_type` is set → generate full spec

**Proposed ReAct Approach:**
1. **REASON**: Understand user intent (what scenario? what do they want?)
2. **ACT**: Execute appropriate action based on detected intent
3. **OBSERVE**: Return appropriate response

**Three distinct user scenarios** that need ReAct-based intent detection:

1. ✅ **Scenario 1**: User provides prompt → System picks diagram (Working, but should use ReAct)
2. ⚠️ **Scenario 2**: User knows diagram type → System fills topic (Needs ReAct-based intent detection)
3. ✅ **Scenario 3**: User provides topic + diagram + instructions → System builds diagram (Working, but should use ReAct)

---

## Current System Architecture

### Prompt System Structure

```
prompts/
├── main_agent.py          # Classification + Topic Extraction
├── thinking_maps.py       # 8 Thinking Maps generation prompts
└── mind_maps.py           # 1 Mind Map generation prompt
```

### Classification System (Scenario 1)

**Location:** `prompts/main_agent.py` lines 38-118

**Coverage:** All 9 diagram types
- ✅ circle_map
- ✅ bubble_map
- ✅ double_bubble_map
- ✅ brace_map
- ✅ bridge_map
- ✅ tree_map
- ✅ flow_map
- ✅ multi_flow_map
- ✅ mind_map

**Quality:** Excellent
- Comprehensive examples for each type
- Edge case handling (diagram type vs topic confusion)
- Returns "unclear" for ambiguous prompts (fallback to mind_map)

### Topic Extraction System (All Scenarios)

**Location:** `prompts/main_agent.py` lines 120-172

**Quality:** Good
- Clear examples showing correct vs incorrect extraction
- Handles diagram type words in prompt
- Language-specific (EN/ZH)

**Issue:** Could be enhanced for Scenario 2 (when diagram type is already known)

### Generation Prompts (Scenario 3)

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

---

## Three Scenarios Analysis

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

**Status:** ✅ **Working Well**
- Uses centralized classification prompt
- Handles all 9 diagram types
- Good edge case handling
- Returns clarity indicators for frontend

**Recommendation:** No changes needed

---

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
- User can use auto-complete to fill details

**Recommendation:** Add `extract_topic_only` parameter

```python
# In agent_graph_workflow_with_styles()
if forced_diagram_type and extract_topic_only:
    # Scenario 2: Extract topic, return template
    topic_extraction_prompt = get_prompt("topic_extraction", language, "generation")
    main_topic = await llm_service.chat(...)
    return {
        'success': True,
        'diagram_type': forced_diagram_type,
        'extracted_topic': main_topic,
        'use_default_template': True
    }
```

---

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

**Status:** ✅ **Working Well**
- Uses specialized agents for each diagram type
- Handles learning sheet detection
- Supports dimension preferences
- Supports auto-complete modes

**Recommendation:** No changes needed

---

## Key Findings

### ✅ Strengths

1. **Centralized Prompt System**
   - All prompts in `prompts/` directory
   - Clear organization by diagram type
   - Consistent structure across prompts

2. **Comprehensive Coverage**
   - All 9 diagram types have classification prompts
   - All 9 diagram types have generation prompts
   - Good edge case handling

3. **Quality Prompts**
   - Clear instructions
   - Good examples
   - Handles quoted topics
   - Supports alternative dimensions (tree_map, brace_map, bridge_map)

### ⚠️ Issues

1. **Double Bubble Map Prompts Not Centralized**
   - Uses hardcoded prompts in `agents/main_agent.py` lines 402-507
   - Should be moved to `prompts/main_agent.py`

2. **Scenario 2 Not Clearly Distinguished**
   - Currently treated same as Scenario 3
   - Needs `extract_topic_only` parameter

3. **Topic Extraction Prompt Could Be Enhanced**
   - Could add examples for Scenario 2
   - Could handle cases where diagram type is already known

---

## Recommendations

### Priority 1: Implement ReAct Pattern for Main Agent

1. **Add Intent Detection Function (REASON step)**
   - Create `_detect_user_intent()` function similar to thinking mode agents
   - Analyze user prompt to determine which scenario applies
   - Return intent with action type (e.g., `extract_topic_only`, `generate_full_spec`, `detect_and_extract`)
   
2. **Refactor Workflow to Use ReAct**
   - REASON: Detect user intent from prompt
   - ACT: Execute action based on intent
   - OBSERVE: Return appropriate response
   - Replace simple if/else logic with ReAct-based decision making

3. **Create Intent Detection Prompt**
   - Add to `prompts/main_agent.py`
   - Analyze user prompt to determine:
     - Does user specify diagram type?
     - Does user provide explicit instructions?
     - What is user's primary intent?

### Priority 2: Centralize Prompts

4. **Centralize Double Bubble Map Prompts**
   - Move to `prompts/main_agent.py`
   - Register as `DOUBLE_BUBBLE_TOPIC_EXTRACTION_EN/ZH` and `CHARACTERISTICS_GENERATION_EN/ZH`
   - Update `create_topic_extraction_chain()` and `create_characteristics_chain()`

### Priority 3: Enhancements

5. **Enhance Topic Extraction Prompt**
   - Add Scenario 2 examples
   - Handle cases where diagram type is already known

6. **Document Three Scenarios**
   - Update API documentation
   - Add examples for each scenario
   - Document ReAct pattern usage

### Priority 4: Testing

7. **Add Test Cases**
   - Test ReAct intent detection for all three scenarios
   - Scenario 1: Test all 9 diagram types detection
   - Scenario 2: Test topic extraction with known diagram type
   - Scenario 3: Test full generation with instructions

---

## Implementation Plan

### Step 1: Implement ReAct Pattern - Intent Detection (REASON)

**File:** `prompts/main_agent.py`
```python
INTENT_DETECTION_EN = """Analyze the user's prompt to determine their intent for diagram generation.

Possible intents:
1. detect_and_extract: User provides natural language prompt, wants system to detect diagram type and extract topic
2. extract_topic_only: User has already specified diagram type, just wants topic extracted (minimal prompt)
3. generate_full_spec: User provides diagram type + prompt with explicit instructions for full generation

User prompt: "{user_prompt}"
Diagram type provided: {diagram_type_provided}

Analyze:
- Does user explicitly specify a diagram type in the prompt?
- Does user provide detailed instructions (e.g., "包含8个特征", "按栖息地分类")?
- Is the prompt minimal (just topic) or detailed (instructions)?

Return JSON:
{
  "intent": "detect_and_extract" | "extract_topic_only" | "generate_full_spec",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}
"""

INTENT_DETECTION_ZH = """分析用户的提示以确定他们生成图表的意图。

可能的意图：
1. detect_and_extract: 用户提供自然语言提示，希望系统检测图表类型并提取主题
2. extract_topic_only: 用户已指定图表类型，只想提取主题（最小提示）
3. generate_full_spec: 用户提供图表类型 + 带有明确生成指令的提示

用户提示："{user_prompt}"
是否提供图表类型：{diagram_type_provided}

分析：
- 用户是否在提示中明确指定图表类型？
- 用户是否提供详细指令（例如："包含8个特征"、"按栖息地分类"）？
- 提示是最小的（仅主题）还是详细的（指令）？

返回JSON：
{{
  "intent": "detect_and_extract" | "extract_topic_only" | "generate_full_spec",
  "confidence": 0.0-1.0,
  "reasoning": "简要说明"
}}
"""
```

**File:** `agents/main_agent.py`
```python
async def _detect_user_intent(
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
    ReAct Step 1: REASON
    Detect user intent for diagram generation workflow.
    
    Returns:
        dict: {
            'intent': 'detect_and_extract' | 'extract_topic_only' | 'generate_full_spec',
            'confidence': float,
            'reasoning': str
        }
    """
    from services.llm_service import llm_service
    from prompts import get_prompt
    
    # Get intent detection prompt
    intent_prompt = get_prompt("intent_detection", language, "generation")
    intent_prompt = intent_prompt.format(
        user_prompt=user_prompt,
        diagram_type_provided="Yes" if forced_diagram_type else "No"
    )
    
    response = await llm_service.chat(
        prompt=intent_prompt,
        model=model,
        max_tokens=200,
        temperature=0.3,
        user_id=user_id,
        organization_id=organization_id,
        request_type=request_type,
        endpoint_path=endpoint_path
    )
    
    # Parse JSON response
    import json
    try:
        intent_data = json.loads(response.strip())
        logger.info(f"Detected intent: {intent_data.get('intent')} (confidence: {intent_data.get('confidence')})")
        return intent_data
    except Exception as e:
        logger.error(f"Intent detection parsing failed: {e}")
        # Fallback: use heuristics
        if forced_diagram_type:
            # If diagram type provided, check if prompt has instructions
            has_instructions = any(word in user_prompt.lower() for word in ['包含', '包含', 'include', 'with', '按', 'by'])
            return {
                'intent': 'generate_full_spec' if has_instructions else 'extract_topic_only',
                'confidence': 0.7,
                'reasoning': 'Fallback heuristic'
            }
        else:
            return {
                'intent': 'detect_and_extract',
                'confidence': 0.8,
                'reasoning': 'Fallback heuristic'
            }
```

### Step 2: Refactor Workflow to Use ReAct (ACT)

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
        
        # REACT STEP 1: REASON - Detect user intent
        intent_result = await _detect_user_intent(
            user_prompt,
            language,
            forced_diagram_type,
            model,
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path=endpoint_path
        )
        
        user_intent = intent_result.get('intent', 'detect_and_extract')
        logger.info(f"REASON → Detected intent: {user_intent}")
        
        # REACT STEP 2: ACT - Execute action based on intent
        if user_intent == 'detect_and_extract':
            # Scenario 1: Detect diagram type and extract topic
            detection_result = await _detect_diagram_type_from_prompt(...)
            diagram_type = detection_result['diagram_type']
            
            topic_extraction_prompt = get_prompt("topic_extraction", language, "generation")
            main_topic = await llm_service.chat(...)
            
            return {
                'success': True,
                'diagram_type': diagram_type,
                'extracted_topic': main_topic,
                'use_default_template': True
            }
        
        elif user_intent == 'extract_topic_only':
            # Scenario 2: Extract topic only (diagram type already known)
            topic_extraction_prompt = get_prompt("topic_extraction", language, "generation")
            main_topic = await llm_service.chat(...)
            
            return {
                'success': True,
                'diagram_type': forced_diagram_type,
                'extracted_topic': main_topic,
                'use_default_template': True
            }
        
        elif user_intent == 'generate_full_spec':
            # Scenario 3: Full generation with instructions
            diagram_type = forced_diagram_type or await _detect_diagram_type_from_prompt(...)
            is_learning_sheet = _detect_learning_sheet_from_prompt(user_prompt, language)
            generation_prompt = _clean_prompt_for_learning_sheet(user_prompt) if is_learning_sheet else user_prompt
            
            spec = await _generate_spec_with_agent(...)
            
            return {
                'success': True,
                'spec': spec,
                'diagram_type': diagram_type,
                'is_learning_sheet': is_learning_sheet,
                ...
            }
        
        # REACT STEP 3: OBSERVE - Response returned above
        # (Handled by return statements)
        
    except Exception as e:
        logger.error(f"ReAct workflow failed: {e}")
        ...
```

### Step 3: Centralize Double Bubble Map Prompts

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
}
```

**File:** `agents/main_agent.py`
```python
def create_topic_extraction_chain(language='zh'):
    prompt = get_prompt("double_bubble_topic_extraction", language, "generation")
    ...

def create_characteristics_chain(language='zh'):
    prompt = get_prompt("characteristics_generation", language, "generation")
    ...
```

### Step 4: Enhance Topic Extraction Prompt

**File:** `prompts/main_agent.py`
```python
TOPIC_EXTRACTION_EN = """
...
Scenario 2 Examples (diagram type already known):
- diagram_type="bubble_map", prompt="photosynthesis" → "photosynthesis"
- diagram_type="tree_map", prompt="animal classification" → "animals"
- diagram_type="flow_map", prompt="coffee making steps" → "coffee making"
"""
```

---

## Conclusion

The centralized prompt system is **well-designed and comprehensive**, covering all 9 diagram types with high-quality prompts. However, the main agent should adopt **ReAct pattern** to reason about user intentions before deciding what action to take.

**Current State:**
- Uses simple if/else logic based on `forced_diagram_type` parameter
- No intent detection - decisions are rule-based, not reasoning-based

**Proposed State:**
- Use ReAct pattern: REASON → ACT → OBSERVE
- Intent detection analyzes user prompt to determine scenario
- Actions executed based on detected intent, not just parameters

**Next Steps:**
1. Implement ReAct pattern with intent detection (REASON step)
2. Refactor workflow to use ReAct-based decision making (ACT step)
3. Centralize double bubble map prompts
4. Enhance topic extraction prompt for Scenario 2
5. Add comprehensive tests for all three scenarios with ReAct

