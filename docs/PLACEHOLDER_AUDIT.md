# Prompt Placeholder Usage Audit

**Date:** 2025-10-05  
**Purpose:** Verify if `{user_prompt}` placeholders in prompt templates are being used

---

## Summary

**Finding:** `{user_prompt}` placeholders in **9 out of 11 diagram types** are **NEVER filled** - they appear as literal text in prompts sent to the LLM.

### Affected Diagrams (Placeholders NOT Used)
1. ✅ Bridge Map
2. ✅ Bubble Map  
3. ✅ Circle Map
4. ✅ Double Bubble Map
5. ✅ Tree Map
6. ✅ Brace Map
7. ✅ Flow Map
8. ✅ Multi-Flow Map
9. ✅ Mind Map

### Working Correctly (Placeholders ARE Used)
1. ❌ Concept Map - Uses `.format(**kwargs)`
2. ❌ Main Agent (classification) - Uses `.format(user_prompt=...)`

---

## Evidence

### Example: Bridge Map (BROKEN)

**Prompt Template** (`prompts/thinking_maps.py` line 20):
```python
BRIDGE_MAP_GENERATION_EN = """Please generate a JSON specification for a bridge map for the following user request.

Request: {user_prompt}

CRITICAL REQUIREMENTS - READ CAREFULLY:
...
"""
```

**Agent Code** (`agents/thinking_maps/bridge_map_agent.py` line 123):
```python
system_prompt = get_prompt("bridge_map_agent", language, "generation")
# ↑ Gets template with literal "{user_prompt}" text

user_prompt = f"请为以下描述创建一个桥形图：{prompt}"
# ↑ Creates SEPARATE user message

messages = [
    {"role": "system", "content": system_prompt},  # Has "{user_prompt}" as literal text!
    {"role": "user", "content": user_prompt}
]
```

**What LLM Receives:**
- **System**: "Request: {user_prompt}" ← Literal placeholder!
- **User**: "请为以下描述创建一个桥形图：iPhone"

**Problem**: The LLM sees `{user_prompt}` as literal text, not as the actual prompt.

---

## All Affected Agents (Same Pattern)

### Bridge Map
```python
# Line 123
system_prompt = get_prompt("bridge_map_agent", language, "generation")
# Line 132
user_prompt = f"请为以下描述创建一个桥形图：{prompt}"
# NO .format() call!
```

### Bubble Map
```python
# Line 78
system_prompt = get_prompt("bubble_map_agent", language, "generation")
# Line 84
user_prompt = f"请为以下描述创建一个气泡图：{prompt}"
```

### Circle Map
```python
# Line 78
system_prompt = get_prompt("circle_map_agent", language, "generation")
# Line 84
user_prompt = f"请为以下描述创建一个圆圈图：{prompt}"
```

### Double Bubble Map
```python
# Line 83
system_prompt = get_prompt("double_bubble_map_agent", language, "generation")
# Line 90
user_prompt = f"请为以下描述创建一个双气泡图：{topics}"
```

### Tree Map
```python
# Line 82
system_prompt = get_prompt("tree_map_agent", language, "generation")
# Line 88
user_prompt = f"请为以下描述创建一个树形图：{prompt}"
```

### Brace Map
```python
# Line 1175
system_prompt = get_prompt("brace_map_agent", language, "generation")
# Line 1181
user_prompt = f"请为以下描述创建一个括号图：{prompt}"
```

### Flow Map
```python
# Line 81
system_prompt = get_prompt("flow_map_agent", language, "generation")
# Line 87
user_prompt = f"请为以下描述创建一个流程图：{prompt}"
```

### Multi-Flow Map
```python
# Line 78
system_prompt = get_prompt("multi_flow_map_agent", language, "generation")
# Line 84
user_prompt = f"请为以下描述创建一个复流程图：{prompt}"
```

### Mind Map
```python
# Line 124
system_prompt = get_prompt("mind_map", language, "generation")
# Line 130
user_prompt = f"请为以下描述创建一个思维导图：{prompt}"
```

---

## Concept Map (WORKING CORRECTLY)

**Prompt Template** (`prompts/concept_maps.py`):
```python
CONCEPT_MAP_V2_FALLBACK_SYSTEM_EN = """...
Topic: {user_prompt}
...
"""
```

**Agent Code** (`agents/concept_maps/concept_map_agent.py` line 456):
```python
prompt_template = CONCEPT_MAP_PROMPTS.get(zh_key)
if prompt_template:
    return prompt_template.format(**kwargs)  # ✅ FILLS THE PLACEHOLDER!
```

**This one works correctly because it calls `.format()`**

---

## Main Agent (WORKING CORRECTLY)

**Code** (`agents/main_agent.py` line 559):
```python
return llm_classification._call(prompt.format(user_prompt=user_prompt))
```

**This one also works correctly**

---

## Impact Analysis

### Current Behavior (With Literal Placeholders)

**LLM receives:**
```
System: "Please generate JSON for the following user request.

Request: {user_prompt}

CRITICAL REQUIREMENTS: ..."

User: "Please create a bridge map for the following description: iPhone"
```

The `{user_prompt}` appears as literal text, potentially confusing the LLM.

### Expected Behavior (Without Placeholders)

**LLM should receive:**
```
System: "Please generate JSON for a bridge map.

CRITICAL REQUIREMENTS: ..."

User: "Please create a bridge map for the following description: iPhone"
```

Clean system prompt without confusing placeholder text.

---

## Why Hasn't This Caused Issues?

The LLMs are smart enough to:
1. Ignore the literal `{user_prompt}` text
2. Focus on the actual user message
3. Still generate correct output

But it's **inefficient** and **confusing**:
- Wasted tokens (sending unnecessary placeholder text)
- Potential confusion for the LLM
- Makes prompts look unprofessional

---

## Solution

### Option 1: Remove Placeholders from Templates (RECOMMENDED)

Remove the `Request: {user_prompt}` lines from all prompt templates since they're not being used.

**Pros:**
- ✅ Clean, professional prompts
- ✅ Reduced token usage
- ✅ No code changes to agents
- ✅ Fast to implement

**Cons:**
- None

### Option 2: Make Agents Use Placeholders

Update all agents to call `.format(user_prompt=prompt)` like ConceptMapAgent does.

**Pros:**
- ✅ Consistent with ConceptMapAgent
- ✅ Could be useful for future features

**Cons:**
- ❌ More code changes
- ❌ Not needed since agents already pass prompt in user message
- ❌ Redundant (prompt appears twice)

---

## Recommended Action

**Remove the unused placeholders** from these files:

1. `prompts/thinking_maps.py`:
   - Lines with `Request: {user_prompt}` (EN versions)
   - Lines with `需求：{user_prompt}` (ZH versions)
   - Affects: Bridge, Bubble, Circle, Double Bubble, Tree, Brace, Flow, Multi-Flow maps

2. `prompts/mind_maps.py`:
   - Remove any `{user_prompt}` references
   - Mind Map prompts

### Files to Modify
- `prompts/thinking_maps.py` (8 diagram types × 2 languages = 16 changes)
- `prompts/mind_maps.py` (1 diagram type × 2 languages = 2 changes)

### Files to Keep As-Is
- `prompts/concept_maps.py` (already working correctly)
- `prompts/main_agent.py` (already working correctly)

---

## Token Savings

Each placeholder line wastes approximately:
- English: `Request: {user_prompt}` = 5 tokens
- Chinese: `需求：{user_prompt}` = 4 tokens

**Total savings per request**: ~5 tokens  
**Requests per day**: ~1,000  
**Daily savings**: ~5,000 tokens  
**Monthly savings**: ~150,000 tokens

**Cost savings**: Minimal but adds up over time.

---

## Verification Steps

After removing placeholders:

1. Test all 9 affected diagram types
2. Verify LLM still generates correct JSON
3. Compare output quality before/after
4. Monitor for any regressions

Expected result: **No change in functionality**, just cleaner prompts.

---

**Recommendation: Proceed with Option 1 - Remove all unused `{user_prompt}` placeholders**

