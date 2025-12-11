# ReAct LLM Call Analysis: Current vs Proposed

**Date:** 2024-12-19  
**Question:** How many LLM calls would ReAct require vs current approach?

---

## Current Approach: LLM Call Count

### Scenario 1: User provides prompt → System picks diagram
```
Flow:
1. Classification LLM call → detect diagram_type
2. Topic Extraction LLM call → extract topic
3. Return {diagram_type, extracted_topic, use_default_template: True}

Total: 2 LLM calls
```

### Scenario 2: User knows diagram type → System fills topic
```
Flow:
1. Topic Extraction LLM call → extract topic (if implemented)
2. Return {diagram_type, extracted_topic, use_default_template: True}

Total: 1 LLM call (currently not implemented - goes to Scenario 3)
```

### Scenario 3: User provides topic + diagram + instructions → System builds diagram
```
Flow:
1. Generation LLM call → generate full spec
2. Return {spec, diagram_type, ...}

Total: 1 LLM call
```

### Current Total Summary

| Scenario | LLM Calls | Breakdown |
|----------|-----------|-----------|
| Scenario 1 | **2 calls** | Classification + Topic Extraction |
| Scenario 2 | **1 call** | Topic Extraction (not currently implemented) |
| Scenario 3 | **1 call** | Generation |

---

## Proposed ReAct Approach: LLM Call Count

### ReAct Pattern Structure
```
REASON Step: 1 LLM call (intent detection)
    ↓
ACT Step: 1-2 LLM calls (based on intent)
    ↓
OBSERVE Step: No LLM call (just return response)
```

### Scenario 1: User provides prompt → System picks diagram
```
Flow:
1. REASON: Intent Detection LLM call → detect intent = "detect_and_extract"
2. ACT: Classification LLM call → detect diagram_type
3. ACT: Topic Extraction LLM call → extract topic
4. OBSERVE: Return {diagram_type, extracted_topic, use_default_template: True}

Total: 3 LLM calls (+1 from current)
```

### Scenario 2: User knows diagram type → System fills topic
```
Flow:
1. REASON: Intent Detection LLM call → detect intent = "extract_topic_only"
2. ACT: Topic Extraction LLM call → extract topic
3. OBSERVE: Return {diagram_type, extracted_topic, use_default_template: True}

Total: 2 LLM calls (+1 from current, but enables Scenario 2)
```

### Scenario 3: User provides topic + diagram + instructions → System builds diagram
```
Flow:
1. REASON: Intent Detection LLM call → detect intent = "generate_full_spec"
2. ACT: Generation LLM call → generate full spec
3. OBSERVE: Return {spec, diagram_type, ...}

Total: 2 LLM calls (+1 from current)
```

### ReAct Total Summary

| Scenario | LLM Calls | Breakdown |
|----------|-----------|-----------|
| Scenario 1 | **3 calls** | REASON (intent) + Classification + Topic Extraction |
| Scenario 2 | **2 calls** | REASON (intent) + Topic Extraction |
| Scenario 3 | **2 calls** | REASON (intent) + Generation |

---

## Cost Comparison

### Current Approach
- **Scenario 1**: 2 calls
- **Scenario 2**: 1 call (not implemented)
- **Scenario 3**: 1 call
- **Average**: ~1.5 calls per request

### ReAct Approach
- **Scenario 1**: 3 calls (+50% increase)
- **Scenario 2**: 2 calls (+100% increase, but enables new scenario)
- **Scenario 3**: 2 calls (+100% increase)
- **Average**: ~2.3 calls per request (+53% increase)

### Token Usage Estimate

**Current (Scenario 1):**
- Classification: ~100 tokens (prompt) + ~50 tokens (response) = 150 tokens
- Topic Extraction: ~200 tokens (prompt) + ~50 tokens (response) = 250 tokens
- **Total: ~400 tokens**

**ReAct (Scenario 1):**
- Intent Detection: ~300 tokens (prompt) + ~100 tokens (response) = 400 tokens
- Classification: ~100 tokens (prompt) + ~50 tokens (response) = 150 tokens
- Topic Extraction: ~200 tokens (prompt) + ~50 tokens (response) = 250 tokens
- **Total: ~800 tokens (+100% increase)**

---

## Optimization Strategies

### Strategy 1: Combine REASON + Classification (Hybrid)
```
Flow:
1. REASON+CLASSIFY: Single LLM call → detect intent + diagram_type
2. ACT: Topic Extraction or Generation based on intent
3. OBSERVE: Return response

Scenario 1: 2 calls (same as current!)
Scenario 2: 2 calls
Scenario 3: 2 calls
```

**Benefits:**
- ✅ No increase for Scenario 1
- ✅ Enables Scenario 2
- ✅ Only +1 call for Scenario 3
- ✅ Better intent understanding

**Implementation:**
```python
async def _reason_and_classify(user_prompt, language, forced_diagram_type, ...):
    """
    Combined REASON + Classification step.
    Returns: {'intent': ..., 'diagram_type': ..., 'confidence': ...}
    """
    prompt = f"""
    Analyze user intent AND detect diagram type:
    
    User prompt: {user_prompt}
    Diagram type provided: {forced_diagram_type or 'None'}
    
    Return JSON:
    {{
      "intent": "detect_and_extract" | "extract_topic_only" | "generate_full_spec",
      "diagram_type": "bubble_map" | "tree_map" | ...,
      "confidence": 0.0-1.0,
      "reasoning": "..."
    }}
    """
    # Single LLM call
    return await llm_service.chat(...)
```

### Strategy 2: Conditional REASON (Only When Needed)
```
Flow:
- If forced_diagram_type is None → REASON+CLASSIFY (combined)
- If forced_diagram_type is set → Check if prompt has instructions
  - If minimal prompt → REASON (intent only) → Topic Extraction
  - If detailed prompt → Skip REASON → Direct Generation

Scenario 1: 2 calls (REASON+CLASSIFY combined)
Scenario 2: 2 calls (REASON + Topic Extraction)
Scenario 3: 1 call (Skip REASON, direct generation)
```

**Benefits:**
- ✅ Scenario 1: Same as current (2 calls)
- ✅ Scenario 2: Enables new scenario (2 calls)
- ✅ Scenario 3: Same as current (1 call)
- ✅ Smart skipping when intent is obvious

### Strategy 3: Cached Intent Detection
```
Flow:
- Cache intent detection results for similar prompts
- Use cache when prompt is very similar to previous request
- Only call REASON when prompt is significantly different

Benefits:
- ✅ Reduces LLM calls for repeated/similar requests
- ✅ Faster response times
- ✅ Lower costs
```

---

## Recommended Approach: Strategy 1 (Hybrid REASON+CLASSIFY)

### Why This Is Best

1. **No Cost Increase for Scenario 1**
   - Current: 2 calls
   - ReAct: 2 calls (REASON+CLASSIFY combined + Topic Extraction)

2. **Enables Scenario 2**
   - Can detect when user just wants topic extraction
   - Only 2 calls needed

3. **Minimal Increase for Scenario 3**
   - Current: 1 call
   - ReAct: 2 calls (+1, but enables better intent understanding)

4. **Better Intent Understanding**
   - Single call analyzes both intent and diagram type
   - More context-aware decisions

### Implementation Example

```python
async def agent_graph_workflow_with_styles(...):
    # REASON + CLASSIFY: Combined step (1 LLM call)
    reasoning_result = await _reason_and_classify(
        user_prompt,
        language,
        forced_diagram_type,
        ...
    )
    
    intent = reasoning_result['intent']
    diagram_type = reasoning_result['diagram_type']
    
    # ACT: Execute based on intent
    if intent == 'detect_and_extract':
        # Topic extraction (1 LLM call)
        topic = await _extract_topic(...)
        return {'diagram_type': diagram_type, 'extracted_topic': topic, ...}
    
    elif intent == 'extract_topic_only':
        # Topic extraction (1 LLM call)
        topic = await _extract_topic(...)
        return {'diagram_type': diagram_type, 'extracted_topic': topic, ...}
    
    elif intent == 'generate_full_spec':
        # Generation (1 LLM call)
        spec = await _generate_spec(...)
        return {'spec': spec, 'diagram_type': diagram_type, ...}
```

### Final Call Count Comparison

| Scenario | Current | ReAct (Hybrid) | Increase |
|----------|---------|----------------|----------|
| Scenario 1 | 2 calls | 2 calls | **0%** ✅ |
| Scenario 2 | N/A | 2 calls | **New** ✅ |
| Scenario 3 | 1 call | 2 calls | **+100%** ⚠️ |

---

## Conclusion

### Pure ReAct Approach
- **+1 LLM call** for all scenarios
- **+50-100% cost increase**
- Better intent understanding

### Hybrid ReAct Approach (Recommended)
- **0% increase** for Scenario 1 (most common)
- **+100% increase** for Scenario 3 (but enables better intent understanding)
- **Enables Scenario 2** (new capability)

### Recommendation

**Use Hybrid ReAct (Strategy 1):**
- Combine REASON + Classification in single LLM call
- No cost increase for most common scenario
- Better intent understanding
- Enables Scenario 2 support
- Minimal cost increase for Scenario 3

**Total LLM Calls:**
- Scenario 1: **2 calls** (same as current)
- Scenario 2: **2 calls** (new capability)
- Scenario 3: **2 calls** (+1 from current, but better intent understanding)




