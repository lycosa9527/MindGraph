# Main Agent Architecture Analysis

**Date:** 2024-12-19  
**Question:** What framework/pattern does the main agent currently use?

---

## Current Architecture: Prompt Engineering + Sequential LLM Calls

### Framework Classification

The main agent (`agents/main_agent.py`) uses **Prompt Engineering** with **Sequential LLM Calls**, NOT ReAct pattern.

### Architecture Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    MAIN AGENT WORKFLOW                      │
│                  (Prompt Engineering)                       │
└─────────────────────────────────────────────────────────────┘

User Prompt
    │
    ├─→ [Step 1: Classification]
    │   └─→ LLM Call with Classification Prompt
    │       └─→ Returns: diagram_type
    │
    ├─→ [Step 2: Topic Extraction] (if not forced_diagram_type)
    │   └─→ LLM Call with Topic Extraction Prompt
    │       └─→ Returns: extracted_topic
    │
    └─→ [Step 3: Generation] (if forced_diagram_type)
        └─→ Route to Specialized Agent
            └─→ LLM Call with Generation Prompt
                └─→ Returns: diagram_spec
```

### Key Characteristics

1. **Prompt Engineering**
   - Uses carefully crafted prompts from `prompts/` directory
   - Each step has a dedicated prompt template
   - Prompts guide LLM behavior through examples and instructions

2. **Sequential LLM Calls**
   - Step-by-step processing: Classification → Extraction → Generation
   - Each step is a separate LLM call
   - No reasoning loop or iterative refinement

3. **Rule-Based Routing**
   - Simple if/else logic based on parameters
   - `forced_diagram_type` parameter determines flow
   - No intent reasoning or adaptive decision making

### Code Flow Example

```python
async def agent_graph_workflow_with_styles(...):
    # Rule-based decision (not ReAct)
    if forced_diagram_type:
        diagram_type = forced_diagram_type
    else:
        # Sequential LLM call 1: Classification
        detection_result = await _detect_diagram_type_from_prompt(...)
        diagram_type = detection_result['diagram_type']
    
    # Rule-based decision (not ReAct)
    if not forced_diagram_type:
        # Sequential LLM call 2: Topic Extraction
        topic_extraction_prompt = get_prompt("topic_extraction", ...)
        main_topic = await llm_service.chat(...)
        return {'extracted_topic': main_topic, 'use_default_template': True}
    else:
        # Sequential LLM call 3: Generation
        spec = await _generate_spec_with_agent(...)
        return {'spec': spec}
```

---

## Comparison: Main Agent vs Thinking Mode Agents

### Main Agent (Current)
```
Pattern: Prompt Engineering + Sequential LLM Calls
Decision Making: Rule-based (if/else)
Intent Detection: None (uses parameters)
Reasoning: None (sequential steps)
```

### Thinking Mode Agents (ReAct)
```
Pattern: ReAct (Reason → Act → Observe)
Decision Making: Intent-based
Intent Detection: LLM-based (_detect_user_intent)
Reasoning: Yes (REASON step analyzes intent)
```

### Side-by-Side Comparison

| Aspect | Main Agent | Thinking Mode Agents |
|--------|-----------|---------------------|
| **Pattern** | Prompt Engineering | ReAct |
| **Decision Making** | Rule-based (if/else) | Intent-based |
| **Intent Detection** | ❌ None | ✅ LLM-based |
| **Reasoning** | ❌ Sequential steps | ✅ REASON step |
| **Adaptability** | ⚠️ Limited | ✅ High |
| **LLM Calls** | Sequential (1-3 calls) | Iterative (REASON → ACT → OBSERVE) |

---

## Why Not ReAct Currently?

### Current Approach Benefits
1. **Simplicity**: Straightforward sequential flow
2. **Performance**: Fewer LLM calls (1-3 vs potentially more)
3. **Predictability**: Rule-based routing is deterministic
4. **Cost**: Lower token usage (no reasoning loops)

### Current Approach Limitations
1. **Inflexibility**: Cannot adapt to nuanced requests
2. **Parameter Dependency**: Relies on `forced_diagram_type` parameter
3. **No Intent Understanding**: Doesn't reason about user's actual intent
4. **Edge Cases**: May not handle ambiguous requests well

---

## Should Main Agent Use ReAct?

### Arguments FOR ReAct
1. **Better Intent Understanding**: Can analyze user prompt semantically
2. **Flexibility**: Handles edge cases and ambiguous requests
3. **Consistency**: Matches thinking mode agents' architecture
4. **Adaptability**: Can reason about user's actual intent, not just parameters

### Arguments AGAINST ReAct
1. **Complexity**: More complex than current simple flow
2. **Performance**: Additional LLM call for intent detection
3. **Cost**: Higher token usage
4. **Current Works**: Simple approach works for most cases

### Recommendation

**Hybrid Approach**: Use ReAct for intent detection, but keep sequential flow for execution.

```
REASON: Detect user intent (1 LLM call)
    ↓
ACT: Execute based on intent (1-2 LLM calls)
    ↓
OBSERVE: Return response
```

This gives:
- ✅ Intent understanding (ReAct benefit)
- ✅ Simple execution flow (current benefit)
- ✅ Moderate complexity increase
- ✅ One additional LLM call (acceptable cost)

---

## Current Framework Summary

**Framework Name**: Prompt Engineering with Sequential LLM Calls

**Pattern**: 
- Not ReAct
- Not LangChain Agents
- Not AutoGPT/Agentic loops
- Simple prompt-based LLM orchestration

**Architecture**:
- Centralized prompts (`prompts/` directory)
- Sequential LLM calls
- Rule-based routing
- Modular agent delegation

**Decision Making**:
- Parameter-based (not intent-based)
- Rule-based (not reasoning-based)
- Sequential (not iterative)

---

## Conclusion

The main agent currently uses **Prompt Engineering** with **Sequential LLM Calls**, NOT ReAct pattern. It's a simpler, more straightforward approach that works well for most cases but lacks the reasoning and adaptability of ReAct.

**Recommendation**: Consider adopting ReAct pattern for intent detection while keeping the sequential execution flow for performance and simplicity.




