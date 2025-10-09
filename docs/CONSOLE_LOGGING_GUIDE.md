# Console Logging Best Practices for MindGraph

## Overview

This guide explains how to use the centralized logger for clean, professional browser console logging.

## The Problem Before

- 570+ raw `console.log()` statements scattered everywhere
- No debug mode control
- Logs spam the console even in production
- Hard to find important errors among debug messages
- No consistent formatting

## The Solution: Centralized Logger

A new `logger.js` provides structured logging with levels:

- **DEBUG**: Detailed debugging info (only visible in debug mode)
- **INFO**: Important operations (only visible in debug mode)
- **WARN**: Warnings (always visible)
- **ERROR**: Errors (always visible + sent to backend)

## How to Enable Debug Mode

### Method 1: URL Parameter
```
http://localhost:9527/editor?debug=1
```

### Method 2: Browser Console
```javascript
enableDebug()   // Turn on debug logging
disableDebug()  // Turn off debug logging
```

## Usage Examples

### Before (Bad) ❌
```javascript
console.log('ToolbarManager: Add Node button clicked');
console.log('Rendering qwen - spec:', spec);
console.warn('Property panel not found!');
console.error('Editor not initialized');
```

### After (Good) ✅
```javascript
// DEBUG level - only in debug mode
logger.debug('ToolbarManager', 'Add node button clicked');
logger.debug('ToolbarManager', 'Rendering spec', { model: 'qwen', nodes: spec?.nodes?.length });

// WARN level - always visible
logger.warn('ToolbarManager', 'Property panel not found');

// ERROR level - always visible + sent to backend
logger.error('ToolbarManager', 'Editor not initialized', error);
```

### Grouped Logging
```javascript
logger.group('ToolbarManager', 'Auto-complete process', () => {
    logger.debug('ToolbarManager', 'Extracted nodes', existingNodes);
    logger.debug('ToolbarManager', 'Language detected', language);
    logger.debug('ToolbarManager', 'LLM model', llmModel);
}, true); // true = collapsed by default
```

## Migration Rules

### 1. Button Clicks → DEBUG
```javascript
// Before
console.log('ToolbarManager: Add Node button clicked');

// After
logger.debug('ToolbarManager', 'Add node clicked');
```

### 2. Data Logging → DEBUG with structured data
```javascript
// Before
console.log('Rendering qwen - spec:', { nodes: spec?.nodes?.length });

// After  
logger.debug('Renderer', 'Rendering diagram', { 
    model: 'qwen', 
    nodes: spec?.nodes?.length,
    type: diagramType 
});
```

### 3. Warnings → WARN
```javascript
// Before
console.warn('Property panel not found!');

// After
logger.warn('ToolbarManager', 'Property panel not found');
```

### 4. Errors → ERROR
```javascript
// Before
console.error('Failed to render:', error);

// After
logger.error('Renderer', 'Rendering failed', error);
```

### 5. Remove Excessive Logs
```javascript
// DELETE these types of logs entirely:
console.log('ToolbarManager: applyText showing notification (silent=false)'); // Too verbose
console.log('Property panel cleared to default values'); // Obvious from UI
console.log('ToolbarManager: Duplicate Node button clicked'); // User already knows
```

## Component Names

Use consistent component names for easier filtering:

- `'Editor'` - InteractiveEditor
- `'ToolbarManager'` - Toolbar operations
- `'Renderer'` - Diagram rendering
- `'SelectionManager'` - Node selection
- `'CanvasManager'` - Canvas operations
- `'NodeEditor'` - Node editing
- `'LanguageManager'` - i18n
- `'PromptManager'` - Prompt handling
- `'AIAssistant'` - AI chat
- `'LearningMode'` - Learning features
- `'DiagramValidator'` - Validation
- `'DiagramSelector'` - Type selection

## Production vs Debug

### Production (debug=false, default):
- ✅ Errors (red)
- ✅ Warnings (orange)
- ❌ Info (hidden)
- ❌ Debug (hidden)

### Debug Mode (debug=true):
- ✅ Errors (red)
- ✅ Warnings (orange)  
- ✅ Info (blue, bold)
- ✅ Debug (gray)

## Priority Refactoring

Files with most logging (refactor first):

1. `toolbar-manager.js` - 200+ logs
2. `interactive-editor.js` - 150+ logs
3. `diagram-selector.js` - 80+ logs
4. `ai-assistant-manager.js` - 50+ logs
5. `learning-mode-manager.js` - 40+ logs

## Testing Your Changes

```javascript
// In browser console with debug mode:
enableDebug()

// Perform an action
// Check logs are:
// 1. Properly formatted with timestamp
// 2. Using correct log level
// 3. Not duplicating
// 4. Showing structured data

// Turn off debug mode
disableDebug()

// Verify only WARN and ERROR logs appear
```

## Quick Reference

| Old | New | When Visible |
|-----|-----|--------------|
| `console.log()` | `logger.debug()` | Debug only |
| `console.log()` (important) | `logger.info()` | Debug only |
| `console.warn()` | `logger.warn()` | Always |
| `console.error()` | `logger.error()` | Always |

---

**Made by MindSpring Team | Author: lycosa9527**

