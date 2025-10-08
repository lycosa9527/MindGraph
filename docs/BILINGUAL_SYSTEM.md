# MindGraph Bilingual System Architecture

## Overview

MindGraph is designed to support **K-12 teachers** with **Chinese (zh) as the primary language** and **English (en) as the secondary language**. The entire application—from frontend UI to backend API errors—must be fully bilingual.

---

## Architecture

### 1. Frontend Translation System

**File**: `static/js/editor/language-manager.js`

**Status**: ✅ **COMPLETE & CENTRALIZED**

#### Features:
- **Default Language**: Chinese (`zh`)
- **Switch Button**: Shows opposite language (中文 in EN mode, EN in ZH mode)
- **All UI Elements Translated**:
  - Gallery interface (diagram types, descriptions)
  - Editor toolbar (Add, Delete, Auto, Line, Empty, Undo, Redo)
  - Properties panel (labels, inputs, buttons)
  - MindMate AI panel (title, status, welcome message, placeholder)
  - Tooltips (all button tooltips)
  - Learning mode (questions, feedback, progress)
  - Notifications (success, error, warning, info)
  - Node editor (modal dialogs)

#### API:
```javascript
// Get current language
languageManager.currentLanguage // 'zh' or 'en'

// Translate UI element
languageManager.translate('add') // '添加' (zh) or 'Add' (en)

// Get notification message
languageManager.getNotification('nodeAdded') // '节点已添加！双击编辑文本。' (zh)

// Toggle language
languageManager.toggleLanguage()
```

#### Translation Coverage:
```javascript
translations: {
  en: {
    // Main page
    mainTitle: 'MindGraph Pro',
    mainSubtitle: 'The universe\'s most powerful AI diagram generation software',
    
    // Toolbar
    add: 'Add',
    delete: 'Delete',
    auto: 'Auto',
    
    // Notifications
    notif: {
      textEmpty: 'Text cannot be empty',
      nodeAdded: 'Node added! Double-click to edit text.',
      nodesDeleted: (count) => `Deleted ${count} node${count > 1 ? 's' : ''}`
    }
  },
  zh: {
    // Main page
    mainTitle: 'MindGraph专业版',
    mainSubtitle: '宇宙中最强大的AI思维图示生成软件',
    
    // Toolbar
    add: '添加',
    delete: '删除',
    auto: '自动',
    
    // Notifications
    notif: {
      textEmpty: '文本不能为空',
      nodeAdded: '节点已添加！双击编辑文本。',
      nodesDeleted: (count) => `已删除 ${count} 个节点`
    }
  }
}
```

---

### 2. Frontend Notification System

**File**: `static/js/editor/notification-manager.js`

**Status**: ✅ **COMPLETE & CENTRALIZED**

#### Features:
- **Centralized**: All notifications go through `NotificationManager`
- **Smart queue**: Max 3 visible, others wait in queue
- **Type-based duration**: Success (2s), Info (3s), Warning (4s), Error (5s)
- **Smooth animations**: Slide-in/slide-out from right
- **Bilingual support**: Uses `LanguageManager` for all messages

#### API:
```javascript
// Show notification in current language
window.notificationManager.show(
  languageManager.getNotification('nodeAdded'), // Bilingual message
  'success',
  2000
);
```

---

### 3. Backend API Error Messages

**File**: `models/messages.py`

**Status**: ✅ **COMPLETE & CENTRALIZED** (as of FastAPI migration)

#### Features:
- **Bilingual errors**: All API errors return messages in zh/en
- **Language detection**: Reads `X-Language` header or `Accept-Language`
- **Parameterized messages**: Support for dynamic error details

#### API:
```python
from models import Messages, get_request_language

# In API endpoint
lang = get_request_language(x_language_header)

# Raise bilingual error
raise HTTPException(
    status_code=400,
    detail=Messages.error("message_required", lang)
)
# Returns: "消息不能为空" (zh) or "Message is required" (en)

# Parameterized error
raise HTTPException(
    status_code=500,
    detail=Messages.error("generation_failed", lang, str(e))
)
# Returns: "生成图示失败：{error}" (zh) or "Failed to generate graph: {error}" (en)
```

#### Error Categories:
```python
class Messages:
    ERRORS = {
        "message_required": {"zh": "消息不能为空", "en": "Message is required"},
        "ai_not_configured": {"zh": "AI助手未配置", "en": "AI assistant not configured"},
        "invalid_prompt": {"zh": "提示词无效或为空", "en": "Invalid or empty prompt"},
        "diagram_data_required": {"zh": "需要图示数据", "en": "Diagram data is required"},
        "generation_failed": {"zh": "生成图示失败：{}", "en": "Failed to generate graph: {}"},
        "export_failed": {"zh": "导出PNG失败：{}", "en": "PNG export failed: {}"}
    }
    
    SUCCESS = {
        "diagram_generated": {"zh": "图示生成成功", "en": "Diagram generated successfully"}
    }
    
    WARNINGS = {
        "slow_request": {"zh": "请求处理较慢", "en": "Slow request processing"}
    }
```

---

### 4. Backend Logging System

**Status**: ✅ **CENTRALIZED** (English-only, for developers)

#### Philosophy:
- **Backend logs**: English-only (for developers, not end-users)
- **API errors**: Bilingual (for end-users)

#### Implementation:
```python
import logging

logger = logging.getLogger(__name__)

# Logs are in English (for developers)
logger.info(f"[{request_id}] Request: llm={llm_model}, language={language}")
logger.error(f"[{request_id}] Error generating graph: {e}", exc_info=True)

# But API responses are bilingual (for users)
raise HTTPException(
    status_code=500,
    detail=Messages.error("generation_failed", lang, str(e))
)
```

---

### 5. Agent Prompts (LLM Input)

**Files**: `prompts/*.py`

**Status**: ✅ **COMPLETE & BILINGUAL**

#### Features:
- **Language-specific prompts**: Each diagram type has `_zh` and `_en` versions
- **Quality optimization**: Chinese prompts include examples to ensure quality

#### Structure:
```python
PROMPT_REGISTRY = {
    "bubble_map_generation_zh": "...",  # Chinese prompt
    "bubble_map_generation_en": "...",  # English prompt
}

def get_prompt(diagram_type: str, language: str = 'en') -> str:
    key = f"{diagram_type}_generation_{language}"
    return PROMPT_REGISTRY.get(key, "")
```

---

## Frontend-Backend Language Flow

### Scenario 1: User selects Chinese, generates diagram

```
[Frontend]
1. User clicks language toggle → languageManager.currentLanguage = 'zh'
2. User generates diagram → API call includes language='zh'

[Backend]
3. Agent uses Chinese prompt from prompts/thinking_maps.py
4. LLM generates Chinese content
5. Returns: { "diagram_type": "bubble_map", "language": "zh", ... }

[Frontend]
6. Editor renders with Chinese labels: languageManager.translate('newAttribute') → '新属性'
```

### Scenario 2: User in English mode, API error occurs

```
[Frontend]
1. User in EN mode → sends X-Language: 'en' header (or Accept-Language: en-US)
2. Invalid request → API call fails

[Backend]
3. get_request_language() detects 'en'
4. Returns: HTTPException(detail=Messages.error("invalid_prompt", "en"))
   → "Invalid or empty prompt"

[Frontend]
5. Error displayed in English via notification system
```

---

## Developer Guidelines

### Adding New Translations

#### Frontend (UI/Notifications):
1. Edit `static/js/editor/language-manager.js`
2. Add to both `en` and `zh` sections:
   ```javascript
   en: {
     myNewButton: 'My Button',
     notif: {
       myNewNotification: 'Operation successful'
     }
   },
   zh: {
     myNewButton: '我的按钮',
     notif: {
       myNewNotification: '操作成功'
     }
   }
   ```

#### Backend (API Errors):
1. Edit `models/messages.py`
2. Add to `ERRORS`, `SUCCESS`, or `WARNINGS`:
   ```python
   "my_error": {
       "zh": "错误描述",
       "en": "Error description"
   }
   ```

#### Agent Prompts (LLM):
1. Edit `prompts/*.py`
2. Add both language versions:
   ```python
   MY_DIAGRAM_GENERATION_ZH = "..."
   MY_DIAGRAM_GENERATION_EN = "..."
   
   PROMPT_REGISTRY = {
       "my_diagram_generation_zh": MY_DIAGRAM_GENERATION_ZH,
       "my_diagram_generation_en": MY_DIAGRAM_GENERATION_EN,
   }
   ```

---

## Testing Bilingual Support

### Frontend:
```javascript
// Test language toggle
languageManager.toggleLanguage();
console.log(languageManager.currentLanguage); // Should alternate zh/en

// Test translation
console.log(languageManager.translate('add')); // '添加' or 'Add'

// Test notification
window.notificationManager.show(
    languageManager.getNotification('nodeAdded'),
    'success'
);
```

### Backend:
```python
# Test error messages
from models import Messages

assert Messages.error("invalid_prompt", "zh") == "提示词无效或为空"
assert Messages.error("invalid_prompt", "en") == "Invalid or empty prompt"

# Test parameterized messages
error_msg = Messages.error("generation_failed", "zh", "connection timeout")
assert "connection timeout" in error_msg
```

---

## Compliance Checklist

### ✅ Complete:
- [x] Frontend UI fully bilingual (zh/en)
- [x] Frontend notifications centralized + bilingual
- [x] Backend API errors centralized + bilingual
- [x] Agent prompts bilingual (zh/en)
- [x] Dynamic node creation bilingual
- [x] Learning mode bilingual
- [x] Properties panel bilingual
- [x] AI assistant panel bilingual

### ❌ NOT Bilingual (by design):
- Backend logs (English-only, for developers)
- Server startup banners (English-only, for ops)
- Code comments/docstrings (English-only, for developers)

---

## Future Enhancements

1. **Add more languages** (e.g., Japanese, Korean):
   - Add `ja`, `ko` to `language-manager.js`
   - Add `ja`, `ko` to `models/messages.py`
   - Add `_ja`, `_ko` prompt versions

2. **Automatic language detection**:
   - Detect browser language on first visit
   - Store preference in localStorage

3. **Translation validation**:
   - CI/CD check: ensure all keys have both zh/en
   - Automated tests for missing translations

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     USER (K-12 Teacher)                     │
│                    Language: zh (default)                   │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                  FRONTEND (Browser)                         │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  language-manager.js                                  │ │
│  │  - currentLanguage: 'zh' or 'en'                      │ │
│  │  - translate(key) → UI text                           │ │
│  │  - getNotification(key) → notification text           │ │
│  └───────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  notification-manager.js                              │ │
│  │  - show(message, type) → toast notification           │ │
│  │  - Uses LanguageManager for all messages              │ │
│  └───────────────────────────────────────────────────────┘ │
└──────────────────┬────────────────────────┬─────────────────┘
                   │                        │
        API Request (zh/en)      X-Language: zh/en header
                   │                        │
                   ▼                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  BACKEND (FastAPI)                          │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  models/messages.py                                   │ │
│  │  - Messages.error(key, lang) → bilingual error        │ │
│  │  - get_request_language() → detect lang from headers  │ │
│  └───────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  routers/api.py                                       │ │
│  │  - All endpoints return bilingual errors              │ │
│  │  - HTTPException(detail=Messages.error(..., lang))    │ │
│  └───────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  prompts/*.py                                         │ │
│  │  - BUBBLE_MAP_GENERATION_ZH = "..."                   │ │
│  │  - BUBBLE_MAP_GENERATION_EN = "..."                   │ │
│  │  - get_prompt(type, language) → LLM prompt            │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Conclusion

MindGraph's bilingual system is **fully centralized** and covers:

1. **Frontend**: UI, notifications, tooltips, modals (via `language-manager.js`)
2. **Backend**: API errors, success messages (via `models/messages.py`)
3. **AI**: LLM prompts for diagram generation (via `prompts/*.py`)

**All user-facing text** is available in **Chinese (zh)** and **English (en)**, making MindGraph accessible to K-12 teachers globally.

