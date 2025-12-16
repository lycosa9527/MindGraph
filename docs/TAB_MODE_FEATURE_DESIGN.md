# Tab Mode Feature Design Document

## Table of Contents
1. [Feature Overview](#feature-overview)
2. [Codebase Verification Summary](#codebase-verification-summary)
3. [Code Review of Existing Patterns](#code-review-of-existing-patterns)
4. [Architecture Design](#architecture-design)
5. [UI/UX Design](#uiux-design)
6. [Backend API Design](#backend-api-design)
7. [Frontend Implementation](#frontend-implementation)
8. [LLM Integration](#llm-integration)
9. [Implementation Plan](#implementation-plan)

---

## Codebase Verification Summary

✅ **Verified Against Actual Codebase**

This design has been reviewed against the actual MindGraph codebase to ensure feasibility and alignment with existing patterns:

### ✅ Centralized Prompt System
- **Location**: `prompts/__init__.py` with `get_prompt(diagram_type, language, prompt_type)`
- **Pattern**: Prompts stored as constants in files/folders like `prompts/thinking_maps.py` or `prompts/thinking_modes/`, registered in dictionaries
- **Key Format**: `"{diagram_type}_{prompt_type}_{language}"` (e.g., `"double_bubble_map_agent_generation_en"`)
- **Action**: Tab mode prompts will have dedicated folder `prompts/tab_mode/` with sub-files for organization

### ✅ Agent Architecture
- **Base Class**: All agents inherit from `BaseAgent` (`agents/core/base_agent.py`)
- **LLM Calls**: Use `llm_service.chat()` with proper parameters
- **Pattern**: Agents use `from prompts import get_prompt` for centralized prompts
- **LangChain Support**: Complex agents (like Learning Agent V3) use LangChain with tools for context extraction
- **Action**: Tab agent will use LangChain with tools for complex context extraction across 10 diagram types, while maintaining `llm_service.chat()` for LLM calls (preserves middleware)

### ✅ API Endpoint Pattern
- **Router Structure**: FastAPI routers in `routers/` directory (e.g., `routers/thinking.py`, `routers/api.py`)
- **Registration**: Routers registered in `main.py` with `app.include_router()`
- **Authentication**: Use `get_current_user_or_api_key` from `utils.auth` (supports both JWT and API keys)
- **Action**: Create `routers/tab_mode.py` following same pattern

### ✅ Request/Response Models
- **Location**: `models/requests.py` and `models/responses.py`
- **Pattern**: Pydantic `BaseModel` with `Field()` validators
- **Enums**: Use `DiagramType`, `LLMModel`, `Language` from `models.common`
- **Action**: Add `TabSuggestionRequest` and `TabSuggestionResponse` models

### ✅ Frontend Integration Points
- **NodeEditor**: `static/js/editor/node-editor.js` - uses native `<textarea>` element
- **PropertyPanel**: `static/js/managers/toolbar/property-panel-manager.js` - uses `document.getElementById('prop-text')`
- **Event Bus**: `static/js/core/event-bus.js` - centralized event system
- **State Manager**: `static/js/core/state-manager.js` - state management
- **Action**: Tab mode manager will integrate with these existing systems

### ✅ Double Bubble Map Structure
- **Data Format**: `{left: str, right: str, similarities: [], left_differences: [], right_differences: []}`
- **Main Topics**: `spec.left` and `spec.right` are the two main topics
- **Node Categories**: Three categories for different node types
- **Action**: Context extraction will read `left` and `right` from spec

### ✅ LLM Service Integration
- **Service**: `services/llm_service.py` with `llm_service.chat()` async method
- **Token Tracking**: Via `user_id`, `organization_id`, `request_type`, `endpoint_path` parameters
- **Configuration**: Temperature, max_tokens from `config.settings`
- **Action**: Tab agent will use `llm_service.chat()` with `request_type='autocomplete'`

### ✅ LangChain Integration
- **Pattern**: Complex agents (like Learning Agent V3) use LangChain with tools for context extraction
- **Tools**: Tab Agent uses LangChain tools (`extract_diagram_context`, `extract_node_info`) for structured context extraction across 10 diagram types
- **LLM Calls**: Still uses `llm_service.chat()` directly (preserves middleware: rate limiting, error handling, token tracking, performance tracking, timeouts)
- **Benefits**: Cleaner code, reusable tools, better parsing, easier to extend
- **Action**: Tab agent uses LangChain tools for context extraction while maintaining `llm_service.chat()` for LLM calls

**Conclusion**: The design is fully aligned with existing codebase patterns and is ready for implementation. Tab Agent uses LangChain for structured context extraction while maintaining middleware benefits through `llm_service.chat()`.

---

## Feature Overview

### Purpose
Tab Mode provides two intelligent features:

1. **Editing Autocomplete**: Context-aware autocomplete suggestions when users edit node content in modals or property panels. Similar to Cursor's tab completion, it uses LLM to analyze the current diagram context and provide relevant suggestions based on:
   - Main topic node content (e.g., "apples" and "oranges" in double bubble map)
   - Current partial input (e.g., "fru..." or "水...")
   - Diagram type and node category context
   - Existing node content in the diagram

2. **Viewing Expansion**: Quick node expansion when users click a node and press Tab in viewing mode. Automatically generates and fills out children nodes using LLM:
   - User clicks a branch node → Presses Tab → Children nodes are generated
   - Example: In mindmap, click "Fruits" branch → Tab → Generates ["Apples", "Oranges", "Bananas"] as children
   - Works for hierarchical diagrams (mindmap, tree map, flow map, brace map)

### Key Features
1. **Tab Button**: Lower right corner toggle button to enable/disable tab mode
2. **Dual Mode Support**: 
   - **Editing Mode**: Inline autocomplete suggestions in text inputs
   - **Viewing Mode**: Node expansion on Tab key press
3. **Context-Aware Suggestions**: LLM analyzes main topic nodes and current input
4. **Multi-language Support**: Handles both English and Chinese completions
5. **Visual Feedback**: Inline suggestion display with Tab key acceptance (editing) or loading indicator (viewing)
6. **Diagram-Specific Logic**: Different behavior for different diagram types (double bubble map example for editing, mindmap example for expansion)

### Use Case Examples

#### Editing Autocomplete: Double Bubble Map
**Scenario**: User is comparing "apples" vs "oranges"
- User types "fru..." in a similarity node → Suggests "fruit"
- User types "水..." in Chinese → Suggests "水果" (fruit in Chinese)
- User types "vit..." → Suggests "vitamin C" (common similarity)
- User types "red" → Suggests "red color" (apple-specific difference)

#### Viewing Expansion: Mindmap
**Scenario**: User has a mindmap with topic "Learning Methods" and branch "Active Learning"
- User clicks the "Active Learning" branch node → Presses Tab → System generates children:
  - "Group Discussions"
  - "Role Playing"
  - "Case Studies"
  - "Peer Teaching"
- Children nodes are automatically added to the diagram
- User can continue: Click "Group Discussions" → Tab → Generates sub-children:
  - "Round Robin"
  - "Think-Pair-Share"
  - "Jigsaw Method"

#### Viewing Expansion: Tree Map
**Scenario**: User has a tree map with category "Fruits"
- User clicks "Fruits" category → Presses Tab → System generates items:
  - "Apples"
  - "Oranges"
  - "Bananas"
  - "Grapes"

---

## Code Review of Existing Patterns

### 1. Editing Mechanisms

#### NodeEditor Modal (`static/js/editor/node-editor.js`)
**Current Implementation:**
- Creates modal overlay with textarea for node text editing
- Handles keyboard shortcuts (Escape to cancel, Ctrl+Enter for newline)
- Character count display
- Auto-focus on text input

**Key Patterns:**
```12:20:static/js/editor/node-editor.js
class NodeEditor {
    constructor(nodeData, onSave, onCancel) {
        this.nodeData = nodeData;
        this.onSave = onSave;
        this.onCancel = onCancel;
        this.modal = null;
        this.textInput = null;
    }
```

**Observations:**
- Uses D3.js for DOM manipulation
- Event-driven architecture with callbacks
- Clean separation of concerns (modal creation, event handling, save/cancel)
- Text input is a native `<textarea>` element (line 155-183)

**Integration Points for Tab Mode:**
- Need to intercept `input` events on `textInput` (native DOM element)
- Need to add suggestion UI overlay near cursor position
- Need to handle Tab key for accepting suggestions (currently Tab is not handled)
- Can attach event listeners after modal creation (in `attachEventListeners()` method)
- **CRITICAL**: Must extract `nodeId` from `this.nodeData.nodeId` (passed to constructor)
- **CRITICAL**: Must get diagram type from `window.currentEditor?.diagramType`
- **CRITICAL**: Must extract node metadata from DOM or spec using nodeId

#### Property Panel (`static/js/managers/toolbar/property-panel-manager.js`)
**Current Implementation:**
- Side panel with textarea for node text editing (`prop-text`)
- Auto-resize functionality
- Real-time property updates

**Key Patterns:**
```132:136:static/js/managers/toolbar/property-panel-manager.js
        if (this.propText && this.propText.tagName === 'TEXTAREA') {
            this.propText.addEventListener('input', (e) => {
                this.autoResizeTextarea(e.target);
            });
        }
```

**Observations:**
- Uses native DOM event listeners (`addEventListener`)
- Integrates with event bus architecture (`eventBus.onWithOwner()`)
- Auto-resize prevents UI jumps
- Text input is `this.propText` (textarea element from `document.getElementById('prop-text')`)

**Integration Points for Tab Mode:**
- Similar to NodeEditor, need to intercept input events on `this.propText`
- Suggestion UI should appear below textarea (calculate position from `getBoundingClientRect()`)
- Tab key handling needs to prevent default behavior (currently Tab is not handled)
- Can integrate in `attachEventListeners()` method or when loading properties
- **CRITICAL**: Must extract `nodeId` from `this.currentNodeId` (set in `loadNodeProperties()`)
- **CRITICAL**: Must get diagram type from `window.currentEditor?.diagramType`
- **CRITICAL**: Must extract node metadata from DOM element using `d3.select(\`[data-node-id="${nodeId}"]\`)`

### 2. Double Bubble Map Structure

#### Data Structure (`agents/thinking_maps/double_bubble_map_agent.py`)
**Current Implementation:**
```200:228:agents/thinking_maps/double_bubble_map_agent.py
    def validate_output(self, spec: Dict) -> Tuple[bool, str]:
        """
        Validate the generated double bubble map specification.
        
        Args:
            spec: The specification to validate
            
        Returns:
            Tuple of (is_valid, validation_message)
        """
        try:
            # Check required fields
            if not isinstance(spec, dict):
                return False, "Specification must be a dictionary"
            
            if 'left' not in spec or not spec['left']:
                return False, "Missing or empty left topic"
            
            if 'right' not in spec or not spec['right']:
                return False, "Missing or empty right topic"
            
            if 'left_differences' not in spec or not isinstance(spec['left_differences'], list):
                return False, "Missing or invalid left_differences list"
            
            if 'right_differences' not in spec or not isinstance(spec['right_differences'], list):
                return False, "Missing or invalid right_differences list"
            
            if 'similarities' not in spec or not isinstance(spec['similarities'], list):
                return False, "Missing or invalid similarities list"
```

**Key Structure:**
```json
{
  "left": "apples",
  "right": "oranges",
  "similarities": ["fruit", "vitamin C", "round"],
  "left_differences": ["red color", "grows on trees"],
  "right_differences": ["orange color", "citrus"]
}
```

**Observations:**
- Two main topics: `left` and `right`
- Three node categories: `similarities`, `left_differences`, `right_differences`
- Nodes are simple text strings in arrays

**Tab Mode Context Extraction:**
- Main topics: `spec.left` and `spec.right`
- Current node category: Determined by node's position/type
- Existing nodes: All nodes in the same category

### 3. LLM Integration Patterns

#### API Call Pattern (`routers/api.py`)
**Current Implementation:**
```151:189:routers/api.py
@router.post('/generate_graph', response_model=GenerateResponse)
async def generate_graph(
    req: GenerateRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Generate graph specification from user prompt using selected LLM model (async).
    
    This endpoint returns JSON with the diagram specification for the frontend editor to render.
    For PNG file downloads, use /api/export_png instead.
    """
    
    # Get language for error messages
    lang = get_request_language(x_language)
    
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("invalid_prompt", lang)
        )
    
    request_id = f"gen_{int(time.time()*1000)}"
    llm_model = req.llm.value if hasattr(req.llm, 'value') else str(req.llm)
    language = req.language.value if hasattr(req.language, 'value') else str(req.language)
    
    logger.debug(f"[{request_id}] Request: llm={llm_model!r}, language={language!r}, diagram_type={req.diagram_type}")
    
    if req.dimension_preference:
        logger.debug(f"[{request_id}] Dimension preference: {req.dimension_preference!r}")
    
    logger.debug(f"[{request_id}] Using LLM model: {llm_model!r}")
    
    try:
        # Generate diagram specification - fully async
        # Pass model directly through call chain (no global state)
        # Pass user context for token tracking
        user_id = current_user.id if current_user else None
```

**Observations:**
- Uses FastAPI router with dependency injection
- Supports both API key and JWT authentication
- Token tracking for user/organization
- Language support (en/zh)
- Request ID for logging

**Tab Mode API Requirements:**
- New endpoint: `/api/tab_suggestions` in `routers/tab_mode.py`
- Follow FastAPI router pattern (`APIRouter(prefix="/api", tags=["tab_mode"])`)
- Use `get_current_user_or_api_key` for authentication (matching `/api/generate_graph`)
- Fast response time (debouncing on frontend, 300ms)
- Context-aware prompt construction using centralized prompt system
- Returns array of suggestion strings
- Token tracking via `llm_service.chat()` parameters (`user_id`, `organization_id`, `request_type='autocomplete'`)

#### LLM Service Pattern (`services/llm_service.py`)
**Actual Pattern (verified from codebase):**
- Uses `llm_service.chat()` async method for LLM calls
- Centralized prompt management via `prompts/__init__.py` with `get_prompt()`
- Model selection (qwen, deepseek, hunyuan, kimi) via `LLMModel` enum
- Temperature and max_tokens configuration via `config.settings`
- Token tracking via `user_id`, `organization_id`, `request_type`, `endpoint_path` parameters

**Tab Mode LLM Requirements:**
- Low temperature (0.3) for consistent completions
- Low max_tokens (100) for fast responses
- Context injection: main topics, current input, node category
- Use `request_type='autocomplete'` for token tracking
- Use `endpoint_path='/api/tab_suggestions'` for tracking

### 4. UI Patterns

#### Status Bar (`templates/editor.html`)
**Current Implementation:**
```1085:1105:templates/editor.html
        <div class="editor-status-bar">
            <div class="status-left">
                <span id="node-count">Nodes: 0</span>
                <span id="edit-mode">Edit Mode: Active</span>
            </div>
            <div class="status-center">
                <span class="llm-label">AI Model:</span>
                <div class="llm-selector">
                    <button class="llm-btn" data-llm="qwen" title="Qwen (Fast & Reliable)">Qwen</button>
                    <button class="llm-btn" data-llm="deepseek" title="DeepSeek-v3.1 (High Quality)">DeepSeek</button>
                    <button class="llm-btn" data-llm="hunyuan" title="Hunyuan/混元 (Tencent Cloud)">Hunyuan</button>
                    <button class="llm-btn" data-llm="kimi" title="Kimi (Moonshot AI)">Kimi</button>
                </div>
            </div>
            <div class="status-right">
                <span id="school-name-display" class="school-name" style="display: none;"></span>
                <button id="reset-view-btn" class="reset-view-btn" title="Fit diagram to window">
                    <span class="reset-view-icon">⛶</span> Reset View
                </button>
            </div>
        </div>
```

**Observations:**
- Three-column layout: left, center, right
- Lower right corner has reset view button
- Uses semantic HTML with proper button elements
- Responsive design considerations

**Tab Mode UI Placement:**
- Add tab mode toggle button in `status-right` div
- Position before or after reset view button
- Use consistent styling with existing buttons

#### Event Bus Architecture (`static/js/core/event-bus.js`)
**Pattern:**
- Centralized event bus for component communication
- Owner-based event listener registration
- Event names follow `component:action` pattern

**Tab Mode Events:**
- `tab_mode:enabled` - Tab mode activated
- `tab_mode:disabled` - Tab mode deactivated
- `tab_mode:suggestion_requested` - Request suggestions for current input
- `tab_mode:suggestion_received` - Suggestions received from backend
- `tab_mode:suggestion_accepted` - User accepted a suggestion

### 5. Node Palette Comparison

#### Node Palette Manager (`static/js/editor/node-palette-manager.js`)
**Current Implementation:**
- Full-screen panel overlay
- Grid layout with node cards
- Batch loading with scroll detection
- Selection and assembly workflow

**Key Differences from Tab Mode:**
- **Node Palette**: Full-screen, visual selection, batch operations
- **Tab Mode**: Inline, text-based, real-time suggestions

**Similarities:**
- Both use LLM for intelligent suggestions
- Both need diagram context (main topics, node categories)
- Both integrate with event bus architecture

**Lessons Learned:**
- Debouncing is critical for performance
- Context extraction should be cached
- Error handling should be graceful (fallback to no suggestions)

---

## Architecture Design

### Component Structure

```
Tab Mode System
├── Frontend Components
│   ├── tab-mode-manager.js          # Main orchestrator (handles both modes)
│   ├── tab-mode-ui.js                # UI rendering (suggestion overlay + loading)
│   ├── tab-mode-input-handler.js    # Input event interception (editing mode)
│   ├── tab-mode-expansion-handler.js # Node expansion handler (viewing mode)
│   └── tab-mode-button.js            # Toggle button component
├── Backend Components
│   ├── routers/tab_mode.py           # API endpoints (suggestions + expansion)
│   ├── agents/tab_mode/tab_agent.py  # LLM agent (both autocomplete & expansion)
│   └── prompts/tab_mode/             # Dedicated centralized prompt folder
│       ├── __init__.py               # Prompt registry and exports
│       ├── autocomplete.py           # Autocomplete prompts (editing mode)
│       ├── expansion.py              # Expansion prompts (viewing mode)
│       └── colors.py                 # Color suggestion prompts
└── Integration Points
    ├── NodeEditor integration (editing mode)
    ├── PropertyPanel integration (editing mode)
    ├── Node selection integration (viewing mode)
    └── Event Bus integration
```

### Data Flow

#### Editing Mode (Autocomplete)
```
User types in input field
    ↓
Tab Mode Input Handler intercepts input event
    ↓
Debounce (300ms) to avoid excessive API calls
    ↓
Extract context:
  - Current diagram spec
  - Main topic nodes (left/right for double bubble)
  - Current node category
  - Partial input text
  - Cursor position
    ↓
Check if Tab Mode is enabled
    ↓
Call /api/tab_suggestions with mode="autocomplete"
    ↓
Backend Tab Agent:
  - Reads main topic nodes
  - Constructs LLM prompt for autocomplete
  - Calls LLM service
  - Returns top 3-5 suggestions
    ↓
Frontend receives suggestions
    ↓
Tab Mode UI renders suggestion overlay
    ↓
User presses Tab → Accept first suggestion
User presses Escape → Dismiss suggestions
User clicks suggestion → Accept that suggestion
```

#### Viewing Mode (Expansion)
```
User clicks a node in viewing mode
    ↓
Tab Mode Expansion Handler detects Tab key press
    ↓
Check if Tab Mode is enabled AND node is expandable
    ↓
Extract context:
  - Current diagram spec
  - Selected node (branch/category)
  - Node type and hierarchy level
  - Existing children (if any)
  - Main topic/center node
    ↓
Call /api/tab_expand with mode="expansion"
    ↓
Backend Tab Agent:
  - Reads selected node context
  - Constructs LLM prompt for expansion
  - Calls LLM service
  - Returns array of child node texts
    ↓
Frontend receives children nodes
    ↓
Tab Mode Manager adds children to diagram
    ↓
Trigger diagram re-render
    ↓
Show success notification
```

### State Management

**Tab Mode State:**
```javascript
{
  enabled: boolean,              // Tab mode toggle state
  mode: 'editing' | 'viewing',  // Current mode (editing = autocomplete, viewing = expansion)
  
  // Editing mode state
  activeInput: HTMLElement,      // Currently focused input/textarea
  currentSuggestions: string[],   // Current suggestion list
  selectedIndex: number,         // Currently highlighted suggestion (0-based)
  
  // Viewing mode state
  selectedNode: Object,          // Currently selected node for expansion
  isExpanding: boolean,          // Expansion in progress
  
  // Shared state
  isLoading: boolean,            // API request in progress
  lastRequestId: string,         // For cancelling stale requests
  context: {                     // Cached context
    diagramType: string,
    mainTopics: string[],
    nodeCategory: string,
    existingNodes: string[]
  }
}
```

### Context Extraction Logic

**For Double Bubble Map (Editing Mode):**
```javascript
function extractContext(editor, nodeId) {
  const spec = editor.currentSpec;
  
  // Get node element from DOM
  const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
  if (nodeElement.empty()) {
    throw new Error(`Node not found: ${nodeId}`);
  }
  
  // Extract node type and category from node ID pattern
  const nodeIdStr = nodeId;
  let nodeCategory = 'similarities'; // default
  if (nodeIdStr.startsWith('similarity_')) {
    nodeCategory = 'similarities';
  } else if (nodeIdStr.startsWith('left_diff_')) {
    nodeCategory = 'left_differences';
  } else if (nodeIdStr.startsWith('right_diff_')) {
    nodeCategory = 'right_differences';
  }
  
  // Get existing nodes in same category
  const existingNodes = spec[nodeCategory] || [];
  
  // Get main topics
  const mainTopics = [spec.left || '', spec.right || ''];
  
  return {
    diagramType: editor.diagramType || 'double_bubble_map',
    mainTopics: mainTopics,
    nodeCategory: nodeCategory,
    existingNodes: existingNodes.map(n => typeof n === 'string' ? n : n.text || n),
    currentNodeText: nodeElement.text() || '',
    cursorPosition: getCursorPosition(inputElement),
    nodeId: nodeId,
    nodeType: nodeElement.attr('data-node-type') || 'node'
  };
}
```

**For Mindmap Child Nodes (Editing Mode - Special Case):**

When editing a child node in a mindmap, Tab Mode has two behaviors:

1. **Placeholder Text Detection**: If the node text is a placeholder (e.g., "Child 1.1", "子项1.1"), Tab should expand/fill the node with generated content.

2. **User Typing**: If the user is typing something, Tab should provide autocomplete suggestions based on:
   - Main topic (center topic)
   - Parent branch label
   - Current partial input

**Context Extraction for Mindmap Child Nodes:**
```javascript
function extractMindmapChildContext(editor, nodeId, inputElement) {
  const spec = editor.currentSpec;
  
  // Get node element
  const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
  const nodeText = nodeElement.text() || nodeElement.attr('data-text-for') || '';
  
  // Extract branch and child indices from node ID (child_0_1 -> branch 0, child 1)
  const match = nodeId.match(/child_(\d+)_(\d+)/);
  if (!match) return null;
  
  const branchIndex = parseInt(match[1]);
  const childIndex = parseInt(match[2]);
  
  // Get parent branch
  const branch = spec.children?.[branchIndex];
  const branchLabel = branch?.label || '';
  
  // Get main topic
  const mainTopic = spec.topic || '';
  
  // Check if current text is placeholder
  const isPlaceholder = isPlaceholderText(nodeText);
  
  // Get existing children in same branch
  const existingChildren = branch?.children?.map(c => c.label || c.text || c) || [];
  
  return {
    diagramType: 'mindmap',
    nodeId: nodeId,
    nodeType: 'child',
    mainTopic: mainTopic,
    branchLabel: branchLabel,  // Parent branch context
    branchIndex: branchIndex,
    childIndex: childIndex,
    currentNodeText: nodeText,
    isPlaceholder: isPlaceholder,
    existingChildren: existingChildren,
    cursorPosition: getCursorPosition(inputElement),
    partialInput: inputElement?.value || nodeText
  };
}

// Placeholder detection (use DiagramValidator)
function isPlaceholderText(text) {
  const validator = window.currentEditor?.toolbarManager?.validator;
  if (validator && validator.isPlaceholderText) {
    return validator.isPlaceholderText(text);
  }
  
  // Fallback patterns for mindmap child nodes
  const patterns = [
    /^Child \d+\.\d+$/i,        // "Child 1.1", "Child 2.3"
    /^子项 \d+\.\d+$/i,          // "子项 1.1"
    /^子项\d+\.\d+$/i,          // "子项1.1"
    /^Sub-item \d+\.\d+$/i,     // "Sub-item 1.1"
    /^New Child$/i,             // "New Child"
    /^新子项$/i                  // "新子项"
  ];
  
  return patterns.some(pattern => pattern.test(text.trim()));
}
```

**Tab Mode Behavior for Mindmap Child Nodes:**
```javascript
// In tab-mode-manager.js
async handleInput(inputElement, context) {
  if (context.diagramType === 'mindmap' && context.nodeType === 'child') {
    // Check if placeholder or user typing
    if (context.isPlaceholder && !context.partialInput.trim()) {
      // Placeholder mode: Expand/fill the node
      await this.expandChildNode(context);
    } else {
      // User typing: Provide autocomplete suggestions
      await this.requestSuggestions(context);
    }
  }
}

async expandChildNode(context) {
  // Generate content for placeholder child node
  const children = await this.agent.generate_expansion(
    diagram_type: 'mindmap',
    node_text: context.branchLabel,  // Use branch as context
    main_topic: context.mainTopic,
    node_type: 'child',
    existing_children: context.existingChildren,
    num_children: 1,  // Generate single child content
    language: this.getLanguage()
  );
  
  if (children.length > 0) {
    // Fill the placeholder with generated content
    this.fillNodeContent(context.nodeId, children[0].text);
  }
}
```

**For Mindmap (Viewing Mode - Expansion):**
```javascript
function extractExpansionContext(editor, nodeId) {
  const spec = editor.currentSpec;
  
  // Get node element from DOM
  const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
  if (nodeElement.empty()) {
    throw new Error(`Node not found: ${nodeId}`);
  }
  
  // Extract node type from data-node-type attribute
  const nodeType = nodeElement.attr('data-node-type') || 'branch';
  
  // Extract branch index from node ID pattern (branch_0 -> 0, child_0_1 -> 0)
  let branchIndex = null;
  let childIndex = null;
  const nodeIdStr = nodeId;
  
  if (nodeIdStr.startsWith('branch_')) {
    branchIndex = parseInt(nodeIdStr.match(/branch_(\d+)/)?.[1] || '0');
  } else if (nodeIdStr.startsWith('child_')) {
    const match = nodeIdStr.match(/child_(\d+)_(\d+)/);
    if (match) {
      branchIndex = parseInt(match[1]);
      childIndex = parseInt(match[2]);
    }
  }
  
  // Get node text
  const nodeText = nodeElement.text() || 
                   nodeElement.attr('data-text-for') || 
                   nodeElement.select('text').text() || '';
  
  // Get existing children from spec
  let existingChildren = [];
  if (nodeType === 'branch' && branchIndex !== null) {
    const branch = spec.children?.[branchIndex];
    if (branch && branch.children) {
      existingChildren = branch.children.map(c => c.label || c.text || c);
    }
  } else if (nodeType === 'child' && branchIndex !== null && childIndex !== null) {
    const branch = spec.children?.[branchIndex];
    if (branch && branch.children) {
      const child = branch.children[childIndex];
      existingChildren = child?.children?.map(c => c.label || c.text || c) || [];
    }
  }
  
  // Get main topic
  const mainTopic = spec.topic || '';
  
  return {
    diagramType: editor.diagramType || 'mindmap',
    nodeId: nodeId,
    nodeText: nodeText,
    nodeType: nodeType,
    branchIndex: branchIndex,
    childIndex: childIndex,
    mainTopic: mainTopic,
    existingChildren: existingChildren,
    numChildren: 4 // Default number of children to generate
  };
}
```

**Node Expandability Check:**
```javascript
function isNodeExpandable(diagramType, nodeId, nodeElement) {
  // Get node type from element
  const nodeType = nodeElement?.attr('data-node-type') || '';
  
  // Check if node can have children based on diagram type and node type
  switch (diagramType) {
    case 'mindmap':
      // Branches can have children, children can have sub-children
      // Topic cannot be expanded (it's the center)
      return nodeType === 'branch' || nodeType === 'child';
    
    case 'tree_map':
      // Categories can have items (leaves)
      // Topic and dimension cannot be expanded
      return nodeType === 'category';
    
    case 'flow_map':
      // Steps can have substeps
      // Title cannot be expanded
      return nodeType === 'step';
    
    case 'brace_map':
      // Parts can have subparts
      // Topic and dimension cannot be expanded
      return nodeType === 'part';
    
    case 'multi_flow_map':
      // Causes and effects cannot have children (flat structure)
      return false;
    
    case 'double_bubble_map':
    case 'bubble_map':
    case 'circle_map':
    case 'bridge_map':
    case 'concept_map':
      // These don't have hierarchical children
      return false;
    
    default:
      return false;
  }
}

// Helper function to get node element from nodeId
function getNodeElement(nodeId) {
  return d3.select(`[data-node-id="${nodeId}"]`);
}

// Helper function to determine node category from node ID (for double bubble map)
function determineNodeCategory(nodeId, diagramType) {
  if (diagramType !== 'double_bubble_map') {
    return null;
  }
  
  if (nodeId.startsWith('similarity_')) {
    return 'similarities';
  } else if (nodeId.startsWith('left_diff_')) {
    return 'left_differences';
  } else if (nodeId.startsWith('right_diff_')) {
    return 'right_differences';
  }
  
  return null;
}
```

---

## UI/UX Design

### Tab Mode Toggle Button

**Location**: Lower right corner of status bar, before reset view button

**Design:**
- Icon: Tab key symbol (⇥) or similar
- Text: "Tab Mode" (or icon only with tooltip)
- State indicators:
  - Enabled: Active color (e.g., #667eea)
  - Disabled: Gray (#94a3b8)
- Tooltip: "Enable Tab Mode for AI suggestions"

**HTML Structure:**
```html
<button id="tab-mode-toggle" class="tab-mode-btn" title="Enable Tab Mode">
    <span class="tab-mode-icon">⇥</span>
    <span class="tab-mode-label">Tab</span>
</button>
```

### Suggestion Overlay

**Position**: Below the input field, aligned with cursor position

**Design:**
- Compact list (max 5 suggestions)
- Each suggestion:
  - Highlighted text (matching input) in bold
  - Remaining text in normal weight
  - Subtle background on hover
- First suggestion highlighted by default
- Keyboard navigation:
  - Tab: Accept first suggestion
  - Arrow Down/Up: Navigate suggestions
  - Enter: Accept highlighted suggestion
  - Escape: Dismiss suggestions

**Visual Example:**
```
[Textarea: "fru..."]
┌─────────────────────────┐
│ fruit                   │ ← Highlighted (Tab to accept)
│ fruit juice             │
│ fruit salad             │
│ fruit tree              │
└─────────────────────────┘
```

**CSS Classes:**
- `.tab-suggestion-overlay` - Container
- `.tab-suggestion-item` - Individual suggestion
- `.tab-suggestion-item.highlighted` - Currently selected
- `.tab-suggestion-item.matched` - Matched portion (bold)

### Loading State

**Indicator**: Small spinner or "..." next to input field
**Placement**: Inline with suggestion overlay, or as part of overlay header

### Error State

**Behavior**: Silently fail (no suggestions shown)
**Reason**: Non-critical feature, shouldn't interrupt user workflow

---

## Backend API Design

### Endpoint 1: `/api/tab_suggestions` (Editing Mode - Autocomplete)

**Method**: POST

**Authentication**: Optional (supports both API key and JWT token, following existing pattern)

**Request Model** (add to `models/requests.py`):
```python
class TabSuggestionRequest(BaseModel):
    """Request model for /api/tab_suggestions endpoint (editing autocomplete)"""
    mode: str = Field("autocomplete", description="Mode: 'autocomplete' for editing suggestions")
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    main_topics: List[str] = Field(..., min_items=1, description="Main topic nodes (e.g., ['apples', 'oranges'] for double bubble)")
    node_category: Optional[str] = Field(None, description="Node category (e.g., 'similarities', 'left_differences')")
    partial_input: str = Field(..., description="User's current partial input")
    existing_nodes: Optional[List[str]] = Field(None, description="Existing nodes in same category")
    language: Language = Field(Language.EN, description="Language code")
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")
    cursor_position: Optional[int] = Field(None, description="Cursor position in input (for future use)")
```

**Request Body Example:**
```json
{
  "mode": "autocomplete",
  "diagram_type": "double_bubble_map",
  "main_topics": ["apples", "oranges"],
  "node_category": "similarities",
  "partial_input": "fru",
  "existing_nodes": ["vitamin C", "round"],
  "language": "en",
  "llm": "qwen"
}
```

### Endpoint 2: `/api/tab_expand` (Viewing Mode - Node Expansion)

**Method**: POST

**Authentication**: Optional (supports both API key and JWT token)

**Request Model** (add to `models/requests.py`):
```python
class TabExpandRequest(BaseModel):
    """Request model for /api/tab_expand endpoint (viewing node expansion)"""
    mode: str = Field("expansion", description="Mode: 'expansion' for node expansion")
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    node_id: str = Field(..., description="ID of node to expand")
    node_text: str = Field(..., description="Text content of selected node")
    node_type: str = Field(..., description="Type of node (e.g., 'branch', 'category', 'step')")
    node_index: Optional[int] = Field(None, description="Index of node (for hierarchical diagrams)")
    branch_index: Optional[int] = Field(None, description="Branch index (for mindmap)")
    parent_node: Optional[str] = Field(None, description="Parent node text (for context)")
    main_topic: Optional[str] = Field(None, description="Main topic/center node text")
    existing_children: Optional[List[str]] = Field(None, description="Existing children nodes (to avoid duplicates)")
    language: Language = Field(Language.EN, description="Language code")
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")
    num_children: Optional[int] = Field(4, ge=2, le=10, description="Number of children to generate (default: 4)")
```

**Request Body Example (Mindmap):**
```json
{
  "mode": "expansion",
  "diagram_type": "mindmap",
  "node_id": "branch_0",
  "node_text": "Active Learning",
  "node_type": "branch",
  "branch_index": 0,
  "main_topic": "Learning Methods",
  "existing_children": [],
  "language": "en",
  "llm": "qwen",
  "num_children": 4
}
```

**Request Body Example (Tree Map):**
```json
{
  "mode": "expansion",
  "diagram_type": "tree_map",
  "node_id": "category_0",
  "node_text": "Fruits",
  "node_type": "category",
  "node_index": 0,
  "main_topic": "Food Categories",
  "existing_children": [],
  "language": "en",
  "llm": "qwen",
  "num_children": 5
}
```

**Response (Autocomplete):**
```json
{
  "success": true,
  "mode": "autocomplete",
  "suggestions": [
    {
      "text": "fruit",
      "confidence": 0.95,
      "reason": "Common similarity between apples and oranges"
    },
    {
      "text": "fruit juice",
      "confidence": 0.82,
      "reason": "Both can be made into juice"
    },
    {
      "text": "fruit salad",
      "confidence": 0.75,
      "reason": "Common combination"
    }
  ],
  "request_id": "tab_1234567890"
}
```

**Response (Expansion):**
```json
{
  "success": true,
  "mode": "expansion",
  "children": [
    {
      "text": "Group Discussions",
      "id": "sub_0_0"
    },
    {
      "text": "Role Playing",
      "id": "sub_0_1"
    },
    {
      "text": "Case Studies",
      "id": "sub_0_2"
    },
    {
      "text": "Peer Teaching",
      "id": "sub_0_3"
    }
  ],
  "request_id": "tab_expand_1234567890"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Invalid request: missing diagram_type",
  "request_id": "tab_1234567890"
}
```

### Request Validation

**Required Fields:**
- `diagram_type`: Must be valid diagram type
- `main_topics`: Array of strings (at least one)
- `partial_input`: String (can be empty for general suggestions)
- `language`: "en" or "zh"

**Optional Fields:**
- `node_category`: For diagram types with categories
- `existing_nodes`: Array of existing node texts
- `cursor_position`: Number (for future cursor-aware suggestions)
- `llm`: Model name (defaults to "qwen" for speed)

### Rate Limiting

**Strategy**: Per-user rate limiting
- 10 requests per second per user
- Burst allowance: 20 requests
- Uses existing rate limiter service

### Performance Requirements

**Target Latency**: < 500ms (p95)
**Strategy**:
- Use fast LLM model (qwen-turbo) by default
- Low max_tokens (50-100)
- Low temperature (0.3)
- Debouncing on frontend (300ms)

---

## Frontend Implementation

### Tab Mode Manager (`static/js/editor/tab-mode-manager.js`)

**Responsibilities:**
- Manage tab mode state (both editing and viewing modes)
- Coordinate between input handlers and expansion handlers
- Handle API communication for both modes
- Integrate with event bus
- Manage node expansion workflow

**Key Methods:**
```javascript
class TabModeManager {
  constructor(eventBus, stateManager, logger, editor) {
    this.eventBus = eventBus;
    this.stateManager = stateManager;
    this.logger = logger;
    this.editor = editor; // Reference to current editor
    this.enabled = false;
    this.mode = 'editing'; // 'editing' or 'viewing'
    
    // Editing mode state
    this.activeInput = null;
    this.suggestions = [];
    this.selectedIndex = 0;
    this.debounceTimer = null;
    
    // Viewing mode state
    this.selectedNode = null;
    this.isExpanding = false;
    
    // Shared state
    this.abortController = null;
  }
  
  enable() { /* Enable tab mode */ }
  disable() { /* Disable tab mode */ }
  setMode(mode) { /* Switch between 'editing' and 'viewing' modes */ }
  
  // Editing mode methods
  attachToInput(inputElement, contextExtractor) { /* Attach to input field */ }
  detachFromInput() { /* Detach from current input */ }
  async requestSuggestions(context) { /* Call /api/tab_suggestions */ }
  showSuggestions(suggestions) { /* Render suggestion overlay */ }
  hideSuggestions() { /* Hide suggestion overlay */ }
  acceptSuggestion(index) { /* Insert suggestion into input */ }
  handleEditingKeyDown(event) { /* Handle Tab, Arrow keys, Escape in editing */ }
  
  // Viewing mode methods
  attachToNodeSelection() { /* Listen for node selection events */ }
  async expandNode(nodeId, nodeData) { /* Call /api/tab_expand and add children */ }
  handleViewingKeyDown(event) { /* Handle Tab key in viewing mode */ }
  isNodeExpandable(nodeData) { /* Check if node can have children */ }
  
  // Shared methods
  handleKeyDown(event) { /* Route to appropriate handler based on mode */ }
}
```

### Input Handler Integration

**NodeEditor Integration (Editing Mode):**
```javascript
// In node-editor.js, after creating textInput (in attachEventListeners method)
if (window.tabModeManager && window.tabModeManager.isEnabled()) {
  window.tabModeManager.setMode('editing');
  window.tabModeManager.attachToInput(this.textInput, () => {
    // Extract complete context
    const editor = window.currentEditor;
    if (!editor) {
      this.logger.warn('NodeEditor', 'No current editor found for Tab Mode');
      return null;
    }
    
    const nodeId = this.nodeData.nodeId || this.nodeData.id;
    if (!nodeId) {
      this.logger.warn('NodeEditor', 'No nodeId found for Tab Mode');
      return null;
    }
    
    // Use Tab Mode Manager's context extraction
    return window.tabModeManager.extractContext(editor, nodeId, this.textInput);
  });
}
```

**Property Panel Integration (Editing Mode):**
```javascript
// In property-panel-manager.js, in loadNodeProperties() method (after line 276)
if (window.tabModeManager && window.tabModeManager.isEnabled()) {
  window.tabModeManager.setMode('editing');
  window.tabModeManager.attachToInput(this.propText, () => {
    // Extract complete context
    const editor = window.currentEditor;
    if (!editor) {
      this.logger.warn('PropertyPanelManager', 'No current editor found for Tab Mode');
      return null;
    }
    
    const nodeId = this.currentNodeId;
    if (!nodeId) {
      this.logger.warn('PropertyPanelManager', 'No currentNodeId found for Tab Mode');
      return null;
    }
    
    // Use Tab Mode Manager's context extraction
    return window.tabModeManager.extractContext(editor, nodeId, this.propText);
  });
}
```

**Node Selection Integration (Viewing Mode):**
```javascript
// In interaction-handler.js or similar, listen for node selection
if (window.tabModeManager && window.tabModeManager.isEnabled()) {
  window.tabModeManager.setMode('viewing');
  window.tabModeManager.attachToNodeSelection();
  
  // Listen for Tab key when node is selected
  // CRITICAL: Only trigger if NOT in an input field (to avoid conflicts)
  document.addEventListener('keydown', (event) => {
    const activeElement = document.activeElement;
    const isInputFocused = activeElement && (
      activeElement.tagName === 'INPUT' || 
      activeElement.tagName === 'TEXTAREA' ||
      activeElement.isContentEditable
    );
    
    if (event.key === 'Tab' && 
        !event.shiftKey && 
        !event.ctrlKey && 
        !event.metaKey &&
        !isInputFocused &&
        window.tabModeManager.mode === 'viewing') {
      
      // Get selected nodes from state manager or selection manager
      const selectedNodes = window.stateManager?.getSelectedNodes() || 
                          window.currentEditor?.selectedNodes || [];
      
      if (selectedNodes.length === 1) {
        event.preventDefault();
        const nodeId = typeof selectedNodes[0] === 'string' ? selectedNodes[0] : selectedNodes[0].id;
        
        // Get node element to check expandability
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (!nodeElement.empty()) {
          const diagramType = window.currentEditor?.diagramType;
          if (window.tabModeManager.isNodeExpandable(diagramType, nodeId, nodeElement)) {
            // Extract expansion context
            const context = window.tabModeManager.extractExpansionContext(
              window.currentEditor,
              nodeId
            );
            window.tabModeManager.expandNode(nodeId, context);
          }
        }
      }
    }
  });
}
```

### Debouncing Strategy

**Implementation:**
```javascript
requestSuggestions(context) {
  // Cancel previous request if still pending
  if (this.abortController) {
    this.abortController.abort();
  }
  
  // Clear debounce timer
  if (this.debounceTimer) {
    clearTimeout(this.debounceTimer);
  }
  
  // Debounce API call
  this.debounceTimer = setTimeout(async () => {
    this.abortController = new AbortController();
    try {
      const suggestions = await this.callAPI(context, this.abortController.signal);
      this.showSuggestions(suggestions);
    } catch (error) {
      if (error.name !== 'AbortError') {
        this.logger.error('TabModeManager', 'Failed to get suggestions', error);
      }
    }
  }, 300); // 300ms debounce
}
```

### Suggestion UI Rendering

**Position Calculation:**
```javascript
function calculateSuggestionPosition(inputElement) {
  const rect = inputElement.getBoundingClientRect();
  const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
  
  return {
    top: rect.bottom + scrollTop + 4, // 4px gap
    left: rect.left,
    width: rect.width
  };
}
```

**Rendering:**
```javascript
showSuggestions(suggestions) {
  if (!suggestions || suggestions.length === 0) {
    this.hideSuggestions();
    return;
  }
  
  const position = calculateSuggestionPosition(this.activeInput);
  const overlay = this.createOverlay(position, suggestions);
  document.body.appendChild(overlay);
  this.selectedIndex = 0;
  this.highlightSuggestion(0);
}
```

---

## LLM Integration

### Tab Agent (`agents/tab_mode/tab_agent.py`)

**Structure (using LangChain with BaseAgent pattern):**

Tab Agent uses LangChain tools for structured context extraction across 10 diagram types, while maintaining `llm_service.chat()` for LLM calls to preserve middleware benefits.

```python
from agents.core.base_agent import BaseAgent
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import BaseModel, Field
from agents.learning.qwen_langchain import QwenLLM
from prompts import get_prompt
from services.llm_service import llm_service
from agents.core.agent_utils import extract_json_from_response

class TabAgent(BaseAgent):
    """
    Agent for generating tab completion suggestions and node expansions.
    
    Uses LangChain tools for:
    - extract_diagram_context(): Extract main topics from spec (handles 10 diagram types)
    - extract_node_info(): Extract node-specific info (node ID parsing, category detection)
    
    LLM Calls:
    - Still uses llm_service.chat() directly (preserves middleware: rate limiting,
      error handling, token tracking, performance tracking, timeouts)
    """
    
    def __init__(self, model='qwen-plus'):
        super().__init__(model=model)
        self.diagram_type = "tab_mode"
        
        # Initialize LangChain LLM wrapper (for future tool-based workflows)
        self.llm = QwenLLM(model_type='generation')
        
        # Create tools for context extraction
        self.tools = self._create_tools()
    
    async def generate_suggestions(
        self,
        diagram_type: str,
        main_topics: List[str],
        partial_input: str,
        node_category: Optional[str] = None,
        existing_nodes: Optional[List[str]] = None,
        language: str = "en",
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None
    ) -> List[str]:
        """Generate completion suggestions."""
        try:
            # Get prompt from centralized system
            prompt_key = f"tab_mode_{diagram_type}_suggestion"
            prompt_template = get_prompt(prompt_key, language, "suggestion")
            
            if not prompt_template:
                logger.warning(f"No prompt found for {prompt_key}, falling back to generic")
                prompt_template = self._get_generic_prompt(diagram_type, language)
            
            # Format prompt with context
            system_prompt = prompt_template.format(
                left_topic=main_topics[0] if len(main_topics) > 0 else "",
                right_topic=main_topics[1] if len(main_topics) > 1 else "",
                node_category=node_category or "general",
                partial_input=partial_input,
                existing_nodes=", ".join(existing_nodes) if existing_nodes else "None"
            )
            
            # Use LangChain tools for context extraction (if needed)
            # Tools available: extract_diagram_context(), extract_node_info()
            
            # Use llm_service.chat() directly (maintains middleware: rate limiting,
            # error handling, token tracking, performance tracking, timeouts)
            response = await llm_service.chat(
                prompt=partial_input or "Provide suggestions",
                model='qwen-plus',  # Use Qwen-plus for generation
                system_message=system_prompt,
                max_tokens=100,
                temperature=0.3,  # Lower temperature for consistent suggestions
                timeout=15.0,  # 15s timeout for autocomplete
                user_id=user_id,
                organization_id=organization_id,
                request_type='autocomplete',
                endpoint_path='/api/tab_suggestions',
                diagram_type=diagram_type
            )
            
            # Parse response
            suggestions = self._parse_suggestions(response)
            return suggestions[:5]  # Limit to 5 suggestions
            
        except Exception as e:
            logger.error(f"TabAgent: Error generating suggestions: {e}")
            return []
    
    def _parse_suggestions(self, response: str) -> List[str]:
        """Parse LLM response into list of suggestions."""
        try:
            # Try to extract JSON array
            parsed = extract_json_from_response(response)
            if isinstance(parsed, list):
                return [str(s) for s in parsed]
            elif isinstance(parsed, dict) and 'suggestions' in parsed:
                return [str(s) for s in parsed['suggestions']]
        except:
            pass
        
        # Fallback: try to extract text lines
        lines = [line.strip() for line in response.split('\n') if line.strip() and not line.strip().startswith('#')]
        return lines[:5]
```

### Prompt Design (`prompts/tab_mode/`)

**Following Codebase Pattern:**
Prompts should be organized in a dedicated folder `prompts/tab_mode/` following the pattern of `prompts/thinking_modes/`. This allows better organization for multiple prompt types.

**Folder Structure:**
```
prompts/tab_mode/
├── __init__.py          # Registry and exports (imports from sub-modules)
├── autocomplete.py      # Autocomplete prompts for all diagram types
├── expansion.py         # Expansion prompts for hierarchical diagrams
└── colors.py           # Color suggestion prompts
```

**Example Structure (following `prompts/thinking_modes/` pattern):**

**`prompts/tab_mode/autocomplete.py`:**
```python
"""
Tab Mode Autocomplete Prompts
=============================

Autocomplete suggestions for editing mode.
Supports all diagram types with context-aware prompts.

@author MindGraph Team
"""

# Double Bubble Map Autocomplete
TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_EN = """..."""
TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_ZH = """..."""

# Mind Map Autocomplete
TAB_MODE_MINDMAP_AUTOCOMPLETE_EN = """..."""
TAB_MODE_MINDMAP_AUTOCOMPLETE_ZH = """..."""

# ... prompts for all diagram types ...

# Registry
TAB_MODE_AUTOCOMPLETE_PROMPTS = {
    "tab_mode_double_bubble_autocomplete_en": TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_EN,
    "tab_mode_double_bubble_autocomplete_zh": TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_ZH,
    "tab_mode_mindmap_autocomplete_en": TAB_MODE_MINDMAP_AUTOCOMPLETE_EN,
    "tab_mode_mindmap_autocomplete_zh": TAB_MODE_MINDMAP_AUTOCOMPLETE_ZH,
    # ... all diagram types ...
}
```

**`prompts/tab_mode/expansion.py`:**
```python
"""
Tab Mode Expansion Prompts
==========================

Node expansion prompts for viewing mode.
Supports hierarchical diagrams (mindmap, tree_map, flow_map, brace_map).

@author MindGraph Team
"""

# Mindmap Branch Expansion
TAB_MODE_MINDMAP_EXPANSION_EN = """..."""
TAB_MODE_MINDMAP_EXPANSION_ZH = """..."""

# Tree Map Category Expansion
TAB_MODE_TREEMAP_EXPANSION_EN = """..."""
TAB_MODE_TREEMAP_EXPANSION_ZH = """..."""

# Registry
TAB_MODE_EXPANSION_PROMPTS = {
    "tab_mode_mindmap_expansion_en": TAB_MODE_MINDMAP_EXPANSION_EN,
    "tab_mode_mindmap_expansion_zh": TAB_MODE_MINDMAP_EXPANSION_ZH,
    # ... all hierarchical diagrams ...
}
```

**`prompts/tab_mode/colors.py`:**
```python
"""
Tab Mode Color Suggestion Prompts
==================================

High-contrast color suggestions for color picker inputs.

@author MindGraph Team
"""

TAB_MODE_COLOR_SUGGESTION_EN = """..."""
TAB_MODE_COLOR_SUGGESTION_ZH = """..."""

# Registry
TAB_MODE_COLOR_PROMPTS = {
    "tab_mode_color_suggestion_en": TAB_MODE_COLOR_SUGGESTION_EN,
    "tab_mode_color_suggestion_zh": TAB_MODE_COLOR_SUGGESTION_ZH,
}
```

**`prompts/tab_mode/__init__.py`:**
```python
"""
Tab Mode Prompts - Centralized Registry
========================================

Unified prompt registry for Tab Mode feature.
Organizes prompts by function: autocomplete, expansion, colors.

@author MindGraph Team
"""

from .autocomplete import TAB_MODE_AUTOCOMPLETE_PROMPTS
from .expansion import TAB_MODE_EXPANSION_PROMPTS
from .colors import TAB_MODE_COLOR_PROMPTS

# Unified registry
TAB_MODE_PROMPTS = {
    **TAB_MODE_AUTOCOMPLETE_PROMPTS,
    **TAB_MODE_EXPANSION_PROMPTS,
    **TAB_MODE_COLOR_PROMPTS,
}

# Export for use in prompts/__init__.py
__all__ = ['TAB_MODE_PROMPTS']
```

**Autocomplete Prompts (`prompts/tab_mode/autocomplete.py`):**

**Double Bubble Map Example:**
```python
# In prompts/tab_mode.py (new file)

TAB_MODE_DOUBLE_BUBBLE_SUGGESTION_EN = """You are an intelligent autocomplete assistant. The user is editing node content in a double bubble map.

Main topics:
- Left: {left_topic}
- Right: {right_topic}

Node category: {node_category}
Current input: {partial_input}
Existing nodes: {existing_nodes}

Based on the main topics and node category, provide 3-5 most relevant completion suggestions.
- If similarities: provide shared characteristics of both topics
- If left_differences: provide characteristics unique to left topic
- If right_differences: provide characteristics unique to right topic

Return only a JSON array of suggestion strings.
Example: ["fruit", "vitamin C", "round"]"""

TAB_MODE_DOUBLE_BUBBLE_SUGGESTION_ZH = """你是一个智能补全助手。用户正在编辑双气泡图的节点内容。

主话题：
- 左侧：{left_topic}
- 右侧：{right_topic}

节点类别：{node_category}
当前输入：{partial_input}
已有节点：{existing_nodes}

请根据主话题和节点类别，提供3-5个最相关的补全建议。
- 如果是相似点（similarities），提供两者的共同特征
- 如果是左侧不同点（left_differences），提供左侧话题独有的特征
- 如果是右侧不同点（right_differences），提供右侧话题独有的特征

只返回JSON数组，每个元素是建议文本字符串。
示例：["fruit", "vitamin C", "round"]"""

# In prompts/tab_mode/__init__.py
from .autocomplete import TAB_MODE_AUTOCOMPLETE_PROMPTS
from .expansion import TAB_MODE_EXPANSION_PROMPTS
from .colors import TAB_MODE_COLOR_PROMPTS

# Unified registry
TAB_MODE_PROMPTS = {
    **TAB_MODE_AUTOCOMPLETE_PROMPTS,
    **TAB_MODE_EXPANSION_PROMPTS,
    **TAB_MODE_COLOR_PROMPTS,
}

# Export for use in prompts/__init__.py
__all__ = ['TAB_MODE_PROMPTS']
```

**Register in `prompts/__init__.py`:**
```python
from .tab_mode import TAB_MODE_PROMPTS

PROMPT_REGISTRY = {
    **THINKING_MAP_PROMPTS,
    **CONCEPT_MAP_PROMPTS,
    **MIND_MAP_PROMPTS,
    **MAIN_AGENT_PROMPTS,
    **THINKING_TOOLS_PROMPTS,
    **VOICE_AGENT_PROMPTS,
    **TAB_MODE_PROMPTS,  # Add tab mode prompts
}
```

**Usage Pattern (matching codebase):**
```python
# In tab_agent.py
from prompts import get_prompt

# Get prompt using centralized system
prompt_key = f"tab_mode_{diagram_type}_autocomplete"
prompt_template = get_prompt(prompt_key, language, "suggestion")
# Format with variables
system_prompt = prompt_template.format(
    left_topic=left_topic,
    right_topic=right_topic,
    node_category=node_category,
    partial_input=partial_input,
    existing_nodes=", ".join(existing_nodes) if existing_nodes else "None"
)
```

**Expansion Prompts (`prompts/tab_mode/expansion.py`):**

**Mindmap Branch Expansion Example:**
```python
TAB_MODE_MINDMAP_EXPANSION_EN = """You are an intelligent node expansion assistant. The user clicked a branch node in a mindmap and wants to generate child nodes.

Main topic: {main_topic}
Branch node: {node_text}
Existing children: {existing_children}

Generate {num_children} child nodes for this branch. Each child should:
- Be directly related to the branch topic
- Be concise (2-4 words)
- Follow educational/teaching principles
- Be mutually exclusive and collectively exhaustive (MECE)

Return only a JSON array of child node texts.
Example: ["Group Discussions", "Role Playing", "Case Studies", "Peer Teaching"]"""

TAB_MODE_MINDMAP_EXPANSION_ZH = """你是一个智能节点扩展助手。用户点击了思维导图中的一个分支节点，想要生成子节点。

中心主题：{main_topic}
分支节点：{node_text}
已有子节点：{existing_children}

为此分支生成 {num_children} 个子节点。每个子节点应该：
- 与分支主题直接相关
- 简洁（2-4个字）
- 遵循教学/教育原则
- 相互独立且完全穷尽（MECE）

只返回JSON数组，每个元素是子节点文本。
示例：["小组讨论", "角色扮演", "案例分析", "同伴教学"]"""
```

**Tree Map Category Expansion Example:**
```python
TAB_MODE_TREEMAP_EXPANSION_EN = """You are an intelligent node expansion assistant. The user clicked a category node in a tree map and wants to generate items.

Main topic: {main_topic}
Category node: {node_text}
Existing items: {existing_children}

Generate {num_children} items for this category. Each item should:
- Belong to the category
- Be specific and concrete
- Be concise (1-3 words)
- Avoid duplicates with existing items

Return only a JSON array of item texts.
Example: ["Apples", "Oranges", "Bananas", "Grapes"]"""
```

**Prompt Variables (Autocomplete):**
- `{left_topic}`: Left main topic text
- `{right_topic}`: Right main topic text
- `{node_category}`: "similarities", "left_differences", or "right_differences"
- `{partial_input}`: User's current partial input
- `{existing_nodes}`: Comma-separated list of existing nodes in same category

**Prompt Variables (Expansion):**
- `{main_topic}`: Main topic/center node text
- `{node_text}`: Selected node text to expand
- `{node_type}`: Type of node ("branch", "category", "step", etc.)
- `{existing_children}`: Comma-separated list of existing children
- `{num_children}`: Number of children to generate (default: 4)

### LLM Configuration

**Settings:**
- Model: `qwen-turbo` (fast, cost-effective)
- Temperature: `0.3` (consistent, focused suggestions)
- Max tokens: `100` (short responses)
- Top-p: `0.9` (balanced creativity)

**Response Parsing:**
```python
def parse_suggestions(response: str) -> List[str]:
    """Parse LLM response into list of suggestions."""
    try:
        # Try to extract JSON array
        suggestions = extract_json_from_response(response)
        if isinstance(suggestions, list):
            return [str(s) for s in suggestions[:5]]  # Limit to 5
        elif isinstance(suggestions, dict) and 'suggestions' in suggestions:
            return [str(s) for s in suggestions['suggestions'][:5]]
    except:
        pass
    
    # Fallback: try to extract text lines
    lines = [line.strip() for line in response.split('\n') if line.strip()]
    return lines[:5]
```

---

## Implementation Plan

### Phase 1: Backend Foundation (Week 1)

**Tasks:**
1. Create `agents/tab_mode/` directory and `__init__.py`
2. Implement `tab_agent.py` inheriting from `BaseAgent` (following existing agent pattern)
   - Add `generate_suggestions()` method for autocomplete
   - Add `generate_expansion()` method for node expansion
3. Create dedicated prompt folder `prompts/tab_mode/`:
   - Create `prompts/tab_mode/__init__.py` for registry and exports
   - Create `prompts/tab_mode/autocomplete.py` with autocomplete prompts for all diagram types
   - Create `prompts/tab_mode/expansion.py` with expansion prompts for hierarchical diagrams
   - Create `prompts/tab_mode/colors.py` with color suggestion prompts
4. Register prompts in `prompts/__init__.py`:
   - Import `TAB_MODE_PROMPTS` from `prompts.tab_mode`
   - Add to `PROMPT_REGISTRY` dictionary
5. Add `TabSuggestionRequest` model to `models/requests.py` (autocomplete)
6. Add `TabExpandRequest` model to `models/requests.py` (expansion)
7. Add `TabSuggestionResponse` and `TabExpandResponse` models to `models/responses.py`
8. Create `routers/tab_mode.py` with two endpoints:
   - `/api/tab_suggestions` (autocomplete)
   - `/api/tab_expand` (expansion)
9. Register router in `main.py` (add `app.include_router(tab_mode.router)`)
10. Write unit tests for tab agent (both modes)

**Deliverables:**
- Backend API endpoint functional
- Double bubble map suggestions working
- Basic error handling

### Phase 2: Frontend Core (Week 1-2)

**Tasks:**
1. Create `static/js/editor/tab-mode-manager.js` (handles both modes)
2. Create `static/js/editor/tab-mode-ui.js` (suggestion overlay + loading indicator)
3. Create `static/js/editor/tab-mode-input-handler.js` (editing mode)
4. Create `static/js/editor/tab-mode-expansion-handler.js` (viewing mode)
5. Add tab mode toggle button to `templates/editor.html`
6. Add CSS styles in `static/css/tab-mode.css`
7. Integrate with NodeEditor (editing mode)
8. Integrate with PropertyPanel (editing mode)
9. Integrate with node selection system (viewing mode)
10. Add Tab key handler for viewing mode expansion

**Deliverables:**
- Tab mode toggle button visible
- Suggestion overlay renders
- Basic input interception works

### Phase 3: Integration & Polish (Week 2)

**Tasks:**
1. Connect frontend to backend API
2. Implement debouncing
3. Add keyboard navigation (Tab, Arrow keys, Escape)
4. Add loading states
5. Add error handling
6. Test with double bubble map examples

**Deliverables:**
- End-to-end functionality working
- Smooth user experience
- Error handling graceful

### Phase 4: Testing & Documentation (Week 2-3)

**Tasks:**
1. Write integration tests
2. Test with various diagram types
3. Test edge cases (empty input, very long input, special characters)
4. Performance testing (latency, rate limiting)
5. Update API documentation
6. Create user guide

**Deliverables:**
- Comprehensive test coverage
- Documentation complete
- Performance benchmarks met

### Phase 5: Extension to Other Diagram Types (Week 3+)

**Tasks:**
1. Add prompts for other diagram types:
   - Mind map
   - Concept map
   - Bubble map
   - Circle map
   - Flow map
   - Tree map
   - Brace map
   - Bridge map
2. Test each diagram type
3. Optimize prompts based on feedback

**Deliverables:**
- Tab mode works for all diagram types
- Optimized prompts for each type

---

## Code Review Checklist

### Architecture
- [ ] Follows existing event bus pattern (`static/js/core/event-bus.js`)
- [ ] Uses centralized prompt system (`prompts/__init__.py` with `get_prompt()`)
- [ ] Agent inherits from `BaseAgent` (`agents/core/base_agent.py`)
- [ ] Uses `llm_service.chat()` for LLM calls (`services/llm_service.py`)
- [ ] Integrates with existing state manager (`static/js/core/state-manager.js`)
- [ ] Follows existing logging patterns (logger from `logging.getLogger(__name__)`)
- [ ] Uses existing authentication system (`get_current_user_or_api_key` from `utils.auth`)
- [ ] Router follows FastAPI pattern (`routers/api.py`, `routers/thinking.py`)
- [ ] Request/Response models use Pydantic (`models/requests.py`, `models/responses.py`)

### Code Quality
- [ ] No hardcoded values (use config/settings)
- [ ] Proper error handling
- [ ] Input validation
- [ ] Rate limiting implemented
- [ ] Debouncing for API calls
- [ ] Memory leak prevention (cleanup event listeners)

### Performance
- [ ] API response time < 500ms (p95)
- [ ] Debouncing prevents excessive calls
- [ ] Request cancellation for stale requests
- [ ] Context caching where appropriate
- [ ] Minimal DOM manipulation

### User Experience
- [ ] Smooth animations
- [ ] Clear visual feedback
- [ ] Keyboard shortcuts intuitive
- [ ] Error states don't interrupt workflow
- [ ] Loading states visible
- [ ] Accessible (keyboard navigation, screen readers)

### Security
- [ ] Input sanitization
- [ ] Rate limiting per user
- [ ] Authentication checks
- [ ] No XSS vulnerabilities
- [ ] Proper CORS handling

### Testing
- [ ] Unit tests for tab agent
- [ ] Integration tests for API endpoint
- [ ] Frontend unit tests
- [ ] E2E tests for user workflow
- [ ] Edge case testing

---

## Future Enhancements

### Short-term (Post-MVP)
1. **Multi-language suggestions**: Support bilingual completions
2. **Color suggestions**: For color picker inputs, suggest high-contrast colors
3. **Smart formatting**: Auto-capitalization, punctuation handling
4. **Suggestion history**: Remember user's previous completions

### Medium-term
1. **Context-aware formatting**: Different suggestions for titles vs descriptions
2. **Learning from user behavior**: Improve suggestions based on acceptance rate
3. **Fuzzy matching**: Handle typos and partial matches better
4. **Rich suggestions**: Include icons or categories for suggestions

### Long-term
1. **Cross-diagram suggestions**: Learn from other diagrams user created
2. **Collaborative suggestions**: Learn from other users' patterns
3. **Voice input integration**: Tab mode for voice-to-text
4. **Advanced context**: Consider node relationships, diagram structure

---

## Comprehensive Review: Missing Scenarios & Edge Cases

### ✅ Verified Input Fields

Based on codebase review, the following input fields exist and need Tab Mode support:

1. **Node Text Editing:**
   - ✅ `prop-text` (textarea) - Property panel text editing
   - ✅ `node-text-input` (textarea) - NodeEditor modal text editing
   - **Status**: Covered in design

2. **Color Inputs:**
   - ⚠️ `prop-color-hex` (input type="text") - Hex color input (#RRGGBB format)
   - ⚠️ Color picker buttons (text, fill, stroke colors)
   - **Status**: Mentioned but needs detailed implementation

3. **Numeric Inputs:**
   - ⚠️ `prop-font-size` (input type="number") - Font size (8-72)
   - **Status**: Not covered - should suggest common sizes (12, 14, 16, 18, 20, 24)

4. **Other Text Inputs:**
   - ❌ `prompt-input` (input) - Main diagram generation prompt
   - ❌ `thinking-input` (textarea) - ThinkGuide input
   - ❌ `ai-chat-input` (textarea) - AI assistant chat input
   - **Status**: Not covered - should work like Cursor (context-aware everywhere)

### Missing Scenarios

#### 1. Color Suggestions (High Contrast)
**Current Gap**: User mentioned "high contrast color" suggestions but design lacks details.

**Required Implementation:**
```javascript
// When user types in prop-color-hex input
// Example: User types "#ff" → Suggest high-contrast colors
// Context: Current node fill color is #2196f3 (blue)
// Suggestions: ["#FF5722", "#FF9800", "#4CAF50"] (high contrast to blue)

// Algorithm:
function suggestContrastColors(currentColor, partialInput) {
  // 1. Calculate complementary colors
  // 2. Calculate triadic colors
  // 3. Calculate high-contrast colors (WCAG AA compliant)
  // 4. Filter by partial input match
  // 5. Return top 3-5 suggestions
}
```

**Backend Support Needed:**
- Color contrast calculation (use existing `getContrastingTextColor` from `style-manager.js`)
- LLM prompt for color suggestions based on diagram context
- Return hex color codes in suggestions
- Consider current node colors (fill, stroke, text) for contrast suggestions

**Implementation Details:**
```python
# In tab_agent.py
async def generate_color_suggestions(
    self,
    current_colors: Dict[str, str],  # {'fill': '#2196f3', 'text': '#ffffff', 'stroke': '#1976d2'}
    partial_input: str,  # e.g., "#ff" or "ff"
    diagram_type: str,
    language: str = "en"
) -> List[str]:
    """Generate high-contrast color suggestions."""
    # 1. Extract base color from current_colors (use fill or stroke)
    base_color = current_colors.get('fill') or current_colors.get('stroke', '#2196f3')
    
    # 2. Calculate complementary/triadic colors
    complementary = calculate_complementary_color(base_color)
    triadic = calculate_triadic_colors(base_color)
    
    # 3. Use LLM to suggest contextually appropriate colors
    prompt = f"""Suggest 3-5 high-contrast colors for a {diagram_type} diagram.
Current colors: fill={current_colors.get('fill')}, stroke={current_colors.get('stroke')}
User typed: {partial_input}

Return only hex color codes as JSON array.
Example: ["#FF5722", "#FF9800", "#4CAF50"]"""
    
    # 4. Filter by partial input match
    # 5. Return suggestions
```

**Frontend Implementation:**
```javascript
// In tab-mode-input-handler.js
function detectInputType(inputElement) {
  if (inputElement.id === 'prop-color-hex') {
    return 'color';
  } else if (inputElement.id === 'prop-font-size') {
    return 'number';
  } else if (inputElement.tagName === 'TEXTAREA') {
    return 'text';
  }
  return 'text';
}

// Route to appropriate suggestion handler
if (inputType === 'color') {
  requestColorSuggestions(context);
} else if (inputType === 'number') {
  requestNumberSuggestions(context);
} else {
  requestTextSuggestions(context);
}
```

#### 2. Font Size Suggestions
**Current Gap**: Not mentioned in design.

**Required Implementation:**
```javascript
// When user types in prop-font-size input
// Example: User types "1" → Suggest ["12", "14", "16", "18"]
// Context: Current font size is 14, diagram type is mindmap
// Suggestions: Common sizes for mindmap (12, 14, 16, 18, 20, 24)
```

**Backend Support Needed:**
- Simple rule-based suggestions (no LLM needed)
- Diagram-specific size recommendations
- Common size patterns (body: 12-16, headings: 18-24, titles: 24-36)

**Implementation:**
```javascript
// In tab-mode-manager.js
function getFontSizeSuggestions(partialInput, diagramType, currentSize) {
  const commonSizes = {
    'mindmap': [12, 14, 16, 18, 20, 24],
    'tree_map': [12, 14, 16, 18],
    'flow_map': [12, 14, 16],
    'default': [12, 14, 16, 18, 20, 24]
  };
  
  const sizes = commonSizes[diagramType] || commonSizes['default'];
  
  // Filter by partial input
  if (partialInput) {
    return sizes
      .map(s => s.toString())
      .filter(s => s.startsWith(partialInput))
      .slice(0, 5);
  }
  
  // Return common sizes near current size
  return sizes
    .filter(s => Math.abs(s - currentSize) <= 4)
    .slice(0, 5)
    .map(s => s.toString());
}
```

#### 3. Cursor Position Handling
**Current Gap**: Design mentions cursor position but doesn't detail how to handle mid-text editing.

**Required Implementation:**
```javascript
// User has text: "apples and oranges"
// Cursor is at position 7 (after "apples ")
// User types "fr" → Should suggest "fruit" and insert at cursor position
// Result: "apples fruit and oranges" (not "apples and orangesfruit")

function insertSuggestionAtCursor(inputElement, suggestion) {
  const start = inputElement.selectionStart;
  const end = inputElement.selectionEnd;
  const value = inputElement.value;
  const before = value.substring(0, start);
  const after = value.substring(end);
  const newValue = before + suggestion + after;
  inputElement.value = newValue;
  // Set cursor after inserted text
  inputElement.setSelectionRange(start + suggestion.length, start + suggestion.length);
}
```

#### 4. Multi-line Text Handling
**Current Gap**: Design doesn't specify how to handle textareas with multiple lines.

**Required Implementation:**
- Suggestions should work per-line (current line where cursor is)
- Context extraction should consider current line, not entire textarea
- Suggestion overlay should position relative to current line

#### 5. Empty Input Handling
**Current Gap**: What happens when user hasn't typed anything yet?

**Required Implementation:**
```javascript
// When input is empty or just whitespace
// Option 1: Don't show suggestions (current design)
// Option 2: Show general suggestions based on context
// Example: Empty similarity node → Suggest ["fruit", "vitamin C", "round"]

// Decision: Show general suggestions when input is empty (like Cursor)
if (partialInput.trim().length === 0) {
  // Request general suggestions (no partial match)
  requestGeneralSuggestions(context);
} else if (partialInput.trim().length < 2) {
  // Too short, don't request yet (wait for more input)
  hideSuggestions();
} else {
  // Normal autocomplete request
  requestSuggestions(context);
}
```

#### 6. Special Characters Handling
**Current Gap**: How to handle special characters, emojis, punctuation?

**Required Implementation:**
- Filter suggestions to match input pattern (if user types "#", suggest hex colors)
- Handle Unicode characters (Chinese, emojis)
- Preserve formatting (spaces, punctuation) when inserting

**Unicode Handling:**
```javascript
// Chinese input: "水" → Should match "水果", "水彩", etc.
// Use Unicode-aware string matching
function matchesPartialInput(suggestion, partialInput) {
  // Normalize Unicode (handle different Chinese character variants)
  const normalizedSuggestion = suggestion.normalize('NFC');
  const normalizedInput = partialInput.normalize('NFC');
  
  // Case-insensitive matching for English
  // Exact prefix matching for Chinese
  if (/[\u4e00-\u9fff]/.test(partialInput)) {
    // Chinese: exact prefix match
    return normalizedSuggestion.startsWith(normalizedInput);
  } else {
    // English: case-insensitive prefix match
    return normalizedSuggestion.toLowerCase().startsWith(normalizedInput.toLowerCase());
  }
}
```

**Special Character Filtering:**
```javascript
// If user types "#", only show hex color suggestions
// If user types number, only show numeric suggestions
function filterSuggestionsByPattern(suggestions, partialInput) {
  if (partialInput.startsWith('#')) {
    // Hex color pattern
    return suggestions.filter(s => /^#[0-9A-Fa-f]{6}$/.test(s));
  } else if (/^\d+$/.test(partialInput)) {
    // Numeric pattern
    return suggestions.filter(s => /^\d+$/.test(s));
  }
  return suggestions;
}
```

#### 7. All Diagram Types Support
**Current Gap**: Design only details double bubble map example.

**Required Implementation:**
- Add prompts for all 10 diagram types:
  - ✅ Double bubble map (detailed)
  - ❌ Mind map (needs autocomplete prompts)
  - ❌ Tree map (needs autocomplete prompts)
  - ❌ Flow map (needs autocomplete prompts)
  - ❌ Bubble map (needs autocomplete prompts)
  - ❌ Circle map (needs autocomplete prompts)
  - ❌ Brace map (needs autocomplete prompts)
  - ❌ Bridge map (needs autocomplete prompts)
  - ❌ Multi-flow map (needs autocomplete prompts)
  - ❌ Concept map (needs autocomplete prompts)

#### 8. Viewing Mode Edge Cases
**Current Gap**: What if node already has children? What if node is not expandable?

**Required Implementation:**
```javascript
// Case 1: Node already has children
// Option: Append new children or replace?
// Decision: Append new children (don't replace existing)

// Case 2: Node is not expandable (e.g., double bubble map node)
// Behavior: Show notification "This node type cannot be expanded"
// Or: Silently ignore Tab key press

// Case 3: Multiple nodes selected
// Behavior: Only expand first selected node
// Or: Show error "Please select a single node to expand"
```

#### 9. Performance Edge Cases
**Current Gap**: What if API is slow? What if user types very fast?

**Required Implementation:**
- Request cancellation: Cancel previous request when new input arrives
- Loading state: Show spinner/indicator while waiting
- Timeout handling: If request takes >2s, show "Taking longer than usual..."
- Rate limiting: Frontend should respect backend rate limits

#### 10. Error Handling
**Current Gap**: What if API fails? What if LLM returns invalid data?

**Required Implementation:**
```javascript
// API failure: Silently fail (don't show error to user)
// Invalid response: Fallback to empty suggestions
// Network error: Retry once, then fail silently
// Timeout: Show "Suggestions unavailable" message
```

### Cursor-like Behavior Requirements

Based on Cursor's tab completion, Tab Mode should:

1. **Work Everywhere**: All text inputs, not just node text
   - ✅ Node text (covered)
   - ❌ Prompt input (missing)
   - ❌ ThinkGuide input (missing)
   - ❌ AI chat input (missing)
   - ⚠️ Color hex input (partially covered)

2. **Context-Aware**: Understand what user is typing
   - ✅ Diagram context (covered)
   - ✅ Node category (covered)
   - ⚠️ Input type (color vs text vs number) - needs improvement
   - ❌ Current line context (missing for multi-line)

3. **Smart Insertion**: Insert at cursor, not at end
   - ⚠️ Mentioned but not detailed
   - Need: Cursor position tracking and insertion logic

4. **Visual Feedback**: Clear indication of suggestions
   - ✅ Overlay design (covered)
   - ⚠️ Loading state (mentioned but not detailed)
   - ❌ Keyboard navigation hints (missing)

5. **Keyboard Shortcuts**: Intuitive navigation
   - ✅ Tab to accept (covered)
   - ✅ Escape to dismiss (covered)
   - ⚠️ Arrow keys (mentioned but not detailed)
   - ❌ Ctrl+Space to trigger manually (missing)

### Updated Implementation Checklist

**Phase 1 Additions:**
- [ ] Add color hex input support with contrast color suggestions
- [ ] Add font size input support with common size suggestions
- [ ] Add cursor position tracking and insertion logic
- [ ] Add multi-line text handling (per-line context)
- [ ] Add empty input handling (general suggestions)
- [ ] Add special character filtering

**Phase 2 Additions:**
- [ ] Add prompts for all 10 diagram types
- [ ] Add prompt input support (diagram generation)
- [ ] Add ThinkGuide input support
- [ ] Add AI chat input support
- [ ] Add keyboard navigation (Arrow keys, Ctrl+Space)

**Phase 3 Additions:**
- [ ] Add error handling and retry logic
- [ ] Add performance optimizations (caching, debouncing)
- [ ] Add loading states and timeouts
- [ ] Add accessibility features (screen reader support)

---

## Complete Code Review & Step-by-Step Implementation Guide

> **Quick Start**: This guide provides complete, step-by-step instructions for implementing Tab Mode. Each step includes exact file paths, code examples, and verification checkpoints. Follow sequentially for best results.

### Implementation Overview

**Total Steps**: 8 phases, ~25 files to create/modify
**Estimated Time**: 2-3 weeks (backend: 1 week, frontend: 1 week, testing: 3-5 days)
**Prerequisites**: Understanding of FastAPI, JavaScript ES6+, D3.js basics

**Implementation Order:**
1. Backend Foundation (Prompts → Agent → Models → Router)
2. Frontend Core (Manager → UI → Handlers)
3. Integration (NodeEditor → PropertyPanel → Viewing Mode)
4. Testing & Polish

### Complete Metadata & Node Information Review

**✅ Node ID Patterns (Verified from `routers/voice.py` and `docs/DRAG_AND_DROP_CROSS_BRANCH_FEATURE.md`):**

Each diagram type has specific node ID patterns that Tab Mode must handle:

| Diagram Type | Node ID Pattern | Example |
|------------|-----------------|---------|
| `circle_map` | `context_${index}` | `context_0`, `context_1` |
| `bubble_map` | `attribute_${index}` | `attribute_0`, `attribute_1` |
| `double_bubble_map` | `similarity_${index}`, `left_diff_${index}`, `right_diff_${index}` | `similarity_0`, `left_diff_1` |
| `tree_map` | `tree-category-${index}`, `tree-leaf-${catIdx}-${leafIdx}` | `tree-category-0`, `tree-leaf-0-1` |
| `flow_map` | `flow-step-${index}`, `flow-substep-${stepIdx}-${subIdx}` | `flow-step-0`, `flow-substep-0-1` |
| `multi_flow_map` | `multi-flow-cause-${index}`, `multi-flow-effect-${index}` | `multi-flow-cause-0` |
| `brace_map` | `brace-part-${index}`, `brace-subpart-${partIdx}-${subIdx}` | `brace-part-0` |
| `bridge_map` | `bridge-left-${index}`, `bridge-right-${index}` | `bridge-left-0` |
| `mindmap` | `branch_${index}`, `child_${branchIdx}_${childIdx}` | `branch_0`, `child_0_1` |
| `concept_map` | `concept_${index}` | `concept_0` |

**✅ Node Type Values (Verified from `docs/DRAG_AND_DROP_CROSS_BRANCH_FEATURE.md`):**

Node types stored in `data-node-type` attribute:
- `topic`, `branch`, `child`, `attribute`, `context`
- `similarity`, `left_difference`, `right_difference`
- `category`, `leaf`, `step`, `substep`
- `cause`, `effect`, `event`
- `part`, `subpart`, `left`, `right`
- `dimension`, `center`, `boundary`, `title`

**✅ Diagram Type Detection (Verified from `static/js/editor/interactive-editor.js`):**

```javascript
// Diagram type is stored in:
this.diagramType  // Editor instance property
this.currentSpec  // Current diagram specification
window.currentEditor?.diagramType  // Global access

// State Manager also stores it:
stateManager.getDiagramState()?.type

// Detection priority:
// 1. Editor instance (this.diagramType)
// 2. State Manager (stateManager.getDiagramState()?.type)
// 3. Spec metadata (currentSpec._metadata?.diagram_type)
```

**✅ Node Metadata Extraction (Verified from `static/js/managers/toolbar/property-panel-manager.js`):**

```javascript
// Get node element
const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);

// Extract metadata
const nodeId = nodeElement.attr('data-node-id');
const nodeType = nodeElement.attr('data-node-type');
const branchIndex = nodeElement.attr('data-branch-index');
const childIndex = nodeElement.attr('data-child-index');
const categoryIndex = nodeElement.attr('data-category-index');
const partIndex = nodeElement.attr('data-part-index');
const subpartIndex = nodeElement.attr('data-subpart-index');
const stepIndex = nodeElement.attr('data-step-index');
const substepIndex = nodeElement.attr('data-substep-index');

// Get text content
const text = nodeElement.text() || nodeElement.attr('data-text-for') || '';
```

**✅ Diagram Metadata Structure (Verified from `static/js/editor/node-palette-manager.js`):**

```javascript
// Diagram metadata includes:
{
    arrayName: 'similarities',  // Array name in spec
    nodeName: 'similarity',     // Singular node name
    nodeNamePlural: 'similarities',  // Plural node name
    nodeType: 'similarity',     // Node type value
    arrays: {                    // For multi-array diagrams
        'similarities': {...},
        'left_differences': {...}
    },
    useTabs: true,              // Whether tabs are used
    useStages: true             // Whether multi-stage workflow
}
```

**✅ Context Extraction Requirements:**

Tab Mode must extract:
1. **Diagram Type**: From `editor.diagramType` or `stateManager.getDiagramState()?.type`
2. **Node ID**: From `data-node-id` attribute
3. **Node Type**: From `data-node-type` attribute
4. **Node Category**: For double bubble map, determine from node ID pattern or position
5. **Main Topics**: From `spec.left`, `spec.right`, `spec.topic`, etc.
6. **Hierarchical Indices**: `branch_index`, `child_index`, `category_index`, etc.
7. **Existing Nodes**: From spec arrays based on node category

### Code Review Summary

**✅ Architecture Alignment:**
- All patterns match existing codebase structure
- Follows FastAPI router pattern (`routers/thinking.py` as reference)
- Uses centralized prompt system (`prompts/__init__.py` pattern)
- Inherits from `BaseAgent` (`agents/core/base_agent.py`)
- Uses LangChain tools for complex context extraction (like Learning Agent V3)
- Uses `llm_service.chat()` for LLM calls (preserves middleware: rate limiting, error handling, token tracking)
- Follows Pydantic model patterns (`models/requests.py`, `models/responses.py`)

**✅ Frontend Patterns:**
- Event bus architecture (`static/js/core/event-bus.js`)
- State manager integration (`static/js/core/state-manager.js`)
- Manager class pattern (similar to `PropertyPanelManager`, `NodePaletteManager`)
- D3.js for DOM manipulation (matching `NodeEditor`)

**✅ Integration Points Verified:**
- NodeEditor: `static/js/editor/node-editor.js` (line 155-183: textarea creation)
- PropertyPanel: `static/js/managers/toolbar/property-panel-manager.js` (line 60-83: element initialization)
- Status bar: `templates/editor.html` (line 1085-1105: status-right div)
- Router registration: `main.py` (line 1053-1066: router imports and registration)

---

## Step-by-Step Implementation Guide

### Phase 1: Backend Foundation

#### Step 1.1: Create Prompt Folder Structure

**File**: `prompts/tab_mode/__init__.py`
```python
"""
Tab Mode Prompts - Centralized Registry
========================================

Unified prompt registry for Tab Mode feature.
Organizes prompts by function: autocomplete, expansion, colors.

@author MindGraph Team
"""

from .autocomplete import TAB_MODE_AUTOCOMPLETE_PROMPTS
from .expansion import TAB_MODE_EXPANSION_PROMPTS
from .colors import TAB_MODE_COLOR_PROMPTS

# Unified registry
TAB_MODE_PROMPTS = {
    **TAB_MODE_AUTOCOMPLETE_PROMPTS,
    **TAB_MODE_EXPANSION_PROMPTS,
    **TAB_MODE_COLOR_PROMPTS,
}

# Export for use in prompts/__init__.py
__all__ = ['TAB_MODE_PROMPTS']
```

**File**: `prompts/tab_mode/autocomplete.py`
```python
"""
Tab Mode Autocomplete Prompts
=============================

Autocomplete suggestions for editing mode.
Supports all diagram types with context-aware prompts.

@author MindGraph Team
"""

# Double Bubble Map Autocomplete
TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_EN = """You are an intelligent autocomplete assistant. The user is editing node content in a double bubble map.

Main topics:
- Left: {left_topic}
- Right: {right_topic}

Node category: {node_category}
Current input: {partial_input}
Existing nodes: {existing_nodes}

Based on the main topics and node category, provide 3-5 most relevant completion suggestions.
- If similarities: provide shared characteristics of both topics
- If left_differences: provide characteristics unique to left topic
- If right_differences: provide characteristics unique to right topic

Return only a JSON array of suggestion strings.
Example: ["fruit", "vitamin C", "round"]"""

TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_ZH = """你是一个智能补全助手。用户正在编辑双气泡图的节点内容。

主话题：
- 左侧：{left_topic}
- 右侧：{right_topic}

节点类别：{node_category}
当前输入：{partial_input}
已有节点：{existing_nodes}

请根据主话题和节点类别，提供3-5个最相关的补全建议。
- 如果是相似点（similarities），提供两者的共同特征
- 如果是左侧不同点（left_differences），提供左侧话题独有的特征
- 如果是右侧不同点（right_differences），提供右侧话题独有的特征

只返回JSON数组，每个元素是建议文本字符串。
示例：["fruit", "vitamin C", "round"]"""

# Add prompts for other diagram types here...
# TAB_MODE_MINDMAP_AUTOCOMPLETE_EN = """..."""
# TAB_MODE_TREEMAP_AUTOCOMPLETE_EN = """..."""
# etc.

# Registry
TAB_MODE_AUTOCOMPLETE_PROMPTS = {
    "tab_mode_double_bubble_autocomplete_en": TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_EN,
    "tab_mode_double_bubble_autocomplete_zh": TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_ZH,
    # Add more as you implement...
}
```

**File**: `prompts/tab_mode/expansion.py`
```python
"""
Tab Mode Expansion Prompts
==========================

Node expansion prompts for viewing mode.
Supports hierarchical diagrams (mindmap, tree_map, flow_map, brace_map).

@author MindGraph Team
"""

# Mindmap Branch Expansion
TAB_MODE_MINDMAP_EXPANSION_EN = """You are an intelligent node expansion assistant. The user clicked a branch node in a mindmap and wants to generate child nodes.

Main topic: {main_topic}
Branch node: {node_text}
Existing children: {existing_children}

Generate {num_children} child nodes for this branch. Each child should:
- Be directly related to the branch topic
- Be concise (2-4 words)
- Follow educational/teaching principles
- Be mutually exclusive and collectively exhaustive (MECE)

Return only a JSON array of child node texts.
Example: ["Group Discussions", "Role Playing", "Case Studies", "Peer Teaching"]"""

TAB_MODE_MINDMAP_EXPANSION_ZH = """你是一个智能节点扩展助手。用户点击了思维导图中的一个分支节点，想要生成子节点。

中心主题：{main_topic}
分支节点：{node_text}
已有子节点：{existing_children}

为此分支生成 {num_children} 个子节点。每个子节点应该：
- 与分支主题直接相关
- 简洁（2-4个字）
- 遵循教学/教育原则
- 相互独立且完全穷尽（MECE）

只返回JSON数组，每个元素是子节点文本。
示例：["小组讨论", "角色扮演", "案例分析", "同伴教学"]"""

# Registry
TAB_MODE_EXPANSION_PROMPTS = {
    "tab_mode_mindmap_expansion_en": TAB_MODE_MINDMAP_EXPANSION_EN,
    "tab_mode_mindmap_expansion_zh": TAB_MODE_MINDMAP_EXPANSION_ZH,
    # Add more as you implement...
}
```

**File**: `prompts/tab_mode/colors.py`
```python
"""
Tab Mode Color Suggestion Prompts
==================================

High-contrast color suggestions for color picker inputs.

@author MindGraph Team
"""

TAB_MODE_COLOR_SUGGESTION_EN = """Suggest 3-5 high-contrast colors for a {diagram_type} diagram.
Current colors: fill={fill_color}, stroke={stroke_color}, text={text_color}
User typed: {partial_input}

Return only hex color codes as JSON array.
Example: ["#FF5722", "#FF9800", "#4CAF50"]"""

TAB_MODE_COLOR_SUGGESTION_ZH = """为{diagram_type}图表建议3-5个高对比度颜色。
当前颜色：填充={fill_color}，边框={stroke_color}，文字={text_color}
用户输入：{partial_input}

只返回十六进制颜色代码的JSON数组。
示例：["#FF5722", "#FF9800", "#4CAF50"]"""

# Registry
TAB_MODE_COLOR_PROMPTS = {
    "tab_mode_color_suggestion_en": TAB_MODE_COLOR_SUGGESTION_EN,
    "tab_mode_color_suggestion_zh": TAB_MODE_COLOR_SUGGESTION_ZH,
}
```

**Action**: Register in `prompts/__init__.py`
```python
# Add import at top
from .tab_mode import TAB_MODE_PROMPTS

# Add to PROMPT_REGISTRY
PROMPT_REGISTRY = {
    **THINKING_MAP_PROMPTS,
    **CONCEPT_MAP_PROMPTS,
    **MIND_MAP_PROMPTS,
    **MAIN_AGENT_PROMPTS,
    **THINKING_TOOLS_PROMPTS,
    **VOICE_AGENT_PROMPTS,
    **TAB_MODE_PROMPTS,  # ADD THIS LINE
}
```

#### Step 1.2: Create Tab Agent

**File**: `agents/tab_mode/__init__.py`
```python
"""
Tab Mode Agent Package
======================

Intelligent autocomplete and node expansion agent.
"""

from .tab_agent import TabAgent

__all__ = ['TabAgent']
```

**File**: `agents/tab_mode/tab_agent.py`

**Uses LangChain for structured context extraction:**

```python
"""
Tab Mode Agent
==============

Agent for generating tab completion suggestions and node expansions.
Uses LangChain with Qwen-plus for structured, tool-based context extraction.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import BaseModel, Field
from ..core.base_agent import BaseAgent
from agents.learning.qwen_langchain import QwenLLM
from prompts import get_prompt
from services.llm_service import llm_service
from services.error_handler import LLMServiceError

logger = logging.getLogger(__name__)


class TabAgent(BaseAgent):
    """
    Tab Agent using LangChain tools for context extraction.
    
    Tools:
    - extract_diagram_context(): Extract main topics from spec (handles 10 diagram types)
    - extract_node_info(): Extract node-specific info (node ID parsing, category detection)
    
    LLM Calls:
    - Still uses llm_service.chat() directly (preserves middleware benefits)
    """
    
    def __init__(self, model='qwen-plus'):
        """
        Initialize Tab Agent.
        
        Args:
            model: LLM model to use. Default 'qwen-plus' for generation tasks.
        """
        super().__init__(model=model)
        self.diagram_type = "tab_mode"
        
        # Initialize LangChain LLM wrapper (for future tool-based workflows)
        self.llm = QwenLLM(model_type='generation')
        
        # Create tools for context extraction
        self.tools = self._create_tools()
    
    async def generate_suggestions(
        self,
        diagram_type: str,
        main_topics: List[str],
        partial_input: str,
        node_category: Optional[str] = None,
        existing_nodes: Optional[List[str]] = None,
        language: str = "en",
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None
    ) -> List[str]:
        """Generate completion suggestions for editing mode."""
        try:
            # Get prompt from centralized system
            prompt_key = f"tab_mode_{diagram_type}_autocomplete"
            prompt_template = get_prompt(prompt_key, language, "suggestion")
            
            if not prompt_template:
                logger.warning(f"No prompt found for {prompt_key}, using generic")
                prompt_template = self._get_generic_autocomplete_prompt(diagram_type, language)
            
            # Format prompt with context (handle different diagram types)
            if diagram_type == 'mindmap' and node_category == 'children':
                # Mindmap child nodes need branch_label
                branch_label = main_topics[1] if len(main_topics) > 1 else ""
                main_topic = main_topics[0] if len(main_topics) > 0 else ""
                system_prompt = prompt_template.format(
                    main_topic=main_topic,
                    branch_label=branch_label,
                    partial_input=partial_input,
                    existing_children=", ".join(existing_nodes) if existing_nodes else "None"
                )
            elif diagram_type == 'double_bubble_map':
                system_prompt = prompt_template.format(
                    left_topic=main_topics[0] if len(main_topics) > 0 else "",
                    right_topic=main_topics[1] if len(main_topics) > 1 else "",
                    main_topic=main_topics[0] if len(main_topics) > 0 else "",
                    node_category=node_category or "general",
                    partial_input=partial_input,
                    existing_nodes=", ".join(existing_nodes) if existing_nodes else "None"
                )
            else:
                # Generic format
                system_prompt = prompt_template.format(
                    main_topic=main_topics[0] if len(main_topics) > 0 else "",
                    node_category=node_category or "general",
                    partial_input=partial_input,
                    existing_nodes=", ".join(existing_nodes) if existing_nodes else "None"
                )
            
            # Call LLM service with Qwen-plus (generation model)
            # CRITICAL: llm_service.chat() IS the middleware - provides:
            #   - Rate limiting (automatic via rate_limiter)
            #   - Error handling with retry (automatic via error_handler.with_retry)
            #   - Token tracking (automatic via token_tracker)
            #   - Performance tracking (automatic via performance_tracker)
            #   - Timeout handling (automatic via asyncio.wait_for)
            # 
            # Use 'qwen-plus' for generation tasks (not 'qwen' which is classification)
            # Timeout: 15s for autocomplete (faster response expected)
            # Temperature: 0.3 for consistent, focused suggestions
            # Max tokens: 100 (suggestions are short)
            response = await llm_service.chat(
                prompt=partial_input,
                model='qwen-plus',  # Use Qwen-plus for generation
                system_message=system_prompt,
                max_tokens=100,
                temperature=0.3,  # Lower temperature for consistent suggestions
                timeout=15.0,  # 15s timeout for autocomplete
                user_id=user_id,
                organization_id=organization_id,
                request_type='autocomplete',
                endpoint_path='/api/tab_suggestions',
                diagram_type=diagram_type
            )
            
            # Parse response
            suggestions = self._parse_suggestions(response)
            return suggestions[:5]  # Limit to 5 suggestions
            
        except Exception as e:
            logger.error(f"TabAgent: Error generating suggestions: {e}")
            return []
    
    async def generate_expansion(
        self,
        diagram_type: str,
        node_text: str,
        main_topic: Optional[str] = None,
        node_type: str = "branch",
        existing_children: Optional[List[str]] = None,
        num_children: int = 4,
        language: str = "en",
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Generate child nodes for expansion mode."""
        try:
            # Get prompt from centralized system
            prompt_key = f"tab_mode_{diagram_type}_expansion"
            prompt_template = get_prompt(prompt_key, language, "expansion")
            
            if not prompt_template:
                logger.warning(f"No prompt found for {prompt_key}")
                return []
            
            # Format prompt
            system_prompt = prompt_template.format(
                main_topic=main_topic or "",
                node_text=node_text,
                existing_children=", ".join(existing_children) if existing_children else "None",
                num_children=num_children
            )
            
            # Call LLM service with Qwen-plus (generation model)
            # CRITICAL: llm_service.chat() IS the middleware - provides:
            #   - Rate limiting (automatic via rate_limiter)
            #   - Error handling with retry (automatic via error_handler.with_retry)
            #   - Token tracking (automatic via token_tracker)
            #   - Performance tracking (automatic via performance_tracker)
            #   - Timeout handling (automatic via asyncio.wait_for)
            # 
            # Use 'qwen-plus' for generation tasks
            # Timeout: 20s for expansion (may take longer)
            # Temperature: 0.5 for more creative but still focused expansion
            # Max tokens: 150 (children nodes are short but need more tokens for multiple nodes)
            response = await llm_service.chat(
                prompt=f"Generate {num_children} child nodes for: {node_text}",
                model='qwen-plus',  # Use Qwen-plus for generation
                system_message=system_prompt,
                max_tokens=150,
                temperature=0.5,  # Slightly higher for creative expansion
                timeout=20.0,  # 20s timeout for expansion
                user_id=user_id,
                organization_id=organization_id,
                request_type='autocomplete',  # Same request type (both are autocomplete-like)
                endpoint_path='/api/tab_expand',
                diagram_type=diagram_type
            )
            
            # Parse response
            children_texts = self._parse_suggestions(response)
            
            # Format as list of dicts with IDs
            children = []
            for idx, text in enumerate(children_texts[:num_children]):
                children.append({
                    "text": text,
                    "id": f"child_{idx}"
                })
            
            return children
            
        except LLMServiceError as e:
            # LLM service errors (timeout, rate limit, etc.)
            logger.error(f"TabAgent: LLM service error generating expansion: {e}")
            return []
        except ValueError as e:
            # Validation errors (invalid model, etc.)
            logger.error(f"TabAgent: Validation error: {e}")
            return []
        except Exception as e:
            # Unexpected errors
            logger.error(f"TabAgent: Unexpected error generating expansion: {e}", exc_info=True)
            return []
    
    def _parse_suggestions(self, response: str) -> List[str]:
        """
        Parse LLM response into list of suggestions.
        
        Handles multiple response formats:
        1. JSON array: ["suggestion1", "suggestion2"]
        2. JSON object with 'suggestions' key: {"suggestions": [...]}
        3. Markdown code block with JSON
        4. Plain text lines (fallback)
        
        Args:
            response: Raw LLM response string
            
        Returns:
            List of suggestion strings (max 5)
        """
        if not response or not isinstance(response, str):
            logger.warning("TabAgent: Empty or invalid response")
            return []
        
        try:
            # Try to extract JSON array using agent_utils
            parsed = extract_json_from_response(response)
            
            if isinstance(parsed, list):
                # Direct JSON array: ["suggestion1", "suggestion2"]
                suggestions = [str(s).strip() for s in parsed if s]
                # Filter out empty strings and validate length
                suggestions = [s for s in suggestions if len(s) > 0 and len(s) <= 100]
                logger.debug(f"TabAgent: Parsed {len(suggestions)} suggestions from JSON array")
                return suggestions[:5]
            
            elif isinstance(parsed, dict):
                # JSON object with 'suggestions' key
                if 'suggestions' in parsed:
                    suggestions = parsed['suggestions']
                    if isinstance(suggestions, list):
                        suggestions = [str(s).strip() for s in suggestions if s]
                        suggestions = [s for s in suggestions if len(s) > 0 and len(s) <= 100]
                        logger.debug(f"TabAgent: Parsed {len(suggestions)} suggestions from JSON object")
                        return suggestions[:5]
                
                # Try other common keys
                for key in ['nodes', 'children', 'items', 'results']:
                    if key in parsed and isinstance(parsed[key], list):
                        suggestions = [str(s).strip() for s in parsed[key] if s]
                        suggestions = [s for s in suggestions if len(s) > 0 and len(s) <= 100]
                        logger.debug(f"TabAgent: Parsed {len(suggestions)} suggestions from key '{key}'")
                        return suggestions[:5]
        
        except Exception as e:
            logger.warning(f"TabAgent: JSON parsing failed, using fallback: {e}")
        
        # Fallback: try to extract text lines
        # Remove markdown code blocks if present
        cleaned = response.strip()
        if '```' in cleaned:
            # Remove markdown code blocks
            cleaned = re.sub(r'```(?:json)?\s*\n(.*?)\n```', r'\1', cleaned, flags=re.DOTALL)
        
        # Split into lines and filter
        lines = []
        for line in cleaned.split('\n'):
            line = line.strip()
            # Skip empty lines, comments, and markdown separators
            if not line or line.startswith('#') or line.startswith('---') or line.startswith('```'):
                continue
            # Remove list markers (1., 2., -, *, etc.)
            line = re.sub(r'^\d+[\.\)]\s*', '', line)  # "1. " or "1) "
            line = re.sub(r^[-*]\s+', '', line)  # "- " or "* "
            line = line.strip()
            if line and len(line) > 0 and len(line) <= 100:
                lines.append(line)
        
        logger.debug(f"TabAgent: Parsed {len(lines)} suggestions from text lines (fallback)")
        return lines[:5]
    
    def _get_generic_autocomplete_prompt(self, diagram_type: str, language: str) -> str:
        """Fallback generic prompt."""
        if language == 'zh':
            return """根据上下文提供3-5个补全建议。只返回JSON数组。"""
        return """Provide 3-5 completion suggestions based on context. Return only JSON array."""
```

#### Step 1.3: Create Request/Response Models

**File**: `models/requests.py` (add to existing file)

Add after existing models (around line 785):
```python
# ============================================================================
# TAB MODE REQUEST MODELS
# ============================================================================

class TabSuggestionRequest(BaseModel):
    """Request model for /api/tab_suggestions endpoint (editing autocomplete)"""
    mode: str = Field("autocomplete", description="Mode: 'autocomplete' for editing suggestions")
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    main_topics: List[str] = Field(..., min_items=1, description="Main topic nodes")
    node_category: Optional[str] = Field(None, description="Node category")
    partial_input: str = Field(..., description="User's current partial input")
    existing_nodes: Optional[List[str]] = Field(None, description="Existing nodes in same category")
    language: Language = Field(Language.EN, description="Language code")
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")
    cursor_position: Optional[int] = Field(None, description="Cursor position in input")
    
    class Config:
        json_schema_extra = {
            "example": {
                "mode": "autocomplete",
                "diagram_type": "double_bubble_map",
                "main_topics": ["apples", "oranges"],
                "node_category": "similarities",
                "partial_input": "fru",
                "existing_nodes": ["vitamin C"],
                "language": "en",
                "llm": "qwen"
            }
        }


class TabExpandRequest(BaseModel):
    """Request model for /api/tab_expand endpoint (viewing node expansion)"""
    mode: str = Field("expansion", description="Mode: 'expansion' for node expansion")
    diagram_type: DiagramType = Field(..., description="Type of diagram")
    node_id: str = Field(..., description="ID of node to expand")
    node_text: str = Field(..., description="Text content of selected node")
    node_type: str = Field(..., description="Type of node")
    node_index: Optional[int] = Field(None, description="Index of node")
    branch_index: Optional[int] = Field(None, description="Branch index (for mindmap)")
    parent_node: Optional[str] = Field(None, description="Parent node text")
    main_topic: Optional[str] = Field(None, description="Main topic/center node text")
    existing_children: Optional[List[str]] = Field(None, description="Existing children nodes")
    language: Language = Field(Language.EN, description="Language code")
    llm: LLMModel = Field(LLMModel.QWEN, description="LLM model to use")
    num_children: Optional[int] = Field(4, ge=2, le=10, description="Number of children to generate")
    
    class Config:
        json_schema_extra = {
            "example": {
                "mode": "expansion",
                "diagram_type": "mindmap",
                "node_id": "branch_0",
                "node_text": "Active Learning",
                "node_type": "branch",
                "branch_index": 0,
                "main_topic": "Learning Methods",
                "existing_children": [],
                "language": "en",
                "llm": "qwen",
                "num_children": 4
            }
        }
```

**File**: `models/responses.py` (add to existing file)

Add after existing models:
```python
# ============================================================================
# TAB MODE RESPONSE MODELS
# ============================================================================

class TabSuggestionResponse(BaseModel):
    """Response model for /api/tab_suggestions endpoint"""
    success: bool = Field(..., description="Whether request succeeded")
    mode: str = Field("autocomplete", description="Mode: 'autocomplete'")
    suggestions: List[Dict[str, Any]] = Field(..., description="List of suggestions")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "mode": "autocomplete",
                "suggestions": [
                    {"text": "fruit", "confidence": 0.95},
                    {"text": "fruit juice", "confidence": 0.82}
                ],
                "request_id": "tab_1234567890"
            }
        }


class TabExpandResponse(BaseModel):
    """Response model for /api/tab_expand endpoint"""
    success: bool = Field(..., description="Whether request succeeded")
    mode: str = Field("expansion", description="Mode: 'expansion'")
    children: List[Dict[str, str]] = Field(..., description="List of child nodes")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "mode": "expansion",
                "children": [
                    {"text": "Group Discussions", "id": "sub_0_0"},
                    {"text": "Role Playing", "id": "sub_0_1"}
                ],
                "request_id": "tab_expand_1234567890"
            }
        }
```

#### Step 1.4: Create Router

**File**: `routers/tab_mode.py`
```python
"""
Tab Mode API Router
===================

Handles tab completion suggestions and node expansion endpoints.

@author MindGraph Team
"""

import logging
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

# Import authentication
from models.auth import User
from utils.auth import get_current_user_or_api_key

# Import models
from models.requests import TabSuggestionRequest, TabExpandRequest
from models.responses import TabSuggestionResponse, TabExpandResponse
from models import Messages, get_request_language

# Import agent
from agents.tab_mode.tab_agent import TabAgent

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["tab_mode"])


@router.post('/tab_suggestions', response_model=TabSuggestionResponse)
async def tab_suggestions(
    req: TabSuggestionRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Get autocomplete suggestions for editing mode.
    
    Returns context-aware suggestions based on diagram type, main topics, and partial input.
    """
    lang = get_request_language(x_language)
    request_id = f"tab_{int(time.time()*1000)}"
    
    try:
        # Validate request
        if not req.partial_input or len(req.partial_input.strip()) < 1:
            # Empty input: return general suggestions
            req.partial_input = ""
        
        # Get user context
        user_id = current_user.id if current_user else None
        organization_id = current_user.organization_id if current_user else None
        
        # Create agent
        agent = TabAgent(model=req.llm.value if hasattr(req.llm, 'value') else str(req.llm))
        
        # Generate suggestions
        suggestions_text = await agent.generate_suggestions(
            diagram_type=req.diagram_type.value if hasattr(req.diagram_type, 'value') else str(req.diagram_type),
            main_topics=req.main_topics,
            partial_input=req.partial_input,
            node_category=req.node_category,
            existing_nodes=req.existing_nodes,
            language=req.language.value if hasattr(req.language, 'value') else str(req.language),
            user_id=user_id,
            organization_id=organization_id
        )
        
        # Format suggestions
        suggestions = [
            {"text": text, "confidence": 0.9 - (idx * 0.1)}  # Decreasing confidence
            for idx, text in enumerate(suggestions_text)
        ]
        
        logger.debug(f"[{request_id}] Generated {len(suggestions)} suggestions")
        
        return TabSuggestionResponse(
            success=True,
            mode="autocomplete",
            suggestions=suggestions,
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] Error generating suggestions: {e}")
        raise HTTPException(
            status_code=500,
            detail=Messages.error("internal_error", lang)
        )


@router.post('/tab_expand', response_model=TabExpandResponse)
async def tab_expand(
    req: TabExpandRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Expand a node by generating child nodes.
    
    Returns generated child nodes for hierarchical diagrams.
    """
    lang = get_request_language(x_language)
    request_id = f"tab_expand_{int(time.time()*1000)}"
    
    try:
        # Get user context
        user_id = current_user.id if current_user else None
        organization_id = current_user.organization_id if current_user else None
        
        # Create agent
        agent = TabAgent(model=req.llm.value if hasattr(req.llm, 'value') else str(req.llm))
        
        # Generate expansion
        children = await agent.generate_expansion(
            diagram_type=req.diagram_type.value if hasattr(req.diagram_type, 'value') else str(req.diagram_type),
            node_text=req.node_text,
            main_topic=req.main_topic,
            node_type=req.node_type,
            existing_children=req.existing_children,
            num_children=req.num_children or 4,
            language=req.language.value if hasattr(req.language, 'value') else str(req.language),
            user_id=user_id,
            organization_id=organization_id
        )
        
        logger.debug(f"[{request_id}] Generated {len(children)} children for node {req.node_id}")
        
        return TabExpandResponse(
            success=True,
            mode="expansion",
            children=children,
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] Error generating expansion: {e}")
        raise HTTPException(
            status_code=500,
            detail=Messages.error("internal_error", lang)
        )
```

#### Step 1.5: Register Router

**File**: `main.py`

Add import (around line 1053):
```python
from routers import pages, cache, api, thinking, auth, admin_env, admin_logs, voice, update_notification, tab_mode
```

Add registration (around line 1066):
```python
app.include_router(tab_mode.router)  # Tab Mode endpoints
```

**File**: `routers/__init__.py`

Add to `__all__` list:
```python
__all__ = [
    "api",
    "pages",
    "learning",
    "cache",
    "auth",
    "admin_env",
    "admin_logs",
    "thinking",
    "voice",
    "update_notification",
    "tab_mode"  # ADD THIS
]
```

### Phase 2: Frontend Core

#### Step 2.1: Create Tab Mode Manager

**File**: `static/js/editor/tab-mode-manager.js`
```javascript
/**
 * Tab Mode Manager
 * ================
 * 
 * Main orchestrator for Tab Mode feature.
 * Handles both editing (autocomplete) and viewing (expansion) modes.
 * 
 * @author MindGraph Team
 */

class TabModeManager {
    constructor(eventBus, stateManager, logger, editor) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        
        this.enabled = false;
        this.mode = 'editing'; // 'editing' or 'viewing'
        
        // Editing mode state
        this.activeInput = null;
        this.suggestions = [];
        this.selectedIndex = 0;
        this.debounceTimer = null;
        this.abortController = null;
        
        // Viewing mode state
        this.selectedNode = null;
        this.isExpanding = false;
        
        // Initialize
        this.initialize();
    }
    
    initialize() {
        this.logger.info('TabModeManager', 'Tab Mode Manager initialized');
        this.attachGlobalKeyHandler();
    }
    
    enable() {
        this.enabled = true;
        this.eventBus.emit('tab_mode:enabled');
        this.logger.info('TabModeManager', 'Tab mode enabled');
    }
    
    disable() {
        this.enabled = false;
        this.hideSuggestions();
        this.eventBus.emit('tab_mode:disabled');
        this.logger.info('TabModeManager', 'Tab mode disabled');
    }
    
    setMode(mode) {
        this.mode = mode;
        this.logger.debug('TabModeManager', `Mode set to: ${mode}`);
    }
    
    // ... (continue with other methods from design)
}

// Export
if (typeof window !== 'undefined') {
    window.TabModeManager = TabModeManager;
}
```

#### Step 2.2: Add Tab Mode Button

**File**: `templates/editor.html`

Add button in status-right div (around line 1099):
```html
<div class="status-right">
    <span id="school-name-display" class="school-name" style="display: none;"></span>
    <button id="tab-mode-toggle" class="tab-mode-btn" title="Enable Tab Mode">
        <span class="tab-mode-icon">⇥</span>
        <span class="tab-mode-label">Tab</span>
    </button>
    <button id="reset-view-btn" class="reset-view-btn" title="Fit diagram to window">
        <span class="reset-view-icon">⛶</span> Reset View
    </button>
</div>
```

#### Step 2.3: Add CSS Styles

**File**: `static/css/tab-mode.css` (new file)
```css
/**
 * Tab Mode Styles
 * ===============
 * 
 * Styles for Tab Mode feature.
 */

.tab-mode-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    color: #64748b;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.tab-mode-btn:hover {
    background: #f1f5f9;
    border-color: #cbd5e1;
}

.tab-mode-btn.active {
    background: #667eea;
    border-color: #667eea;
    color: white;
}

.tab-mode-icon {
    font-size: 16px;
}

.tab-suggestion-overlay {
    position: absolute;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 10001;
    min-width: 200px;
    max-width: 400px;
    max-height: 300px;
    overflow-y: auto;
}

.tab-suggestion-item {
    padding: 8px 12px;
    cursor: pointer;
    border-bottom: 1px solid #f1f5f9;
    transition: background 0.15s;
}

.tab-suggestion-item:hover,
.tab-suggestion-item.highlighted {
    background: #f8fafc;
}

.tab-suggestion-item:last-child {
    border-bottom: none;
}

.tab-suggestion-item .matched {
    font-weight: 600;
    color: #667eea;
}
```

**File**: `templates/editor.html`

Add CSS link in head section (around line 200):
```html
<link rel="stylesheet" href="/static/css/tab-mode.css?v={{ version }}">
```

### Phase 3: Integration

#### Step 3.1: Add Context Extraction Methods to Tab Mode Manager

**File**: `static/js/editor/tab-mode-manager.js`

Add these methods to the TabModeManager class:

```javascript
/**
 * Extract complete context for autocomplete (editing mode)
 * @param {Object} editor - Current editor instance
 * @param {string} nodeId - Node ID
 * @param {HTMLElement} inputElement - Input/textarea element
 * @returns {Object|null} Context object or null if extraction fails
 */
extractContext(editor, nodeId, inputElement) {
  if (!editor || !nodeId) {
    this.logger.warn('TabModeManager', 'Missing editor or nodeId for context extraction');
    return null;
  }
  
  const spec = editor.currentSpec;
  const diagramType = editor.diagramType;
  
  // Get node element from DOM (source of truth)
  const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
  if (nodeElement.empty()) {
    this.logger.warn('TabModeManager', `Node element not found: ${nodeId}`);
    return null;
  }
  
  // Extract node type and indices
  const nodeType = nodeElement.attr('data-node-type') || 'node';
  const branchIndex = nodeElement.attr('data-branch-index');
  const childIndex = nodeElement.attr('data-child-index');
  const categoryIndex = nodeElement.attr('data-category-index');
  
  // Extract main topics based on diagram type
  let mainTopics = [];
  let nodeCategory = null;
  
  switch (diagramType) {
    case 'double_bubble_map':
      mainTopics = [spec.left || '', spec.right || ''];
      // Determine category from node ID pattern
      if (nodeId.startsWith('similarity_')) {
        nodeCategory = 'similarities';
      } else if (nodeId.startsWith('left_diff_')) {
        nodeCategory = 'left_differences';
      } else if (nodeId.startsWith('right_diff_')) {
        nodeCategory = 'right_differences';
      }
      break;
    
    case 'mindmap':
      mainTopics = [spec.topic || ''];
      // For child nodes, also extract branch context
      if (nodeType === 'child') {
        const match = nodeId.match(/child_(\d+)_(\d+)/);
        if (match) {
          const branchIndex = parseInt(match[1]);
          const branch = spec.children?.[branchIndex];
          if (branch) {
            // Add branch label as additional context
            mainTopics.push(branch.label || '');
            nodeCategory = 'children'; // Child nodes category
          }
        }
      } else if (nodeType === 'branch') {
        nodeCategory = 'branches';
      }
      break;
    
    case 'tree_map':
      mainTopics = [spec.topic || ''];
      if (nodeType === 'category') {
        nodeCategory = 'categories';
      } else if (nodeType === 'leaf') {
        nodeCategory = 'children';
      }
      break;
    
    case 'bubble_map':
      mainTopics = [spec.topic || ''];
      nodeCategory = 'attributes';
      break;
    
    case 'circle_map':
      mainTopics = [spec.topic || ''];
      nodeCategory = 'context';
      break;
    
    case 'flow_map':
      mainTopics = [spec.title || ''];
      if (nodeType === 'step') {
        nodeCategory = 'steps';
      } else if (nodeType === 'substep') {
        nodeCategory = 'substeps';
      }
      break;
    
    case 'multi_flow_map':
      mainTopics = [spec.event || ''];
      if (nodeType === 'cause') {
        nodeCategory = 'causes';
      } else if (nodeType === 'effect') {
        nodeCategory = 'effects';
      }
      break;
    
    case 'brace_map':
      mainTopics = [spec.whole || ''];
      if (nodeType === 'part') {
        nodeCategory = 'parts';
      } else if (nodeType === 'subpart') {
        nodeCategory = 'subparts';
      }
      break;
    
    case 'bridge_map':
      mainTopics = [spec.dimension || ''];
      nodeCategory = 'analogies';
      break;
    
    default:
      mainTopics = [spec.topic || spec.center?.text || ''];
  }
  
  // Get existing nodes in same category
  let existingNodes = [];
  if (nodeCategory && spec[nodeCategory]) {
    existingNodes = spec[nodeCategory].map(n => {
      if (typeof n === 'string') return n;
      return n.text || n.label || n;
    });
  }
  
  // For mindmap child nodes, check if placeholder
  let isPlaceholder = false;
  if (diagramType === 'mindmap' && nodeType === 'child') {
    const currentText = nodeElement.text() || nodeElement.attr('data-text-for') || '';
    isPlaceholder = this.isPlaceholderText(currentText);
    
    // Extract branch label for child nodes
    if (branchIndex !== null) {
      const branch = spec.children?.[branchIndex];
      if (branch) {
        mainTopics.push(branch.label || ''); // Add branch as context
      }
    }
  }
  
  return {
    diagramType: diagramType,
    nodeId: nodeId,
    nodeType: nodeType,
    mainTopics: mainTopics.filter(t => t), // Remove empty strings
    nodeCategory: nodeCategory,
    existingNodes: existingNodes,
    currentNodeText: nodeElement.text() || nodeElement.attr('data-text-for') || '',
    cursorPosition: inputElement ? this.getCursorPosition(inputElement) : null,
    branchIndex: branchIndex ? parseInt(branchIndex) : null,
    childIndex: childIndex ? parseInt(childIndex) : null,
    categoryIndex: categoryIndex ? parseInt(categoryIndex) : null,
    isPlaceholder: isPlaceholder,
    branchLabel: (diagramType === 'mindmap' && branchIndex !== null) 
      ? (spec.children?.[branchIndex]?.label || '') 
      : null
  };
}

/**
 * Extract expansion context for viewing mode
 * @param {Object} editor - Current editor instance
 * @param {string} nodeId - Node ID to expand
 * @returns {Object|null} Expansion context or null
 */
extractExpansionContext(editor, nodeId) {
  if (!editor || !nodeId) {
    this.logger.warn('TabModeManager', 'Missing editor or nodeId for expansion context');
    return null;
  }
  
  const spec = editor.currentSpec;
  const diagramType = editor.diagramType;
  
  // Get node element from DOM
  const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
  if (nodeElement.empty()) {
    this.logger.warn('TabModeManager', `Node element not found: ${nodeId}`);
    return null;
  }
  
  const nodeType = nodeElement.attr('data-node-type') || 'branch';
  
  // Extract indices from node ID pattern
  let branchIndex = null;
  let childIndex = null;
  
  if (nodeId.startsWith('branch_')) {
    branchIndex = parseInt(nodeId.match(/branch_(\d+)/)?.[1] || '0');
  } else if (nodeId.startsWith('child_')) {
    const match = nodeId.match(/child_(\d+)_(\d+)/);
    if (match) {
      branchIndex = parseInt(match[1]);
      childIndex = parseInt(match[2]);
    }
  } else if (nodeId.startsWith('tree-category-')) {
    branchIndex = parseInt(nodeId.match(/tree-category-(\d+)/)?.[1] || '0');
  } else if (nodeId.startsWith('tree-leaf-')) {
    const match = nodeId.match(/tree-leaf-(\d+)-(\d+)/);
    if (match) {
      branchIndex = parseInt(match[1]);
      childIndex = parseInt(match[2]);
    }
  }
  
  // Get node text
  const nodeText = nodeElement.text() || 
                   nodeElement.attr('data-text-for') || 
                   nodeElement.select('text').text() || '';
  
  // Get existing children from spec based on diagram type
  let existingChildren = [];
  let mainTopic = '';
  
  if (diagramType === 'mindmap') {
    mainTopic = spec.topic || '';
    if (nodeType === 'branch' && branchIndex !== null) {
      const branch = spec.children?.[branchIndex];
      if (branch && branch.children) {
        existingChildren = branch.children.map(c => c.label || c.text || c);
      }
    }
  } else if (diagramType === 'tree_map') {
    mainTopic = spec.topic || '';
    if (nodeType === 'category' && branchIndex !== null) {
      const category = spec.children?.[branchIndex];
      if (category && category.children) {
        existingChildren = category.children.map(c => c.text || c);
      }
    }
  } else if (diagramType === 'flow_map') {
    mainTopic = spec.title || '';
    if (nodeType === 'step' && branchIndex !== null) {
      const step = spec.steps?.[branchIndex];
      if (step && spec.substeps) {
        const stepSubsteps = spec.substeps.find(s => s.step === step);
        if (stepSubsteps && stepSubsteps.substeps) {
          existingChildren = stepSubsteps.substeps.map(s => s.text || s);
        }
      }
    }
  }
  
  return {
    diagramType: diagramType,
    nodeId: nodeId,
    nodeText: nodeText,
    nodeType: nodeType,
    branchIndex: branchIndex,
    childIndex: childIndex,
    mainTopic: mainTopic,
    existingChildren: existingChildren,
    numChildren: 4
  };
}

/**
 * Get cursor position in input element
 * @param {HTMLElement} inputElement - Input or textarea element
 * @returns {number} Cursor position (0-based)
 */
getCursorPosition(inputElement) {
  if (!inputElement) return 0;
  
  if (inputElement.selectionStart !== undefined) {
    return inputElement.selectionStart;
  }
  
  // Fallback for older browsers
  return 0;
}

/**
 * Check if text is a placeholder
 * @param {string} text - Text to check
 * @returns {boolean} True if placeholder
 */
isPlaceholderText(text) {
  if (!text || typeof text !== 'string') {
    return false;
  }
  
  // Use DiagramValidator if available
  const validator = window.currentEditor?.toolbarManager?.validator;
  if (validator && validator.isPlaceholderText) {
    return validator.isPlaceholderText(text);
  }
  
  // Fallback patterns for mindmap child nodes
  const patterns = [
    /^Child \d+\.\d+$/i,        // "Child 1.1", "Child 2.3"
    /^子项 \d+\.\d+$/i,          // "子项 1.1"
    /^子项\d+\.\d+$/i,          // "子项1.1"
    /^Sub-item \d+\.\d+$/i,     // "Sub-item 1.1"
    /^New Child$/i,             // "New Child"
    /^新子项$/i,                 // "新子项"
    /^Branch \d+$/i,            // "Branch 1"
    /^分支\d+$/i,                // "分支1"
    /^New Branch$/i,            // "New Branch"
    /^新分支$/i                  // "新分支"
  ];
  
  return patterns.some(pattern => pattern.test(text.trim()));
}

/**
 * Handle input for mindmap child nodes (placeholder vs typing)
 * @param {HTMLElement} inputElement - Input element
 * @param {Object} context - Context object
 */
async handleMindmapChildInput(inputElement, context) {
  const currentValue = inputElement.value || '';
  const trimmedValue = currentValue.trim();
  
  // Check if placeholder or user typing
  if (context.isPlaceholder && !trimmedValue) {
    // Placeholder mode: Expand/fill the node
    await this.expandChildNode(context);
  } else if (trimmedValue.length > 0) {
    // User typing: Provide autocomplete suggestions
    // Update context with current input
    context.partialInput = trimmedValue;
    await this.requestSuggestions(context);
  }
}

/**
 * Expand a placeholder child node with generated content
 * @param {Object} context - Context object with nodeId, branchLabel, mainTopic
 */
async expandChildNode(context) {
  try {
    // Generate content for placeholder child node
    const response = await fetch('/api/tab_expand', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.getAuthToken()}`
      },
      body: JSON.stringify({
        mode: 'expansion',
        diagram_type: 'mindmap',
        node_id: context.nodeId,
        node_text: context.branchLabel || '', // Use branch as context
        node_type: 'child',
        branch_index: context.branchIndex,
        main_topic: context.mainTopic,
        existing_children: context.existingChildren,
        language: this.getLanguage(),
        llm: 'qwen',
        num_children: 1  // Generate single child content
      })
    });
    
    const data = await response.json();
    if (data.success && data.children && data.children.length > 0) {
      // Fill the placeholder with generated content
      this.fillNodeContent(context.nodeId, data.children[0].text);
    }
  } catch (error) {
    this.logger.error('TabModeManager', `Error expanding child node: ${error}`);
  }
}

/**
 * Fill node content (update both DOM and spec)
 * @param {string} nodeId - Node ID
 * @param {string} content - Content to fill
 */
fillNodeContent(nodeId, content) {
  // Update DOM
  const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
  if (!nodeElement.empty()) {
    nodeElement.select('text').text(content);
  }
  
  // Update spec
  const editor = window.currentEditor;
  if (editor && editor.currentSpec) {
    const match = nodeId.match(/child_(\d+)_(\d+)/);
    if (match) {
      const branchIndex = parseInt(match[1]);
      const childIndex = parseInt(match[2]);
      const branch = editor.currentSpec.children?.[branchIndex];
      if (branch && branch.children) {
        const child = branch.children[childIndex];
        if (child) {
          child.label = content;
          child.text = content;
        }
      }
    }
  }
  
  // Emit update event
  if (this.eventBus) {
    this.eventBus.emit('diagram:node_updated', { nodeId, content });
  }
}
```

#### Step 3.2: Integrate with NodeEditor

**File**: `static/js/editor/node-editor.js`

Add after `attachEventListeners()` method (around line 303):
```javascript
// Tab Mode integration
if (window.tabModeManager && window.tabModeManager.isEnabled()) {
  window.tabModeManager.setMode('editing');
  
  const nodeId = this.nodeData.nodeId || this.nodeData.id;
  if (nodeId) {
    window.tabModeManager.attachToInput(this.textInput, () => {
      const editor = window.currentEditor;
      if (!editor) {
        logger.warn('NodeEditor', 'No current editor found for Tab Mode');
        return null;
      }
      return window.tabModeManager.extractContext(editor, nodeId, this.textInput);
    });
  }
}
```

#### Step 3.3: Integrate with PropertyPanel

**File**: `static/js/managers/toolbar/property-panel-manager.js`

Add in `loadNodeProperties()` method (after line 276, after `this.currentNodeId = nodeId;`):
```javascript
// Tab Mode integration
if (window.tabModeManager && window.tabModeManager.isEnabled() && this.propText) {
  window.tabModeManager.setMode('editing');
  
  const nodeId = this.currentNodeId;
  if (nodeId) {
    window.tabModeManager.attachToInput(this.propText, () => {
      const editor = window.currentEditor;
      if (!editor) {
        this.logger.warn('PropertyPanelManager', 'No current editor found for Tab Mode');
        return null;
      }
      return window.tabModeManager.extractContext(editor, nodeId, this.propText);
    });
  }
}
```

#### Step 3.4: Initialize Tab Mode Manager

**File**: `static/js/editor/interactive-editor.js` or main initialization file

Add initialization in `initialize()` method (around line 174):
```javascript
// Initialize Tab Mode Manager (after event bus and state manager are ready)
if (window.eventBus && window.stateManager && !window.tabModeManager) {
  window.tabModeManager = new TabModeManager(
    window.eventBus,
    window.stateManager,
    logger,
    this  // editor instance
  );
  
  // Initialize tab mode button handler
  const tabModeToggle = document.getElementById('tab-mode-toggle');
  if (tabModeToggle) {
    tabModeToggle.addEventListener('click', () => {
      if (window.tabModeManager.enabled) {
        window.tabModeManager.disable();
        tabModeToggle.classList.remove('active');
      } else {
        window.tabModeManager.enable();
        tabModeToggle.classList.add('active');
      }
    });
  }
}
```

#### Step 3.5: Add Viewing Mode Integration

**File**: `static/js/managers/editor/interaction-handler.js` or similar

Add Tab key handler for viewing mode expansion (in keydown event handler):
```javascript
// Tab Mode viewing expansion (add to existing keydown handler)
if (event.key === 'Tab' && 
    !event.shiftKey && 
    !event.ctrlKey && 
    !event.metaKey &&
    window.tabModeManager &&
    window.tabModeManager.enabled &&
    window.tabModeManager.mode === 'viewing') {
  
  // Check if focus is NOT in an input field
  const activeElement = document.activeElement;
  const isInputFocused = activeElement && (
    activeElement.tagName === 'INPUT' || 
    activeElement.tagName === 'TEXTAREA' ||
    activeElement.isContentEditable
  );
  
  if (!isInputFocused) {
    // Get selected nodes
    const selectedNodes = window.stateManager?.getSelectedNodes() || 
                        window.currentEditor?.selectedNodes || [];
    
    if (selectedNodes.length === 1) {
      event.preventDefault();
      const nodeId = typeof selectedNodes[0] === 'string' ? selectedNodes[0] : selectedNodes[0].id;
      
      // Get node element
      const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
      if (!nodeElement.empty()) {
        const diagramType = window.currentEditor?.diagramType;
        if (window.tabModeManager.isNodeExpandable(diagramType, nodeId, nodeElement)) {
          // Extract expansion context
          const context = window.tabModeManager.extractExpansionContext(
            window.currentEditor,
            nodeId
          );
          if (context) {
            window.tabModeManager.expandNode(nodeId, context);
          }
        }
      }
    }
  }
}
```

### Phase 4: Testing Checklist

**Backend Testing:**
- [ ] Test `/api/tab_suggestions` endpoint with double bubble map
- [ ] Test `/api/tab_expand` endpoint with mindmap
- [ ] Test error handling (invalid requests, LLM failures)
- [ ] Test authentication (JWT and API key)
- [ ] Test rate limiting

**Frontend Testing:**
- [ ] Test tab mode toggle button
- [ ] Test autocomplete in NodeEditor modal
- [ ] Test autocomplete in PropertyPanel
- [ ] Test node expansion in viewing mode
- [ ] Test keyboard navigation (Tab, Arrow keys, Escape)
- [ ] Test debouncing (rapid typing)
- [ ] Test error states (API failures)

**Integration Testing:**
- [ ] Test end-to-end autocomplete flow
- [ ] Test end-to-end expansion flow
- [ ] Test with different diagram types
- [ ] Test with Chinese language
- [ ] Test performance (response times)

### Phase 5: File Loading Order

**Critical**: Files must be loaded in this order in `templates/editor.html`:

1. **Core Dependencies** (already loaded):
   ```html
   <script src="/static/js/logger.js"></script>
   <script src="/static/js/core/event-bus.js"></script>
   <script src="/static/js/core/state-manager.js"></script>
   ```

2. **Tab Mode Files** (add after core):
   ```html
   <!-- Tab Mode -->
   <script src="/static/js/editor/tab-mode-manager.js"></script>
   <script src="/static/js/editor/tab-mode-ui.js"></script>
   <script src="/static/js/editor/tab-mode-input-handler.js"></script>
   <script src="/static/js/editor/tab-mode-expansion-handler.js"></script>
   ```

3. **Editor Initialization** (after all managers):
   ```html
   <script src="/static/js/editor/interactive-editor.js"></script>
   ```

4. **Initialize Tab Mode** (in interactive-editor.js or main init):
   ```javascript
   // After editor is created
   if (window.eventBus && window.stateManager) {
       window.tabModeManager = new TabModeManager(
           window.eventBus,
           window.stateManager,
           logger,
           this
       );
   }
   ```

### Phase 6: Common Pitfalls & Solutions

**Pitfall 1: Tab key conflicts with browser navigation**
- **Solution**: Prevent default when Tab Mode is active and suggestions are shown
```javascript
if (event.key === 'Tab' && this.suggestions.length > 0) {
    event.preventDefault();
    this.acceptSuggestion(this.selectedIndex);
}
```

**Pitfall 2: Suggestions overlay positioning**
- **Solution**: Use `getBoundingClientRect()` and account for scroll position
```javascript
const rect = inputElement.getBoundingClientRect();
const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
position = {
    top: rect.bottom + scrollTop + 4,
    left: rect.left,
    width: rect.width
};
```

**Pitfall 3: Memory leaks from event listeners**
- **Solution**: Clean up listeners when detaching
```javascript
detachFromInput() {
    if (this.activeInput) {
        this.activeInput.removeEventListener('input', this.inputHandler);
        this.activeInput.removeEventListener('keydown', this.keyHandler);
        this.activeInput = null;
    }
}
```

**Pitfall 4: Race conditions with rapid typing**
- **Solution**: Cancel previous requests and use AbortController
```javascript
if (this.abortController) {
    this.abortController.abort();
}
this.abortController = new AbortController();
```

**Pitfall 5: Z-index conflicts with modals**
- **Solution**: Use high z-index (10001+) and check for modal overlays
```css
.tab-suggestion-overlay {
    z-index: 10001; /* Higher than modals (10000) */
}
```

### Phase 7: Quick Reference

**Key File Locations:**
- Prompts: `prompts/tab_mode/`
- Agent: `agents/tab_mode/tab_agent.py`
- Router: `routers/tab_mode.py`
- Models: `models/requests.py`, `models/responses.py`
- Frontend: `static/js/editor/tab-mode-*.js`
- CSS: `static/css/tab-mode.css`
- HTML: `templates/editor.html` (button + script tags)

**Key API Endpoints:**
- `POST /api/tab_suggestions` - Autocomplete suggestions
- `POST /api/tab_expand` - Node expansion

**Key Event Bus Events:**
- `tab_mode:enabled` - Tab mode activated
- `tab_mode:disabled` - Tab mode deactivated
- `tab_mode:suggestion_requested` - Request suggestions
- `tab_mode:suggestion_received` - Suggestions received
- `tab_mode:suggestion_accepted` - User accepted suggestion

**Key State Variables:**
- `tabModeManager.enabled` - Whether tab mode is active
- `tabModeManager.mode` - 'editing' or 'viewing'
- `tabModeManager.suggestions` - Current suggestions array
- `tabModeManager.selectedIndex` - Currently highlighted suggestion

**Testing Commands:**
```bash
# Test backend endpoint
curl -X POST http://localhost:9527/api/tab_suggestions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "mode": "autocomplete",
    "diagram_type": "double_bubble_map",
    "main_topics": ["apples", "oranges"],
    "node_category": "similarities",
    "partial_input": "fru",
    "language": "en",
    "llm": "qwen"
  }'

# Test expansion endpoint
curl -X POST http://localhost:9527/api/tab_expand \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "mode": "expansion",
    "diagram_type": "mindmap",
    "node_id": "branch_0",
    "node_text": "Active Learning",
    "node_type": "branch",
    "main_topic": "Learning Methods",
    "language": "en",
    "llm": "qwen"
  }'
```

### Phase 8: Verification Checklist

**Before Deployment:**
- [ ] All prompts registered in `prompts/__init__.py`
- [ ] Router registered in `main.py`
- [ ] Router added to `routers/__init__.py`
- [ ] All JavaScript files loaded in correct order
- [ ] CSS file linked in HTML
- [ ] Tab mode button visible in UI
- [ ] Event listeners properly cleaned up
- [ ] Error handling implemented
- [ ] Logging added for debugging
- [ ] Rate limiting configured
- [ ] Authentication working (JWT + API key)
- [ ] Token tracking working
- [ ] All diagram types have prompts (or fallback)

**Code Quality:**
- [ ] No hardcoded values
- [ ] Proper error messages
- [ ] Input validation
- [ ] Type hints (Python)
- [ ] JSDoc comments (JavaScript)
- [ ] Consistent naming conventions
- [ ] No console.log (use logger)
- [ ] Proper async/await usage
- [ ] No memory leaks

### Phase 9: Mindmap Child Node Special Handling

**✅ Critical Scenario: Mindmap Child Nodes**

When editing a child node in a mindmap, Tab Mode has **two distinct behaviors**:

1. **Placeholder Mode** (Node text is placeholder like "Child 1.1", "子项1.1"):
   - Tab key → **Expand/Fill** the node with generated content
   - Uses branch label and main topic as context
   - Generates single child content to replace placeholder

2. **Typing Mode** (User is typing something):
   - Tab key → **Autocomplete** suggestions
   - Context includes:
     - Main topic (center topic)
     - Parent branch label
     - Current partial input
     - Existing children in same branch

**Implementation Requirements:**
- ✅ Detect placeholder text using `DiagramValidator.isPlaceholderText()` or fallback patterns
- ✅ Extract branch label from `spec.children[branchIndex].label`
- ✅ Extract main topic from `spec.topic`
- ✅ Check if input is empty (placeholder) or has content (typing)
- ✅ Route to appropriate handler: `expandChildNode()` vs `requestSuggestions()`

**Prompt Key:** `tab_mode_mindmap_child_autocomplete_{lang}`

**Context Fields:**
- `main_topic`: Center topic
- `branch_label`: Parent branch label
- `partial_input`: Current user input
- `existing_children`: Existing children in same branch

### Phase 10: Complete Diagram Type Verification

**✅ Tab Mode Behavior for All Diagram Types**

This section documents how Tab Mode should work for each diagram type, covering both editing (autocomplete) and viewing (expansion) modes.

---

#### 1. Circle Map (`circle_map`)

**Structure:**
- Center: `topic` (non-editable via Tab Mode)
- Nodes: `context` array (flat, no hierarchy)

**Editing Mode (Autocomplete):**
- ✅ **Supported**: Context nodes
- **Context Extraction:**
  - Main topic: `spec.topic`
  - Node category: `'context'`
  - Existing nodes: `spec.context`
- **Suggestion Logic:**
  - Provide context-related suggestions based on main topic
  - Example: Topic "Climate Change" → User types "tem..." → Suggests "temperature", "temperate zone"
- **Placeholder Handling:** If placeholder (e.g., "Context 1", "联想1"), Tab fills with generated content

**Viewing Mode (Expansion):**
- ❌ **Not Supported**: No hierarchical children
- **Reason**: Flat structure, no expandable nodes

**Special Cases:**
- Center topic (`topic_center`) is non-editable via Tab Mode

---

#### 2. Bubble Map (`bubble_map`)

**Structure:**
- Center: `topic` (non-editable via Tab Mode)
- Nodes: `attributes` array (flat, no hierarchy)

**Editing Mode (Autocomplete):**
- ✅ **Supported**: Attribute nodes
- **Context Extraction:**
  - Main topic: `spec.topic`
  - Node category: `'attributes'`
  - Existing nodes: `spec.attributes`
- **Suggestion Logic:**
  - Provide attribute/descriptive suggestions based on main topic
  - Example: Topic "Dogs" → User types "loy..." → Suggests "loyal", "loyalty"
- **Placeholder Handling:** If placeholder (e.g., "Attribute 1", "属性1"), Tab fills with generated content

**Viewing Mode (Expansion):**
- ❌ **Not Supported**: No hierarchical children
- **Reason**: Flat structure, no expandable nodes

**Special Cases:**
- Center topic (`topic_center`) is non-editable via Tab Mode

---

#### 3. Double Bubble Map (`double_bubble_map`)

**Structure:**
- Centers: `left`, `right` (both main topics)
- Nodes: `similarities`, `left_differences`, `right_differences` (categorized arrays)

**Editing Mode (Autocomplete):**
- ✅ **Supported**: All three node categories
- **Context Extraction:**
  - Main topics: `[spec.left, spec.right]`
  - Node category: Determined from node ID pattern (`similarity_`, `left_diff_`, `right_diff_`)
  - Existing nodes: From corresponding category array
- **Suggestion Logic:**
  - **Similarities**: Shared characteristics of both topics
    - Example: "apples" vs "oranges" → User types "fru..." → Suggests "fruit", "fruit juice"
  - **Left Differences**: Unique to left topic
    - Example: User types "red" → Suggests "red color", "red skin"
  - **Right Differences**: Unique to right topic
    - Example: User types "orange" → Suggests "orange color", "orange peel"
- **Placeholder Handling:** If placeholder, Tab fills with generated content

**Viewing Mode (Expansion):**
- ❌ **Not Supported**: No hierarchical children
- **Reason**: Flat structure, no expandable nodes

**Special Cases:**
- Must extract both `left` and `right` topics for context
- Node category must be determined from node ID pattern, not node type attribute

---

#### 4. Tree Map (`tree_map`)

**Structure:**
- Center: `topic` (non-editable via Tab Mode)
- Nodes: `children` array (hierarchical: categories with items)
  - Categories can have items (leaves)

**Editing Mode (Autocomplete):**
- ✅ **Supported**: Category nodes, Item nodes
- **Context Extraction:**
  - Main topic: `spec.topic`
  - Node category: `'category'` or `'leaf'` (determined from node type)
  - Existing nodes: From `spec.children` array
- **Suggestion Logic:**
  - **Categories**: Classification suggestions based on main topic
    - Example: Topic "Animals" → User types "mam..." → Suggests "mammals", "mammalian"
  - **Items**: Specific examples within category
    - Example: Category "Mammals" → User types "do..." → Suggests "dogs", "dolphins"
- **Placeholder Handling:** If placeholder (e.g., "Category 1", "类别1"), Tab fills with generated content

**Viewing Mode (Expansion):**
- ✅ **Supported**: Category nodes only
- **Expandable Nodes:** `category` type (not `leaf` or `dimension`)
- **Expansion Logic:**
  - Click category → Tab → Generates 4-6 items for that category
  - Example: Category "Mammals" → Generates ["Dogs", "Cats", "Whales", "Bats"]
- **Context Extraction:**
  - Main topic: `spec.topic`
  - Category text: Selected category node text
  - Existing items: `spec.children[categoryIndex].children`

**Special Cases:**
- Dimension label (`dimension_label`) is non-editable
- Items (leaves) cannot be expanded (they're the end of hierarchy)

---

#### 5. Flow Map (`flow_map`)

**Structure:**
- Center: `title` (non-editable via Tab Mode)
- Nodes: `steps` array (flat) + `substeps` array (hierarchical under steps)

**Editing Mode (Autocomplete):**
- ✅ **Supported**: Step nodes, Substep nodes
- **Context Extraction:**
  - Main topic: `spec.title`
  - Node category: `'steps'` or `'substeps'` (determined from node type)
  - Existing nodes: From `spec.steps` or `spec.substeps`
- **Suggestion Logic:**
  - **Steps**: Sequential process suggestions
    - Example: Title "Coffee Making" → User types "grin..." → Suggests "grind beans", "grinding"
  - **Substeps**: Detailed sub-actions within a step
    - Example: Step "Brew" → User types "pour..." → Suggests "pour water", "pour coffee"
- **Placeholder Handling:** If placeholder (e.g., "Step 1", "步骤1"), Tab fills with generated content

**Viewing Mode (Expansion):**
- ✅ **Supported**: Step nodes only
- **Expandable Nodes:** `step` type (not `substep` or `title`)
- **Expansion Logic:**
  - Click step → Tab → Generates 3-4 substeps for that step
  - Example: Step "Brew Coffee" → Generates ["Heat water", "Add coffee", "Steep", "Strain"]
- **Context Extraction:**
  - Main topic: `spec.title`
  - Step text: Selected step node text
  - Existing substeps: From `spec.substeps` array matching the step

**Special Cases:**
- Title (`flow-title`) is non-editable via Tab Mode
- Substeps cannot be expanded (they're the end of hierarchy)

---

#### 6. Multi-Flow Map (`multi_flow_map`)

**Structure:**
- Center: `event` (non-editable via Tab Mode)
- Nodes: `causes` array, `effects` array (categorized, flat)

**Editing Mode (Autocomplete):**
- ✅ **Supported**: Cause nodes, Effect nodes
- **Context Extraction:**
  - Main topic: `spec.event`
  - Node category: `'causes'` or `'effects'` (determined from node type)
  - Existing nodes: From corresponding category array
- **Suggestion Logic:**
  - **Causes**: Reasons/triggers for the event
    - Example: Event "Lamp Explosion" → User types "over..." → Suggests "overheating", "overvoltage"
  - **Effects**: Consequences/results of the event
    - Example: User types "fire" → Suggests "fire hazard", "fire damage"
- **Placeholder Handling:** If placeholder (e.g., "Cause 1", "原因1"), Tab fills with generated content

**Viewing Mode (Expansion):**
- ❌ **Not Supported**: No hierarchical children
- **Reason**: Flat structure, no expandable nodes

**Special Cases:**
- Event (`multi-flow-event`) is non-editable via Tab Mode
- Must distinguish between cause and effect nodes for context

---

#### 7. Brace Map (`brace_map`)

**Structure:**
- Center: `whole` (non-editable via Tab Mode)
- Nodes: `parts` array (hierarchical: parts with subparts)

**Editing Mode (Autocomplete):**
- ✅ **Supported**: Part nodes, Subpart nodes
- **Context Extraction:**
  - Main topic: `spec.whole`
  - Node category: `'parts'` or `'subparts'` (determined from node type)
  - Existing nodes: From `spec.parts` array
- **Suggestion Logic:**
  - **Parts**: Component suggestions based on whole
    - Example: Whole "Computer" → User types "moni..." → Suggests "monitor", "monitoring system"
  - **Subparts**: Sub-components within a part
    - Example: Part "CPU" → User types "core" → Suggests "cores", "core count"
- **Placeholder Handling:** If placeholder (e.g., "Part 1", "部分1"), Tab fills with generated content

**Viewing Mode (Expansion):**
- ✅ **Supported**: Part nodes only
- **Expandable Nodes:** `part` type (not `subpart` or `dimension`)
- **Expansion Logic:**
  - Click part → Tab → Generates 3-4 subparts for that part
  - Example: Part "CPU" → Generates ["Cores", "Cache", "Clock Speed", "Architecture"]
- **Context Extraction:**
  - Main topic: `spec.whole`
  - Part text: Selected part node text
  - Existing subparts: `spec.parts[partIndex].subparts`

**Special Cases:**
- Dimension label (`dimension_label`) is non-editable
- Subparts cannot be expanded (they're the end of hierarchy)

---

#### 8. Bridge Map (`bridge_map`)

**Structure:**
- Center: `dimension` (non-editable via Tab Mode)
- Nodes: `analogies` array (pairs with `left` and `right`)

**Editing Mode (Autocomplete):**
- ✅ **Supported**: Analogy left/right nodes
- **Context Extraction:**
  - Main topic: `spec.dimension` (the relationship pattern)
  - Node category: `'analogies'`
  - Existing analogies: `spec.analogies`
- **Suggestion Logic:**
  - Provide analogy suggestions based on dimension
  - Example: Dimension "is like" → User types "learn..." → Suggests "learning", "learned behavior"
  - Must maintain analogy relationship (left and right should be related via dimension)
- **Placeholder Handling:** If placeholder (e.g., "New Node"), Tab fills with generated content

**Viewing Mode (Expansion):**
- ❌ **Not Supported**: No hierarchical children
- **Reason**: Flat structure, no expandable nodes

**Special Cases:**
- Dimension (`dimension_label`) is non-editable via Tab Mode
- Analogies come in pairs (left/right), but Tab Mode works on individual nodes
- Must preserve analogy relationship when suggesting

---

#### 9. Mindmap (`mindmap` / `mind_map`)

**Structure:**
- Center: `topic` (non-editable via Tab Mode)
- Nodes: `children` array (hierarchical: branches with children)
  - Branches can have children (sub-branches)

**Editing Mode (Autocomplete):**
- ✅ **Supported**: Branch nodes, Child nodes
- **Context Extraction:**
  - Main topic: `spec.topic`
  - For branches: Node category `'branches'`
  - For children: Node category `'children'`, also extract parent branch label
- **Suggestion Logic:**
  - **Branches**: Main category suggestions based on topic
    - Example: Topic "Learning Methods" → User types "act..." → Suggests "active learning", "active recall"
  - **Children**: Sub-category suggestions based on parent branch
    - Example: Branch "Active Learning" → User types "gro..." → Suggests "group discussions", "group work"
- **Placeholder Handling:** 
  - **Branches**: If placeholder (e.g., "Branch 1", "分支1"), Tab fills with generated content
  - **Children**: If placeholder (e.g., "Child 1.1", "子项1.1"), Tab fills with generated content
  - **Special**: For child nodes, if placeholder AND empty input → Expand mode, else → Autocomplete mode

**Viewing Mode (Expansion):**
- ✅ **Supported**: Branch nodes, Child nodes (if they have children)
- **Expandable Nodes:** `branch` type, `child` type (if not leaf)
- **Expansion Logic:**
  - Click branch → Tab → Generates 4-6 children for that branch
    - Example: Branch "Active Learning" → Generates ["Group Discussions", "Role Playing", "Case Studies", "Peer Teaching"]
  - Click child (if expandable) → Tab → Generates sub-children
- **Context Extraction:**
  - Main topic: `spec.topic`
  - Branch/child text: Selected node text
  - Existing children: `spec.children[branchIndex].children` or nested children

**Special Cases:**
- **CRITICAL**: Child nodes have dual behavior:
  - If placeholder text → Tab expands/fills the node
  - If user typing → Tab provides autocomplete suggestions
- Must extract parent branch label for child node context
- Topic (`topic_center`) is non-editable via Tab Mode

---

#### 10. Concept Map (`concept_map`)

**Structure:**
- Center: `topic` (non-editable via Tab Mode)
- Nodes: `concepts` array (flat) + `relationships` array (edges between concepts)

**Editing Mode (Autocomplete):**
- ✅ **Supported**: Concept nodes, Relationship labels
- **Context Extraction:**
  - Main topic: `spec.topic`
  - Node category: `'concepts'` or `'relationships'` (determined from node type)
  - Existing nodes: From `spec.concepts` or `spec.relationships`
- **Suggestion Logic:**
  - **Concepts**: Related concept suggestions
    - Example: Topic "Photosynthesis" → User types "chlo..." → Suggests "chlorophyll", "chloroplast"
  - **Relationships**: Relationship verb suggestions
    - Example: User types "prod..." → Suggests "produces", "production of"
- **Placeholder Handling:** If placeholder (e.g., "Concept 1", "概念1"), Tab fills with generated content

**Viewing Mode (Expansion):**
- ❌ **Not Supported**: No hierarchical children
- **Reason**: Flat structure (concepts and relationships), no expandable nodes

**Special Cases:**
- Relationships are edges, not nodes (may need special handling)
- Concepts are flat, no hierarchy

---

### Summary Table: Tab Mode Support by Diagram Type

| Diagram Type | Editing Mode | Viewing Expansion | Expandable Nodes | Special Notes |
|-------------|--------------|-------------------|------------------|---------------|
| `circle_map` | ✅ Context nodes | ❌ | None | Flat structure |
| `bubble_map` | ✅ Attribute nodes | ❌ | None | Flat structure |
| `double_bubble_map` | ✅ All 3 categories | ❌ | None | Two main topics |
| `tree_map` | ✅ Category/Item | ✅ Categories | `category` | Items are leaves |
| `flow_map` | ✅ Step/Substep | ✅ Steps | `step` | Substeps are leaves |
| `multi_flow_map` | ✅ Cause/Effect | ❌ | None | Flat structure |
| `brace_map` | ✅ Part/Subpart | ✅ Parts | `part` | Subparts are leaves |
| `bridge_map` | ✅ Analogy nodes | ❌ | None | Pairs structure |
| `mindmap` | ✅ Branch/Child | ✅ Branch/Child | `branch`, `child` | **Dual behavior for children** |
| `concept_map` | ✅ Concept/Rel | ❌ | None | Flat structure |

### Phase 11: Implementation Quick Reference by Diagram Type

**Quick lookup table for implementing Tab Mode for each diagram type:**

#### Context Extraction Patterns

```javascript
// Pattern for extracting main topic
function getMainTopic(diagramType, spec) {
  switch (diagramType) {
    case 'double_bubble_map': return [spec.left, spec.right];
    case 'flow_map': return [spec.title];
    case 'multi_flow_map': return [spec.event];
    case 'brace_map': return [spec.whole];
    case 'bridge_map': return [spec.dimension];
    default: return [spec.topic || spec.center?.text || ''];
  }
}

// Pattern for extracting node category
function getNodeCategory(diagramType, nodeId, nodeType) {
  switch (diagramType) {
    case 'double_bubble_map':
      if (nodeId.startsWith('similarity_')) return 'similarities';
      if (nodeId.startsWith('left_diff_')) return 'left_differences';
      if (nodeId.startsWith('right_diff_')) return 'right_differences';
      return null;
    
    case 'mindmap':
      if (nodeType === 'branch') return 'branches';
      if (nodeType === 'child') return 'children';
      return null;
    
    case 'tree_map':
      if (nodeType === 'category') return 'categories';
      if (nodeType === 'leaf') return 'children';
      return null;
    
    case 'flow_map':
      if (nodeType === 'step') return 'steps';
      if (nodeType === 'substep') return 'substeps';
      return null;
    
    case 'multi_flow_map':
      if (nodeType === 'cause') return 'causes';
      if (nodeType === 'effect') return 'effects';
      return null;
    
    case 'brace_map':
      if (nodeType === 'part') return 'parts';
      if (nodeType === 'subpart') return 'subparts';
      return null;
    
    case 'bridge_map':
      return 'analogies';
    
    case 'bubble_map':
      return 'attributes';
    
    case 'circle_map':
      return 'context';
    
    case 'concept_map':
      if (nodeType === 'concept') return 'concepts';
      if (nodeType === 'relationship') return 'relationships';
      return null;
    
    default:
      return null;
  }
}

// Pattern for checking expandability
function isExpandable(diagramType, nodeType) {
  const expandableTypes = {
    'mindmap': ['branch', 'child'],
    'tree_map': ['category'],
    'flow_map': ['step'],
    'brace_map': ['part']
  };
  
  return expandableTypes[diagramType]?.includes(nodeType) || false;
}
```

#### Prompt Key Patterns

```javascript
// Pattern for getting prompt key
function getPromptKey(diagramType, nodeCategory, language, mode) {
  // Editing mode autocomplete
  if (mode === 'autocomplete') {
    // Special case: mindmap child nodes
    if (diagramType === 'mindmap' && nodeCategory === 'children') {
      return `tab_mode_mindmap_child_autocomplete_${language}`;
    }
    
    // Generic pattern
    return `tab_mode_${diagramType}_autocomplete_${language}`;
  }
  
  // Viewing mode expansion
  if (mode === 'expansion') {
    return `tab_mode_${diagramType}_expansion_${language}`;
  }
  
  return null;
}
```

#### Expansion Context Extraction Patterns

```javascript
// Pattern for extracting expansion context
function extractExpansionContext(diagramType, spec, nodeId, nodeElement) {
  const nodeType = nodeElement.attr('data-node-type');
  const nodeText = nodeElement.text() || '';
  
  switch (diagramType) {
    case 'mindmap': {
      const match = nodeId.match(/branch_(\d+)|child_(\d+)_(\d+)/);
      if (match) {
        if (nodeType === 'branch') {
          const branchIndex = parseInt(match[1]);
          const branch = spec.children?.[branchIndex];
          return {
            mainTopic: spec.topic,
            nodeText: nodeText,
            existingChildren: branch?.children?.map(c => c.label || c.text || c) || [],
            branchIndex: branchIndex
          };
        } else if (nodeType === 'child') {
          const branchIndex = parseInt(match[2]);
          const childIndex = parseInt(match[3]);
          const branch = spec.children?.[branchIndex];
          const child = branch?.children?.[childIndex];
          return {
            mainTopic: spec.topic,
            nodeText: nodeText,
            existingChildren: child?.children?.map(c => c.label || c.text || c) || [],
            branchIndex: branchIndex,
            childIndex: childIndex
          };
        }
      }
      return null;
    }
    
    case 'tree_map': {
      const match = nodeId.match(/tree-category-(\d+)/);
      if (match && nodeType === 'category') {
        const categoryIndex = parseInt(match[1]);
        const category = spec.children?.[categoryIndex];
        return {
          mainTopic: spec.topic,
          nodeText: nodeText,
          existingChildren: category?.children?.map(c => c.text || c) || [],
          categoryIndex: categoryIndex
        };
      }
      return null;
    }
    
    case 'flow_map': {
      const match = nodeId.match(/flow-step-(\d+)/);
      if (match && nodeType === 'step') {
        const stepIndex = parseInt(match[1]);
        const step = spec.steps?.[stepIndex];
        const stepSubsteps = spec.substeps?.find(s => s.step === step);
        return {
          mainTopic: spec.title,
          nodeText: nodeText,
          existingChildren: stepSubsteps?.substeps?.map(s => s.text || s) || [],
          stepIndex: stepIndex
        };
      }
      return null;
    }
    
    case 'brace_map': {
      const match = nodeId.match(/brace-part-(\d+)/);
      if (match && nodeType === 'part') {
        const partIndex = parseInt(match[1]);
        const part = spec.parts?.[partIndex];
        return {
          mainTopic: spec.whole,
          nodeText: nodeText,
          existingChildren: part?.subparts?.map(s => s.name || s.text || s) || [],
          partIndex: partIndex
        };
      }
      return null;
    }
    
    default:
      return null;
  }
}
```

### Phase 12: Implementation Checklist by Diagram Type

**Quick checklist for implementing Tab Mode support:**

#### ✅ Circle Map (`circle_map`)
- [ ] Extract main topic from `spec.topic`
- [ ] Extract node category: `'context'`
- [ ] Extract existing nodes from `spec.context`
- [ ] Implement autocomplete for context nodes
- [ ] Handle placeholder detection ("Context 1", "联想1")
- [ ] ❌ No viewing expansion (flat structure)

#### ✅ Bubble Map (`bubble_map`)
- [ ] Extract main topic from `spec.topic`
- [ ] Extract node category: `'attributes'`
- [ ] Extract existing nodes from `spec.attributes`
- [ ] Implement autocomplete for attribute nodes
- [ ] Handle placeholder detection ("Attribute 1", "属性1")
- [ ] ❌ No viewing expansion (flat structure)

#### ✅ Double Bubble Map (`double_bubble_map`)
- [ ] Extract main topics from `spec.left` and `spec.right`
- [ ] Determine node category from node ID pattern:
  - `similarity_*` → `'similarities'`
  - `left_diff_*` → `'left_differences'`
  - `right_diff_*` → `'right_differences'`
- [ ] Extract existing nodes from corresponding category array
- [ ] Implement autocomplete with category-specific logic
- [ ] Handle placeholder detection
- [ ] ❌ No viewing expansion (flat structure)

#### ✅ Tree Map (`tree_map`)
- [ ] Extract main topic from `spec.topic`
- [ ] Determine node category from node type:
  - `category` → `'categories'`
  - `leaf` → `'children'`
- [ ] Extract existing nodes from `spec.children`
- [ ] Implement autocomplete for categories and items
- [ ] Handle placeholder detection ("Category 1", "类别1")
- [ ] ✅ Implement viewing expansion for `category` nodes
- [ ] Extract expansion context: category text, existing items

#### ✅ Flow Map (`flow_map`)
- [ ] Extract main topic from `spec.title`
- [ ] Determine node category from node type:
  - `step` → `'steps'`
  - `substep` → `'substeps'`
- [ ] Extract existing nodes from `spec.steps` or `spec.substeps`
- [ ] Implement autocomplete for steps and substeps
- [ ] Handle placeholder detection ("Step 1", "步骤1")
- [ ] ✅ Implement viewing expansion for `step` nodes
- [ ] Extract expansion context: step text, existing substeps

#### ✅ Multi-Flow Map (`multi_flow_map`)
- [ ] Extract main topic from `spec.event`
- [ ] Determine node category from node type:
  - `cause` → `'causes'`
  - `effect` → `'effects'`
- [ ] Extract existing nodes from corresponding category array
- [ ] Implement autocomplete with category-specific logic
- [ ] Handle placeholder detection ("Cause 1", "原因1")
- [ ] ❌ No viewing expansion (flat structure)

#### ✅ Brace Map (`brace_map`)
- [ ] Extract main topic from `spec.whole`
- [ ] Determine node category from node type:
  - `part` → `'parts'`
  - `subpart` → `'subparts'`
- [ ] Extract existing nodes from `spec.parts`
- [ ] Implement autocomplete for parts and subparts
- [ ] Handle placeholder detection ("Part 1", "部分1")
- [ ] ✅ Implement viewing expansion for `part` nodes
- [ ] Extract expansion context: part text, existing subparts

#### ✅ Bridge Map (`bridge_map`)
- [ ] Extract main topic from `spec.dimension`
- [ ] Extract node category: `'analogies'`
- [ ] Extract existing nodes from `spec.analogies`
- [ ] Implement autocomplete for analogy nodes
- [ ] Handle placeholder detection
- [ ] Maintain analogy relationship in suggestions
- [ ] ❌ No viewing expansion (flat structure)

#### ✅ Mindmap (`mindmap`)
- [ ] Extract main topic from `spec.topic`
- [ ] Determine node category from node type:
  - `branch` → `'branches'`
  - `child` → `'children'` (also extract parent branch label)
- [ ] Extract existing nodes from `spec.children`
- [ ] **CRITICAL**: For child nodes, check if placeholder:
  - If placeholder → Expand mode
  - If user typing → Autocomplete mode
- [ ] Implement autocomplete for branches and children
- [ ] Handle placeholder detection ("Branch 1", "Child 1.1")
- [ ] ✅ Implement viewing expansion for `branch` and `child` nodes
- [ ] Extract expansion context: branch/child text, existing children
- [ ] Extract parent branch label for child node context

#### ✅ Concept Map (`concept_map`)
- [ ] Extract main topic from `spec.topic`
- [ ] Determine node category from node type:
  - `concept` → `'concepts'`
  - `relationship` → `'relationships'`
- [ ] Extract existing nodes from `spec.concepts` or `spec.relationships`
- [ ] Implement autocomplete for concepts and relationships
- [ ] Handle placeholder detection ("Concept 1", "概念1")
- [ ] ❌ No viewing expansion (flat structure)

### Phase 13: Tab Agent Behavior Verification Against Actual Codebase

**✅ Verified Against Actual Agent Implementations**

This section verifies Tab Agent behavior against actual codebase patterns from:
- `agents/learning/learning_agent.py` - Context extraction patterns
- `agents/thinking_modes/node_palette/` - Diagram-specific generation patterns
- `services/voice_agent.py` - Diagram-specific field handling
- `static/js/managers/voice-agent-manager.js` - Spec structure access patterns

---

#### Verified Spec Structure Access Patterns

**From `learning_agent.py` (lines 312-365):**
```python
# Bubble Map
topic = spec.get('topic', 'Central Topic')
attributes = spec.get('attributes', [])

# Mind Map (note: uses 'branches' not 'children' in some contexts)
main_topic = spec.get('mainTopic', 'Main Topic')  # OR spec.get('topic')
branches = spec.get('branches', [])  # OR spec.get('children', [])
```

**From `voice-agent-manager.js` (lines 1336-1377):**
```javascript
// Spec access patterns
const spec = window.currentEditor.currentSpec;
const rawNodes = spec.children || spec.context || spec.attributes || 
                 spec.adjectives || spec.items || [];

// Center text extraction
center: {
    text: spec.topic || ''
}
```

**From `voice_agent.py` (lines 406-499):**
- Mindmap: Uses `spec.topic` and `spec.children` (array of branches with nested children)
- Tree Map: Uses `spec.topic` and `spec.children` (hierarchical)
- Flow Map: Uses `spec.title` and `spec.steps` + `spec.substeps`
- Double Bubble: Uses `spec.left`, `spec.right`, `spec.similarities`, `spec.left_differences`, `spec.right_differences`
- Multi-Flow: Uses `spec.event`, `spec.causes`, `spec.effects`
- Brace Map: Uses `spec.whole`, `spec.parts` (with nested `subparts`)
- Bridge Map: Uses `spec.dimension`, `spec.analogies`
- Circle Map: Uses `spec.topic`, `spec.context`
- Bubble Map: Uses `spec.topic`, `spec.attributes`

---

#### Tab Agent Context Extraction - Verified Patterns

**1. Main Topic Extraction (Verified from `voice_agent.py`):**
```python
def get_main_topic(diagram_type: str, spec: Dict[str, Any]) -> List[str]:
    """Extract main topic(s) based on diagram type - VERIFIED PATTERN"""
    if diagram_type == 'double_bubble_map':
        return [spec.get('left', ''), spec.get('right', '')]
    elif diagram_type == 'flow_map':
        return [spec.get('title', '')]
    elif diagram_type == 'multi_flow_map':
        return [spec.get('event', '')]
    elif diagram_type == 'brace_map':
        return [spec.get('whole', '')]
    elif diagram_type == 'bridge_map':
        return [spec.get('dimension', '')]
    else:
        # circle_map, bubble_map, tree_map, mindmap, concept_map
        return [spec.get('topic', '')]
```

**2. Node Category Extraction (Verified from `double_bubble_palette.py`):**
```python
def get_node_category(diagram_type: str, node_id: str, node_type: str) -> Optional[str]:
    """Extract node category - VERIFIED PATTERN"""
    if diagram_type == 'double_bubble_map':
        # Node ID pattern determines category (VERIFIED)
        if node_id.startswith('similarity_'):
            return 'similarities'
        elif node_id.startswith('left_diff_'):
            return 'left_differences'
        elif node_id.startswith('right_diff_'):
            return 'right_differences'
        return None
    
    # For other diagrams, use node_type attribute
    category_map = {
        'mindmap': {'branch': 'branches', 'child': 'children'},
        'tree_map': {'category': 'categories', 'leaf': 'children'},
        'flow_map': {'step': 'steps', 'substep': 'substeps'},
        'multi_flow_map': {'cause': 'causes', 'effect': 'effects'},
        'brace_map': {'part': 'parts', 'subpart': 'subparts'},
        'bubble_map': {'attribute': 'attributes'},
        'circle_map': {'context': 'context'},
        'bridge_map': {'analogy': 'analogies'},
        'concept_map': {'concept': 'concepts', 'relationship': 'relationships'}
    }
    
    return category_map.get(diagram_type, {}).get(node_type)
```

**3. Existing Nodes Extraction (Verified from `learning_agent.py`):**
```python
def get_existing_nodes(diagram_type: str, spec: Dict[str, Any], 
                      node_category: str, node_id: str) -> List[str]:
    """Extract existing nodes in same category - VERIFIED PATTERN"""
    # Get array from spec
    nodes_array = spec.get(node_category, [])
    
    # Handle different node formats (string vs dict)
    existing = []
    for node in nodes_array:
        if isinstance(node, dict):
            # Extract text based on diagram type
            if diagram_type == 'mindmap':
                text = node.get('label') or node.get('text')
            elif diagram_type == 'tree_map':
                text = node.get('text')
            elif diagram_type == 'brace_map':
                text = node.get('name') or node.get('text')
            else:
                text = node.get('text') or node.get('label') or str(node)
        else:
            text = str(node)
        
        if text:
            existing.append(text)
    
    # Remove current node from siblings (VERIFIED from learning_agent.py line 331-334)
    if node_id:
        try:
            node_idx = int(node_id.split('_')[-1])
            if node_idx < len(existing):
                existing = existing[:node_idx] + existing[node_idx+1:]
        except:
            pass
    
    return existing
```

**4. Hierarchical Context Extraction (Verified from `mindmap_palette.py`):**
```python
def extract_hierarchical_context(diagram_type: str, spec: Dict[str, Any], 
                                node_id: str) -> Dict[str, Any]:
    """Extract hierarchical context for child nodes - VERIFIED PATTERN"""
    context = {}
    
    if diagram_type == 'mindmap':
        # Parse node ID: child_0_1 -> branch 0, child 1
        match = re.match(r'child_(\d+)_(\d+)', node_id)
        if match:
            branch_idx = int(match.group(1))
            child_idx = int(match.group(2))
            
            # Get branch from spec.children (VERIFIED)
            branches = spec.get('children', [])
            if branch_idx < len(branches):
                branch = branches[branch_idx]
                context['branch_label'] = branch.get('label') or branch.get('text', '')
                context['existing_children'] = [
                    c.get('label') or c.get('text', '') 
                    for c in branch.get('children', [])
                ]
    
    elif diagram_type == 'tree_map':
        # Parse: tree-leaf-0-1 -> category 0, item 1
        match = re.match(r'tree-leaf-(\d+)-(\d+)', node_id)
        if match:
            cat_idx = int(match.group(1))
            item_idx = int(match.group(2))
            
            categories = spec.get('children', [])
            if cat_idx < len(categories):
                category = categories[cat_idx]
                context['category_label'] = category.get('text', '')
                context['existing_items'] = [
                    item.get('text', '') 
                    for item in category.get('children', [])
                ]
    
    elif diagram_type == 'flow_map':
        # Parse: flow-substep-0-1 -> step 0, substep 1
        match = re.match(r'flow-substep-(\d+)-(\d+)', node_id)
        if match:
            step_idx = int(match.group(1))
            substep_idx = int(match.group(2))
            
            steps = spec.get('steps', [])
            if step_idx < len(steps):
                step_text = steps[step_idx]
                # Find substeps for this step (VERIFIED structure)
                substeps_array = spec.get('substeps', [])
                step_substeps = next(
                    (s for s in substeps_array if s.get('step') == step_text),
                    None
                )
                if step_substeps:
                    context['step_label'] = step_text
                    context['existing_substeps'] = [
                        s.get('text', '') if isinstance(s, dict) else str(s)
                        for s in step_substeps.get('substeps', [])
                    ]
    
    elif diagram_type == 'brace_map':
        # Parse: brace-subpart-0-1 -> part 0, subpart 1
        match = re.match(r'brace-subpart-(\d+)-(\d+)', node_id)
        if match:
            part_idx = int(match.group(1))
            subpart_idx = int(match.group(2))
            
            parts = spec.get('parts', [])
            if part_idx < len(parts):
                part = parts[part_idx]
                context['part_label'] = part.get('name') or part.get('text', '')
                context['existing_subparts'] = [
                    sp.get('name') or sp.get('text', '')
                    for sp in part.get('subparts', [])
                ]
    
    return context
```

---

#### Tab Agent Prompt Building - Verified Patterns

**From `double_bubble_palette.py` (lines 156-191):**
- Similarities mode: Uses `left_topic` and `right_topic` separately
- Differences mode: Generates paired nodes with `left` and `right` fields
- Center topic format: "Left Topic vs Right Topic"

**From `mindmap_palette.py` (lines 112-150):**
- Branches stage: Uses `center_topic` (main topic)
- Children stage: Uses `branch_name` from `stage_data` as context
- Educational context: Extracted from `educational_context.get('raw_message')`

**Verified Prompt Context Fields:**
```python
# Double Bubble Map
{
    'left_topic': spec.get('left'),
    'right_topic': spec.get('right'),
    'node_category': 'similarities' | 'left_differences' | 'right_differences',
    'existing_nodes': [...],
    'partial_input': user_input
}

# Mindmap Child Nodes
{
    'main_topic': spec.get('topic'),
    'branch_label': branch.get('label'),  # Parent branch
    'existing_children': branch.get('children', []),
    'partial_input': user_input
}

# Generic (Bubble, Circle, etc.)
{
    'main_topic': spec.get('topic'),
    'node_category': 'attributes' | 'context' | etc.,
    'existing_nodes': [...],
    'partial_input': user_input
}
```

---

#### Tab Agent Expansion - Verified Patterns

**From `mindmap_palette.py` (lines 40-110):**
- Expansion uses `stage='children'` with `stage_data={'branch_name': '...'}`
- Center topic remains main topic, but branch name is used as context
- Generated nodes are tagged with `mode` field matching branch name

**Verified Expansion Context:**
```python
# Mindmap Branch Expansion
{
    'main_topic': spec.get('topic'),
    'node_text': branch.get('label'),  # Branch being expanded
    'existing_children': branch.get('children', []),
    'num_children': 4-6
}

# Tree Map Category Expansion
{
    'main_topic': spec.get('topic'),
    'node_text': category.get('text'),
    'existing_children': category.get('children', []),
    'num_children': 4-6
}

# Flow Map Step Expansion
{
    'main_topic': spec.get('title'),
    'node_text': step_text,
    'existing_children': step_substeps.get('substeps', []),
    'num_children': 3-4
}
```

---

#### Critical Implementation Notes (Verified from Codebase)

1. **Spec Structure Variations:**
   - Some diagrams use `spec.children`, others use `spec.attributes`, `spec.context`, etc.
   - Mindmap uses `spec.children` (array of branch objects), not `spec.branches`
   - Flow map uses `spec.steps` (array) + `spec.substeps` (array of objects with `step` field)

2. **Node Text Extraction:**
   - Mindmap: `node.get('label')` or `node.get('text')`
   - Tree Map: `node.get('text')`
   - Brace Map: `node.get('name')` or `node.get('text')`
   - Others: `node.get('text')` or `str(node)`

3. **Node ID Parsing:**
   - Use regex patterns, not simple string splitting
   - Handle hierarchical IDs: `child_0_1`, `tree-leaf-0-1`, `flow-substep-0-1`
   - Extract indices correctly (0-based)

4. **Double Bubble Map Special Handling:**
   - Node category MUST be determined from node ID pattern, not node type
   - Three separate arrays: `similarities`, `left_differences`, `right_differences`
   - Both `left` and `right` topics are required for context

5. **Mindmap Child Node Special Handling:**
   - Must extract parent branch label for child node context
   - Check if placeholder to determine expand vs autocomplete mode
   - Use `spec.children[branchIndex].label` for branch text

### Phase 14: Event Bus & State Manager Integration Verification

**✅ Complete Integration Patterns Verified Against Codebase**

This section documents how Tab Mode integrates with Event Bus and State Manager, verified against actual manager implementations (`PropertyPanelManager`, `VoiceAgentManager`, `ThinkGuideManager`).

---

#### Event Bus Integration Pattern (Verified)

**Constructor Pattern:**
```javascript
class TabModeManager {
    constructor(eventBus, stateManager, logger, editor) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        
        // CRITICAL: Owner ID for Event Bus Listener Registry
        this.ownerId = 'TabModeManager';
        
        // Initialize
        this.initialize();
        this.subscribeToEvents();
    }
}
```

**Event Subscription Pattern (Verified from `property-panel-manager.js`):**
```javascript
subscribeToEvents() {
    // Use onWithOwner() for all subscriptions (enables cleanup)
    
    // Listen for node selection changes
    this.eventBus.onWithOwner('interaction:selection_changed', (data) => {
        const selectedNodes = data.selectedNodes || [];
        if (selectedNodes.length === 1 && this.mode === 'viewing') {
            this.selectedNode = selectedNodes[0];
            this.updateExpansionState();
        }
    }, this.ownerId);
    
    // Listen for diagram updates (node content changes)
    this.eventBus.onWithOwner('diagram:node_updated', (data) => {
        // Invalidate cached context if node was updated
        if (data.nodeId === this.context?.nodeId) {
            this.context = null;
        }
    }, this.ownerId);
    
    // Listen for diagram rendering (new diagram loaded)
    this.eventBus.onWithOwner('diagram:rendered', () => {
        // Reset Tab Mode state when new diagram is rendered
        this.detachFromInput();
        this.selectedNode = null;
        this.context = null;
    }, this.ownerId);
    
    // Listen for state changes
    this.eventBus.onWithOwner('state:diagram_updated', (data) => {
        // Update context if diagram type changed
        if (data.updates?.type) {
            this.context = null; // Invalidate cached context
        }
    }, this.ownerId);
    
    // Listen for selection changes from State Manager
    this.eventBus.onWithOwner('state:selection_changed', (data) => {
        if (this.mode === 'viewing' && data.selectedNodes?.length === 1) {
            this.selectedNode = data.selectedNodes[0];
        }
    }, this.ownerId);
    
    this.logger.debug('TabModeManager', 'Subscribed to events with owner tracking');
}
```

**Event Emission Pattern (Verified from `double-bubble-map-operations.js`):**
```javascript
// Emit events for Tab Mode state changes
enable() {
    this.enabled = true;
    this.eventBus.emit('tab_mode:enabled', {
        mode: this.mode,
        timestamp: Date.now()
    });
    this.logger.info('TabModeManager', 'Tab mode enabled');
}

disable() {
    this.enabled = false;
    this.hideSuggestions();
    this.eventBus.emit('tab_mode:disabled', {
        timestamp: Date.now()
    });
    this.logger.info('TabModeManager', 'Tab mode disabled');
}

// Emit when suggestions are requested
async requestSuggestions(context) {
    this.eventBus.emit('tab_mode:suggestion_requested', {
        nodeId: context.nodeId,
        diagramType: context.diagramType,
        partialInput: context.partialInput,
        timestamp: Date.now()
    });
    
    // ... API call ...
    
    this.eventBus.emit('tab_mode:suggestion_received', {
        nodeId: context.nodeId,
        suggestions: suggestions,
        count: suggestions.length,
        timestamp: Date.now()
    });
}

// Emit when suggestion is accepted
acceptSuggestion(index) {
    const suggestion = this.suggestions[index];
    this.eventBus.emit('tab_mode:suggestion_accepted', {
        nodeId: this.context?.nodeId,
        suggestion: suggestion,
        index: index,
        timestamp: Date.now()
    });
    
    // ... insert suggestion ...
}

// Emit when expansion starts/completes
async expandNode(nodeId, context) {
    this.isExpanding = true;
    this.eventBus.emit('tab_mode:expansion_started', {
        nodeId: nodeId,
        diagramType: context.diagramType,
        nodeType: context.nodeType,
        timestamp: Date.now()
    });
    
    try {
        // ... API call ...
        
        this.eventBus.emit('tab_mode:expansion_completed', {
            nodeId: nodeId,
            children: children,
            count: children.length,
            timestamp: Date.now()
        });
        
        // Trigger diagram update event
        this.eventBus.emit('diagram:node_expanded', {
            nodeId: nodeId,
            children: children,
            diagramType: context.diagramType
        });
    } finally {
        this.isExpanding = false;
    }
}
```

**Cleanup Pattern (Verified from `interaction-handler.js`):**
```javascript
destroy() {
    // Remove all event listeners for this owner
    const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
    this.logger.debug('TabModeManager', `Removed ${removedCount} event listeners`);
    
    // Cleanup state
    this.detachFromInput();
    this.hideSuggestions();
    this.enabled = false;
}
```

---

#### State Manager Integration Pattern (Verified)

**Reading State (Verified from `state-manager.js`):**
```javascript
// Get diagram type from State Manager
getDiagramType() {
    const diagramState = this.stateManager.getDiagramState();
    return diagramState?.type || this.editor?.diagramType;
}

// Get selected nodes from State Manager
getSelectedNodes() {
    const diagramState = this.stateManager.getDiagramState();
    return diagramState?.selectedNodes || [];
}

// Get diagram spec from State Manager
getDiagramSpec() {
    const diagramState = this.stateManager.getDiagramState();
    return diagramState?.data || this.editor?.currentSpec;
}
```

**Updating State (Verified from `state-manager.js`):**
```javascript
// Update Tab Mode state in State Manager
updateTabModeState(updates) {
    // Note: Tab Mode state is NOT stored in State Manager
    // It's local to TabModeManager instance
    // But we can emit events for other components to react
    
    this.eventBus.emit('tab_mode:state_changed', {
        enabled: this.enabled,
        mode: this.mode,
        ...updates
    });
}

// Update diagram state when node is expanded
async expandNode(nodeId, context) {
    // ... generate children ...
    
    // Update diagram spec in editor
    this.editor.currentSpec = updatedSpec;
    
    // Update State Manager
    this.stateManager.updateDiagram({
        data: updatedSpec,
        // Don't update type - it shouldn't change
    });
    
    // Emit event for diagram update
    this.eventBus.emit('diagram:node_expanded', {
        nodeId: nodeId,
        children: children
    });
}
```

**State Initialization (Verified from `state-manager.js`):**
```javascript
// Tab Mode state is NOT added to State Manager's initial state
// It's managed locally in TabModeManager instance
// Reason: Tab Mode is a UI feature, not core application state

// However, we can sync enabled state if needed:
syncEnabledState() {
    // Read from State Manager if it exists
    const state = this.stateManager.getState();
    // Tab Mode state is not stored in State Manager
    // It's purely local to TabModeManager
}
```

---

#### Complete Event List

**Events Tab Mode Emits:**
```javascript
// Tab Mode lifecycle
'tab_mode:enabled'           // Tab mode activated
'tab_mode:disabled'          // Tab mode deactivated
'tab_mode:state_changed'     // Internal state changed

// Editing mode (autocomplete)
'tab_mode:suggestion_requested'  // API request started
'tab_mode:suggestion_received'   // API response received
'tab_mode:suggestion_accepted'   // User accepted suggestion
'tab_mode:suggestion_dismissed'  // User dismissed suggestions

// Viewing mode (expansion)
'tab_mode:expansion_started'    // Expansion API request started
'tab_mode:expansion_completed'  // Expansion completed successfully
'tab_mode:expansion_failed'     // Expansion failed

// Diagram updates
'diagram:node_expanded'         // Node expanded (children added)
```

**Events Tab Mode Listens To:**
```javascript
// Selection changes
'interaction:selection_changed'  // Node selection changed (from InteractionHandler)
'state:selection_changed'        // Selection changed (from State Manager)

// Diagram lifecycle
'diagram:rendered'               // New diagram rendered
'diagram:node_updated'           // Node content updated
'diagram:node_added'             // New node added
'diagram:node_deleted'           // Node deleted

// State changes
'state:diagram_updated'           // Diagram state updated (type, spec, etc.)

// Panel lifecycle (for input focus detection)
'property_panel:opened'          // Property panel opened
'property_panel:closed'           // Property panel closed
'node_editor:opened'              // Node editor modal opened
'node_editor:closed'              // Node editor modal closed
```

---

#### Integration with Other Managers

**Property Panel Manager Integration:**
```javascript
// In PropertyPanelManager.subscribeToEvents()
this.eventBus.onWithOwner('tab_mode:suggestion_accepted', (data) => {
    // Update property panel if it's showing the same node
    if (this.currentNodeId === data.nodeId) {
        // Refresh property panel to show updated text
        this.loadNodeProperties(data.nodeId);
    }
}, this.ownerId);
```

**Node Editor Integration:**
```javascript
// In NodeEditor (when saving)
this.eventBus.emit('node_editor:saved', {
    nodeId: this.nodeData.nodeId,
    newText: this.textInput.value
});

// Tab Mode listens to this to invalidate cached context
this.eventBus.onWithOwner('node_editor:saved', (data) => {
    if (this.context?.nodeId === data.nodeId) {
        this.context = null; // Invalidate cache
    }
}, this.ownerId);
```

**Interaction Handler Integration:**
```javascript
// Tab Mode listens to selection changes
this.eventBus.onWithOwner('interaction:selection_changed', (data) => {
    if (this.mode === 'viewing' && data.selectedNodes?.length === 1) {
        // Check if node is expandable
        const nodeId = data.selectedNodes[0];
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (!nodeElement.empty()) {
            const diagramType = this.getDiagramType();
            if (this.isNodeExpandable(diagramType, nodeId, nodeElement)) {
                this.selectedNode = nodeId;
                // Ready for Tab key expansion
            }
        }
    }
}, this.ownerId);
```

---

#### State Manager State Structure

**Current State Manager Structure (from `state-manager.js`):**
```javascript
{
    panels: {
        thinkguide: {...},
        mindmate: {...},
        nodePalette: {...},
        property: {...}
        // Note: Tab Mode is NOT a panel, so no state here
    },
    diagram: {
        type: string,           // Diagram type
        sessionId: string,      // Session ID
        data: object,           // Current spec
        selectedNodes: [],     // Selected node IDs
        history: [],           // Undo/redo stack
        historyIndex: number
    },
    voice: {...},
    ui: {...}
}
```

**Tab Mode State (Local to TabModeManager):**
```javascript
// Tab Mode state is NOT stored in State Manager
// It's managed locally in TabModeManager instance
{
    enabled: boolean,
    mode: 'editing' | 'viewing',
    activeInput: HTMLElement,
    suggestions: [],
    selectedIndex: number,
    selectedNode: string,
    isExpanding: boolean,
    context: {...}
}
```

**Rationale:**
- Tab Mode is a UI feature, not core application state
- State Manager is for persistent, shared state
- Tab Mode state is transient and UI-specific
- Events are emitted for other components to react, but state stays local

---

#### Event Bus Cleanup & Lifecycle

**Session Lifecycle (Verified from `voice-agent-manager.js`):**
```javascript
// Listen for session ending
this.eventBus.onWithOwner('lifecycle:session_ending', () => {
    this.destroy(); // Cleanup all listeners
}, this.ownerId);

// Listen for diagram changes
this.eventBus.onWithOwner('diagram:rendered', () => {
    // Reset Tab Mode when new diagram loads
    this.detachFromInput();
    this.selectedNode = null;
    this.context = null;
}, this.ownerId);
```

**Memory Leak Prevention:**
```javascript
// CRITICAL: Always use onWithOwner() for subscriptions
// This enables automatic cleanup via removeAllListenersForOwner()

// Example cleanup in destroy()
destroy() {
    // Remove all listeners for this owner
    this.eventBus.removeAllListenersForOwner(this.ownerId);
    
    // Cleanup timers
    if (this.debounceTimer) {
        clearTimeout(this.debounceTimer);
    }
    
    // Cancel pending requests
    if (this.abortController) {
        this.abortController.abort();
    }
    
    // Detach from input
    this.detachFromInput();
    
    // Clear state
    this.enabled = false;
    this.suggestions = [];
    this.selectedNode = null;
    this.context = null;
}
```

---

#### Verification Checklist

**Event Bus Integration:**
- [x] Constructor receives `eventBus` and `stateManager`
- [x] Owner ID set: `this.ownerId = 'TabModeManager'`
- [x] All subscriptions use `onWithOwner()`
- [x] Events emitted for all state changes
- [x] Cleanup uses `removeAllListenersForOwner()`
- [x] Listens to diagram lifecycle events
- [x] Listens to selection changes
- [x] Emits events for other components to react

**State Manager Integration:**
- [x] Reads diagram type from `stateManager.getDiagramState()?.type`
- [x] Reads selected nodes from `stateManager.getDiagramState()?.selectedNodes`
- [x] Reads diagram spec from `stateManager.getDiagramState()?.data`
- [x] Updates diagram state via `stateManager.updateDiagram()`
- [x] Listens to state changes via events
- [x] Tab Mode state is local (not in State Manager)

**Integration Points:**
- [x] Property Panel Manager can react to Tab Mode events
- [x] Node Editor can react to Tab Mode events
- [x] Interaction Handler can react to Tab Mode events
- [x] Tab Mode reacts to diagram lifecycle events
- [x] Tab Mode reacts to selection changes

### Phase 15: LLM Middleware Integration Verification

**✅ Tab Agent Already Uses LLM Middleware**

**Important:** `llm_service` IS the middleware layer. When Tab Agent calls `llm_service.chat()`, it automatically gets:

1. **Rate Limiting** ✅
   - Automatic via `rate_limiter` (Dashscope QPM/concurrent limits)
   - Applied via `async with self.rate_limiter:` context manager
   - Prevents API rate limit errors

2. **Error Handling with Retry** ✅
   - Automatic via `error_handler.with_retry()`
   - Exponential backoff (1s, 2s, 4s)
   - Handles timeouts, rate limits, network errors
   - Max 3 retries by default

3. **Token Tracking** ✅
   - Automatic via `token_tracker.track_usage()`
   - Tracks per-user, per-organization usage
   - Calculates costs based on model pricing
   - Async, non-blocking (queue-based batch writes)

4. **Performance Tracking** ✅
   - Automatic via `performance_tracker.record_request()`
   - Tracks response times, success rates
   - Records errors for monitoring

5. **Timeout Handling** ✅
   - Automatic via `asyncio.wait_for()`
   - Per-model default timeouts (qwen-plus: 70s)
   - Custom timeout override supported

**Verified from `services/llm_service.py` (lines 85-265):**
```python
async def chat(self, ...):
    # Rate limiting
    if self.rate_limiter:
        async with self.rate_limiter:
            # Error handling with retry
            response = await asyncio.wait_for(
                error_handler.with_retry(_call),
                timeout=timeout
            )
    
    # Token tracking (async, non-blocking)
    await token_tracker.track_usage(...)
    
    # Performance tracking
    self.performance_tracker.record_request(...)
```

**No Additional Middleware Needed:**
- ✅ Tab Agent uses `llm_service.chat()` directly (correct pattern)
- ✅ All middleware functionality is built-in
- ✅ No wrapper class needed (unlike WebSocket connections)
- ✅ Follows same pattern as all other agents (`BaseThinkingAgent`, `NodePaletteGenerator`, etc.)

**WebSocket Middleware Note:**
- `WebSocketLLMMiddleware` is ONLY for WebSocket connections (Omni)
- Tab Agent uses REST endpoints, so `llm_service` is sufficient
- No need to use `WebSocketLLMMiddleware` for Tab Agent

**Verification:**
- [x] Tab Agent uses `llm_service.chat()` ✅
- [x] Rate limiting applied automatically ✅
- [x] Error handling with retry applied automatically ✅
- [x] Token tracking applied automatically ✅
- [x] Performance tracking applied automatically ✅
- [x] Timeout handling applied automatically ✅
- [x] Follows same pattern as other agents ✅

---

### Phase 16: Metadata Verification Summary

**✅ Complete Metadata Checkup Verified:**

1. **Node IDs** ✅
   - All 10 diagram types' node ID patterns documented
   - Extraction logic handles all patterns (simple `_${index}`, hierarchical `_${idx}_${idx}`, prefixed patterns)
   - Helper functions provided for parsing node IDs

2. **Node Types** ✅
   - All `data-node-type` values documented (23 types)
   - Type-based logic for expandability checks
   - Type-based category determination (double bubble map)

3. **Diagram Detection** ✅
   - Multiple detection methods documented (editor instance, state manager, spec)
   - Priority order established
   - Fallback mechanisms included

4. **Metadata Extraction** ✅
   - Complete `extractContext()` method for editing mode
   - Complete `extractExpansionContext()` method for viewing mode
   - Handles all diagram types with proper spec field access
   - Extracts hierarchical indices (branch_index, child_index, etc.)
   - Extracts node category from ID patterns or type

5. **Integration Points** ✅
   - NodeEditor: Uses `this.nodeData.nodeId`
   - PropertyPanel: Uses `this.currentNodeId`
   - Viewing Mode: Uses `stateManager.getSelectedNodes()`
   - All integration points use DOM elements as source of truth

6. **Context Requirements** ✅
   - Main topics extraction for all diagram types
   - Existing nodes extraction per category
   - Cursor position tracking
   - Node category determination
   - Hierarchical index extraction

**Critical Implementation Notes:**
- Always use DOM elements (`d3.select(\`[data-node-id="${nodeId}"]\`)`) as source of truth
- Extract node type from `data-node-type` attribute, not from spec
- Parse node IDs using regex patterns, not string splitting (handles complex patterns)
- Check expandability using both diagram type AND node type
- Handle null/undefined values gracefully (use optional chaining)

---

## Conclusion

Tab Mode is a powerful feature that enhances the editing experience by providing intelligent, context-aware suggestions. By leveraging the existing LLM infrastructure and following established patterns in the codebase, we can implement this feature efficiently and maintainably.

The design prioritizes:
1. **Performance**: Fast response times through debouncing and efficient LLM calls
2. **User Experience**: Intuitive keyboard shortcuts and smooth interactions
3. **Maintainability**: Clean architecture following existing patterns
4. **Extensibility**: Easy to add support for other diagram types

The implementation plan is structured to deliver value incrementally, starting with double bubble map support and expanding to other diagram types.

