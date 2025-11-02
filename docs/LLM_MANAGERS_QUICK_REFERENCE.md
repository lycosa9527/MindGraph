# LLM Managers - Quick Reference Guide

**Date:** 2025-11-02  
**Version:** 1.1 (Updated)  
**Purpose:** Quick reference for using the modular LLM auto-complete architecture

---

## 📚 Overview

The LLM auto-complete system is now composed of 5 specialized managers working together:

```
User Action
    ↓
LLMAutoCompleteManager (Orchestrator)
    ├→ LLMEngineManager (API calls)
    ├→ PropertyValidator (Validation)
    ├→ LLMResultCache (Caching)
    └→ LLMProgressRenderer (UI updates)
```

---

## 🔧 Manager Reference

### 1. PropertyValidator

**File:** `static/js/managers/toolbar/property-validator.js`  
**Responsibility:** Validate LLM-generated specs and analyze consistency

#### Methods

```javascript
// Validate a spec against diagram type requirements
const validation = validator.validateLLMSpec(modelName, spec, 'mindmap');
// Returns: { isValid: boolean, issues: [], missingFields: [], invalidFields: [] }

// Analyze consistency across multiple model results
const analysis = validator.analyzeConsistency(llmResults, logger);
// Returns: { modelsAnalyzed, hasConsistencyIssues, inconsistencies, specComparison }
```

#### Supported Diagram Types
- bubble_map, circle_map, mindmap/mind_map, tree_map
- brace_map, bridge_map, double_bubble_map
- flow_map, multi_flow_map, concept_map

#### Example Usage
```javascript
const validator = new PropertyValidator(logger);

// Check if a spec is valid
const spec = { topic: 'Learning', children: [...] };
const result = validator.validateLLMSpec('qwen', spec, 'mindmap');

if (result.isValid) {
    logger.info('Spec is valid!');
} else {
    logger.warn('Issues:', result.issues);
    logger.warn('Missing:', result.missingFields);
}
```

---

### 2. LLMResultCache

**File:** `static/js/managers/toolbar/llm-result-cache.js`  
**Responsibility:** Cache and retrieve LLM generation results with TTL

#### Methods

```javascript
// Store a result
cache.store('qwen', { success: true, result: {...} });

// Retrieve a cached result (returns null if expired)
const result = cache.getResult('qwen');

// Get list of valid cached models
const cachedModels = cache.getCachedModels(); // ['qwen', 'deepseek']

// Clear all cached results
cache.clear();

// Clear results for specific model
cache.clearModel('qwen');

// Get all results (for analysis)
const allResults = cache.getAllResults();

// Get cache statistics
const stats = cache.getStats();
// Returns: { cachedModels: [], validResults: 2, totalCapacity: 4 }
```

#### Configuration
```javascript
// Custom TTL (default: 10 minutes)
const cache = new LLMResultCache(logger, {
    ttlMs: 5 * 60 * 1000, // 5 minutes
    maxResults: 4
});
```

#### Example Usage
```javascript
const cache = new LLMResultCache(logger);

// After getting result from API
cache.store('qwen', apiResponse);

// Later, retrieve cached result
const cached = cache.getResult('qwen');

// Check what models have valid cache
if (cache.getCachedModels().includes('deepseek')) {
    // Render deepseek result
}
```

---

### 3. LLMProgressRenderer

**File:** `static/js/managers/toolbar/llm-progress-renderer.js`  
**Responsibility:** Manage UI updates for LLM progress and button states

#### Methods

```javascript
// Show loading progress
renderer.showProgress('Generating content...');

// Update progress message
renderer.updateProgressMessage('Processing results...');

// Update progress bar (0-100)
renderer.updateProgressBar(50);

// Set state for specific button
renderer.setLLMButtonState('qwen', 'ready'); // 'loading', 'ready', 'error', 'idle'

// Update multiple buttons at once
renderer.updateButtonStates(llmResults);

// Set all buttons to loading
renderer.setAllLLMButtonsLoading(true);

// Highlight selected model
renderer.highlightSelectedModel('qwen');

// Clear all visual states
renderer.clearAllStates();
```

#### Button States
- **loading** - Request in progress (disabled)
- **ready** - Result available (enabled, green)
- **error** - Request failed (enabled, red)
- **idle** - Default state (enabled, gray)

#### Example Usage
```javascript
const renderer = new LLMProgressRenderer(toolbarManager, logger);

// Start loading
renderer.setAllLLMButtonsLoading(true);

// When first result comes in
renderer.setLLMButtonState('qwen', 'ready');
renderer.highlightSelectedModel('qwen');
renderer.updateProgressMessage('First result loaded');

// When all done
renderer.setAllLLMButtonsLoading(false);
renderer.updateButtonStates(allResults);
```

---

### 4. LLMEngineManager

**File:** `static/js/managers/toolbar/llm-engine-manager.js`  
**Responsibility:** Handle API calls and response processing

#### Methods

```javascript
// Call single model API
const result = await engine.callLLMWithModel('qwen', requestBody, {
    onSuccess: (result) => { /* handle success */ },
    onError: (result) => { /* handle error */ }
});

// Call multiple models in parallel
const allResults = await engine.callMultipleModels(
    ['qwen', 'deepseek', 'kimi', 'hunyuan'],
    requestBody,
    {
        onEachSuccess: (result) => { /* handle each success */ },
        onEachError: (result) => { /* handle each error */ },
        onComplete: (allResults) => { /* handle all done */ },
        onProgress: (status, model) => { /* track progress */ }
    }
);

// Cancel all active requests
engine.cancelAllRequests();

// Check if requests are active
const hasActive = engine.hasActiveRequests();
const count = engine.getActiveRequestCount();
```

#### Request Body Format
```javascript
const requestBody = {
    prompt: 'Continue the following mindmap diagram...',
    diagram_type: 'mindmap',
    language: 'en',
    model: null // Filled per model by engine
};
```

#### Response Format
```javascript
{
    model: 'qwen',
    success: true,
    result: {
        spec: { /* diagram spec */ },
        diagram_type: 'mindmap',
        topics: [...],
        style_preferences: {...}
    },
    validation: { /* from PropertyValidator */ },
    elapsed: '1.23s'
}
```

#### Example Usage
```javascript
const engine = new LLMEngineManager(llmValidationManager, validator, logger);

const results = await engine.callMultipleModels(
    ['qwen', 'deepseek'],
    {
        prompt: 'Generate mindmap about AI',
        diagram_type: 'mindmap',
        language: 'en'
    },
    {
        onEachSuccess: (result) => {
            logger.info(`${result.model} succeeded`);
        },
        onComplete: (allResults) => {
            const successCount = Object.values(allResults)
                .filter(r => r.success).length;
            logger.info(`${successCount} models succeeded`);
        }
    }
);
```

---

### 5. LLMAutoCompleteManager (Orchestrator)

**File:** `static/js/managers/toolbar/llm-autocomplete-manager.js`  
**Responsibility:** Coordinate the entire auto-complete workflow

#### Main Methods

```javascript
// Start auto-complete process
await autoComplete.handleAutoComplete();

// Render a cached result
autoComplete.renderCachedLLMResult('qwen');

// Update button states
autoComplete.updateLLMButtonStates();

// Cancel all requests
autoComplete.cancelAllLLMRequests();
```

#### Event Bus Integration

```javascript
// Requests auto-complete
eventBus.emit('autocomplete:start_requested', {});

// Requests cached result render
eventBus.emit('autocomplete:render_cached_requested', {
    llmModel: 'qwen'
});

// Requests button state update
eventBus.emit('autocomplete:update_button_states_requested', {});

// Requests cancellation
eventBus.emit('autocomplete:cancel_requested', {});
```

---

## 🔄 Typical Workflow

```javascript
// 1. User clicks "Generate" button in toolbar
// 2. Event Bus emits 'autocomplete:start_requested'
// 3. LLMAutoCompleteManager.handleAutoComplete() starts:

//    a. Validate editor state
//    b. Extract existing nodes
//    c. Detect language
//    d. Show loading UI via ProgressRenderer
//    e. Call LLMEngineManager.callMultipleModels()
//    f. For each result:
//       - Validate with PropertyValidator
//       - Cache with ResultCache
//       - Update UI with ProgressRenderer
//       - Render first successful result immediately
//    g. Analyze consistency with PropertyValidator
//    h. Show completion message

// 4. User clicks model button to view different result
// 5. LLMAutoCompleteManager.renderCachedLLMResult(modelName)
//    - Retrieves from ResultCache
//    - Updates editor.currentSpec
//    - Calls editor.renderDiagram()
```

---

## 🧪 Testing Examples

### Unit Test: PropertyValidator
```javascript
describe('PropertyValidator', () => {
    const validator = new PropertyValidator(console);
    
    it('should validate valid mindmap spec', () => {
        const spec = { topic: 'AI', children: [{text: 'ML'}, {text: 'NLP'}] };
        const result = validator.validateLLMSpec('qwen', spec, 'mindmap');
        expect(result.isValid).toBe(true);
    });
    
    it('should reject invalid mindmap spec', () => {
        const spec = { topic: 'AI' }; // Missing children
        const result = validator.validateLLMSpec('qwen', spec, 'mindmap');
        expect(result.isValid).toBe(false);
        expect(result.missingFields).toContain('children');
    });
});
```

### Unit Test: LLMResultCache
```javascript
describe('LLMResultCache', () => {
    let cache;
    
    beforeEach(() => {
        cache = new LLMResultCache(console);
    });
    
    it('should store and retrieve result', () => {
        const result = { success: true, model: 'qwen' };
        cache.store('qwen', result);
        expect(cache.getResult('qwen')).toEqual(result);
    });
    
    it('should expire old results', (done) => {
        const cache = new LLMResultCache(console, { ttlMs: 100 });
        cache.store('qwen', { success: true });
        
        setTimeout(() => {
            expect(cache.getResult('qwen')).toBeNull();
            done();
        }, 150);
    });
});
```

---

## 🐛 Debugging

### Enable Verbose Logging
```javascript
// All managers use consistent logging pattern
// Check browser console for detailed logs
logger.info('ManagerName', 'Message', { context });
logger.debug('ManagerName', 'Message', { context });
logger.warn('ManagerName', 'Message', { context });
logger.error('ManagerName', 'Message', { context });
```

### Check Cache State
```javascript
// In browser console:
window.eventBus.on('autocomplete:render_cached_requested', (data) => {
    console.log('Cache stats:', llmAutoCompleteManager.resultCache.getStats());
});
```

### Monitor API Calls
```javascript
// LLMEngineManager logs all API calls:
// - Request start/end
// - Response received
// - Validation results
// - Errors encountered
```

---

## 📋 Common Tasks

### Add New Diagram Type Validation
1. Add case to `PropertyValidator.validateLLMSpec()` switch statement
2. Define required and optional fields for your diagram type
3. Add to validation logic

### Change Cache TTL
```javascript
const cache = new LLMResultCache(logger, {
    ttlMs: 30 * 60 * 1000 // 30 minutes
});
```

### Add New Button State
1. Update `LLMProgressRenderer.setLLMButtonState()` switch statement
2. Add CSS styles for the new state
3. Update button state logic in orchestrator

### Customize API Response Handling
1. Modify callbacks in `LLMEngineManager.callMultipleModels()` invocation
2. Add custom handling in `LLMAutoCompleteManager._handleModelSuccess()` or `_handleAllModelsComplete()`

---

## 🔗 File Dependencies

```
LLMAutoCompleteManager
├─ requires PropertyValidator
├─ requires LLMResultCache
├─ requires LLMProgressRenderer
├─ requires LLMEngineManager
│  ├─ requires llmValidationManager
│  └─ requires PropertyValidator
└─ requires llmValidationManager
```

### Script Loading Order (in editor.html)
1. property-validator.js
2. llm-result-cache.js
3. llm-progress-renderer.js
4. llm-engine-manager.js
5. llm-autocomplete-manager.js

---

## 📚 References

- **Editor Improvements:** `docs/EDITOR_IMPROVEMENT_GUIDE.md` (contains toolbar refactoring details)
- **Event Bus:** `static/js/managers/event-bus.js`
- **Logger:** `static/js/managers/logger.js`
- **Validation Manager:** `static/js/managers/toolbar/llm-validation-manager.js`
