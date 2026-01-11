# AskOnce Code Review

**Date:** 2026-01-11  
**Status:** Review Complete

## Overview

AskOnce is a multi-LLM comparison feature that allows users to send a single prompt to 3 different LLMs (Qwen, DeepSeek, Kimi) simultaneously and compare their responses.

---

## Issues Fixed

### 1. Backend Multi-turn Context (Critical) - FIXED

**Files:** `services/llm_service.py`, `routers/askonce.py`

**Problem:** Assistant messages were concatenated with `[Assistant]:` prefix into a single prompt string, destroying proper message structure for multi-turn conversations.

**Solution:** Added `messages` parameter to `llm_service.chat_stream()` for proper multi-turn support. LLMs now receive proper `[{role: "user"}, {role: "assistant"}, ...]` format.

### 2. Thinking Content Not Persisted (Critical) - FIXED

**Files:** `frontend/src/stores/askonce.ts`, `frontend/src/pages/AskOncePage.vue`

**Problem:** Thinking/reasoning content was lost when revisiting old conversations.

**Solution:** Created `PersistedResponse` interface with `content` and `thinking` fields. Added migration logic for old formats.

### 3. No Stop Button for Individual Models (Medium) - FIXED

**File:** `frontend/src/components/askonce/AskOncePanel.vue`

**Problem:** Users couldn't stop a single model's stream.

**Solution:** Added stop button in footer during streaming that calls `store.abortStream(modelId)`.

### 4. No Conversation Title Display (Medium) - FIXED

**File:** `frontend/src/pages/AskOncePage.vue`

**Problem:** Header showed only "AskOnce" without indicating which conversation was active.

**Solution:** Header now shows: "AskOnce | Conversation Name"

### 5. Unused Code Cleanup (Low) - FIXED

**Files:** Multiple

**Items removed:**
- `EMPTY_MODEL_RESPONSES` constant (never used)
- `displayName` prop from AskOncePanel (passed but never displayed)
- `displayName` from MODEL_CONFIG

---

## Remaining Issues (Not Yet Implemented)

### Medium Priority

#### 6. Only Last Response Visible

**Current behavior:** Each panel shows only the most recent response.

**Expected (like ChatGPT):** Show full conversation history with alternating user/assistant messages.

**Effort:** High

#### 7. Token Count Not Persisted Per-Response

**Problem:** Tokens show `0` when loading a conversation because they're not saved in `modelResponses`.

**Effort:** Low

### Low Priority

#### 8. No Retry for Individual Model

**Problem:** If DeepSeek errors but Qwen succeeds, user must resend to all 3 models.

**Recommendation:** Allow retry for just the failed model.

**Effort:** Medium

#### 9. No Code Syntax Highlighting

**Problem:** Using basic `markdown-it` without `highlight.js` plugin. Code blocks lack syntax coloring.

**Effort:** Low

#### 10. No Dark Mode Support

**Problem:** Panel styles are hardcoded light mode colors (e.g., `bg-gray-50`, `text-gray-700`).

**Effort:** Medium

---

## UX Improvements (Nice to Have)

| Issue | Description | Effort |
|-------|-------------|--------|
| No loading spinner on Send | Button just disables, no visual feedback | Low |
| No response time display | Can't compare which model is faster | Medium |
| No export/share | Can't share comparison results | Medium |
| No model health indicator | Don't know if a model is down before sending | Medium |
| No reconnection UI | No way to retry if network fails mid-stream | Medium |

---

## Architecture

```
Frontend Layer:
├── AskOncePage.vue        - Main page with input and 3 panels
├── AskOncePanel.vue       - Individual model response panel
└── askonce.ts (Store)     - State management with localStorage persistence

Backend Layer:
├── askonce.py (Router)    - SSE streaming endpoints
└── llm_service.py         - Centralized LLM infrastructure

LLM Models:
├── Qwen (qwen3-235b-a22b-thinking)
├── DeepSeek (deepseek-v3.2, load balanced)
└── Kimi (ark-kimi via Volcengine)
```

---

## Data Structure

### Conversation Format (Current)

```typescript
interface AskOnceConversation {
  id: string
  name: string
  userMessages: string[]                          // Shared user messages
  modelResponses: Record<ModelId, PersistedResponse[]>  // Per-model with thinking
  systemPrompt: string
  createdAt: number
  updatedAt: number
}

interface PersistedResponse {
  content: string
  thinking: string
}
```

### Migration Support

The store automatically migrates old conversation formats:
1. `messages[]` array (oldest) → new format
2. `string[]` modelResponses (intermediate) → `PersistedResponse[]`
