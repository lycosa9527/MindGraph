# MindGraph .mg Import/Export Feature

## Overview

This document outlines the implementation plan for the `.mg` file import/export feature. Since MindGraph does not store user files on the server, this feature enables users to save and restore their diagrams locally using a custom `.mg` file format.

## Feature Requirements

1. **Export to .mg**: Save current diagram as a `.mg` file to local machine
2. **Import from .mg**: Load a previously saved `.mg` file and restore the diagram
3. **Client-side only**: No server storage - all operations happen in the browser
4. **Format validation**: Validate imported files before rendering

---

## Codebase Analysis (Verified)

### Current Export Architecture

| Component | Location | Current Behavior |
|-----------|----------|------------------|
| Export Button | `templates/editor.html:428` | Single button `<button id="export-btn">Export</button>` |
| ToolbarManager | `static/js/editor/toolbar-manager.js:1270` | `handleExport()` directly calls `performPNGExport()` |
| ExportManager | `static/js/managers/toolbar/export-manager.js` | Listens for `toolbar:export_requested` event (currently not used by toolbar) |

### Key Findings

1. **ToolbarManager does NOT use Event Bus for export** - It implements PNG export directly
2. **ExportManager exists but is underutilized** - Has JSON/SVG methods, listens for events
3. **Diagram creation flow**: `DiagramSelector.transitionToEditor()` -> `new InteractiveEditor(diagramType, template)` -> `editor.render()`
4. **Translations**: Use `notif` object in `language-manager.js` (e.g., `notif.noDiagramToExport`)

---

## File Format Specification

### .mg File Structure

The `.mg` file is a JSON file with a MindGraph-specific structure:

```json
{
  "mindgraph": {
    "version": "1.0",
    "format": "mg"
  },
  "created_at": "2025-12-06T10:30:00.000Z",
  "diagram_type": "bubble_map",
  "spec": {
    // Diagram-specific data structure
  },
  "style": {
    "theme": "default",
    "colors": {
      "topicFill": "#1976d2",
      "topicText": "#ffffff",
      "attributeFill": "#e3f2fd",
      "attributeText": "#333333",
      "background": "#f5f5f5"
    },
    "fonts": {
      "primary": "Inter, Segoe UI, sans-serif",
      "topicSize": 20,
      "attributeSize": 14
    }
  },
  "metadata": {
    "app_version": "4.28.19",
    "language": "en",
    "source_llm": "qwen",
    "author": {
      "name": "John Doe",
      "id": "user_12345"
    },
    "title": "My Bubble Map",
    "description": "A diagram about..."
  }
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| **Core Fields** | | | |
| `mindgraph.version` | string | Yes | **File format version** for compatibility checking and migrations |
| `mindgraph.format` | string | Yes | Always "mg" to identify file type |
| `created_at` | string | Yes | ISO 8601 timestamp of export |
| `diagram_type` | string | Yes | One of the supported diagram types |
| `spec` | object | Yes | The diagram data (varies by type) |
| **Style Fields** | | | |
| `style.theme` | string | No | Theme name (default, classic, modern, etc.) |
| `style.colors` | object | No | Custom color overrides for diagram elements |
| `style.fonts` | object | No | Font family and sizes used in diagram |
| **Metadata Fields** | | | |
| `metadata.app_version` | string | No | MindGraph app version that created the file |
| `metadata.language` | string | No | UI language at time of export |
| `metadata.source_llm` | string | No | LLM model used to generate diagram |
| `metadata.author` | object | No | Author information (optional, privacy-aware) |
| `metadata.author.name` | string | No | Display name of author |
| `metadata.author.id` | string | No | User ID (anonymized if needed) |
| `metadata.title` | string | No | User-defined title for the diagram |
| `metadata.description` | string | No | User-defined description |

### Version Strategy

| Version Type | Purpose | Example |
|--------------|---------|---------|
| `mindgraph.version` | File format version - used for migrations | `"1.0"`, `"2.0"` |
| `metadata.app_version` | App version - for debugging only | `"4.28.19"` |

**Why both?**
- **File format version**: Changes when the `.mg` structure changes (rare). Used to migrate old files.
- **App version**: Changes with every release. Helps debug "which version created this file?" without affecting compatibility.

### Style Preservation

The `style` section captures the visual appearance of the diagram:

| Style Property | Source | Description |
|----------------|--------|-------------|
| `theme` | `styleManager` | Current theme name |
| `colors.*` | `styleManager.getTheme()` | All color values from current theme |
| `fonts.primary` | Renderer config | Primary font family |
| `fonts.*Size` | `styleManager` | Font sizes for each element type |

### Author Information (Privacy Considerations)

Author info is **optional** and should only be included if:
1. User explicitly enables "include author info" in export settings
2. Or user is exporting for sharing/collaboration

```javascript
// Default: No author info (privacy-first)
metadata: {
    author: null
}

// With author info (user opt-in)
metadata: {
    author: {
        name: "John Doe",
        id: "user_abc123"  // Can be hashed for privacy
    }
}
```

### Supported Diagram Types

**Thinking Maps (8 types):**
- `bubble_map` - Describing with adjectives
- `double_bubble_map` - Comparing and contrasting
- `circle_map` - Defining in context
- `tree_map` - Classifying and grouping
- `brace_map` - Whole to parts
- `flow_map` - Sequencing and ordering
- `multi_flow_map` - Cause and effect
- `bridge_map` - Seeing analogies

**Advanced Diagrams:**
- `mindmap` - Creative brainstorming
- `concept_map` - Complex relationships *(Note: currently under development)*

**Thinking Tools (under development):**
- `factor_analysis`
- `three_position_analysis`
- `perspective_analysis`
- `goal_analysis`
- `possibility_analysis`
- `result_analysis`
- `five_w_one_h`
- `whwm_analysis`
- `four_quadrant`

> **Note:** When importing a file with a diagram type that's under development (e.g., `concept_map`, thinking tools), the import will succeed but the diagram may not render correctly until the feature is released.

### Spec Structure Examples

#### Bubble Map
```json
{
  "topic": "Happiness",
  "adjectives": ["joyful", "content", "peaceful", "grateful"]
}
```

#### Double Bubble Map
```json
{
  "leftTopic": "Dogs",
  "rightTopic": "Cats",
  "similarities": ["pets", "furry", "loyal"],
  "leftDifferences": ["bark", "pack animals"],
  "rightDifferences": ["meow", "independent"]
}
```

#### Circle Map
```json
{
  "topic": "Friendship",
  "context": ["trust", "support", "sharing", "loyalty", "fun"]
}
```

#### Tree Map
```json
{
  "title": "Animals",
  "categories": [
    {
      "name": "Mammals",
      "children": ["Dog", "Cat", "Elephant"]
    },
    {
      "name": "Birds",
      "children": ["Eagle", "Sparrow"]
    }
  ]
}
```

#### Brace Map
```json
{
  "whole": "Computer",
  "parts": [
    {
      "name": "Hardware",
      "subparts": [
        { "name": "CPU" },
        { "name": "RAM" }
      ]
    }
  ]
}
```

#### Flow Map
```json
{
  "title": "Making Coffee",
  "steps": [
    { "text": "Boil water", "substeps": [] },
    { "text": "Add coffee", "substeps": ["Measure 2 tbsp"] },
    { "text": "Pour water", "substeps": [] },
    { "text": "Serve", "substeps": [] }
  ]
}
```

#### Multi-Flow Map
```json
{
  "event": "Industrial Revolution",
  "causes": ["Steam engine invention", "Population growth", "Natural resources"],
  "effects": ["Urbanization", "Factory system", "New social classes"]
}
```

#### Bridge Map
```json
{
  "relatingFactor": "is the capital of",
  "analogies": [
    { "left": "Paris", "right": "France" },
    { "left": "Tokyo", "right": "Japan" },
    { "left": "Berlin", "right": "Germany" }
  ]
}
```

#### Mind Map
```json
{
  "central_topic": "Project Planning",
  "branches": [
    {
      "text": "Research",
      "children": [
        { "text": "Market Analysis" },
        { "text": "Competitor Review" }
      ]
    }
  ]
}
```

### Complete .mg File Example

```json
{
  "mindgraph": {
    "version": "1.0",
    "format": "mg"
  },
  "created_at": "2025-12-06T14:30:00.000Z",
  "diagram_type": "bubble_map",
  "spec": {
    "topic": "Happiness",
    "adjectives": ["joyful", "content", "peaceful", "grateful", "fulfilled"]
  },
  "style": {
    "theme": "default",
    "colors": {
      "topicFill": "#1976d2",
      "topicText": "#ffffff",
      "attributeFill": "#e3f2fd",
      "attributeText": "#333333",
      "background": "#f5f5f5"
    },
    "fonts": {
      "primary": "Inter, Segoe UI, sans-serif",
      "topicSize": 20,
      "attributeSize": 14
    }
  },
  "metadata": {
    "app_version": "4.28.19",
    "language": "en",
    "source_llm": "qwen",
    "title": "Understanding Happiness",
    "description": "A bubble map exploring the characteristics of happiness",
    "author": {
      "name": "Jane Smith",
      "id": "user_abc123"
    }
  }
}
```

---

## Implementation Plan

### Step 0: Expose App Version to Frontend (Prerequisite)

#### 0.1 Backend: Add version to template context

**File:** `routers/pages.py`

**Location:** Lines 130-143 (editor route template context)

**Current State (lines 130-142):**
```python
return templates.TemplateResponse(
    "editor.html",
    {
        "request": request,
        "feature_learning_mode": config.FEATURE_LEARNING_MODE,
        "feature_thinkguide": config.FEATURE_THINKGUIDE,
        "feature_mindmate": config.FEATURE_MINDMATE,
        "feature_voice_agent": config.FEATURE_VOICE_AGENT,
        "verbose_logging": config.VERBOSE_LOGGING,
        "ai_assistant_name": config.AI_ASSISTANT_NAME,
        "default_language": config.DEFAULT_LANGUAGE,
        "wechat_qr_image": config.WECHAT_QR_IMAGE
    }
)
```

**Add `version` to context:**
```python
from pathlib import Path

def get_app_version():
    """Read version from VERSION file"""
    version_file = Path(__file__).parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "unknown"

# In editor route (line 130+):
return templates.TemplateResponse(
    "editor.html",
    {
        "request": request,
        "version": get_app_version(),  # NEW
        "feature_learning_mode": config.FEATURE_LEARNING_MODE,
        # ... rest unchanged ...
    }
)
```

#### 0.2 Frontend: Expose version as global variable

**File:** `templates/editor.html`

**Location:** Lines 30-40 (inside the `<script>` block)

**Add after other config variables:**
```html
<script>
    // Load configuration from data attributes
    const bodyElement = document.body;
    window.VERBOSE_LOGGING = bodyElement.dataset.verboseLogging === 'true';
    // ... existing config ...
    
    // App version for .mg file exports (from VERSION file: currently 4.28.19)
    window.MINDGRAPH_VERSION = '{{ version }}';
</script>
```

---

### Step 1: Update HTML - Add File Operations Group (Export/Save/Import)

**File:** `templates/editor.html`

**Location:** Lines 426-430 (toolbar-left section)

**Current State (Lines 426-430):**
```html
<div class="toolbar-section toolbar-left">
    <button id="back-to-gallery" class="btn-secondary">Back to Gallery</button>
    <button id="export-btn" class="btn-success">Export</button>
    <button id="reset-btn" class="btn-warning">Reset</button>  <!-- REMOVE -->
</div>
```

**Target State:**
```html
<div class="toolbar-section toolbar-left">
    <button id="back-to-gallery" class="btn-secondary">
        <span class="lang-en">Back</span>
        <span class="lang-zh">返回</span>
    </button>
    
    <!-- File Operations Group: Export | Save | Import -->
    <div class="toolbar-group file-operations-group">
        <span class="toolbar-group-label">
            <span class="lang-en">File:</span>
            <span class="lang-zh">文件:</span>
        </span>
        
        <!-- Export Button (PNG - most common for teachers, green) -->
        <button id="export-btn" class="btn-tool" title="Export as PNG image">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 4px;">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
            <span class="lang-en">Export</span>
            <span class="lang-zh">导出</span>
        </button>
        
        <!-- Save Button (.mg file, transparent) -->
        <button id="save-btn" class="btn-tool" title="Save as .mg file">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 4px;">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                <polyline points="17 21 17 13 7 13 7 21"></polyline>
                <polyline points="7 3 7 8 15 8"></polyline>
            </svg>
            <span class="lang-en">Save</span>
            <span class="lang-zh">保存</span>
        </button>
        
        <!-- Import Button (.mg file, transparent) -->
        <button id="import-btn" class="btn-tool" title="Import .mg file">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 4px;">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            <span class="lang-en">Import</span>
            <span class="lang-zh">导入</span>
        </button>
        <input type="file" id="import-file-input" accept=".mg" style="display: none;">
    </div>
</div>
```

**Note:** Reset button removed - rarely used. Users can go Back to gallery and select diagram again if needed.

**Design Notes:**
- **Simplified 3-button design** (no dropdown needed):
  - **Export** = PNG image (most common for teachers) - **Green** (primary action)
  - **Save** = .mg file (for saving work to continue later) - Transparent
  - **Import** = Load .mg file - Transparent
- **Reset button removed** - Rarely used; users can Back → re-select diagram
- **Consistent styling** - Save/Import match other toolbar buttons (transparent)
- Icons clearly indicate function:
  - Export: Image icon (picture frame)
  - Save: Floppy disk icon (classic save)
  - Import: Download arrow icon
- Follows existing toolbar group pattern (see lines 433-473 for `nodes-toolbar-group`)

---

### Step 2: Add CSS for File Operations Group

**File:** `static/css/editor-toolbar.css`

**Location:** Add after line 99 (after `.toolbar-minimal` section, before `/* Mobile mode */`)

```css
/* ============================================
   FILE OPERATIONS GROUP (Export/Save/Import)
   ============================================ */

/* File Operations Group - matches other toolbar groups */
.file-operations-group {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    margin-left: 12px;
}

.file-operations-group .toolbar-group-label {
    font-size: 12px;
    color: #666;
    font-weight: 500;
    margin-right: 4px;
}

/* File Operation Buttons - consistent styling */
.file-operations-group .btn-tool {
    display: flex;
    align-items: center;
    gap: 4px;
}

.file-operations-group .btn-tool svg {
    flex-shrink: 0;
}

/* Export Button (PNG) - Green, primary action for teachers */
#export-btn {
    background-color: #4caf50;
    color: white;
    border-color: #43a047;
}

#export-btn:hover {
    background-color: #43a047;
}

/* Save & Import Buttons - Transparent, matches other toolbar buttons */
#save-btn,
#import-btn {
    background-color: transparent;
    color: inherit;
    border: 1px solid rgba(128, 128, 128, 0.3);
}

#save-btn:hover,
#import-btn:hover {
    background-color: rgba(128, 128, 128, 0.1);
    border-color: rgba(128, 128, 128, 0.5);
}

/* ============================================
   RESPONSIVE ADJUSTMENTS
   ============================================ */

/* Hide labels on smaller screens - show icons only */
@media (max-width: 900px) {
    .file-operations-group .toolbar-group-label {
        display: none;
    }
    
    .file-operations-group .btn-tool span {
        display: none;
    }
    
    .file-operations-group {
        gap: 4px;
        padding: 6px 8px;
    }
}

/* Tighter spacing on very small screens */
@media (max-width: 600px) {
    .file-operations-group {
        margin-left: 8px;
        gap: 2px;
    }
}
```

---

### Step 3: Update ExportManager - Add .mg Export

**File:** `static/js/managers/toolbar/export-manager.js`

Add to constructor:
```javascript
this.exportFormats = ['png', 'svg', 'json', 'mg'];
```

Add new method:
```javascript
/**
 * Export diagram to MindGraph .mg format
 * @param {Object} editor - Editor instance
 * @returns {Promise<Object>} Export result
 */
async exportToMG(editor) {
    try {
        if (!editor || !editor.currentSpec) {
            this.logger.error('ExportManager', 'No diagram data available');
            return {
                success: false,
                error: 'No diagram data to export'
            };
        }
        
        // Get current theme/style from styleManager
        const diagramType = editor.diagramType;
        const currentTheme = window.styleManager?.getTheme(diagramType) || {};
        
        // Extract style information
        const styleData = {
            theme: 'default',  // Could be extended to support named themes
            colors: {
                topicFill: currentTheme.topicFill || currentTheme.centralTopicFill,
                topicText: currentTheme.topicText || currentTheme.centralTopicText,
                attributeFill: currentTheme.attributeFill || currentTheme.branchFill,
                attributeText: currentTheme.attributeText || currentTheme.branchText,
                background: currentTheme.background || '#f5f5f5'
            },
            fonts: {
                primary: 'Inter, Segoe UI, sans-serif',
                topicSize: currentTheme.fontTopic || 18,
                attributeSize: currentTheme.fontAttribute || currentTheme.fontBranch || 14
            }
        };
        
        // Build metadata (author info is optional - privacy first)
        const metadata = {
            app_version: window.MINDGRAPH_VERSION || 'unknown',
            language: window.languageManager?.getCurrentLanguage() || 'en',
            source_llm: window.toolbarManager?.selectedLLM || 'unknown',
            title: null,       // User can set this in export dialog (future feature)
            description: null  // User can set this in export dialog (future feature)
        };
        
        // Include author info only if available and user has opted in
        // (Future: add checkbox in export dialog)
        if (window.MINDGRAPH_USER && window.MINDGRAPH_INCLUDE_AUTHOR) {
            metadata.author = {
                name: window.MINDGRAPH_USER.name || 'Anonymous',
                id: window.MINDGRAPH_USER.id || null
            };
        }
        
        // Prepare .mg file data
        const mgData = {
            mindgraph: {
                version: '1.0',  // File format version (for migrations)
                format: 'mg'
            },
            created_at: new Date().toISOString(),
            diagram_type: diagramType,
            spec: editor.currentSpec,
            style: styleData,
            metadata: metadata
        };
        
        // Convert to JSON string (pretty printed for readability)
        const jsonString = JSON.stringify(mgData, null, 2);
        
        // Create blob and download
        const blob = new Blob([jsonString], { type: 'application/octet-stream' });
        const url = URL.createObjectURL(blob);
        
        const filename = this.generateFilename(editor, 'mg');
        this.downloadFile(url, filename, 'application/octet-stream');
        
        URL.revokeObjectURL(url);
        
        this.logger.info('ExportManager', 'MG export successful', { 
            filename,
            diagramType: diagramType,
            hasStyle: !!styleData,
            hasAuthor: !!metadata.author
        });
        
        this.eventBus.emit('file:mg_export_completed', { filename });
        
        // Show success notification
        this.eventBus.emit('notification:show', {
            message: window.languageManager?.getNotification('diagramSaved') || 'Diagram saved as .mg file!',
            type: 'success'
        });
        
        return {
            success: true,
            filename,
            format: 'mg'
        };
        
    } catch (error) {
        this.logger.error('ExportManager', 'Error exporting to MG', error);
        this.eventBus.emit('file:mg_export_error', { error: error.message });
        return {
            success: false,
            error: error.message
        };
    }
}
```

**Note:** Requires exposing app version to frontend. Add to `templates/editor.html`:
```html
<script>
    window.MINDGRAPH_VERSION = '{{ version }}';  // From VERSION file via backend
    
    // Optional: User info for author metadata (privacy-first - null by default)
    window.MINDGRAPH_USER = {{ user_info | tojson | safe if user_info else 'null' }};
    window.MINDGRAPH_INCLUDE_AUTHOR = false;  // User opt-in via export settings
</script>
```

---

### Step 4: Update ExportManager - Add Import Functionality

**File:** `static/js/managers/toolbar/export-manager.js`

#### 4.1 Update `subscribeToEvents()` (lines 39-46):

```javascript
subscribeToEvents() {
    // Existing: Listen for export requests
    this.eventBus.onWithOwner('toolbar:export_requested', (data) => {
        this.handleExport(data.format, data.editor);
    }, this.ownerId);
    
    // NEW: Listen for import file data (from ToolbarManager)
    this.eventBus.onWithOwner('toolbar:import_file', (data) => {
        this.handleImportData(data.data, data.filename);
    }, this.ownerId);
    
    this.logger.debug('ExportManager', 'Subscribed to events with owner tracking');
}
```

#### 4.2 Update `handleExport()` switch statement (lines 78-88):

```javascript
switch(format) {
    case 'png':
        result = await this.exportToPNG(editor);
        break;
    case 'svg':
        result = await this.exportToSVG(editor);
        break;
    case 'json':
        result = await this.exportToJSON(editor);
        break;
    case 'mg':  // NEW
        result = await this.exportToMG(editor);
        break;
}
```

#### 4.3 Add new methods (after `exportToJSON()` which ends around line 491):

**Location:** After line 491 (end of `exportToJSON` method)

```javascript
/**
 * Handle import data from ToolbarManager
 * @param {Object} data - Parsed .mg file data
 * @param {string} filename - Original filename
 */
async handleImportData(data, filename) {
    this.logger.info('ExportManager', 'Processing import data', {
        filename,
        hasData: !!data
    });
    
    this.eventBus.emit('file:mg_import_started', { filename });
    
    try {
        // Validate file structure
        const validation = this.validateMGFile(data);
        if (!validation.valid) {
            throw new Error(validation.error);
        }
        
        // Apply imported diagram
        await this.applyImportedDiagram(data);
        
        this.logger.info('ExportManager', 'MG import successful', {
            diagramType: data.diagram_type
        });
        
        this.eventBus.emit('file:mg_import_completed', {
            filename,
            diagramType: data.diagram_type
        });
        
        // Show success notification
        this.eventBus.emit('notification:show', {
            message: window.languageManager?.getNotification('importSuccess') || 'Diagram imported successfully',
            type: 'success'
        });
        
    } catch (error) {
        this.logger.error('ExportManager', 'Error importing MG file', error);
        this.eventBus.emit('file:mg_import_error', { error: error.message });
        
        // Show user-friendly error notification
        this.eventBus.emit('notification:show', {
            message: `${window.languageManager?.getNotification('importFailed') || 'Import failed'}: ${error.message}`,
            type: 'error'
        });
    }
}

/**
 * Validate .mg file structure
 * @param {Object} data - Parsed file data
 * @returns {Object} Validation result { valid: boolean, error?: string }
 */
validateMGFile(data) {
    // Check mindgraph header
    if (!data.mindgraph || !data.mindgraph.version || !data.mindgraph.format) {
        return { valid: false, error: 'Invalid file format: missing MindGraph header' };
    }
    
    if (data.mindgraph.format !== 'mg') {
        return { valid: false, error: 'Invalid file format: not a .mg file' };
    }
    
    // Check version compatibility
    const supportedVersions = ['1.0'];
    if (!supportedVersions.includes(data.mindgraph.version)) {
        return { 
            valid: false, 
            error: `Unsupported file version: ${data.mindgraph.version}` 
        };
    }
    
    // Check required fields
    if (!data.diagram_type) {
        return { valid: false, error: 'Invalid file: missing diagram_type' };
    }
    
    if (!data.spec) {
        return { valid: false, error: 'Invalid file: missing diagram data' };
    }
    
    // Check diagram type is supported (matches StateManager validDiagramTypes)
    const validTypes = [
        'bubble_map', 'double_bubble_map', 'circle_map', 'tree_map',
        'brace_map', 'flow_map', 'multi_flow_map', 'bridge_map',
        'concept_map', 'mindmap', 'mind_map',
        'factor_analysis', 'three_position_analysis', 'perspective_analysis',
        'goal_analysis', 'possibility_analysis', 'result_analysis',
        'five_w_one_h', 'whwm_analysis', 'four_quadrant'
    ];
    
    if (!validTypes.includes(data.diagram_type)) {
        return { 
            valid: false, 
            error: `Unsupported diagram type: ${data.diagram_type}` 
        };
    }
    
    // Style and metadata are OPTIONAL - don't fail if missing or malformed
    // Just log a warning and continue (diagram still renders with defaults)
    if (data.style && typeof data.style !== 'object') {
        console.warn('Invalid style section in .mg file, using defaults');
        // Don't fail - just ignore bad style data
    }
    
    if (data.metadata && typeof data.metadata !== 'object') {
        console.warn('Invalid metadata section in .mg file, ignoring');
        // Don't fail - metadata is informational only
    }
    
    return { valid: true };
}

/**
 * Apply imported diagram data
 * Uses DiagramSelector.transitionToEditor() flow (lines 414-452)
 * @param {Object} data - Validated .mg file data
 */
async applyImportedDiagram(data) {
    const diagramType = data.diagram_type;
    const spec = data.spec;
    const style = data.style;
    const metadata = data.metadata;
    
    // Get diagram selector reference
    const diagramSelector = window.diagramSelector;
    if (!diagramSelector) {
        throw new Error('Diagram selector not initialized');
    }
    
    // If already in editor mode, go back to gallery first
    if (diagramSelector.editorActive) {
        await diagramSelector.backToGallery();
        // Small delay to ensure cleanup
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    // Get diagram config for name
    const diagramConfig = diagramSelector.diagramTypes[diagramType];
    if (!diagramConfig) {
        throw new Error(`Unknown diagram type: ${diagramType}`);
    }
    
    // Apply saved style to styleManager before rendering (if valid style data exists)
    // Style is optional - diagram renders with defaults if missing
    if (style && typeof style === 'object' && window.styleManager) {
        this.applyImportedStyle(diagramType, style);
    }
    
    // Use existing transition flow with imported spec instead of template
    diagramSelector.transitionToEditor(diagramType, spec, diagramConfig.name);
    
    this.logger.info('ExportManager', 'Imported diagram applied', {
        diagramType,
        specKeys: Object.keys(spec),
        hasStyle: !!style,
        author: metadata?.author?.name || 'unknown',
        createdAt: data.created_at
    });
}

/**
 * Apply imported style to styleManager
 * @param {string} diagramType - Type of diagram
 * @param {Object} style - Style data from .mg file
 */
applyImportedStyle(diagramType, style) {
    if (!window.styleManager || !style) return;
    
    try {
        // Get a copy of the default theme to modify
        const currentTheme = { ...window.styleManager.getDefaultTheme(diagramType) };
        
        if (style.colors) {
            // Map generic color names to diagram-specific names
            const colorMapping = {
                topicFill: ['topicFill', 'centralTopicFill'],
                topicText: ['topicText', 'centralTopicText'],
                attributeFill: ['attributeFill', 'branchFill'],
                attributeText: ['attributeText', 'branchText'],
                background: ['background']
            };
            
            Object.entries(style.colors).forEach(([key, value]) => {
                if (colorMapping[key]) {
                    colorMapping[key].forEach(themeKey => {
                        if (currentTheme.hasOwnProperty(themeKey)) {
                            currentTheme[themeKey] = value;
                        }
                    });
                }
            });
        }
        
        if (style.fonts) {
            if (style.fonts.topicSize) currentTheme.fontTopic = style.fonts.topicSize;
            if (style.fonts.attributeSize) {
                currentTheme.fontAttribute = style.fonts.attributeSize;
                currentTheme.fontBranch = style.fonts.attributeSize;
            }
        }
        
        // IMPORTANT: Apply the modified theme to styleManager
        // Store as temporary import override (will be used during render)
        window.styleManager.setImportedTheme(diagramType, currentTheme);
        
        this.logger.debug('ExportManager', 'Applied imported style', {
            diagramType,
            colorCount: Object.keys(style.colors || {}).length,
            fontCount: Object.keys(style.fonts || {}).length
        });
        
    } catch (error) {
        this.logger.warn('ExportManager', 'Failed to apply imported style, using defaults', error);
        // Non-fatal: continue with default styles
    }
}
```

---

### Step 5: Update ToolbarManager - Wire Up UI Events

**File:** `static/js/editor/toolbar-manager.js`

#### 5.1 Modify `initializeElements()` (lines 103-169)

**Location:** Around lines 119-120

```javascript
// Existing (line 119):
this.resetBtn = document.getElementById('reset-btn');  // REMOVE this line
this.exportBtn = document.getElementById('export-btn');

// Add new (after exportBtn):
this.saveBtn = document.getElementById('save-btn');
this.importBtn = document.getElementById('import-btn');
this.importFileInput = document.getElementById('import-file-input');
```

#### 5.2 Modify `attachEventListeners()` (method starts at line 174)

**Remove reset button handler (lines 254-257):**
```javascript
// REMOVE these lines:
this.resetBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    this.handleReset();
});
```

**Current export handler (lines 258-261) - keep as is:**
```javascript
this.exportBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    this.handleExport();
});
```

**Add new handlers after export:**
```javascript
// Export button - PNG export (existing, no change needed)
this.exportBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    this.handleExport(); // Existing PNG export (line 1270)
});

// Save button - .mg file export (NEW)
this.saveBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    this.handleSave();
});

// Import button (NEW)
this.importBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    this.handleImport();
});

// Import file input change (NEW)
this.importFileInput?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        this.handleFileSelected(file);
    }
    // Reset input so same file can be selected again
    this.importFileInput.value = '';
});
```

#### 5.3 Add new methods (after `handleExport()` which starts at line 1270):

**Location:** Add after `performPNGExport()` method (which follows `handleExport()`)

```javascript
/**
 * Handle save to .mg format
 */
handleSave() {
    if (!this.editor || !this.editor.currentSpec) {
        this.showNotification(this.getNotif('noDiagramToSave'), 'error');
        return;
    }
    
    // Emit event for ExportManager to handle
    if (window.eventBus) {
        window.eventBus.emit('toolbar:export_requested', {
            format: 'mg',
            editor: this.editor
        });
    }
}

/**
 * Handle import button click
 */
handleImport() {
    this.importFileInput?.click();
}

/**
 * Handle selected file for import
 * @param {File} file - Selected .mg file
 */
async handleFileSelected(file) {
    logger.info('ToolbarManager', 'File selected for import', {
        name: file.name,
        size: file.size
    });
    
    // Warn if file is very large (> 1MB)
    if (file.size > 1024 * 1024) {
        logger.warn('ToolbarManager', 'Large file detected', { size: file.size });
    }
    
    try {
        // Read file contents
        const text = await file.text();
        
        let data;
        try {
            data = JSON.parse(text);
        } catch (parseError) {
            // JSON parse error - show specific message
            logger.error('ToolbarManager', 'JSON parse error', parseError);
            this.showNotification(this.getNotif('invalidFileFormat'), 'error');
            return;
        }
        
        // Validate and import via ExportManager
        if (window.eventBus) {
            window.eventBus.emit('toolbar:import_file', { data, filename: file.name });
        }
    } catch (error) {
        // File read error (rare)
        logger.error('ToolbarManager', 'Error reading import file', error);
        this.showNotification(this.getNotif('importFailed'), 'error');
    }
}
```

---

### Step 6: Update exportFormats Array

**File:** `static/js/managers/toolbar/export-manager.js`

**Location:** Line 27

**Current:**
```javascript
this.exportFormats = ['png', 'svg', 'json'];
```

**Change to:**
```javascript
this.exportFormats = ['png', 'svg', 'json', 'mg'];
```

---

### Step 7: Add Language Support

**File:** `static/js/editor/language-manager.js`

#### 7.1 Add to English `notif` object (lines 241-277, add after line 243):

```javascript
notif: {
    // ... existing notifications ...
    noDiagramToExport: 'No diagram to export!',
    diagramExported: 'Diagram exported as PNG!',
    exportFailed: 'Failed to export diagram',
    
    // NEW: Save/Import .mg notifications
    noDiagramToSave: 'No diagram to save!',
    diagramSaved: 'Diagram saved as .mg file!',
    saveFailed: 'Failed to save diagram',
    importSuccess: 'Diagram imported successfully!',
    importFailed: 'Failed to import diagram',
    invalidFileFormat: 'Invalid file format',
    unsupportedVersion: (version) => `Unsupported file version: ${version}`,
    unsupportedDiagramType: (type) => `Unsupported diagram type: ${type}`,
    
    // ... rest of notifications ...
}
```

#### 7.2 Add to Chinese `notif` object (lines 494-496, add after line 496):

```javascript
notif: {
    // ... existing notifications ...
    noDiagramToExport: '没有可导出的图示！',
    diagramExported: '图示已导出为PNG！',
    exportFailed: '导出图示失败',
    
    // NEW: Save/Import .mg notifications
    noDiagramToSave: '没有可保存的图示！',
    diagramSaved: '图表已保存为 .mg 文件！',
    saveFailed: '保存图表失败',
    importSuccess: '图表导入成功！',
    importFailed: '图表导入失败',
    invalidFileFormat: '无效的文件格式',
    unsupportedVersion: (version) => `不支持的文件版本：${version}`,
    unsupportedDiagramType: (type) => `不支持的图表类型：${type}`,
    
    // ... rest of notifications ...
}
```

#### 7.3 Add to Azerbaijani `notif` object (lines 745-747, add after line 747):

```javascript
notif: {
    // ... existing notifications ...
    noDiagramToExport: 'İxrac ediləcək diaqram yoxdur!',
    diagramExported: 'Diaqram PNG kimi ixrac edildi!',
    exportFailed: 'Diaqramı ixrac etmək mümkün olmadı',
    
    // NEW: Save/Import .mg notifications
    noDiagramToSave: 'Saxlanılacaq diaqram yoxdur!',
    diagramSaved: 'Diaqram .mg faylı kimi saxlanıldı!',
    saveFailed: 'Diaqramı saxlamaq mümkün olmadı',
    importSuccess: 'Diaqram uğurla idxal edildi!',
    importFailed: 'Diaqramı idxal etmək mümkün olmadı',
    invalidFileFormat: 'Yanlış fayl formatı',
    unsupportedVersion: (version) => `Dəstəklənməyən fayl versiyası: ${version}`,
    unsupportedDiagramType: (type) => `Dəstəklənməyən diaqram növü: ${type}`,
    
    // ... rest of notifications ...
}
```

#### 7.4 Button text handled by spans

The `lang-en` and `lang-zh` spans in HTML will be shown/hidden by the existing language toggle mechanism. No additional code needed.

---

### Step 8: Add StyleManager Import Support

**File:** `static/js/style-manager.js`

**Add new method** (after existing theme methods):

```javascript
/**
 * Store imported theme for use during diagram render
 * @param {string} diagramType - Type of diagram
 * @param {Object} theme - Theme object with colors and fonts
 */
setImportedTheme(diagramType, theme) {
    // Store imported theme in temporary storage
    if (!this.importedThemes) {
        this.importedThemes = {};
    }
    this.importedThemes[diagramType] = theme;
    
    this.logger?.debug('StyleManager', 'Stored imported theme', { diagramType });
}

/**
 * Get imported theme if available, otherwise return default
 * @param {string} diagramType - Type of diagram
 * @returns {Object} Theme object
 */
getTheme(diagramType) {
    // Check for imported theme first
    if (this.importedThemes && this.importedThemes[diagramType]) {
        const imported = this.importedThemes[diagramType];
        // Clear after use (one-time import)
        delete this.importedThemes[diagramType];
        return imported;
    }
    // Fall back to default
    return this.getDefaultTheme(diagramType);
}
```

**Note:** This allows imported themes to be applied once during render, then falls back to defaults for subsequent operations.

---

## Import/Export Data Flow

### Export Flow (Save .mg)

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Save Button    │───►│  ToolbarManager │───►│  ExportManager  │
│  (click)        │    │  handleSave()   │    │  exportToMG()   │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
                       ┌───────────────────────────────┘
                       ▼
            ┌──────────────────────┐
            │  Collect data:       │
            │  - editor.currentSpec│
            │  - styleManager      │
            │  - app version       │
            │  - language/LLM      │
            └──────────┬───────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  Create .mg JSON     │
            │  Download file       │
            │  Show notification   │
            └──────────────────────┘
```

### Import Flow (Load .mg)

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Import Button  │───►│  ToolbarManager │───►│  File Input     │
│  (click)        │    │  handleImport() │    │  (file picker)  │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
       ┌───────────────────────────────────────────────┘
       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Read file       │───►│  Parse JSON      │───►│  Emit event      │
│  file.text()     │    │  JSON.parse()    │    │  toolbar:import  │
└──────────────────┘    └──────────────────┘    └────────┬─────────┘
                                                         │
                       ┌─────────────────────────────────┘
                       ▼
            ┌──────────────────────┐
            │  ExportManager       │
            │  handleImportData()  │
            └──────────┬───────────┘
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
┌──────────────┐              ┌──────────────────┐
│ Validate:    │              │ If valid:        │
│ - header     │──────────────│ applyImportedDiagram()
│ - version    │              │ - backToGallery()│
│ - type       │              │ - applyStyle()   │
│ - spec       │              │ - transitionToEditor()
└──────────────┘              └──────────────────┘
```

### Data Symmetry Check

| Field | Export Source | Import Destination |
|-------|---------------|-------------------|
| `mindgraph.version` | Hardcoded "1.0" | Validated in `validateMGFile()` |
| `diagram_type` | `editor.diagramType` | `diagramSelector.transitionToEditor()` |
| `spec` | `editor.currentSpec` | Passed to `InteractiveEditor` |
| `style.colors.*` | `styleManager.getTheme()` | `styleManager.setImportedTheme()` |
| `style.fonts.*` | `styleManager.getTheme()` | `styleManager.setImportedTheme()` |
| `metadata.*` | Various sources | Logged only (informational) |

---

## Testing Plan

### Unit Tests

1. **File Format Validation**
   - Valid .mg file passes validation
   - Missing mindgraph header fails
   - Unsupported version fails
   - Missing diagram_type fails
   - Invalid diagram_type fails

2. **Export Functionality**
   - Export generates valid JSON
   - Filename format is correct
   - All required fields are present

3. **Import Functionality**
   - Valid file imports successfully
   - Diagram renders correctly after import
   - Invalid file shows error message

### Integration Tests

1. **Round-Trip Test**
   - Create diagram
   - Export to .mg
   - Clear/reset
   - Import .mg file
   - Verify diagram matches original

2. **Cross-Diagram-Type Test**
   - Test import/export for each diagram type
   - Verify spec structure is preserved

### Manual Testing Checklist

**Export (PNG) Tests:**
- [ ] Export button exports PNG correctly
- [ ] PNG file downloads with correct name format
- [ ] PNG quality is good (3x scale)
- [ ] Success notification shown after export

**Save (.mg) Tests:**
- [ ] Save button downloads .mg file
- [ ] Filename format is correct: `{diagram_type}_{llm}_{timestamp}.mg`
- [ ] Saved file contains valid JSON
- [ ] Saved file has correct `mindgraph.version` and `mindgraph.format`
- [ ] Saved file contains `style` section with colors/fonts
- [ ] Saved file contains `metadata` section
- [ ] Success notification shown after save

**Import (.mg) Tests:**
- [ ] Import button triggers file picker
- [ ] Only .mg files can be selected (accept=".mg")
- [ ] Valid .mg file imports and renders correctly
- [ ] Imported diagram matches original (round-trip test)
- [ ] Style/colors preserved after import
- [ ] Invalid file shows error notification with specific message
- [ ] Corrupted JSON shows "Invalid file format" error
- [ ] File with wrong version shows "Unsupported version" error
- [ ] File with unknown diagram type shows error
- [ ] Imported diagram is fully editable
- [ ] History/undo works after import
- [ ] Can import from both gallery view and editor view

**UI Tests:**
- [ ] File Operations group displays correctly
- [ ] All three buttons have correct icons
- [ ] Language toggle updates Export/Save/Import button labels
- [ ] Color coding: Export (green), Save & Import (transparent)
- [ ] Mobile: Icons only mode works
- [ ] Mobile: File picker works on iOS/Android

---

## Fallback Philosophy

**Core Principle:** As long as the node text data exists in the JSON, render the diagram. Everything else is optional.

| Field | Required? | If Missing |
|-------|-----------|------------|
| `spec` (node/text data) | **YES** | FAIL - nothing to render |
| `diagram_type` | **YES** | FAIL - don't know how to render |
| `mindgraph.version` | **YES** | FAIL - can't validate compatibility |
| `mindgraph.format` | **YES** | FAIL - might not be a .mg file |
| `style` | No | Use default theme |
| `style.colors` | No | Use default colors |
| `style.fonts` | No | Use default fonts |
| `metadata` | No | Skip (informational only) |
| `created_at` | No | Skip |

**Minimal Valid .mg File:**
```json
{
  "mindgraph": { "version": "1.0", "format": "mg" },
  "diagram_type": "bubble_map",
  "spec": { "topic": "Hello", "adjectives": ["world"] }
}
```
This renders correctly with default styling - no style or metadata needed.

---

## Error Handling

### Import Errors

| Error | User Message | Cause |
|-------|--------------|-------|
| JSON parse error | "Invalid file format" | Corrupted or non-JSON file |
| Missing header | "Invalid file format: missing MindGraph header" | Not a .mg file |
| Unsupported version | "Unsupported file version: X.X" | Old/future format |
| Missing diagram_type | "Invalid file: missing diagram_type" | Corrupted file |
| Invalid diagram_type | "Unsupported diagram type: X" | Unknown type |
| Render failure | "Failed to render diagram" | Spec doesn't match type |

---

## Edge Cases and Limitations

### Known Limitations

| Limitation | Description | Workaround |
|------------|-------------|------------|
| File size | Very large diagrams (>1MB) may be slow to import | Consider splitting into multiple files |
| Custom fonts | Custom fonts not in user's system won't render | Falls back to system fonts |
| Old versions | Files from future versions may not be compatible | Check version before import |
| Thinking tools | Some diagram types are under development | Validation rejects unsupported types |

### Edge Cases Handled

| Edge Case | Handling |
|-----------|----------|
| Import while in editor | Goes back to gallery first, then imports |
| Import while in gallery | Directly transitions to editor |
| Empty spec | Validation rejects file |
| Missing style section | Uses default theme |
| Missing metadata | Uses defaults for all fields |
| Author info null | Gracefully handled, no author shown |

### Browser Compatibility

| Browser | File API | Tested |
|---------|----------|--------|
| Chrome 90+ | Full support | Yes |
| Firefox 90+ | Full support | Yes |
| Safari 14+ | Full support | Yes |
| Edge 90+ | Full support | Yes |
| Mobile Chrome | Full support | Yes |
| Mobile Safari | Full support | Yes |

---

## Backward Compatibility

### Version Migration Strategy

When the `.mg` format evolves, the import system must handle older versions gracefully:

```javascript
/**
 * Migrate old .mg file format to current version
 * @param {Object} data - Parsed .mg file data
 * @returns {Object} Migrated data in current format
 */
migrateMGFile(data) {
    const version = data.mindgraph?.version || '1.0';
    let migrated = { ...data };
    
    // Version 1.0 → 1.1 (example future migration)
    if (version === '1.0') {
        // Future: Add any missing fields introduced in 1.1
        // migrated.someNewField = migrated.someNewField || defaultValue;
    }
    
    // Version 1.1 → 1.2 (example)
    // if (version === '1.0' || version === '1.1') {
    //     // Migrate to 1.2 format
    // }
    
    // Update version to current
    migrated.mindgraph.version = '1.0';  // Keep at 1.0 until we actually change format
    
    this.logger.debug('ExportManager', 'File migration complete', {
        fromVersion: version,
        toVersion: migrated.mindgraph.version
    });
    
    return migrated;
}
```

### Compatibility Rules

| Rule | Implementation |
|------|----------------|
| **Older files always work** | Migration function upgrades old formats |
| **Unknown fields ignored** | Don't fail on extra fields (future-proofing) |
| **Missing optional fields** | Use sensible defaults |
| **Core fields required** | Only `mindgraph`, `diagram_type`, `spec` are required |

### Field Default Values

When importing older files that may be missing newer fields:

```javascript
// Apply defaults for missing optional fields
const defaults = {
    style: {
        theme: 'default',
        colors: null,  // Use styleManager defaults
        fonts: null    // Use styleManager defaults
    },
    metadata: {
        app_version: 'unknown',
        language: 'en',
        source_llm: 'unknown',
        author: null,
        title: null,
        description: null
    },
    created_at: new Date().toISOString()
};

// Merge with defaults (imported data takes precedence)
const normalizedData = {
    ...data,
    style: { ...defaults.style, ...(data.style || {}) },
    metadata: { ...defaults.metadata, ...(data.metadata || {}) },
    created_at: data.created_at || defaults.created_at
};
```

### Update validateMGFile() for Backward Compatibility

```javascript
validateMGFile(data) {
    // Check mindgraph header (required)
    if (!data.mindgraph || !data.mindgraph.format) {
        return { valid: false, error: 'Invalid file format: missing MindGraph header' };
    }
    
    if (data.mindgraph.format !== 'mg') {
        return { valid: false, error: 'Invalid file format: not a .mg file' };
    }
    
    // Version check - accept older versions, reject future versions
    const version = data.mindgraph.version || '1.0';
    const currentVersion = '1.0';
    const [major, minor] = version.split('.').map(Number);
    const [currentMajor] = currentVersion.split('.').map(Number);
    
    // Reject if major version is higher than current (future file)
    if (major > currentMajor) {
        return { 
            valid: false, 
            error: `File version ${version} is newer than supported. Please update MindGraph.` 
        };
    }
    
    // Accept older versions (will be migrated)
    // Accept same major version (compatible)
    
    // Check required fields
    if (!data.diagram_type) {
        return { valid: false, error: 'Invalid file: missing diagram_type' };
    }
    
    if (!data.spec) {
        return { valid: false, error: 'Invalid file: missing diagram data' };
    }
    
    // ... rest of validation (diagram type check)
    
    return { valid: true, needsMigration: version !== currentVersion };
}
```

### Integration with handleImportData()

```javascript
async handleImportData(data, filename) {
    // ... existing code ...
    
    try {
        // Validate file structure
        const validation = this.validateMGFile(data);
        if (!validation.valid) {
            throw new Error(validation.error);
        }
        
        // NEW: Migrate if needed
        let processedData = data;
        if (validation.needsMigration) {
            processedData = this.migrateMGFile(data);
            this.logger.info('ExportManager', 'Migrated old file format', {
                fromVersion: data.mindgraph?.version,
                toVersion: processedData.mindgraph.version
            });
        }
        
        // Apply imported diagram with migrated data
        await this.applyImportedDiagram(processedData);
        
        // ... rest of code ...
    }
}
```

### Compatibility Matrix

| File Version | App Version | Result |
|--------------|-------------|--------|
| 1.0 | 1.0 | ✅ Works directly |
| 1.0 | 1.1+ | ✅ Works (no migration needed yet) |
| 1.1 | 1.0 | ❌ Rejected (future file) |
| 1.0 | 2.0 | ✅ Migrated to 2.0 format |

---

## Future Enhancements

1. **Version Migration**: Auto-upgrade old file versions (framework ready)
2. **Compression**: Compress large diagrams with gzip
3. **Encryption**: Optional password protection
4. **Cloud Sync**: Optional cloud backup integration
5. **Drag & Drop Import**: Drop .mg file onto editor
6. **Recent Files**: Remember recently opened .mg files
7. **Export Dialog**: Modal with options (author, title, compression)
8. **Batch Export**: Export multiple diagrams at once
9. **Keyboard Shortcuts**: Ctrl+S to export, Ctrl+O to import

---

## Files to Modify Summary

| File | Line References | Changes |
|------|-----------------|---------|
| `templates/editor.html` | Lines 30-40 (script), 426-430 (toolbar) | Add globals; Replace export+reset with File Operations group (Export/Save/Import) |
| `static/css/editor-toolbar.css` | After line 99 | Add file-operations-group styling (~80 lines) |
| `static/js/managers/toolbar/export-manager.js` | Lines 27, 39-46, 78-88, after 491 | Add 'mg' format, import event, exportToMG(), validation, apply methods |
| `static/js/editor/toolbar-manager.js` | Lines 119-120, 254-261, after 1270 | Remove resetBtn; Add saveBtn/importBtn; Add save/import methods |
| `static/js/editor/language-manager.js` | After lines 243, 496, 747 | Add save/import notification translations (EN, ZH, AZ) |
| `routers/pages.py` | Lines 130-143 | Pass `version` and `user_info` to template context |
| `static/js/style-manager.js` | **(required)** | Add `setImportedTheme()` method to apply imported theme overrides |

**Removals:**
- `templates/editor.html`: Remove reset button (line 429)
- `static/js/editor/toolbar-manager.js`: Remove `this.resetBtn` (line 119) and its event listener (lines 254-257)

---

## Implementation Priority

### Phase 0: Prerequisites (Step 0)
1. Expose app version to frontend via `window.MINDGRAPH_VERSION`
2. Expose user info via `window.MINDGRAPH_USER` (optional, for author metadata)
3. Update backend to pass version and user_info to template

**Estimated lines of code:** ~20

### Phase 1: Save .mg (Steps 1-3, 6)
1. Update HTML with File Operations group (Export/Save/Import)
2. Add CSS for group styling (simplified, no dropdown)
3. Add `exportToMG()` method with style and author extraction
4. Update `exportFormats` array

**Estimated lines of code:** ~200 (HTML group + CSS + save logic)

### Phase 2: Import .mg (Steps 4-5)
1. Add import button to HTML
2. Wire up file input in ToolbarManager
3. Add validation and apply methods to ExportManager
4. Add `applyImportedStyle()` method
5. Handle `toolbar:import_file` event

**Estimated lines of code:** ~250 (increased for style restoration)

### Phase 3: Polish (Step 7)
1. Add translations (EN, ZH, AZ)
2. Test all diagram types
3. Error handling refinement
4. (Future) Export dialog with author opt-in checkbox

**Estimated lines of code:** ~50

### Phase 4: StyleManager Support (Step 8)
1. Add `setImportedTheme()` method
2. Modify `getTheme()` to check for imported theme first

**Estimated lines of code:** ~30

### Total Estimated: ~550 lines

---

## Verification Checklist

### All Verified Against Codebase (2025-12-06)

**Core Architecture:**
- [x] `DiagramSelector.transitionToEditor(diagramType, template, diagramName)` - Line 414
- [x] `DiagramSelector.backToGallery()` - Line 723 (cancels LLM, cleans canvas)
- [x] `DiagramSelector.editorActive` property - Line 729

**ExportManager:**
- [x] `exportFormats = ['png', 'svg', 'json']` - Line 27
- [x] `subscribeToEvents()` - Lines 39-46
- [x] `handleExport()` switch statement - Lines 78-88
- [x] `exportToJSON()` ends at line 491 (add new methods after)
- [x] `generateFilename(editor, extension)` - Line 532
- [x] `downloadFile(url, filename, mimeType)` - Line 499

**ToolbarManager:**
- [x] `this.resetBtn` - Line 119
- [x] `this.exportBtn` - Line 120
- [x] Reset event listener - Lines 254-257
- [x] Export event listener - Lines 258-261
- [x] `handleExport()` - Line 1270 (calls `performPNGExport()`)

**StyleManager:**
- [x] `getDefaultTheme(diagramType)` - Line 453 (returns copy of theme)
- [ ] `setImportedTheme()` - **DOES NOT EXIST** (must add in Step 8)
- [ ] `getTheme()` with import check - **DOES NOT EXIST** (must add in Step 8)

**Language Manager:**
- [x] EN `notif` object ends at line 277 (add after line 243)
- [x] ZH `notif` object - add after line 496
- [x] AZ `notif` object - add after line 747

**Backend:**
- [x] `routers/pages.py` template response - Lines 130-143

**Note:** `mind_map` and `mindmap` are both in validTypes list for backward compatibility

---

## Quick Reference

### Event Bus Events

| Event | Direction | Data | Description |
|-------|-----------|------|-------------|
| `toolbar:export_requested` | Toolbar → ExportManager | `{ format: 'mg', editor }` | Request export |
| `toolbar:import_file` | Toolbar → ExportManager | `{ data, filename }` | Import file data |
| `file:mg_export_completed` | ExportManager → All | `{ filename }` | Export success |
| `file:mg_export_error` | ExportManager → All | `{ error }` | Export failed |
| `file:mg_import_started` | ExportManager → All | `{ filename }` | Import started |
| `file:mg_import_completed` | ExportManager → All | `{ filename, diagramType }` | Import success |
| `file:mg_import_error` | ExportManager → All | `{ error }` | Import failed |
| `notification:show` | Any → NotificationManager | `{ message, type }` | Show notification |

### Global Variables

| Variable | Type | Description |
|----------|------|-------------|
| `window.MINDGRAPH_VERSION` | string | App version from VERSION file |
| `window.MINDGRAPH_USER` | object/null | User info (optional) |
| `window.MINDGRAPH_INCLUDE_AUTHOR` | boolean | Whether to include author in export |

### File Naming Convention

Export filename format: `{diagram_type}_{llm_model}_{timestamp}.mg`

Example: `bubble_map_qwen_2025-12-06T14-30-45.mg`

---

*Document created: 2025-12-06*
*Last updated: 2025-12-06*
*Status: Planning - Verified against codebase*
*Total lines of code: ~550 estimated*
*Design: Clean 3-button layout (Export green / Save transparent / Import transparent) - Reset removed*

