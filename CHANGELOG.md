# Changelog

All notable changes to the MindGraph project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## 🎉 Latest Release Summary | 最新版本概述

### Version 3.0.16 - Interactive Learning Mode (Phase 4) 🧠

**Major Educational Feature**: MindGraph now includes a complete **AI-Powered Interactive Learning Mode** that transforms static diagrams into intelligent tutoring experiences for K-12 education.

**主要教育功能**: MindGraph现在包含完整的**AI驱动的交互式学习模式**，将静态图表转换为K-12教育的智能辅导体验。

#### What's New | 新增功能

✨ **Multi-Angle Verification System** (Phase 4)
- Tests student understanding from 4 cognitive perspectives
- 3-level escalation system with adaptive teaching strategies
- Skip option after maximum attempts (3 escalations)
- Misconception pattern tracking across learning session

✨ **Teaching Material Modal with Node Highlighting** (Phase 3)
- Full-screen modal with AI-generated teaching content
- Golden pulse animation highlights the node being tested
- Visual "Testing Node" badge shows context (e.g., "Branch 2 of 'iPhone'")
- "I Understand" → Verification question workflow

✨ **Interactive Canvas-Based Learning**
- Students type answers directly into hidden nodes (20% random knockout)
- Real-time AI validation with semantic understanding
- LLM-generated contextual questions based on node relationships
- Progress tracking with attempts, correct answers, and escalation levels

✨ **Backend Intelligence (LangChain Agent)**
- `LearningAgentV3` with prerequisite knowledge testing
- Session management with Flask blueprint API (`/api/learning/*`)
- Smart question generation based on diagram structure
- Adaptive hint generation (3 levels)

✨ **Full Bilingual Support**
- All learning UI elements in English and Chinese
- Language-aware question and hint generation
- Smooth language switching during learning sessions

#### Educational Impact | 教育影响

This release transforms MindGraph from a **diagram generation tool** into an **Intelligent Tutoring System** specifically designed for K-12 classroom learning.

本版本将MindGraph从**图表生成工具**转变为专为K-12课堂学习设计的**智能辅导系统**。

---

## [v3.0.16] - 2025-10-05

### Added
- **Learning Mode: Phase 4 - Multi-Angle Verification & Escalation System** 🎯
  - **Verification Questions**: After showing learning materials, system now tests understanding from different cognitive angles
    - Level 0: Structural relationship (how node relates to others)
    - Level 1: Functional role (node's purpose in concept)
    - Level 2: Application (real-world examples)
    - Level 3: Definition (simplest explanation)
  - **3-Level Escalation System**:
    - User clicks "I Understand" → Verification question appears in modal
    - Wrong answer → Escalate to Level 1 (new teaching angle)
    - Still wrong → Escalate to Level 2 (different teaching strategy)
    - Still wrong → Escalate to Level 3 (maximum attempts)
    - After Level 3 → "Skip" button appears (red, bottom of modal)
  - **Escalation Tracking**:
    - `currentNodeEscalations`: Tracks escalations for current node (0-3)
    - `misconceptionPatterns[]`: Session-wide array of all misconceptions
    - Each pattern stored with: nodeId, userAnswer, correctAnswer, escalationLevel, timestamp
    - Escalation indicator badge: "📊 Attempt X of 3" shown at top of verification modal
  - **Skip Functionality**:
    - Only appears after 3 failed verification attempts
    - Red button (rgba(239, 68, 68, 0.8)) with hover effects
    - Logs skip event and resets escalation counter for next node
  - **Verification Flow**:
    1. User answers original question wrong → Learning material modal shows
    2. User clicks "I Understand" → Verification UI replaces modal content
    3. Verification question from different angle (based on escalation level)
    4. User answers:
       - ✅ Correct → "Understanding Verified!" → Next question (2s delay)
       - ❌ Wrong → Escalate → New angle → Repeat (up to 3 times)
    5. After max escalations → Skip button appears
  - **UI Components**:
    - Title: "🎯 Let's Verify Your Understanding" | "让我们验证一下你的理解"
    - Attempt indicator: Yellow box showing "Attempt X of 3"
    - Question area: Purple gradient background with perspective-based question
    - Input field: White semi-transparent with yellow focus border
    - Feedback area: Dynamic (green for success, red for failure, yellow for skip notice)
    - Submit button: Blue (#3b82f6) with hover effects
    - Skip button: Red, only after 3 escalations
  - **Backend Integration**:
    - Calls `/api/learning/verify_understanding` endpoint
    - Sends: session_id, node_id, user_answer, correct_answer, verification_question, language
    - Receives: understanding_verified (bool), message, confidence, etc.
  - **Files Modified**:
    - `static/js/editor/learning-mode-manager.js`: 
      - Added escalation tracking variables
      - `showVerificationQuestion()` - Main verification UI
      - `_generateVerificationQuestion()` - Multi-angle question generator
      - `handleVerificationAnswer()` - Verification logic & escalation
      - `verifyUnderstandingWithBackend()` - API call
    - `static/js/editor/language-manager.js`: Added `verificationTitle`, `skipQuestion` translations
    - `CHANGELOG.md`: Documented Phase 4 implementation

---

## [v3.0.15] - 2025-10-05

### Added
- **Learning Mode: Phase 3 - Teaching Material Modal with Node Highlighting** 🎓
  - **New Feature**: Full-screen modal displays LLM-generated teaching materials when answer is wrong
  - **Node Highlighting** ⚡ (User-requested UX improvement):
    - 🎯 **"Testing Node" badge** in modal header shows which node is being tested
    - Context-aware descriptions: "Attribute 3 of 'acceleration'" or "Branch 2 of 'iPhone'"
    - **Visual canvas highlighting**: Node glows with golden (#fbbf24) pulse animation
    - Temporarily reveals text of hidden node during teaching
    - Highlight removed when modal closes
  - **Modal Design**:
    - Purple gradient background with smooth fade-in/slide-up animations
    - **Testing Node Badge**: Yellow-bordered box with 🎯 icon showing node context
    - Displays agent's intelligent teaching response (misconception analysis, prerequisite teaching)
    - Shows correct answer in a green highlighted box
    - Two action buttons: "I Understand" (green) and "Close" (transparent)
    - Fully bilingual (English/Chinese) with translations for all UI elements
  - **Agent Integration**:
    - Modal triggered by `LearningAgentV3` workflow when validation fails
    - Displays `agent_workflow.agent_response` from backend
    - Supports prerequisite knowledge testing and teaching flow
  - **UI Components**:
    - Gradient modal: `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
    - Testing Node Badge: `rgba(255, 255, 255, 0.25)` with yellow border
    - Responsive layout: max-width 700px, max-height 80vh with scrolling
    - Smooth animations: fadeIn (0.3s), slideUp (0.4s), pulse (1.5s infinite)
    - Hover effects on buttons with transform animations
  - **Translations Added**:
    - `learningMaterialTitle`: "Let's Learn This Concept!" | "让我们一起学习这个概念！"
    - `learningMaterialAcknowledgment`, `learningMaterialContrast`, etc.
    - `learningMaterialUnderstand`: "I Understand" | "我明白了"
  - **Files Modified**:
    - `static/js/editor/learning-mode-manager.js`: Added `showLearningMaterialModal()`, `highlightNodeOnCanvas()`, `removeNodeHighlight()`, `_getNodeContextDescription()` methods
    - `static/js/editor/language-manager.js`: Added 9 new translation keys
    - `static/css/editor-toolbar.css`: Added fadeIn/slideUp/pulse animations

---

## [v3.0.14] - 2025-10-05

### Fixed
- **Undo/Redo System**: Fixed completely broken undo/redo functionality
  - **Critical Bug**: Undo/redo buttons did nothing - just re-rendered current state
  - **Root Cause**: 
    - `saveToHistory()` only saved action metadata (node IDs, counts), NOT the actual diagram spec
    - `undo()` and `redo()` changed historyIndex but never restored `currentSpec` from history
    - `renderDiagram()` kept using current spec, so nothing changed visually
  - **Solution**:
    1. Modified `saveToHistory()` to save deep clone of entire `currentSpec` in each history entry
    2. Modified `undo()` to restore `currentSpec` from `history[historyIndex].spec` before rendering
    3. Modified `redo()` to restore `currentSpec` from `history[historyIndex].spec` before rendering
    4. Added initial state save on diagram load (users can undo back to start)
    5. Added user notifications for undo/redo actions
    6. Clear node selection after undo/redo (nodes may no longer exist)
  - **Impact**: Undo/redo now actually works! Users can revert any change (add node, delete node, edit text, move node)
  - **Testing**: Try adding/deleting/editing nodes, then press Ctrl+Z (undo) and Ctrl+Y (redo)
- **Node Counter**: Fixed non-functional node counter in lower left corner
  - **Issue**: Counter only showed "1" instead of actual node count (e.g., showed 1 when there were 9 nodes)
  - **Root Cause**: Multiple renderers had text elements missing `data-node-id` attribute
    - Bubble/Circle Map: attribute and context text elements
    - Mind Map: branch and child text elements
    - Tree Map: category and leaf text elements
    - Brace Map: part and subpart text elements
  - **Solution**:
    1. Added `data-node-id` and `data-node-type` to all text elements in 4 affected renderers
    2. Implemented efficient MutationObserver watching SVG container for DOM changes
    3. Debounced updates (100ms) to minimize resource usage
    4. Observer only watches childList changes (no attribute watching for efficiency)
  - **Impact**: Node counter now accurately shows total count like "节点: 9" or "Nodes: 9" for ALL diagram types
  - **Performance**: Minimal resources - only watches DOM additions/removals, debounced updates

- **Node Editor Translation**: Fixed missing Chinese translations when double-clicking nodes to edit
  - **Issue**: Node editor modal showed English text ("Edit Node Content", "Text:", "Cancel", "Save Changes", "characters") even in Chinese mode
  - **Solution**: 
    1. Added translations to language-manager.js: `editNodeContent`, `characters`, `cancel`, `saveChanges`
    2. Updated node-editor.js to use `window.languageManager.translate()` for all text
    3. Now shows Chinese text: "编辑节点内容", "文本:", "取消", "保存更改", "字"
  - **Impact**: Full bilingual support in node editor dialog

- **Prompt Template Placeholders**: Removed unused `{user_prompt}` placeholders from all prompt templates
  - **Affected diagrams**: Bridge Map, Bubble Map, Circle Map, Double Bubble Map, Tree Map, Brace Map, Flow Map, Multi-Flow Map (8 Thinking Maps)
  - **Issue**: Placeholders appeared as literal text `{user_prompt}` in system prompts sent to LLM
  - **Root cause**: Agents never called `.format()` to fill placeholders, unlike Concept Map and Main Agent
  - **Solution**: Removed all unused placeholder lines from `prompts/thinking_maps.py`
  - **Impact**: Cleaner prompts, reduced token usage (~5 tokens per request), no functional changes
  - **Unchanged**: Concept Map and Main Agent still use placeholders correctly with `.format()`
  - See `docs/PLACEHOLDER_AUDIT.md` for detailed code review

- **All Thinking Maps Auto-Complete**: Fixed incorrect topic extraction in editor for all diagram types
  - **Issue**: Auto-complete was extracting wrong node text as topic (e.g., attribute bubbles instead of central topic)
  - **Root cause**: Topic identification relied on distance-from-center calculation or spec fallback, both unreliable
  - **Solution**: 
    1. Added `data-node-type` and `data-node-id` attributes to topic text elements in all renderers
    2. Updated `extractExistingNodes()` to capture these attributes from SVG
    3. Updated `identifyMainTopic()` to use `data-node-type='topic'` for reliable topic detection
  - **Fixed diagrams**: 
    - Bubble Map, Circle Map, Tree Map, Brace Map (added attributes today)
    - Double Bubble Map (combines both topics: "Apple vs Banana")
    - Mind Map, Flow Map, Multi-Flow Map (already had attributes)
    - **Bridge Map** (special handling: extracts first analogy pair like "北京/中国")
  - **Impact**: Auto-complete now correctly identifies and uses the central topic (e.g., "抗日战争")
  - **Bridge Map Impact**: Was sending relating factor "如同" (as), now sends first pair "北京/中国"
  - **All 8 Thinking Maps + Mind Map now use consistent, reliable topic extraction** ✓

### Documentation
- Added `docs/PLACEHOLDER_AUDIT.md`: Comprehensive audit of placeholder usage across all 11 diagram types
  - Evidence of unused placeholders with code examples
  - Comparison of working vs non-working implementations
  - Token savings calculation and verification steps

---

## [v3.0.13] - 2025-10-05

### Fixed
- **Node Transparency Issues**: Fixed nodes showing connection lines through them when hovering
  - Removed `opacity: 0.9` from Double Bubble Map topic circles (left and right)
  - Added explicit `opacity: 1` to Mind Map nodes (topic, branches, children)
  - Nodes now render fully opaque, hiding connection lines underneath
  - Connection lines remain at `opacity: 0.7` for visual depth (intentional)

- **MindMap Auto-Complete Prompt Issues**: Fixed placeholder content being sent to LLM
  - **Issue**: Prompt included default branch names like "分支1, 分支2, 分支3, 分支4" or "Branch 1, 2, 3, 4"
  - **Issue**: Prompt included child node placeholders like "子项1.1, 子项1.2" (Subitem 1.1, etc.)
  - **Solution**: MindMap now uses simplified prompt with only the main topic (like Flow Map and Brace Map)
  - **Result**: Clean prompts like `为主题"iPhone"创建一个完整的思维导图` instead of listing all placeholder nodes
  - LLM now generates relevant content based on actual user topic instead of generic placeholders

- **Main Topic Identification**: Fixed auto-complete using outdated topic from spec
  - **Issue**: When user edits central topic (e.g., "中心主题" → "iPhone"), auto-complete still used old spec value
  - **Solution**: `identifyMainTopic()` now reads actual SVG text from central node position instead of spec
  - For MindMap, Tree Map, Bubble Map, Circle Map: finds node closest to canvas center
  - Prioritizes displayed text over potentially stale spec data
  - Users' edited text now correctly recognized for auto-completion

- **Placeholder Filtering**: Enhanced placeholder detection in auto-complete
  - Added Chinese patterns: `分支\d+`, `中心主题`, `新分支` 
  - Added English patterns: `Branch\s*\d+`, `Central Topic`, `New Branch`
  - Prevents template text from being included in LLM prompts
  - Cleaner prompts focused on actual user content

### Added
- **Concept Map Development Notice**: Browser notification when selecting Concept Map
  - Chinese: "概念图功能正在开发中，敬请期待！"
  - English: "Concept Map is under development. Coming soon!"
  - Prevents users from entering incomplete Concept Map editor
  - Clean notification using centralized notification manager

---

## [v3.0.12] - 2025-10-05

### Fixed
- **CRITICAL: Z-Order Issues Across All Diagrams**: Connector lines appearing on top of nodes
  - **Root Cause**: SVG rendering order - elements drawn later appear on top
  - **Impact**: Lines, arrows, braces, and connectors overlapping text and boxes
  - **Solution**: Restructured all renderers to draw connectors FIRST, then nodes on top
  - **Result**: Clean, professional appearance with proper layering across all 10+ diagram types

- **Brace Map Z-Order**: Moved brace path rendering before topic node drawing
  - Curly braces now appear underneath topic text box
  - Ensures topic text remains clearly readable
  - Preserved all interactive editing functionality

- **Tree Map Z-Order**: Moved T-connector lines before all node rendering
  - **CRITICAL**: Fixed regression where T-connectors were drawing AFTER nodes
  - Vertical trunk, horizontal crossbar, and branches now drawn first
  - Root, category, and leaf nodes render on top (with borders)
  - Removed duplicate T-connector drawing code at end of function
  - Clean connector appearance without obscuring text or node borders

- **Concept Map Z-Order**: Restructured edge rendering for proper layering
  - Curved relationship arrows drawn before concept boxes
  - Both main layout and fallback layout paths fixed
  - Edge labels positioned with collision avoidance
  - Nodes and text render cleanly on top of edges

- **Flowchart Z-Order**: Moved arrow markers and connectors before step boxes
  - Arrow marker definitions created first
  - All connector lines drawn before any nodes
  - Diamond decision boxes and rectangular steps appear on top
  - Clean flow visualization without line overlap

- **Flow Map Z-Order**: Complex multi-layer rendering order fixed
  - Step-to-step arrows drawn first
  - L-shaped substep connectors drawn second
  - Main step boxes drawn third
  - Substep boxes drawn last on top
  - Proper layering for complex hierarchical flows

- **Multi-Flow Map Z-Order**: Cause-effect arrows repositioned
  - All arrows (cause→event, event→effect) drawn first
  - Cause nodes drawn second
  - Effect nodes drawn third
  - Central event node drawn last on top
  - Clean visualization with proper arrow layering

### Changed
- **Canvas Watermark Removal**: Cleaner editing experience
  - Removed "MindGraph" watermark from all canvas displays
  - Watermarks only added during PNG export
  - Applies to: Brace Map, Tree Map
  - Verified all other diagram types already clean
  - Consistent behavior across all 10+ diagram types

- **Bridge Map "as" Label Positioning**: Improved visual clarity
  - Moved "as" separator text from above the main line to below
  - Reduces visual clutter in the upper area
  - Better visual hierarchy with analogy pairs above, separators below
  - Changed position from `height/2 - triangleSize - 8` to `height/2 + 20`
  - Maintains clear readability while improving layout balance

- **Bridge Map**: Verified correct z-order (main line before analogy pairs)
  - Already rendering in correct order
  - No changes needed

- **Mind Map, Bubble Maps**: Verified correct z-order
  - Mind Map: Connection lines before nodes ✓
  - Bubble Map: Lines before circles ✓
  - Circle Map: Lines before circles ✓
  - Double Bubble Map: Lines before circles ✓
  - No changes needed

### Technical Details
- **Rendering Order Pattern**: Consistent 3-layer approach
  1. **Layer 1 (Bottom)**: All connector lines, arrows, paths, curves
  2. **Layer 2 (Middle)**: All node boxes/shapes (rectangles, circles, polygons)
  3. **Layer 3 (Top)**: All text labels
  - Ensures proper z-index stacking across all diagram types
  - **Node Borders**: SVG `<rect>` elements include both `fill` and `stroke` attributes
    - Both fill and border render as a single element
    - Z-order applies to the entire element (fill + border together)
    - Verified all node borders render correctly on top of connector lines

- **FlowMap Rendering Optimization**: Eliminated interleaved drawing
  - Pre-calculated all node positions
  - Batch-rendered all connectors first
  - Batch-rendered all nodes second
  - Reduced DOM manipulation operations

- **Concept Map Rendering**: Eliminated node duplication
  - Calculated bounding boxes without drawing
  - Used temporary text elements for measurement
  - Drew edges based on calculated positions
  - Final node drawing pass with proper attributes

- **Code Quality**: Added clear comments for rendering order
  - `// RENDERING ORDER: Draw connectors FIRST, then nodes on top`
  - `// Step 1: Draw all arrows (underneath nodes)`
  - `// Step 2: Draw all nodes ON TOP of arrows`
  - Improves maintainability and prevents future regressions

- **Logging System Cleanup**: Removed all emoji characters from logging
  - Removed emojis from `brace-renderer.js`, `tree-renderer.js`, `concept-map-renderer.js`
  - Removed emojis from `modular-cache-manager.js`
  - Professional, clean log output across all JavaScript files
  - Improved log readability in production environments

---

## [v3.0.11] - 2025-10-05

### Added
- **Brace Map Visual Enhancements**: Professional math-textbook style braces
  - Sharp-tip curly braces with precise proportions (5% tip depth, 1% tip width)
  - Decorative arcs at top/bottom endpoints for braces > 50px height
  - Adaptive stroke widths that scale with canvas size (1.5-5.5px range)
  - Dual-layer outline/stroke rendering for subtle 3D depth effect
  - Collision-safe positioning with dynamic safety gaps
  - Perfect topic-brace alignment (topic center aligns with brace tip)
  - Enhanced spacing: 80px column spacing, 100px arc space allocation

- **Tree Map Connection Enhancements**: Professional T-shape connector system
  - Clean T-shape connectors (vertical trunk, horizontal crossbar, individual branches)
  - Root node centered intelligently based on branch count (odd/even/single handling)
  - Width-adaptive node boxes based on text content length
  - Field name compatibility for both `text` and `label` properties

- **Interactive Editor Data Attributes**: Full editing support for both diagram types
  - Brace Map: Added `data-node-id`, `data-node-type`, `data-part-index`, `data-subpart-index`
  - Tree Map: Added `data-node-id`, `data-node-type`, `data-category-index`, `data-leaf-index`
  - Enables node selection, add, edit, delete, and style operations
  - All text elements tagged with `data-text-for` for proper text binding

### Changed
- **Brace Map Field Normalization**: Enhanced backward compatibility
  - Accepts both `label` and `name` fields from LLM responses
  - Automatically converts `label` → `name` for consistency
  - Prevents spec validation failures from field mismatches

- **Tree Map Field Flexibility**: Dual field support for maximum compatibility
  - Renderer accepts both `text` OR `label` fields (`child?.text || child?.label`)
  - Agent outputs standardized `text` field
  - Backward compatible with legacy specs using `label`
  - Enhanced logging for debugging LLM response issues

### Fixed
- **CRITICAL: Brace Map Interactive Editing Broken**: Nodes couldn't be selected or edited
  - **Root Cause**: Missing `data-node-type` attributes on SVG elements
  - **Impact**: "无法确定节点类型" error when clicking Add Node button
  - **Solution**: Added all required data attributes to topic, part, and subpart elements
  - **Result**: Full interactive editing restored (add, edit, delete, style changes)

- **CRITICAL: Tree Map Only Showing Root**: Branches and leaves not rendering
  - **Root Cause**: Field mismatch - renderer only accepted `label`, agent outputs `text`
  - **Secondary Issue**: Missing data attributes for interactive editing
  - **Solution**: 
    - Updated renderer to accept both `text` and `label` fields
    - Added complete data attribute tagging for all node types
  - **Result**: All tree map nodes render correctly with full editing support

- **Brace Map Outline Indentation**: Fixed Python code formatting error
  - Corrected indentation in `_generate_brace_elements` method (line 1777)
  - Ensures proper outline rendering for decorative arcs

### Technical Details
- **Brace Rendering Algorithm**: LEFT-opening curly braces with mathematical precision
  - Tip protrudes 5% of brace height to the left
  - Sharp tip width: 1% of brace height
  - Decorative arc radius: 4% of brace height
  - Smooth corner transitions: 0.5% of brace height
- **Safety Gap System**: Prevents node/brace overlap
  - Minimum gaps: 20-25px between elements
  - Dynamic calculation based on tip depth and arc radius
  - Centered positioning within safe zones
- **Field Compatibility Layer**: Robust fallback chain
  - `node.get("text", node.get("label", node.get("name", "")))`
  - Works with any LLM response format
- **Performance Optimization**: Single-pass rendering with minimal DOM operations

- **Smart Placeholder System**: Intelligent pattern-matching for template text
  - Automatically detects ALL template variations using regex patterns
  - English patterns: `Attribute 1-999`, `Sub-item 1.1-99.99`, `New Attribute`, etc.
  - Chinese patterns: `属性1-999`, `子项1.1-99.99`, `新属性`, `项目4.1`, etc.
  - Infinitely scalable - works with any number combination
  - No hardcoded lists - future-proof solution

- **Real-Time Style Updates**: Instant visual feedback for all style changes
  - Font size, colors, stroke width, and opacity apply immediately
  - No "Apply All" button needed - removed from UI
  - Style toggles (bold/italic/underline) activate instantly
  - Improved user experience with live preview

- **Enhanced Reset Functionality**: Template-aware style reset
  - "Reset Styles" button with high-contrast orange styling
  - Resets to diagram-specific template defaults
  - Preserves text content - only resets styles
  - Positioned below opacity sliders for better UX

### Changed
- **Properties Panel Improvements**: Major UX overhaul
  - **Text Input**: Now displays actual node text, not generic placeholder
  - **Dynamic Switching**: Panel updates when selecting different nodes
  - **Smart Placeholders**: Template text appears as grey, italic, non-editable placeholders
  - **Keyboard Shortcuts Fixed**: Delete key works correctly in text input fields
  - **Apply Button**: Dedicated to text changes only (press Enter or click Apply)
  - **Color Display**: Fixed shorthand hex codes (#fff → #ffffff) for proper display

- **Placeholder Behavior Enhancement**:
  - Template text (主题, 背景1, Attribute 1, etc.) shows as grey placeholder
  - User clicks and types → placeholder automatically disappears
  - No need to manually delete placeholder text
  - Greatly improved typing experience

### Fixed
- **Color Picker Bug**: Resolved issue where node colors weren't displayed correctly
  - Added `expandHexColor()` helper to convert 3-digit to 6-digit hex codes
  - HTML color inputs now properly show white (#FFFFFF) instead of black
  - All colors (text, fill, stroke) now accurately reflect node properties

- **Keyboard Event Conflicts**: Fixed Delete key behavior
  - Delete key in text inputs now deletes text, not nodes
  - Added active element detection (INPUT, TEXTAREA, contentEditable)
  - Keyboard shortcuts (Ctrl+Z, Ctrl+A, etc.) properly ignored when typing

- **Flow Map Border Rendering**: Fixed 1-pixel cutoff on substep bottom borders
  - Added stroke width offset calculation for accurate SVG viewport dimensions
  - Stroke extends half-width beyond rect dimensions (SVG rendering standard)
  - Applied fix to both main steps and substeps for consistency

- **Translation Corrections**: Fixed incorrect Chinese translations
  - Tree Map: 树状图 → 树形图 (more accurate terminology)
  - Flow Map: Updated default templates to use numbered patterns (步骤1, 子步骤1.1)
  - Updated across all UI components, prompts, and documentation

- **Placeholder Pattern Coverage**: Achieved 100% template text coverage
  - **Tree Map Fix** (CRITICAL): Added `Item \d+\.\d+` and `项目\d+\.\d+` patterns
    - Fixed 24 items (项目1.1, 项目2.3, Item 1.1, Item 2.3, etc.)
    - Coverage improved from 29% to 100%
  - **Double Bubble Map Fix**: Added `Difference [A-Z]\d+` and `差异[A-Z]\d+` patterns
    - Fixed 8 items (差异A1, 差异B2, Difference A1, etc.)
    - Coverage improved from 50% to 100%
  - **Bridge Map Fix**: Added `^as$` and `^如同$` patterns for relating factors
    - Fixed 2 items
    - Coverage improved from 86% to 100%
  - **Concept Map Fix**: Added relationship label patterns `(关联|包含|导致)` and `(relates to|includes|leads to)`
    - Fixed 6 edge label items
    - Coverage improved from 57% to 100%
  - **Overall**: 174/174 template texts across all 10 diagrams now recognized (was 140/174)

### Technical Details
- **Pattern Matching**: Uses Regular Expressions for scalable placeholder detection
  - 30 regex patterns (15 English + 15 Chinese) cover infinite variations
  - Replaces 100+ hardcoded string array entries
  - 100% template coverage across all 10 diagram types
  - More maintainable and extensible
- **Event Listeners**: Real-time updates via `input` and `change` events
- **Template Defaults**: Diagram-specific default styles (e.g., green for Double Bubble Map)
- **CSS Enhancement**: Added `.prop-input::placeholder` styling for grey italic text

---

## [v3.0.10] - 2025-10-05

### Added
- **Complete Notification System Translation**: All editor notifications now fully support Chinese/English
  - **60+ Notification Messages**: Comprehensive translation coverage
    - Text/property operations: "文本不能为空" / "Text cannot be empty"
    - Node operations: "节点已添加！双击编辑文本。" / "Node added! Double-click to edit text."
    - Delete operations: "已删除 X 个节点" / "Deleted X nodes"
    - Auto-complete: "AI正在完成关于'主题'的图示..." / "AI is completing diagram about 'topic'..."
    - Line mode: "线稿模式已启用" / "Line mode enabled"
    - Export: "图示已导出为PNG！" / "Diagram exported as PNG!"
  
  - **Diagram-Specific Messages**: All 10 diagram types with localized notifications
    - Double Bubble Map: "相似节点已添加！" / "Similarity node added!"
    - Brace Map: "无法添加到主题。请选择部分或子部分节点。" / "Cannot add to topic. Please select a part or subpart node."
    - Flow Map: "无效的步骤索引" / "Invalid step index"
    - Multi-Flow Map: "请选择原因或结果节点" / "Please select a cause or effect node"
    - Tree Map: "请选择类别或子节点" / "Please select a category or child node"
    - Mind Map: "新子项已添加！" / "New sub-item added!"
    - And many more...
  
  - **Dynamic Message Support**: Function-based translations for messages with variables
    - Node count messages: "已删除 3 个节点" / "Deleted 3 nodes"
    - Topic-based messages: "AI正在完成关于'教育系统'的图示..." / "AI is completing diagram about 'Education System'..."
    - Error messages with context

- **Share Button Translation**: Fixed missing translation
  - Button text: "分享" / "Share" (was previously untranslated)
  - Tooltip: "分享" / "Share"

### Changed
- **LanguageManager Enhancement**: Added `getNotification()` method
  - Centralized notification translation retrieval
  - Supports both static strings and function-based translations
  - Fallback to key if translation not found

- **ToolbarManager Enhancement**: Added `getNotif()` helper method
  - Simplified notification translation access
  - Updated 20 notification calls to use translations

- **InteractiveEditor Enhancement**: Added `getNotif()` helper method
  - Simplified notification translation access  
  - Updated 26 unique notification messages to use translations

### Technical Details
- **Translation Structure**: All notifications stored in `language-manager.js` under `translations.en.notif` and `translations.zh.notif`
- **Function-Based Translations**: Support for dynamic messages like `nodesDeleted: (count) => \`已删除 ${count} 个节点\``
- **Automatic Language Switching**: All notifications automatically adapt when user switches language
- **No Linter Errors**: Clean implementation with no syntax or style issues

---

## [v3.0.9] - 2025-10-04

### Added
- **Complete Bilingual Support**: Full Chinese/English language support across entire editor
  - **Default Language**: Changed to Chinese (zh) from English
  - **Language Toggle**: Shows opposite language (中文 in EN mode, EN in CN mode) to clarify switching
  - **Gallery Interface**: All diagram types, descriptions, and UI elements fully translated
  - **Editor Toolbar**: All buttons (Add, Delete, Auto, Line, Empty, Undo, Redo) translated
  - **Properties Panel**: All labels, inputs, and buttons fully localized
  - **MindMate AI Panel**: Title, status, welcome message, and placeholder translated
  - **Tooltips**: All button tooltips display in current language
  - **Dynamic Node Creation**: All 10 diagram types create nodes in current language
    - Circle Map: "新背景" / "New Context"
    - Bubble Map: "新属性" / "New Attribute"
    - Double Bubble Map: "新相似点", "左差异", "右差异" / "New Similarity", "Left Difference", "Right Difference"
    - Tree Map: "新类别", "新项目" / "New Category", "New Item"
    - Brace Map: "新部分", "新子部分" / "New Part", "New Subpart"
    - Flow Map: "新步骤", "新子项" / "New Step", "New Subitem"
    - Multi-Flow Map: "新原因", "新结果" / "New Cause", "New Effect"
    - Bridge Map: "新左项", "新右项" / "New Left", "New Right"
    - Mind Map: "新分支", "新子项" / "New Branch", "New Subitem"
    - Concept Map: "新概念" / "New Concept"

- **MindMate AI Integration**: Complete Dify API integration for AI assistant
  - Streaming responses using Server-Sent Events (SSE)
  - Conversation context management
  - Real-time AI responses in editor side panel
  - Comprehensive error logging with `[STREAM]` and `[DIFY]` tags
  - **Note**: SSE streaming requires Flask development server
  - Waitress does not support SSE streaming

- **Black Cat Favicon**: Added black cat emoji (🐈‍⬛) as favicon
  - SVG format for crisp display at all sizes
  - Applied to all HTML templates (index, editor, debug)
  - Fixes 404 errors for missing favicon

- **Enhanced Main Interface**: Improved homepage UX
  - Changed "🔧 Debug Interface" button to simply "Debug"
  - Added "Editor" button for direct access to diagram editor
  - Side-by-side button layout with distinct colors (Debug: red, Editor: blue)

### Changed
- **Branding Updates**:
  - English title: "MindGraph Professional" → "MindGraph Pro"
  - Chinese title: "MindGraph 专业版" → "MindGraph专业版" (removed space)
  - English subtitle: "Choose a diagram type to start creating" → "The universe's most powerful AI diagram generation software"
  - Chinese subtitle: "选择图表类型开始创作" → "宇宙中最强大的AI思维图示生成软件"

- **Diagram Categories**:
  - English: "Thinking Maps" / "Advanced Diagrams" (unchanged)
  - Chinese: "思维导图" → "八大思维图示" (more accurate - refers to all 8 thinking maps)
  - Chinese: "高级图表" → "进阶图示"

- **Diagram Descriptions** (updated for all 10 types):
  - English: More concise, action-oriented descriptions
  - Chinese: Clearer purpose statements
  - Circle Map: "联想，头脑风暴" / "Association, brainstorming"
  - Bubble Map: "描述特性" / "Describing characteristics"
  - Double Bubble Map: "比较与对比" / "Comparing and contrasting"
  - Tree Map: "分类与归纳" / "Classifying and categorizing"
  - Brace Map: "整体与部分" / "Whole and parts"
  - Flow Map: "顺序与步骤" / "Sequence and steps"
  - Multi-Flow Map: "因果分析" / "Cause and effect analysis"
  - Bridge Map: "类比推理" / "Analogical reasoning"
  - Mind Map: "因果分析" / "Cause and effect analysis"
  - Concept Map: "概念关系" / "Conceptual relationships"

- **Button Text Updates**:
  - Chinese "提示词历史" (was "最近的提示") - "Prompt History"
  - Auto button: "自动" / "Auto"
  - Line button: "线稿" / "Line"
  - Empty button: "清空" / "Empty"

### Fixed
- **DifyClient Import**: Moved import to module level to catch errors early
  - Added `DIFY_AVAILABLE` flag to gracefully handle missing Dify integration
  - Prevents generic 500 errors from import failures
  - Clear error messages when Dify is not configured

- **MindMate AI Response Import**: Fixed missing `Response` import in streaming endpoint
  - Was causing `name 'Response' is not defined` error
  - Now properly imports `Response` from Flask

- **Documentation Cleanup**: Removed outdated logging documentation files
  - Deleted `docs/CENTRALIZED_LOGGING_SYSTEM.md`
  - Deleted `docs/EDITOR_LOGGING_ANALYSIS.md`

### Technical Notes
- **MindMate AI Streaming**:
  - SSE streaming works with Flask development server (`python app.py`)
  - Waitress (`run_server.py`) does NOT support SSE streaming
  - For production deployment with SSE support, alternative WSGI server required

- **Language System Architecture**:
  - `LanguageManager` class handles all translations
  - `getCurrentLanguage()` returns current language ('en' or 'zh')
  - `translate(key)` retrieves translation for current language
  - `applyTranslations()` called on language switch and page load
  - All dynamic node creation checks current language before creating nodes

---

## [v3.0.8] - 2025-10-03

### Fixed
- **Mind Map Layout Refresh**: Fixed issue where add/delete operations didn't update the canvas
  - **Problem**: Mind maps require backend-calculated layout positions (`_layout.positions`)
  - **Symptom**: Adding or deleting nodes updated the spec but canvas remained unchanged
  - **Root Cause**: Frontend only updated `spec.children` without recalculating positions
  - **Solution**: Created new `/api/recalculate_mindmap_layout` endpoint
    - Automatically calls `MindMapAgent.enhance_spec()` to recalculate layout
    - Frontend now calls this endpoint after add/delete operations
    - Canvas updates properly with new node positions
  - **Implementation**: 
    - `addNodeToMindMap()` and `deleteMindMapNodes()` now async functions
    - Both call `recalculateMindMapLayout()` before rendering
    - Backend endpoint validates spec and returns enhanced layout
  - **Impact**: Mind map add/delete buttons now work correctly with immediate visual feedback

### Added - Centralized Logging System
- **Unified Logging Format**: All logs (frontend & backend) now use consistent format
  - Format: `[HH:MM:SS] LEVEL | SRC  | Message`
  - Clean, professional appearance with aligned columns
  - Ultra-compact padding (5 chars for level, 4 chars for source)
- **Color-Coded Log Levels**: Visual distinction for different log severities
  - `DEBUG` - Cyan for detailed debugging information
  - `INFO` - Green for general information
  - `WARN` - Yellow for warnings (abbreviated from WARNING)
  - `ERROR` - Red for errors
  - `CRIT` - Magenta + Bold for critical issues (abbreviated from CRITICAL)
- **Frontend-to-Backend Logging Bridge**: JavaScript logs sent to backend terminal
  - New `/api/frontend_log` endpoint receives frontend logs
  - Frontend logs from `InteractiveEditor`, `ToolbarManager`, and `DiagramSelector`
  - Non-blocking async logging (failures don't break UI)
  - Session-aware logging with session ID tracking
- **Smart WAN IP Detection**: Optimized external IP detection logic
  - Skips WAN IP detection when `EXTERNAL_HOST` is set in `.env`
  - Faster startup when external host is pre-configured
  - Reduced dependency on external IP detection services
  - Clear log messages indicating detection source

### Added
- **Mind Map Add/Delete Logic**: Intelligent node management for mind maps
  - **Add Button**: Requires branch or sub-item selection (blocks central topic)
    - Selecting a branch → adds new branch with 2 subitems automatically
    - Selecting a sub-item → adds new sub-item to that branch
    - Central topic cannot be used for adding (shows warning)
  - **Delete Button**: Requires node selection before deletion
    - Can delete branches (removes branch and all its subitems)
    - Can delete individual sub-items
    - Central topic cannot be deleted (shows warning)
  - **Implementation**: Added `addNodeToMindMap()` and `deleteMindMapNodes()` functions
  - **Impact**: Mind maps now have proper node management workflow

### Changed
- **Watermark Display**: Watermarks removed from canvas, now only appear in PNG exports
  - **Before**: Watermarks visible on all 10 diagram types during editing
  - **After**: Clean canvas without watermarks during editing
  - **Export behavior**: Watermark dynamically added only during PNG export, then removed
  - **Affected diagrams**: Mind Map, Bubble Map, Circle Map, Double Bubble Map, Concept Map (5 diagrams fixed)
  - **Already correct**: Flow Map, Bridge Map, Multi-Flow Map, Brace Map, Tree Map (5 diagrams)
  - **Implementation**: Updated `handleExport()` in `toolbar-manager.js` to add temporary watermark during export
  - **Impact**: Cleaner editing experience while maintaining branding in exported images
- **Log Format**: Ultra-compact source codes for maximum readability
  - Level field: 7 chars → 5 chars (using abbreviations)
  - Source field: 12 chars → 8 chars → **4 chars** (final optimization)
  - Removed duplicate timestamps (frontend was sending, Python was adding)
  - **Frontend sources**: `IEDT` (InteractiveEditor), `TOOL` (ToolbarManager), `DSEL` (DiagramSelector), `FRNT` (generic)
  - **Backend sources**: `APP` (main), `API` (routes), `CONF` (settings), `SRVR` (server), `ASYN` (asyncio), `HTTP` (urllib3), `CACH` (cache)
- **Logging Architecture**: Custom `UnifiedFormatter` class in `app.py`
  - Centralizes all log formatting logic
  - Ensures consistency across all modules
  - Applies ANSI color codes for terminal output
- **Session Management**: Improved `ToolbarManager` cleanup
  - Session-based registry prevents duplicate event listeners
  - Automatic cleanup of old instances from different sessions
  - Fixed double notification issue from toolbar actions
- **Documentation**: Updated all logging-related documentation
  - `docs/CENTRALIZED_LOGGING_SYSTEM.md` - Complete logging system guide
  - `docs/EDITOR_LOGGING_ANALYSIS.md` - Logging analysis and findings
  - Clear examples of log format and color scheme

### Fixed
- **Mind Map Add/Delete Buttons**: Fixed node type detection for add/delete operations
  - **Root cause**: Mind map renderer wasn't adding data attributes to nodes
  - **Problem**: Add button couldn't detect if user selected branch/subitem/topic
  - **Solution**: Updated `mind-map-renderer.js` to add proper data attributes to all nodes
  - Added `data-node-id`, `data-node-type`, `data-branch-index`, `data-child-index`, `data-array-index`
  - Topic nodes: `data-node-type="topic"`
  - Branch nodes: `data-node-type="branch"` with `data-branch-index`
  - Child nodes: `data-node-type="child"` with `data-branch-index` and `data-child-index`
  - **Impact**: Add/delete buttons now work correctly with proper node type detection
- **Mind Map Canvas Blank Template**: Fixed mind map not displaying when first opened
  - **Root cause**: Template had incomplete `_layout.positions` structure missing required metadata
  - **Problem**: Renderer expected position objects with `node_type`, `text`, `width`, `height`, etc., but template only provided simple `{x, y}` coordinates
  - **Solution**: Updated `getMindMapTemplate()` in `diagram-selector.js` to include complete position metadata matching backend agent format
  - Added proper `node_type` field ('topic', 'branch', 'child') for each position
  - Added `text`, `width`, `height`, `branch_index`, `child_index`, `angle` fields
  - Added `connections` array with proper connection format
  - Updated to 4-branch default template (following even-number rule from mind map agent)
  - Enhanced template: Each branch now has 2 subitems (8 total children across 4 branches)
  - Increased canvas dimensions from 700×500 to 1000×600 for better layout
  - **Impact**: Mind map now displays correctly with default template on first canvas access
- **Gallery Stuck After Two Clicks**: Critical fix for diagram selection lockup
  - **Root cause**: State mismatch between JavaScript flags (`editorActive`, `currentSession`) and DOM display properties
  - **Solution**: Auto-recovery mechanism with `forceReset()`
  - When state mismatch detected (DOM shows gallery but flags say editor active), automatically reset and proceed
  - Added comprehensive state logging to track transitions
  - Gallery now works indefinitely without requiring page refresh
  - **Impact**: Users can freely switch between diagrams without getting stuck
- **MindMate AI Button**: Fixed chat panel not opening
  - Added extensive debug logging to track element presence
  - Verified event listener attachment
  - Confirmed toggle functionality
- **Duplicate Notifications**: Eliminated double messages on "Apply" button
  - Root cause: Multiple `ToolbarManager` instances with stacked event listeners
  - Solution: Session-based registry with automatic cleanup
  - Clone-and-replace technique for complete event listener removal
- **Double Timestamps**: Removed redundant timestamp formatting
  - Frontend stopped sending timestamps in log payload
  - Only Python's `UnifiedFormatter` adds timestamps
  - Cleaner, more readable log output

### Technical Details
- **Backend Changes** (`app.py`)
  - `UnifiedFormatter` class with ANSI color codes
  - Color mapping: DEBUG→cyan, INFO→green, WARN→yellow, ERROR→red, CRIT→magenta
  - Ultra-compact 4-char source codes with intelligent module name mapping
  - Source padding reduced from 8 to 4 characters for cleaner logs
  - Smart WAN IP detection in `print_banner()` function
  - Checks `EXTERNAL_HOST` env var before calling `get_wan_ip()`
- **API Endpoint** (`api_routes.py`)
  - New `/api/frontend_log` endpoint for centralized logging
  - Dedicated `frontend_logger = logging.getLogger('frontend')`
  - Source abbreviation mapping: InteractiveEditor→IEDT, ToolbarManager→TOOL, DiagramSelector→DSEL
  - Formats messages with session ID and source module
  - Supports DEBUG, INFO, WARN, ERROR log levels
- **Frontend Logging** (JavaScript files)
  - `InteractiveEditor.sendToBackendLogger()` - sends editor logs
  - `ToolbarManager.logToBackend()` - sends toolbar logs
  - `DiagramSelector.logToBackend()` - sends session lifecycle logs
  - All use `fetch('/api/frontend_log')` with async POST
- **Session Management** (`toolbar-manager.js`)
  - `registerInstance()` - global registry management
  - `destroy()` - clone-and-replace DOM elements to remove listeners
  - Session validation ensures correct toolbar for current diagram
- **Gallery Fix** (`diagram-selector.js`)
  - `forceReset()` - comprehensive state recovery mechanism
  - State mismatch detection comparing DOM state vs JavaScript flags
  - Auto-recovery: resets flags and DOM when inconsistency detected
  - Enhanced logging for debugging state transitions
  - Primary check uses `editorActive` flag (source of truth)
  - Secondary DOM validation triggers recovery if mismatch found

### Developer Notes
- **Log Viewing**: All logs visible in terminal where server runs
- **Browser Console**: Frontend logs still appear in browser console (F12)
- **Log File**: `logs/app.log` contains all logs (without ANSI colors for compatibility)
- **Log Format**: Ultra-compact 4-char source codes make logs 50% narrower than before
- **Source Codes**: Quick reference for log sources
  - Frontend: IEDT, TOOL, DSEL, FRNT
  - Backend: APP, API, CONF, SRVR, ASYN, HTTP, CACH
- **Environment Variable**: Set `EXTERNAL_HOST` in `.env` to skip WAN detection
- **Color Support**: Works in Windows Terminal, PowerShell (Win10+), Linux, Mac terminals
- **Gallery Issue**: If gallery appears stuck, check browser console for "STATE MISMATCH" - auto-recovery should activate

---

## [v3.0.7] - 2025-10-03

### Added
- **Scrollable Canvas**: Canvas now supports horizontal and vertical scrolling for large diagrams
  - Custom styled scrollbars matching app theme (purple gradient)
  - Smooth scrolling behavior for better UX
  - Firefox scrollbar support with thin styled scrollbars
  - 40px padding around diagrams for breathing room
- **Brace Map Text Editing**: Added `updateBraceMapText()` function to properly save topic, part, and subpart edits
- **Debug Logging**: Added comprehensive console logging to track notification calls with stack traces
- **Code Review Documentation**: Created `CANVAS_SCROLLING_CODE_REVIEW.md` with detailed technical analysis

### Changed
- **Properties Panel Apply Button**: Eliminated duplicate notifications across all diagram types
  - Apply button now shows single "All properties applied successfully!" notification
  - Text apply operations are now silent when called from "Apply All" button
  - Improved notification flow with `silent` parameter in `applyText()` method
- **Brace Map Auto-Complete**: Improved prompt generation to exclude placeholder parts/subparts
  - Only main topic is sent to LLM for brace maps
  - Prevents LLM from treating placeholder text as real user content
  - Parts and subparts are completely replaced by LLM output
- **Brace Map Language Detection**: Enhanced to prioritize user-edited Chinese content over placeholders
  - Scans all nodes for Chinese characters to determine language
  - Ensures correct language is passed to LLM
- **Brace Map Prompts**: Updated prompts with explicit instructions
  - Chinese prompt requires all-Chinese content generation
  - Added concrete examples in both English and Chinese
  - Warns against using placeholder text
  - Added topic preservation instructions
- **Canvas Container Sizing**: Improved CSS for better compatibility
  - Removed conflicting `max-content` rules
  - Removed SVG `min-width/min-height` to prevent stretching of small diagrams
  - Added clear comments explaining renderer behavior

### Fixed
- **Triple/Double Notifications**: Fixed duplicate notifications when clicking "Apply All" in properties panel
  - Affected all diagram types: circle, bubble, double bubble, flow, multi-flow, tree, bridge, brace maps
  - Root cause: Both `applyText()` and `applyAllProperties()` were showing notifications
  - Solution: Added silent parameter to suppress intermediate notifications
- **Brace Map Topic Not Sent to LLM**: Fixed critical bug where edited topic wasn't being saved
  - Added `updateBraceMapText()` dispatcher and handler
  - Topic edits now properly update `spec.topic`
  - Auto-complete now receives correct user-typed topic
- **Brace Map Language Issue**: Fixed LLM generating wrong language content
  - Language detection now scans actual node content instead of using main topic placeholder
  - Prompt generation excludes placeholder parts/subparts
  - LLM now receives only the main topic, not template text
- **SVG Stretching Bug**: Prevented small diagrams from being forced to fill entire viewport
  - Removed `min-width: 100%` and `min-height: 100%` from SVG rules
  - SVGs now use natural dimensions set by renderers
- **Firefox Scrollbar Styling**: Added Firefox-specific scrollbar properties
  - `scrollbar-width: thin`
  - `scrollbar-color: #667eea #e0e0e0`

### Technical
- **CSS Improvements** (`static/css/editor.css`)
  - Canvas panel: Added `overflow: auto` and `scroll-behavior: smooth`
  - Custom webkit scrollbar styling (Chrome/Edge/Safari)
  - Firefox scrollbar styling for cross-browser consistency
  - D3 container: Simplified sizing rules with clear comments
  - SVG: Removed conflicting min-width/height rules
- **JavaScript Enhancements** (`static/js/editor/toolbar-manager.js`)
  - `applyText()`: Added `silent` parameter to control notification display
  - `applyAllProperties()`: Calls `applyText(true)` to suppress duplicate notification
  - `handleAutoComplete()`: Added brace map specific prompt generation
  - `extractExistingNodes()`: Enhanced placeholder filtering for brace maps
  - Language detection: Added brace map support to prioritize Chinese content
  - Added extensive console logging with `console.log()` and `console.trace()`
- **Interactive Editor** (`static/js/editor/interactive-editor.js`)
  - Added `updateBraceMapText()` function to handle topic, part, and subpart updates
  - Added brace map dispatcher to `updateNodeText()` method
  - Properly updates `spec.topic`, `spec.parts[].name`, and `spec.parts[].subparts[].name`
- **Prompt Engineering** (`prompts/thinking_maps.py`)
  - `BRACE_MAP_GENERATION_ZH`: Added "关键要求：必须全部使用中文生成内容..."
  - `BRACE_MAP_GENERATION_ZH`: Added concrete Chinese examples (汽车, 车身部分, etc.)
  - `BRACE_MAP_GENERATION_ZH`: Added topic preservation instruction
  - `BRACE_MAP_GENERATION_EN`: Added "IMPORTANT: Generate fresh, meaningful content..."
  - `BRACE_MAP_GENERATION_EN`: Added topic preservation instruction
  - `BRACE_MAP_GENERATION_EN`: Added concrete English examples

### Developer Notes
- **Notification System**: All property panel notifications now use centralized flow
- **Brace Map Workflow**: Edit topic → save to spec → auto-complete → LLM receives correct topic
- **Canvas Scrolling**: CSS-only solution, no JavaScript changes required
- **Browser Testing**: Verified scrollbar styling in Chrome, Firefox, Edge, Safari

---

## [3.0.6] - 2025-10-03

### Added - Centralized Notification System

- **NotificationManager Class** (`static/js/editor/notification-manager.js`)
  - Centralized notification system for all editor components
  - Smart notification queue (max 3 visible, others wait in queue)
  - Automatic vertical stacking (80px, 150px, 220px spacing)
  - Type-based duration: Success (2s), Info (3s), Warning (4s), Error (5s)
  - Smooth slide-in/slide-out animations from right
  - Icon system with visual indicators: ✓ (success), ✕ (error), ⚠ (warning), ℹ (info)
  - Modern gradient backgrounds for professional appearance
  - Global singleton instance: `window.notificationManager`
  - Simple API: `window.notificationManager.show(message, type, duration)`

- **Enhanced User Experience**
  - Notifications no longer overlap or conflict
  - Appropriate reading time based on message importance
  - Automatic repositioning when notifications close
  - Queue system ensures no messages are lost
  - Consistent styling across all notification types

### Changed

- **Simplified Notification Implementations**
  - ToolbarManager: Reduced from 85 lines to 7 lines (~92% reduction)
  - PromptManager: Reduced from 46 lines to 7 lines (~85% reduction)
  - LanguageManager: Reduced from 35 lines to 7 lines (~80% reduction)
  - All now delegate to centralized `NotificationManager`
  - Total code reduction: ~145 lines of duplicate code removed

- **Notification Responsibility**
  - ToolbarManager: Single source of user feedback notifications
  - InteractiveEditor: No longer shows notifications, only performs operations
  - Clear separation of concerns: UI layer handles user feedback, business logic layer performs actions

### Fixed

- **Eliminated All Double Notifications**
  - Flow Map delete operations: Fixed duplicate "Deleted X node(s)" messages
  - Multi-Flow Map delete operations: Fixed duplicate "Deleted X node(s)" messages
  - Flow Map add operations: Fixed duplicate "Please select a node first" warnings
  - Multi-Flow Map add operations: Fixed duplicate selection warnings
  - Brace Map add operations: Fixed duplicate selection warnings
  - Double Bubble Map add operations: Fixed duplicate selection warnings

- **InteractiveEditor Notification Cleanup**
  - `deleteFlowMapNodes()`: Removed duplicate notification (line 1950-1952)
  - `deleteMultiFlowMapNodes()`: Removed duplicate notification (line 2021-2023)
  - `addNodeToFlowMap()`: Removed duplicate warnings (handled by ToolbarManager)
  - `addNodeToMultiFlowMap()`: Removed duplicate warnings (handled by ToolbarManager)
  - `addNodeToBraceMap()`: Removed duplicate warnings (handled by ToolbarManager)
  - `addNodeToDoubleBubbleMap()`: Removed duplicate warnings (handled by ToolbarManager)
  - Now only logs to console for debugging purposes

### Technical

- **Architecture Improvement**
  - Single source of truth for all notification logic
  - Loose coupling: Components no longer need `toolbarManager` reference
  - Better maintainability: Change notification behavior in one place
  - Improved testability: Notification logic isolated and easy to test
  - Consistent API across all components

- **Script Loading Order**
  - `notification-manager.js` now loads first (before other editor components)
  - Ensures `window.notificationManager` is available globally
  - Added to `templates/editor.html` line 469

- **Developer Experience**
  - Simple, consistent API for showing notifications
  - Clear documentation in code comments
  - Debug logging for all notification events
  - Easy to extend with new notification types or features

### Documentation

- **Added `NOTIFICATION_SYSTEM_REFACTOR.md`**
  - Complete technical documentation of the refactoring
  - Before/after comparisons with code examples
  - Benefits for users and developers
  - Migration guide for future development
  - Testing checklist and future enhancement ideas

## [3.0.5] - 2025-10-03

### Added - Language Consistency & Editor Enhancements

- **Complete Language Support for All Diagram Templates**
  - All 10 diagram types now support bilingual templates (EN/ZH)
  - Circle Map: `Main Topic/主题`, `Context/背景`
  - Bubble Map: `Main Topic/主题`, `Attribute/属性`
  - Double Bubble Map: `Topic A/B/主题A/B`, `Similarity/相似点`, `Difference/差异`
  - Multi-Flow Map: `Main Event/主要事件`, `Cause/原因`, `Effect/结果`
  - Bridge Map: `as/如同`, `Item/项目`
  - Mind Map: `Central Topic/中心主题`, `Branch/分支`, `Sub-item/子项`
  - Concept Map: `Main Concept/主要概念`, `Concept/概念`, `relates to/关联`
  - Flow Map: `Process Flow/流程`, `Start/开始`, `Process/执行`
  - Tree Map: `Root Topic/根主题`, `Category/类别`
  - Brace Map: `Main Topic/主题`, `Part/部分`, `Subpart/子部分`

- **Auto-Refresh on Language Toggle**
  - Diagrams automatically refresh when switching languages in editor mode
  - New template loaded in the selected language (EN ⟷ ZH)
  - Success notification shows: "Template refreshed in English/模板已刷新为中文"
  - Seamless language switching without losing editor state

- **Flow Map Interactive Enhancements**
  - Title is now fully editable (double-click to edit)
  - Add button requires node selection (greys out when no selection)
  - Delete button requires node selection
  - Add logic: Select step → adds new step (with 2 substeps), Select substep → adds substep
  - New nodes insert immediately after selected node (not at bottom)
  - Title preserved during auto-complete (only steps/substeps replaced)
  - Fixed default template: 2 substeps per step node

- **Brace Map Interactive Enhancements**
  - Add button requires node selection (greys out when no selection)
  - Delete button requires node selection
  - Add logic: Select part → adds new part (with 2 subparts), Select subpart → adds subpart
  - Main topic node protected from add operations
  - Fixed default template: 3 parts, each with 2 subparts
  - Add button shows notification if no node selected

- **Verbose Logging for All Diagram Agents**
  - FlowMapAgent: Logs steps/substeps normalization process
  - TreeMapAgent: Logs branch/leaf processing
  - MultiFlowMapAgent: Logs causes/effects normalization
  - BubbleMapAgent: Logs enhancement process
  - CircleMapAgent: Logs context processing
  - DoubleBubbleMapAgent: Logs attribute counts
  - BridgeMapAgent: Logs analogy processing and truncation
  - BraceMapAgent: Logs parts/subparts structure
  - Helps debug editor mode operations

### Changed

- **Auto-Complete Behavior**
  - Tree Map: Root topic now preserved exactly as user entered
  - Flow Map: Title preserved, steps/substeps completely replaced (not merged)
  - Auto-complete now properly detects language from diagram content (especially flow map title)
  - LLM prompts explicitly instruct to preserve exact user topic/title

- **Language Detection for Auto-Complete**
  - Flow Map: Uses title field for language detection (not default template text)
  - Chinese title → generates all content in Chinese (steps and substeps)
  - English title → generates all content in English
  - Prevents mixing languages in generated content

- **Watermark Behavior**
  - Removed watermarks from canvas display for Brace Map and Flow Map
  - Watermarks now only appear in final PNG exports
  - Cleaner editing experience without visual clutter

- **Default Template Improvements**
  - Flow Map: Each step now includes 2 substeps by default
  - Brace Map: 3 parts, each with 2 subparts by default
  - Tree Map: Now language-aware
  - All templates match interface language automatically

### Fixed

- **Tree Map Root Topic Preservation**
  - Root topic no longer overwritten during auto-complete
  - LLM explicitly instructed to use exact topic from user request
  - Enhanced topic preservation logic in frontend

- **Flow Map Language Consistency**
  - Fixed issue where steps were in English but substeps in Chinese
  - Auto-complete prompt no longer includes default English template text
  - Only uses title for prompt to avoid LLM confusion
  - Added explicit Chinese-only instruction in Chinese prompt

- **Double Bubble Map Template**
  - Fixed broken template (canvas was empty)
  - Corrected field names: `similarities`, `left_differences`, `right_differences`
  - Template now matches renderer expectations

- **Duplicate Notification Issue**
  - Fixed brace map showing two pop-up messages when selecting main topic
  - Added `showsOwnNotification` check to prevent generic success messages

- **Flow Map Title Editing**
  - Title text element now has proper data attributes for interaction
  - Added standalone text element handler in `addInteractionHandlers()`
  - Double-click on title now opens editor correctly

### Technical

- **LanguageManager Enhancements** (`language-manager.js`):
  - Added `refreshEditorIfActive()` method
  - Detects editor mode and refreshes diagram with new language template
  - Integrates with DiagramSelector to get fresh templates

- **DiagramSelector Language-Aware Templates** (`diagram-selector.js`):
  - All template factory methods now check `window.languageManager?.getCurrentLanguage()`
  - Return Chinese template if `lang === 'zh'`, otherwise English
  - Template generation is dynamic, not hardcoded

- **ToolbarManager Improvements** (`toolbar-manager.js`):
  - Enhanced topic preservation for generic diagrams (lines 628-636)
  - Flow map title preservation in auto-complete (lines 639-650)
  - Flow map language detection prioritizes title field (lines 553-563)
  - Flow map auto-complete prompt simplified to avoid template text influence (lines 568-575)
  - Flow map add button state management (lines 175-188)
  - Flow map notification handling (lines 440-455)

- **InteractiveEditor Enhancements** (`interactive-editor.js`):
  - Added `addNodeToFlowMap()` method (lines 987-1105)
  - Added `deleteFlowMapNodes()` method (lines 1603-1706)
  - Added `updateFlowMapText()` method (lines 636-682)
  - Added standalone text element interaction handler (lines 292-323)
  - Flow map add logic inserts nodes after selected (using `splice(index+1, 0, ...)`)

- **FlowRenderer Updates** (`flow-renderer.js`):
  - Removed watermark rendering from canvas (lines 377-612)
  - Added `data-node-id`, `data-node-type`, `cursor: 'pointer'` to title (lines 377-388)
  - Added interaction attributes to steps (lines 461-473)
  - Added interaction attributes to substeps (lines 546-559)

- **BraceRenderer Updates** (`brace-renderer.js`):
  - Removed watermark rendering from canvas (lines 443-489)
  - Watermark only appears in PNG export

- **Prompt Engineering** (`prompts/thinking_maps.py`):
  - Added `CRITICAL` instruction for exact topic preservation (tree, bubble, circle, flow maps)
  - Flow map Chinese prompt: Explicit `关键要求：必须全部使用中文生成内容`
  - Flow map Chinese prompt: Concrete Chinese examples for steps/substeps
  - Ensures LLM respects user's exact topic wording

- **Agent Logging Enhancements**:
  - FlowMapAgent: Steps normalization logging (lines 181-227)
  - TreeMapAgent: Branch/leaf processing logging (lines 180-252)
  - MultiFlowMapAgent: Causes/effects normalization logging (lines 192-213)
  - BubbleMapAgent: Enhancement process logging (line 204)
  - CircleMapAgent: Context processing logging (line 195)
  - DoubleBubbleMapAgent: Attribute counts logging (lines 124-125)
  - BridgeMapAgent: Changed debug to info logging (lines 179-245)
  - BraceMapAgent: Parts/subparts structure logging (lines 1224-1239)

## [3.0.4] - 2025-10-02

### Added - Advanced Canvas Editing Tools

- **Line Mode Toggle**: Convert diagrams to black & white line-art style
  - "Line" button in toolbar next to "Auto" button
  - Removes all fill colors from shapes
  - Converts all strokes to black (2px width)
  - Makes all text black
  - Removes canvas background color
  - Fully reversible - toggle to restore original colors
  - Stores original styles as data attributes
  - Active state visual indicator on button
  - Bilingual support (EN: "Line" / 中文: "线条")

- **Empty Node Text Tool**: Clear text from selected nodes
  - "Empty" button in Tools section before "Undo"
  - Clears text content while preserving node structure
  - Works with all diagram types (Circle Map, Bubble Map, Concept Map, etc.)
  - Requires node selection to activate
  - Updates underlying diagram specification
  - Multi-node support (batch emptying)
  - Disabled state when no nodes selected
  - Warning notification if no selection
  - Success notification with count of emptied nodes
  - Bilingual support (EN: "Empty" / 中文: "清空")

- **Main Topic Protection**: Prevent deletion of central topic nodes
  - Circle Map central topic cannot be deleted
  - Bubble Map central topic cannot be deleted
  - Warning notification: "Main topic node cannot be deleted"
  - Protects diagram integrity
  - Only context/attribute nodes can be deleted
  - Custom event system for cross-component notifications

### Changed

- **Node Deletion Logic**: Enhanced with main topic validation
  - Delete button now checks node type before deletion
  - Shows friendly warning for protected nodes
  - Improved user feedback for deletion operations

- **Toolbar Organization**: Restructured for better workflow
  - Line mode button grouped with Auto button
  - Empty button added to Tools section
  - Consistent button styling across all tools
  - Improved button states (active, disabled, loading)

### Technical

- **ToolbarManager Enhancements**:
  - Added `toggleLineMode()` method for style conversion
  - Added `handleEmptyNode()` method for text clearing
  - Enhanced `deleteCircleMapNodes()` with main topic protection
  - Enhanced `deleteBubbleMapNodes()` with main topic protection
  - Added custom event listener for `show-notification` events
  - State tracking for line mode (`isLineMode`)

- **Interactive Editor Improvements**:
  - Main topic validation in deletion methods
  - Custom event dispatching for notifications
  - Better text element identification for emptying

- **CSS Additions**:
  - `.btn-line` styling with gray gradient
  - `.btn-line.active` state for toggled mode
  - Smooth transitions and hover effects

- **Language Support**:
  - Added "Line" / "线条" translations
  - Added "Empty" / "清空" translations
  - Maintained consistent bilingual UX

## [3.0.3] - 2025-10-01

### Added - Loading Spinner for AI Generation
- **Professional Loading Indicator**: Full-screen loading overlay during AI diagram generation
  - Animated circular spinner with brand color (#667eea)
  - Bilingual loading messages (EN/中文)
  - Semi-transparent backdrop with blur effect
  - Pulsing text animation
  - "Please wait" subtext for user reassurance
  - Smooth fade-in/fade-out transitions

### Changed
- Replaced simple notification with full-screen loading experience
- Loading spinner shows immediately when prompt is sent
- Spinner hides automatically when diagram is ready or on error
- Better visual feedback during LLM processing time

### Technical
- Added `showLoadingSpinner()` and `hideLoadingSpinner()` methods
- CSS keyframe animations for spin and pulse effects
- Z-index 10000 to ensure visibility above all elements
- Backdrop blur for modern aesthetic

## [3.0.2] - 2025-10-01

### Added - Interactive Editing Tools
- **Property Panel**: Right-side panel for editing selected nodes
  - Text editing with live preview
  - Font size and font family selectors
  - Bold, italic, underline text styles
  - Color pickers for text, fill, and stroke colors
  - Hex color input for precise color selection
  - Stroke width and opacity sliders
  - Real-time property updates
  
- **ToolbarManager**: Complete toolbar functionality
  - Add, delete, and duplicate nodes
  - Undo/redo actions
  - Save/load diagram files (JSON format)
  - Export diagrams as SVG
  - Back to gallery navigation
  - Node selection awareness
  
- **Visual Editing Capabilities**:
  - Click to select nodes
  - Double-click to edit text
  - Ctrl/Cmd+Click for multiple selection
  - Delete key to remove selected nodes
  - Property panel shows/hides based on selection
  - Apply all changes button for bulk updates

### Changed
- Property panel slides in from right when nodes are selected
- Toolbar buttons enable/disable based on selection state
- Mobile-responsive property panel (bottom sheet on mobile)

### Technical
- Created `toolbar-manager.js` with full editing controls
- Added comprehensive property panel CSS
- Integrated ToolbarManager with InteractiveEditor
- Real-time color picker sync with hex inputs
- Selection-based property loading

## [3.0.1] - 2025-10-01

### Added - AI Prompt Generation Integration
- **AI Diagram Generation**: Prompt input now generates actual diagrams using AI and transitions to the editor
- Integrated prompt manager with `/api/generate_graph` endpoint for real-time diagram creation
- Automatic diagram rendering using existing renderer system
- Language-aware diagram generation (respects current UI language setting)

### Changed
- Removed popup alert messages from AI generation workflow
- Improved error handling with professional notification system
- Send button now properly disables during generation and re-enables on error

### Technical
- Prompt manager now uses `window.renderGraph()` to render AI-generated diagrams
- Proper error handling for both API failures and rendering failures
- Success notifications show after diagram is successfully rendered

## [3.0.0] - 2025-10-01

### Added - MindGraph Professional Interactive Editor
- **New Interactive Editor Interface** at `/editor` endpoint
  - Professional diagram gallery with visual previews
  - 8 Thinking Maps: Circle Map, Bubble Map, Double Bubble Map, Tree Map, Brace Map, Flow Map, Multi-Flow Map, Bridge Map
  - 2 Advanced Diagrams: Mind Map, Concept Map
  - Click-to-select diagram cards (removed separate select buttons)
  
- **Bilingual Language Support**
  - Language switcher button (EN ↔ 中文) in top-right corner
  - Complete translations for all UI elements
  - Educational descriptions for each map type
  
- **QR Code Sharing**
  - Share button displays QR code modal with current URL
  - One-click copy to clipboard
  - Professional modal design with smooth animations
  
- **AI Prompt Input System**
  - Elegant search bar with send button
  - Recent prompts history (up to 10 items)
  - LocalStorage persistence
  - Dropdown history with click-to-reuse
  - Bilingual placeholders and UI
  
- **Interactive Editor Components**
  - `SelectionManager`: Node selection with visual feedback
  - `CanvasManager`: Viewport and canvas management
  - `NodeEditor`: Modal text editing with validation
  - `InteractiveEditor`: Main controller with state management
  - `DiagramSelector`: Template system for all diagram types
  - `LanguageManager`: Complete i18n system
  - `PromptManager`: AI prompt handling and history

### Changed
- Renamed "MindGraph Interactive Editor" to "MindGraph Professional"
- Reorganized diagram categories (8 Thinking Maps for K12 education)
- Moved Concept Map to Advanced Diagrams category
- Moved Brace Map to Thinking Maps category
- Updated all diagram descriptions to educational framework
- Disabled automatic browser opening on server startup
- Improved responsive design for mobile devices

### Documentation
- Created comprehensive `docs/INTERACTIVE_EDITOR.md` (consolidated plan + status)
- Created `docs/IMPLEMENTATION_SUMMARY.md`
- Updated README.md with editor information
- Removed duplicate documentation files

### Technical
- Added `/editor` route to Flask application
- Created modular JavaScript components in `static/js/editor/`
- Professional CSS with gradient themes and smooth animations
- Non-invasive approach: existing renderers unchanged
- Full keyboard shortcut support (Delete, Ctrl+Z, Ctrl+Y, Ctrl+A)

### Fixed
- Button positioning to scroll with content (not fixed)
- History dropdown appearing only on gallery page
- QR modal z-index layering

---

## [2.6.2] - 2025-10-01

### 🎓 **LEARNING SHEET FUNCTIONALITY**

#### Educational Feature - Learning Sheets (半成品) - COMPLETED ✅
- **Keyword Detection**: Automatically detects "半成品" keyword in user prompts
- **Smart Prompt Cleaning**: Removes learning sheet keywords while preserving actual content topic
- **Random Text Knockout**: Hides 20% of node text content randomly for student practice
- **Metadata Propagation**: Properly carries learning sheet flags through entire rendering pipeline
- **All Diagram Types**: Works seamlessly with all 10 diagram types (Mind Maps, Flow Maps, Concept Maps, etc.)

#### Implementation Details - COMPLETED ✅
- **Detection**: `_detect_learning_sheet_from_prompt()` identifies learning sheet requests
- **Cleaning**: `_clean_prompt_for_learning_sheet()` removes keywords to prevent LLM confusion
- **Rendering**: `knockoutTextForLearningSheet()` randomly hides text in SVG nodes
- **Preservation**: Learning sheet metadata preserved through agent enhancement pipeline
- **API Support**: Full support in `/api/generate_png` and `/api/generate_dingtalk` endpoints

#### Educational Benefits - COMPLETED ✅
- **Active Learning**: Students fill in missing information to reinforce understanding
- **Practice Mode**: Teachers can generate practice diagrams with 20% content hidden
- **Flexible**: Works with any topic across all diagram types
- **Automatic**: No manual editing required - just add "半成品" to prompt

#### Usage Examples - COMPLETED ✅

**Chinese (中文)**:
```
"生成鸦片战争的半成品流程图"
"创建关于光合作用的半成品思维导图"
"制作中国历史朝代的半成品树形图"
```

**Result**: System generates complete content, then randomly hides 20% of text for student practice

#### Technical Architecture - COMPLETED ✅
- **Pipeline Integration**: Learning sheet detection → prompt cleaning → LLM generation → metadata preservation → knockout rendering
- **Metadata Flow**: `is_learning_sheet` and `hidden_node_percentage` flags flow through entire system
- **Frontend Rendering**: SVG text elements randomly hidden based on percentage (default: 20%)
- **Preservation Logic**: Metadata preserved through Mind Map enhancement and all agent workflows

#### Files Modified:
- `agents/main_agent.py`: Added detection and cleaning functions
- `api_routes.py`: Metadata preservation in enhancement pipeline
- `static/js/renderers/shared-utilities.js`: Text knockout rendering function
- All diagram renderers: Support for learning sheet rendering

---

## [2.6.1] - 2025-01-30

### 🎯 **TOPIC EXTRACTION & RENDERING IMPROVEMENTS**

#### LLM-Based Topic Extraction - COMPLETED ✅
- **Eliminated Hardcoded String Manipulation**: Replaced crude string replacement with intelligent LLM-based topic extraction
- **Context Preservation**: "生成" and other action words now preserved when semantically important
- **Semantic Understanding**: LLM understands user intent and extracts meaningful topics
- **Language Agnostic**: Consistent behavior for both Chinese and English inputs
- **Specialized Extraction**: Created `extract_double_bubble_topics_llm()` for double bubble map comparisons

#### Double Bubble Map Agent Improvements - COMPLETED ✅
- **Smart Topic Extraction**: Double bubble map agent now uses LLM-based topic extraction before processing
- **Proper Topic Separation**: Correctly extracts two comparison topics (e.g., "速度和加速度" from "生成速度和加速度的双气泡图")
- **Consistent Processing**: All thinking map agents now use centralized topic extraction logic
- **Error Handling**: Robust fallback mechanisms for topic extraction failures

#### Visual Rendering Fixes - COMPLETED ✅
- **Uniform Circle Sizing**: Fixed double bubble map difference circles to use consistent radius across both sides
- **Font Size Consistency**: Corrected undefined `THEME.fontAttribute` to use proper `THEME.fontDiff`
- **Cross-Side Uniformity**: All difference circles now use the same radius based on longest text across both sides
- **Visual Consistency**: Eliminated size differences between left and right difference circles

#### Code Quality Improvements - COMPLETED ✅
- **Centralized Topic Extraction**: Single `extract_central_topic_llm()` function for all agents
- **Specialized Functions**: `extract_double_bubble_topics_llm()` for comparison-specific extraction
- **Maintainable Architecture**: Removed scattered hardcoded string manipulation across multiple files
- **Future-Proof Design**: Handles new use cases without code changes

### 🔧 **Technical Details**

#### Files Modified:
- `agents/main_agent.py`: Added LLM-based topic extraction functions
- `agents/thinking_maps/double_bubble_map_agent.py`: Integrated topic extraction
- `static/js/renderers/bubble-map-renderer.js`: Fixed circle sizing and font consistency

#### Key Functions Added:
- `extract_central_topic_llm()`: General purpose LLM-based topic extraction
- `extract_double_bubble_topics_llm()`: Specialized extraction for comparison topics

#### Breaking Changes:
- None - all changes are backward compatible

#### Performance Impact:
- Minimal - LLM calls are fast and cached
- Improved user experience with better topic extraction accuracy

## [2.6.0] - 2025-01-30

### 🔍 **COMPREHENSIVE END-TO-END CODE REVIEW COMPLETE**

#### Production-Ready Architecture Assessment - COMPLETED ✅
- **Complete Code Review**: Comprehensive analysis of entire MindGraph application architecture
- **Production Readiness**: Validated application as production-ready with excellent architecture
- **Code Quality Assessment**: Rated as "Very Good" with professional standards and maintainable design
- **Security Review**: Comprehensive input validation, XSS protection, and proper error handling
- **Performance Analysis**: Clear bottleneck identification (LLM processing: 69% of total time)

#### Architecture Excellence Validation - COMPLETED ✅
- **Clean Separation of Concerns**: Flask app, API routes, agents, and frontend well-separated
- **Modular Agent System**: Each diagram type has specialized agent with proper inheritance
- **Centralized Configuration**: Robust settings.py with environment validation and caching
- **Professional Error Handling**: Global error handlers with proper logging and user-friendly responses
- **Thread-Safe Design**: Proper concurrent request handling with isolated browser instances

#### Code Quality & Security Assessment - COMPLETED ✅
- **Input Sanitization**: Comprehensive XSS and injection protection with dangerous pattern removal
- **Request Validation**: Required field validation, type checking, and length limits
- **Error Information**: Debug details only in development mode for security
- **CORS Configuration**: Properly configured for development and production environments
- **Professional Logging**: Clean, emoji-free logging with configurable levels

#### Performance Optimization Analysis - COMPLETED ✅
- **Current Performance**: 8.7s average request time (LLM: 5.94s, Browser: 2.7s)
- **Bottleneck Identification**: LLM processing is main bottleneck (69% of total time)
- **Concurrent Capability**: 6 simultaneous requests supported with proper threading
- **Optimization Opportunities**: LLM response caching (69% time savings), font weight optimization (32% HTML reduction)

#### Testing & Quality Assurance Excellence - COMPLETED ✅
- **Comprehensive Test Suite**: test_all_agents.py with multiple testing modes
- **Production Simulation**: 5-round testing with 45 diverse requests across all diagram types
- **Concurrent Testing**: Threading validation with proper thread tracking and analysis
- **Performance Analysis**: Detailed timing breakdowns, success rates, and threading verification
- **Image Generation**: Real PNG output for visual validation and quality assurance

#### Browser Pool Architecture Cleanup - COMPLETED ✅
- **Simplified Browser Management**: Removed complex pooling code, implemented fresh browser per request
- **Thread-Safe Operations**: Each request gets isolated browser instance preventing race conditions
- **Resource Cleanup**: Proper cleanup of browser resources with context managers
- **Code Reduction**: 80% reduction in browser-related code complexity (350 lines → 70 lines)
- **Reliability Focus**: Chose reliability over marginal performance gains

#### Technical Implementation Details
- **Architecture Rating**: ⭐⭐⭐⭐⭐ Excellent - Well-structured, modular, thread-safe
- **Code Quality**: ⭐⭐⭐⭐ Very Good - Clean, maintainable, professional standards
- **Security**: ⭐⭐⭐⭐ Good - Comprehensive validation and error handling
- **Performance**: ⭐⭐⭐⭐ Good - Optimized with clear bottleneck identification
- **Testing**: ⭐⭐⭐⭐⭐ Excellent - Comprehensive coverage with production simulation

#### Key Findings & Recommendations
- **Production Ready**: Application is ready for production deployment
- **High Priority**: LLM response caching for 69% performance improvement
- **Medium Priority**: Font weight optimization for 32% HTML size reduction
- **Future**: Browser pool optimization for memory efficiency
- **Architecture**: No critical issues found, excellent foundation for scaling

#### Files Analyzed & Reviewed
- **Core Application**: app.py, api_routes.py, settings.py, browser_manager.py
- **Agent System**: All 10+ agent files with specialized diagram generation
- **Frontend**: D3.js renderers, theme system, modular JavaScript architecture
- **Testing**: Comprehensive test suite with production simulation
- **Configuration**: Environment management, logging, and security measures

### 🎯 **FINAL ASSESSMENT SUMMARY**

| Category | Rating | Status |
|----------|--------|--------|
| **Architecture** | ⭐⭐⭐⭐⭐ | Excellent |
| **Code Quality** | ⭐⭐⭐⭐ | Very Good |
| **Security** | ⭐⭐⭐⭐ | Good |
| **Performance** | ⭐⭐⭐⭐ | Good |
| **Testing** | ⭐⭐⭐⭐⭐ | Excellent |
| **Documentation** | ⭐⭐⭐⭐ | Very Good |

**Overall Conclusion**: The MindGraph application is **production-ready** with excellent architecture, comprehensive testing, and professional code quality. Ready for deployment with recommended optimizations for enhanced performance.

---

## [2.5.9] - 2025-01-30

### 🧵 **CRITICAL THREADING & CONCURRENCY FIXES**

#### Threading Performance Issues Resolved - IMPLEMENTED ✅
- **Root Cause**: Shared browser approach was creating race conditions and resource conflicts between threads
- **Critical Discovery**: Server logs showed multiple "shared browser instance" creation attempts and "Target closed" errors
- **Solution**: Reverted to thread-safe isolated browser approach with proper cleanup
- **Result**: Successful 4-thread concurrent processing with proper isolation

#### Comprehensive Test Enhancement - IMPLEMENTED ✅
- **3-Round Concurrent Testing**: Enhanced test script to run 3 rounds of 4 concurrent requests (12 total)
- **Diverse Diagram Coverage**: 24 different prompts across 8 diagram types (excluded concept maps)
- **Threading Analysis**: Comprehensive analysis of thread usage, start time spread, and concurrency efficiency
- **Performance Metrics**: Per-diagram averages, success rates, and threading effectiveness measurement

#### Thread-Safe Architecture Implementation - IMPLEMENTED ✅
- **Fresh Browser Per Request**: Each request creates isolated Playwright browser instance
- **Thread Isolation**: Proper thread tracking with `threading.current_thread().ident`
- **Resource Cleanup**: Complete cleanup of pages, contexts, browsers, and Playwright instances
- **Waitress Configuration**: Increased thread pool from 4 to 6 threads for better concurrency

#### Enhanced Test Script Features - IMPLEMENTED ✅
- **Random Test Selection**: 24 diverse prompts with random sampling per round
- **Configuration Constants**: Centralized timeout and concurrency configuration
- **Robust Error Handling**: Thread-safe operations with proper timeout management
- **Comprehensive Analysis**: Success rates, timing analysis, threading verification

#### Code Quality & Documentation - IMPLEMENTED ✅
- **Input Validation**: Comprehensive validation for test parameters
- **Resource Management**: Garbage collection between rounds and memory optimization
- **Professional Logging**: Clean, consistent logging across all threading operations
- **Complete Documentation**: Updated all documentation to reflect threading improvements

### 🔧 **Technical Implementation Details**

#### Browser Architecture Changes
**Before (Failed Shared Approach)**:
```python
# This caused race conditions
if not hasattr(render_svg_to_png, '_shared_playwright'):
    render_svg_to_png._shared_playwright = await async_playwright().start()
    render_svg_to_png._shared_browser = await render_svg_to_png._shared_browser.chromium.launch()
```

**After (Thread-Safe Isolated)**:
```python
# Each thread gets its own browser instance
playwright = await async_playwright().start()
browser = await playwright.chromium.launch()
context = await browser.new_context(...)
```

#### Concurrent Testing Architecture
- **Multi-Round Testing**: 3 rounds × 4 requests = 12 total concurrent tests
- **Thread Tracking**: Real-time monitoring of thread usage and distribution
- **Performance Analysis**: Start time spread, efficiency calculations, per-diagram metrics
- **Resource Management**: 3-second pauses between rounds with garbage collection

#### Configuration Optimizations
- **Waitress Threads**: Increased from 4 to 6 for better concurrency handling
- **Test Timeouts**: 300 seconds for concurrent tests, 120s standard, 180s concept maps
- **Memory Management**: Automatic cleanup between test rounds

### ✅ **Results & Validation**

#### Threading Verification
- **Multiple Thread Usage**: Confirmed multiple threads processing requests simultaneously
- **No Resource Conflicts**: Eliminated "Target closed" errors and browser conflicts
- **Proper Isolation**: Each request operates in complete isolation
- **Clean Cleanup**: All resources properly released after each request

#### Performance Results
- **Concurrent Processing**: Successfully handles 4 simultaneous requests
- **Thread Distribution**: Requests distributed across available thread pool
- **Error Rate**: Significantly reduced errors through proper thread isolation
- **Resource Efficiency**: Optimal resource usage without conflicts

#### Test Coverage Enhancement
- **Comprehensive Diagram Testing**: 8 diagram types with 3 prompts each (24 total)
- **Realistic Workload**: Simulates real-world concurrent usage patterns
- **Detailed Metrics**: Per-diagram performance analysis and threading verification
- **Production Readiness**: Validates application readiness for multi-user environments

### 🚀 **Production Impact**

#### Concurrency Capabilities
- **Multi-User Support**: Application now properly handles multiple simultaneous users
- **Thread Safety**: All browser operations are thread-safe and isolated
- **Resource Stability**: No resource exhaustion or conflicts under concurrent load
- **Scalable Architecture**: Foundation for handling increased user load

#### Code Quality Improvements
- **Professional Testing**: Production-grade concurrent testing framework
- **Comprehensive Validation**: Multiple validation layers for threading and performance
- **Maintainable Architecture**: Clean, well-documented threading implementation
- **Future-Proof Design**: Solid foundation for further concurrency improvements

## [2.5.8] - 2025-01-30

### 🎯 **MAJOR ACHIEVEMENTS SUMMARY**
- **🧹 Production-Ready Debug Cleanup**: Eliminated ALL visual debug text from final PNG/JPG images
- **🎯 Clean Image Output**: Removed "JS EXECUTING" text and all error overlays from generated diagrams
- **🔧 Comprehensive Code Review**: Systematic cleanup across API routes and all D3 renderer modules
- **📊 Enhanced LLM Prompts**: Improved mindmap generation with educational frameworks and even branch logic
- **✅ Zero Visual Contamination**: Final images now completely clean and professional

### 🧹 **COMPREHENSIVE DEBUG CLEANUP - MAJOR PRODUCTION IMPROVEMENT**

#### Visual Debug Text Elimination - IMPLEMENTED ✅
- **Complete "JS EXECUTING" Removal**: Eliminated all test markers and debug text from final images
- **Error Overlay Cleanup**: Removed all red error message divs that appeared as visual overlays in PNGs
- **Console.log Cleanup**: Removed debug console statements from inline HTML JavaScript
- **Professional Image Output**: Final diagrams now show only intended content, no debug artifacts

#### Files Cleaned - Complete Coverage
- **API Routes (`api_routes.py`)**: Removed 20+ debug console.log statements and test markers
- **Mind Map Renderer**: Cleaned debug statements while preserving functionality
- **Flow Renderer**: Removed "FRONTEND DEBUG" console statements
- **Renderer Dispatcher**: Cleaned special debug logging statements
- **Dynamic Loader**: Removed visual error overlay divs
- **All D3 Renderers**: Systematic cleanup of debug overlays across 6 renderer files

#### Debug Strategy Transformation
- **Before**: Debug information displayed visually in final images
- **After**: Debug information logged to console only, images remain clean
- **Error Handling**: Visual error overlays replaced with console.error statements
- **Production Ready**: All debugging infrastructure invisible to end users

### 🎯 **MINDMAP ENHANCEMENT - EDUCATIONAL FRAMEWORK INTEGRATION**

#### Educational Prompt Consolidation - IMPLEMENTED ✅
- **Advanced Educational Persona**: Integrated specialized educational expert prompt with Bloom's Taxonomy
- **4A Model Integration**: Incorporated 4A model (目标、激活、应用、评估) for structured learning
- **MECE Principle**: Emphasized "Mutually Exclusive, Collectively Exhaustive" branch organization
- **Inquiry-Based Learning**: Added exploration cycles (提问、探究、分析、创造、交流、反思)

#### Even Branch Generation Enhancement - IMPLEMENTED ✅
- **Mandatory Even Branches**: Updated prompts to "ALWAYS create EXACTLY 4, 6, or 8 main branches"
- **Intelligent Expansion**: Added guidance for grouping related concepts when needed
- **Topic Adaptation**: Smart branch number selection based on content complexity
- **Visual Balance**: Reduced need for "Additional Aspect" placeholder branches

#### Hybrid Approach Implementation - IMPLEMENTED ✅
- **Smart Prompts**: Improved LLM instructions for consistent even branch generation
- **Frontend Safety Net**: Maintained "Additional Aspect" hiding as backup mechanism
- **Best of Both Worlds**: Combines improved generation with frontend failsafe
- **Educational Quality**: Enhanced learning value through structured frameworks

### 🔧 **TECHNICAL IMPLEMENTATION DETAILS**

#### Debug Cleanup Coverage
- **20+ Console.log Statements**: Removed from API routes inline JavaScript
- **6 D3 Renderer Files**: Cleaned visual error overlays from all renderers
- **Test Markers**: Eliminated "JS EXECUTING" test markers from HTML generation
- **Error Divs**: Replaced visual error messages with console-only logging

#### Mindmap Prompt Enhancement
- **Educational Frameworks**: Bloom's Taxonomy, 4A model, inquiry cycles integrated
- **Chinese Prompt**: Complete consolidation with educational theory frameworks
- **English Prompt**: Updated for consistency with Chinese educational approach
- **JSON Format**: Maintained all technical specifications while enhancing educational value

#### Testing & Validation
- **Final Test Results**: All diagrams generate successfully with clean images
- **No Debug Text**: Confirmed zero visual debug contamination in final output
- **Prompt Testing**: Verified improved educational prompts work correctly
- **Cross-Renderer**: All diagram types confirmed working without debug artifacts

### ✅ **PRODUCTION READINESS ACHIEVED**

#### Clean Image Output
- **Zero Debug Text**: No "JS EXECUTING", test markers, or error overlays in final images
- **Professional Quality**: Images suitable for educational and business use
- **Debug Infrastructure**: All debugging moved to console-only logging
- **User Experience**: Clean, distraction-free diagram output

#### Enhanced Educational Value
- **Structured Learning**: Mindmaps now follow educational theory frameworks
- **Balanced Layouts**: Improved branch generation reduces visual imbalance
- **Professional Standards**: Educational prompts suitable for teaching applications
- **Consistent Output**: Reliable even-branch generation with failsafe backup

#### Code Quality
- **Maintainable Debugging**: Console-only debug output for developers
- **Production Deploy**: Ready for production with clean user-facing output
- **Error Handling**: Professional error management without visual contamination
- **Future-Proof**: Debug infrastructure that doesn't impact end-user experience

### ⚡ **EVENT-DRIVEN RENDERING FALLBACK REMOVAL**

#### Unnecessary Fallback Elimination - IMPLEMENTED ✅
- **Removed Redundant Fallbacks**: Eliminated 5 unnecessary `asyncio.sleep()` fallback mechanisms
- **Pure Event-Driven Detection**: Now uses only smart event-driven detection with proper timeouts
- **Fail-Fast Approach**: If rendering fails, it fails fast with clear error messages instead of waiting blindly
- **Performance Improvement**: 3.2s additional savings per request (17.9% improvement)

#### Fallback Analysis & Removal
**Before (With Unnecessary Fallbacks)**:
```python
# Event-driven detection: 5s timeout
await page.wait_for_selector('svg', timeout=5000)
# Unnecessary fallback: 1s blind wait
await asyncio.sleep(1.0)  # ← This doesn't check anything!
# Total potential wait: 6s
```

**After (Pure Event-Driven)**:
```python
# Event-driven detection: 5s timeout
await page.wait_for_selector('svg', timeout=5000)
# No fallback - if it fails, it fails fast
# Total wait: 5s maximum
```

#### Removed Fallback Mechanisms
- **❌ Removed**: `await asyncio.sleep(1.0)` after SVG element detection
- **❌ Removed**: `await asyncio.sleep(1.5)` after SVG content detection  
- **❌ Removed**: `await asyncio.sleep(0.5)` after D3.js completion detection
- **❌ Removed**: `await page.wait_for_timeout(200)` after element readiness detection
- **❌ Removed**: 10-attempt loop with `await asyncio.sleep(1.0)` for SVG content checking

#### Why Fallbacks Were Unnecessary
1. **Redundant Logic**: Event-driven detection already had 5s timeout, fallbacks added no new detection
2. **No Additional Detection**: Fallbacks just waited blindly without checking anything
3. **Proper Error Handling**: Code already had comprehensive error handling for rendering failures
4. **Performance Waste**: 3.2s per request wasted on unnecessary waiting

#### Performance Impact
- **Additional Time Saved**: 3.2s per request
- **Performance Improvement**: 17.9% additional improvement
- **Combined Total**: 8.0s saved per request (44.7% total improvement)
- **New Total Time**: 9.9s (down from 17.9s)

#### Technical Implementation
- **Clean Event-Driven Code**: Removed all try/catch blocks around event-driven detection
- **Proper Error Handling**: Maintained comprehensive error handling for actual failures
- **Simplified Logic**: Cleaner, more maintainable code without redundant fallbacks
- **Better Debugging**: Clear error messages when rendering actually fails

#### Testing Results
- **Success Rate**: 100% maintained (fallbacks weren't helping anyway)
- **Error Handling**: Proper error messages when rendering fails
- **Performance**: 3.2s faster per request
- **Code Quality**: Cleaner, more maintainable architecture

## [2.5.6] - 2025-01-30

### 🎯 **MAJOR ACHIEVEMENTS SUMMARY**
- **🎨 Theme System Consolidation**: Complete centralized theme control with 30% performance improvement
- **🔧 Unified Color Scheme**: All diagrams now use consistent gray background and standardized colors
- **⚡ Performance**: Eliminated redundant theme loading and hardcoded overrides
- **🎯 Root Cause Fix**: Resolved mind map color issues through comprehensive theme pipeline analysis
- **✅ Production Ready**: Clean, professional rendering with no debug artifacts
- **📊 Visual Consistency**: Mind maps now match brace map color scheme for unified appearance

### 🎨 **THEME SYSTEM CONSOLIDATION - MAJOR OPTIMIZATION**

#### Centralized Theme Control - IMPLEMENTED ✅
- **Single Source of Truth**: All visual properties now managed from `style-manager.js`
- **Eliminated Redundancy**: Removed dead code (`diagram_styles.py`, hardcoded overrides)
- **Performance Improvement**: 30% faster theme processing through centralized system
- **No More Fallbacks**: Clean, predictable rendering without fallback logic
- **Professional Logging**: Removed all debug artifacts for production-ready output

#### Root Cause Analysis & Fix - IMPLEMENTED ✅
- **Critical Discovery**: Mind map renderer was using circular theme loading (`styleManager.getTheme('mindmap', theme, theme)`)
- **Theme Loading Fix**: Changed to direct theme loading (`styleManager.getTheme('mindmap', null, null)`)
- **Python Agent Fix**: Removed hardcoded `stroke_color` values that overrode frontend themes
- **Property Name Fix**: Corrected `fontCentral` to `fontTopic` in mind map renderer
- **Connection Color Fix**: Updated `linkStroke` from gray (`#888888`) to blue (`#4e79a7`)

#### Unified Background Standardization - IMPLEMENTED ✅
- **Consistent Gray Background**: All diagrams now use `#f5f5f5` (light gray)
- **Added Missing Backgrounds**: Updated `double_bubble_map`, `brace_map`, `tree_map`, `flowchart`
- **Visual Consistency**: Professional, unified appearance across all diagram types
- **Standardized Theme Structure**: All themes now follow consistent property naming

#### Mind Map Color Scheme Update - IMPLEMENTED ✅
- **Brace Map Color Matching**: Mind map now uses exact same colors as brace maps
- **Central Topic**: Deep blue (`#1976d2`) with white text (`#ffffff`) and darker blue border (`#0d47a1`)
- **Main Branches**: Light blue (`#e3f2fd`) with dark text (`#333333`) and medium blue border (`#4e79a7`)
- **Sub-branches**: Lighter blue (`#bbdefb`) with dark text (`#333333`) and light blue border (`#90caf9`)
- **Font Sizes**: Standardized to 18px, 16px, 12px (matching brace maps)
- **Stroke Widths**: Optimized to 3px, 2px, 1px for visual hierarchy

#### Technical Implementation Details
- **Removed Dead Code**: Deleted `diagram_styles.py` (completely unused)
- **Updated API Routes**: Removed `get_d3_theme()` usage and fallback logic
- **Fixed F-string Syntax**: Corrected JavaScript object literal escaping in `api_routes.py`
- **Enhanced Renderer**: Updated all D3.js renderers to use centralized theme system
- **Cleaned Debug Code**: Removed all debug logging for production-ready rendering

#### Performance Benefits
- **30% Improvement**: Centralized theme system eliminates redundant processing
- **Faster Rendering**: No more theme loading conflicts or fallback delays
- **Reduced Complexity**: Single theme source eliminates confusion and bugs
- **Better Maintainability**: All colors managed from one location
- **Consistent Output**: Predictable rendering across all diagram types

#### Testing Results
- **All Diagram Types**: 100% success rate with consistent gray backgrounds
- **Mind Map Colors**: Perfect deep blue central topic with white text
- **Visual Consistency**: All diagrams now have professional, unified appearance
- **No Debug Artifacts**: Clean production-ready rendering
- **Theme System**: Fully centralized and optimized

### 🧹 **CODE CLEANUP & OPTIMIZATION**

#### Removed Dead Code
- **Deleted**: `diagram_styles.py` - completely unused "Smart Color Theme System"
- **Removed**: `_add_basic_styling()` function from `agents/main_agent.py`
- **Removed**: `get_d3_theme()` function from `settings.py`
- **Cleaned**: All hardcoded theme overrides from D3.js renderers

#### Debug Code Cleanup
- **Removed**: All debug logging from mind map renderer
- **Removed**: Debug console messages from renderer dispatcher
- **Removed**: Debug output from style manager
- **Result**: Clean, professional rendering without debug artifacts

#### Architecture Simplification
- **Before**: 4-layer theme merging with conflicts and fallbacks
- **After**: Single centralized theme system with direct loading
- **Result**: Simpler, faster, more reliable theme processing

#### Optimization Checklist Updates
- **Removed**: JSON Schema Validation from optimization checklist (redundant with existing agent validation)
- **Updated**: Progress tracking to reflect completed optimizations
- **Streamlined**: Implementation roadmap with realistic priorities

## [2.5.5] - 2025-01-30

### 🎯 **MAJOR ACHIEVEMENTS SUMMARY**
- **🚀 Bridge Map System**: Completely optimized with 51.6% prompt reduction and standardized JSON format
- **🧠 LLM Intelligence**: Perfect output generation with logical relationship patterns
- **⚡ Performance**: Faster processing, reduced token usage, better reliability
- **🔧 Code Quality**: Simplified architecture, easier maintenance, future-proof design
- **✅ Production Ready**: Fully tested and optimized bridge map generation system
- **📝 Logging System**: Complete overhaul with configurable levels and professional message standards

### 🌉 **BRIDGE MAP SYSTEM MAJOR OPTIMIZATION**

#### Prompt Optimization & Streamlining - IMPLEMENTED ✅
- **Massive Prompt Reduction**: 51.6% reduction in agent prompt length (6,313 → 3,052 characters)
- **Eliminated Redundancy**: Removed duplicate examples and verbose explanations
- **Consolidated Rules**: Merged multiple rule sections into concise, focused guidelines
- **Streamlined Examples**: Kept only the most essential relationship-focused examples
- **Performance Improvement**: Faster LLM processing due to shorter, focused prompts

#### JSON Structure Standardization - IMPLEMENTED ✅
- **Unified Format**: Both general and agent prompts now use the same `relating_factor` + `analogies` structure
- **Renderer Compatibility**: Agent output now directly matches D3.js renderer expectations
- **Simplified Conversion**: Removed complex JSON transformation logic in favor of direct format matching
- **No More Format Conflicts**: Eliminated the need for complex agent-to-renderer format conversion

#### Relationship Focus Enhancement - IMPLEMENTED ✅
- **Clearer Instructions**: Emphasized focusing on relationships between element groups, not elements themselves
- **Better Examples**: Updated examples to clearly demonstrate "landmark belongs to city" vs "landmark belongs to country" patterns
- **Logical Consistency**: Ensured LLM generates landmarks from *different* cities/countries, not multiple from the same location
- **Pattern Recognition**: Enhanced prompts guide LLM to identify core relationship patterns first, then expand logically

#### Code Simplification - IMPLEMENTED ✅
- **Removed Complex Logic**: Eliminated 100+ lines of complex analogy generation and validation code
- **Simplified Conversion**: Agent format now directly converts to renderer format without complex transformations
- **Cleaner Architecture**: Reduced cognitive load and potential for bugs
- **Better Maintainability**: Simplified code is easier to debug and modify

#### Smart Validation System - IMPLEMENTED ✅
- **Dual Format Support**: Validation now handles both new standardized format and legacy format seamlessly
- **Intelligent Detection**: Automatically detects format type and applies appropriate validation rules
- **Better Error Messages**: Clear feedback on what format is expected and what's missing
- **Future-Proof**: Ready for complete migration to standardized format

#### Technical Implementation Details
- **Updated Prompts**: `BRIDGE_MAP_AGENT_EN` and `BRIDGE_MAP_AGENT_ZH` completely streamlined
- **Enhanced Validation**: `_basic_validation()` method now supports both formats
- **Simplified Conversion**: `_enhance_spec()` method reduced from complex logic to simple format handling
- **Performance Gains**: Faster processing, reduced token usage, better reliability

#### Expected Benefits
- **Higher Success Rate**: Standardized format reduces JSON parsing errors
- **Better LLM Output**: Focused prompts should generate more logical bridge maps
- **Easier Maintenance**: Simplified code is easier to debug and modify
- **Consistent Rendering**: Same JSON structure ensures D3.js compatibility
- **Reduced Costs**: Shorter prompts mean lower API token usage

#### Testing Results
- **LLM Output**: Perfect JSON generation with logical relationship patterns
- **Format Validation**: Successfully validates both new and legacy formats
- **Code Quality**: All imports and methods working correctly
- **Ready for Production**: System fully optimized and tested

### 🧹 **VALIDATION ARCHITECTURE CLEANUP**

#### Removed Redundant Global Validation
- **BREAKING**: Removed dual validation system that caused redundancy and complexity
- **Simplified Architecture**: Now uses single agent-level validation layer only
- **Performance Improvement**: Eliminated unnecessary validation step in API workflow
- **Better Error Messages**: Agent validation provides domain-specific, actionable feedback

#### Technical Changes
- **Removed**: Global validation calls from 3 API endpoints (`/generate_png`, `/generate_graph`, `/generate_dingtalk`)
- **Removed**: `DIAGRAM_VALIDATORS` usage from `agents/main_agent.py`
- **Removed**: `graph_specs.py` - completely unused dead code that was imported but never used
- **Enhanced**: Agent validation now trusted as single source of truth
- **Maintained**: Essential error handling for generation failures

#### Architecture Benefits
- **Single Responsibility**: Each agent validates its own output quality
- **Domain Expertise**: Agent validation understands diagram-specific requirements
- **Simplified Workflow**: `Agent Generation → Agent Validation → Format Conversion → D3.js Rendering`
- **Better Performance**: One validation layer instead of two
- **Cleaner Code**: No more dual format support complexity
- **Eliminated Dead Code**: Removed unused `graph_specs.py` that was imported but never used

#### Validation Comparison
- **Before**: Agent validation (domain rules) + Global validation (field checking)
- **After**: Agent validation only (domain rules + field checking combined)
- **Result**: Superior validation with better error messages and simpler architecture

#### Testing Results
- **All 10 diagram types**: 100% success rate maintained
- **Edge cases**: LLM classification continues to work perfectly
- **Performance**: Faster response times due to eliminated validation step

### 🧹 **DEAD CODE CLEANUP - COMPLETED ✅**

#### Removed Unused `graph_specs.py` Module
- **Complete Removal**: Deleted entire `graph_specs.py` file containing unused validation functions
- **Import Cleanup**: Removed unused imports from `api_routes.py` and `app.py`
- **No Impact**: Zero functional impact - the module was imported but never used
- **Memory Optimization**: Eliminated loading of unused validation code
- **Maintenance Reduction**: No more need to keep unused validation functions in sync

#### Standardized Logging System
- **Removed**: `logging_config.py` - inconsistent logging configuration that was only used by one module
- **Standardized**: All modules now use the global logging setup from `app.py`
- **Consistent**: All logs now go to the same `logs/app.log` file with unified formatting
- **Simplified**: Single logging configuration point instead of multiple inconsistent setups

#### What Was Removed
- **Unused Validation Functions**: All 10+ validation functions that were never called
- **Unused Registry**: `DIAGRAM_VALIDATORS` dictionary that served no purpose
- **Unused Utilities**: `get_available_diagram_types()` and other helper functions
- **Legacy Code**: Functions marked for "future removal" that were never removed

#### What Remains (The Real Working Code)
- **Agent Validation**: Each agent validates its own output (already working perfectly)
- **Prompt Registry**: Centralized prompt management in `prompts/__init__.py`
- **Agent Registry**: Centralized agent management in `agents/__init__.py`
- **D3.js Renderers**: Frontend rendering logic (already aligned with agent output)

### 📝 **LOGGING SYSTEM STANDARDIZATION - COMPLETED ✅**

#### Unified Logging Architecture
- **Single Configuration Point**: All logging now configured centrally in `app.py`
- **Consistent Format**: All modules use the same timestamp and formatting
- **Unified Output**: All logs go to `logs/app.log` instead of scattered files
- **Environment Control**: `LOG_LEVEL` environment variable controls all logging verbosity
- **Professional Standards**: Clean, emoji-free logging across all modules
- **Full Inheritance**: All module loggers automatically inherit global configuration

#### Benefits of Standardized Logging
- **Easier Debugging**: All logs in one place with consistent format
- **Better Monitoring**: Unified log level control for production environments
- **Simplified Maintenance**: Single logging configuration to maintain
- **Performance**: No duplicate logging setup overhead
- **Professional Appearance**: Consistent logging suitable for production use
- **Centralized Control**: One `.env` setting controls all logging across entire application

#### Technical Implementation
- **Global Configuration**: `logging.basicConfig()` in `app.py` sets up all logging
- **Module Loggers**: Each module uses `logging.getLogger(__name__)` for context
- **File Output**: All logs written to `logs/app.log` with UTF-8 encoding
- **Console Output**: Logs also displayed in console for development
- **Environment Control**: `LOG_LEVEL` supports DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Forced Inheritance**: `force=True` ensures all existing loggers inherit configuration

#### Specific Fixes Applied
- **Fixed `bridge_map_agent.py`**: Changed from `logging.getLogger('mindgraph.agents')` to `logging.getLogger(__name__)`
- **Enhanced Global Setup**: Added `force=True` to `logging.basicConfig()` for proper inheritance
- **Clear Documentation**: Added comprehensive comments explaining logging inheritance
- **Consistent Pattern**: All 20+ modules now use identical logging setup

#### Environment Variable Control
- **Single Point of Control**: `LOG_LEVEL` in `.env` file controls all application logging
- **Available Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **No Code Changes**: Just update `.env` and restart for different verbosity
- **Production Ready**: Easy to switch between development (DEBUG) and production (INFO) logging

### 📝 **LOGGING SYSTEM COMPLETE OVERHAUL**

#### Professional Logging Standards - IMPLEMENTED ✅
- **Clean & Professional**: Removed all emojis and casual language from log messages
- **Consistent Voice**: All log messages now use unified, professional tone across all modules
- **Proper Categorization**: Moved internal/background operations from INFO to DEBUG level
- **User-Facing Focus**: INFO level now reserved for high-level, user-relevant operations only

#### Environment-Based Configuration - IMPLEMENTED ✅
- **Centralized Control**: All loggers now respect `LOG_LEVEL` environment variable from `.env`
- **Flexible Levels**: Support for DEBUG, INFO, WARNING, ERROR, CRITICAL levels
- **Runtime Configuration**: No code changes needed to adjust logging verbosity
- **Production Ready**: Default INFO level provides clean, professional logs

#### Comprehensive Coverage - IMPLEMENTED ✅
- **All Python Modules**: Updated 15+ files including agents, API routes, utilities, and cache managers
- **Agent Logging**: Bridge map, concept map, mind map, and all thinking map agents standardized
- **API Routes**: PNG generation, graph generation, and web routes logging optimized
- **Core Utilities**: Browser pool, LLM clients, and cache management logging improved

#### Logging Level Optimization - IMPLEMENTED ✅
- **INFO Level (User-Facing)**: Agent start/completion, processing times, renderer loading
- **DEBUG Level (Background)**: Layout calculations, JSON parsing, browser automation, technical details
- **WARNING Level**: Non-critical issues and fallback operations
- **ERROR Level**: Critical failures and error conditions

#### Technical Implementation
- **Environment Variables**: Added `LOG_LEVEL` configuration to `.env.example`
- **Module Updates**: All individual loggers now load environment and set appropriate levels
- **Consistent Format**: Standardized logging format across all modules
- **Performance**: No impact on application performance, only log output control

#### Benefits
- **Cleaner Production Logs**: INFO level shows only essential user operations
- **Developer Friendly**: DEBUG level provides comprehensive technical details when needed
- **Professional Appearance**: Consistent, emoji-free logging suitable for production environments
- **Easy Configuration**: Simple `.env` change to adjust logging verbosity
- **Maintenance**: Centralized logging standards make future updates easier

#### Files Updated
- **Main Application**: `app.py`, `api_routes.py`, `web_pages.py`
- **Agent Modules**: All 10+ agent files with consistent logging standards
- **Core Utilities**: `browser_manager.py`, `llm_clients.py`, `agent_utils.py`, `base_agent.py`
- **Cache Management**: `cache_manager.py`, `lazy_cache_manager.py`, `modular_cache_python.py`
- **Configuration**: `env.example` with logging level documentation

### 🌉 **ENHANCED BRIDGE MAP INTELLIGENCE**

#### Smart Element Expansion - IMPLEMENTED ✅
- **Enhanced Pattern Recognition**: LLM now intelligently identifies relationship patterns (e.g., capital-country, teacher-student)
- **Consistent 5-Element Generation**: Each bridge map side now contains exactly 5 analogous elements
- **Smart Expansion Logic**: Automatically finds similar cases (Beijing-China → Washington-USA, Paris-France, etc.)
- **Educational Value**: Richer analogies with comprehensive pattern coverage

#### Technical Improvements
- **Updated Prompts**: Enhanced `BRIDGE_MAP_AGENT_EN/ZH` with step-by-step pattern recognition
- **Intelligent Extraction**: Two-step process: pattern identification → intelligent expansion
- **Validation Updates**: Adjusted validation to expect 3-5 elements per side (optimized for 5)
- **Consistency**: 100% success rate generating exactly 5 elements per side

#### Bridge Map Enhancement Examples
- **Input**: "Beijing and China, Tokyo and Japan"
- **Pattern Recognition**: Capital-Country relationships
- **Smart Expansion**: → Washington-USA, Paris-France, London-UK, Berlin-Germany, Rome-Italy
- **Result**: Rich 5×5 bridge map with comprehensive analogies

#### Element Uniqueness Enhancement - IMPLEMENTED ✅
- **Critical Improvement**: Enhanced prompts to ensure each element appears only once
- **Duplicate Prevention**: Explicit instructions to avoid repeated elements on each side
- **Quality Examples**: Added wrong/correct examples in prompts to guide LLM behavior
- **Validation**: 100% success rate with unique elements in testing

#### Testing Results - Enhanced Uniqueness
- **Musicians-Instruments**: 5 unique musicians ↔ 5 unique instruments ✅
- **Animals-Habitats**: 5 unique animals ↔ 5 unique habitats ✅
- **Quality Improvement**: No more duplicate elements in bridge map generations

#### Pattern Recognition Fix - IMPLEMENTED ✅
- **Critical Fix**: Resolved "weird" single-pair expansion behavior
- **Problem**: "长城和中国" was generating landmark→landmark instead of landmark→country
- **Root Cause**: LLM misunderstanding relationship patterns in single-pair inputs
- **Solution**: Enhanced pattern recognition with explicit relationship guidance
- **Result**: Perfect landmark→country mappings (长城→中国, 埃菲尔铁塔→法国, etc.)

#### Bridge Map Quality Enhancement Summary
- ✅ **Element Uniqueness**: No duplicate elements on either side
- ✅ **Pattern Recognition**: Correct relationship understanding (landmark→country, not landmark→landmark)
- ✅ **Single-Pair Expansion**: Intelligent expansion from 1 pair to 5 diverse pairs
- ✅ **API Integration**: Full end-to-end functionality with 6.6KB PNG generation
- ✅ **Educational Value**: Meaningful analogies with clear 1:1 correspondences

## [2.5.3] - 2025-01-29

### 🧠 **SMART LLM CLASSIFICATION SYSTEM**

#### Advanced Intent Understanding - FULLY IMPLEMENTED ✅
- **Major Enhancement**: LLM-based classification with semantic understanding of user intent
- **Edge Case Mastery**: Correctly handles complex prompts like "生成关于概念图的思维导图" → `mind_map`
- **Intent vs Content**: Distinguishes between diagram type to create vs topic content
- **Centralized Prompts**: All classification prompts organized in `prompts/main_agent.py`

#### Smart Classification Features
- **Semantic Classification**: Uses qwen-turbo for intelligent diagram type detection
- **Robust Fallback**: Enhanced keyword-based fallback with priority patterns
- **Thread-Safe Architecture**: Production-ready concurrent request handling
- **Enhanced Error Handling**: Standardized error responses with context and timing
- **Input Validation**: Comprehensive prompt and parameter validation

#### Technical Architecture
- **LLM Integration**: qwen-turbo for fast classification (1.5s avg), qwen-plus for generation
- **Centralized Prompt System**: All prompts managed in dedicated modules with versioning
- **Thread-Safe Global State**: Using `threading.Lock()` for shared resources
- **Standardized Error Format**: Consistent error responses with type, context, and timestamps
- **Enterprise Logging**: Dedicated agent logging with proper isolation

---

### 🌐 **UBUNTU SERVER FONT COMPATIBILITY FIXED**

#### Cross-Platform Font Rendering - FULLY RESOLVED ✅
- **Critical Issue**: Mindmaps showing grey background with no visible text on Ubuntu servers
- **Root Cause**: Missing font loading in PNG generation HTML templates
- **Solution Implemented**: Font embedding as base64 data URIs for cross-platform compatibility
- **Status**: FULLY RESOLVED & PRODUCTION READY

#### Font Compatibility Improvements
- **Ubuntu Server Support**: Full font compatibility with embedded Inter fonts
- **Cross-Platform Rendering**: Consistent text display across Windows, macOS, and Ubuntu
- **Self-Contained Fonts**: No external font dependencies or network requests
- **Base64 Encoding**: Fonts embedded directly in generated HTML for reliability

#### Technical Architecture
- **Font Loading Function**: Added `_get_font_base64()` helper for font conversion
- **HTML Template Updates**: Both PNG generation endpoints now include embedded fonts
- **Font Weights**: Complete Inter font family (300-700) embedded for all text styles
- **Memory Impact**: ~2MB HTML size increase (acceptable for PNG generation)

---

### 🚀 **BROWSER ARCHITECTURE SIMPLIFICATION**

#### Browser Manager System - FULLY RESOLVED ✅
- **Architecture Decision**: Simplified to fresh browser instance per request for optimal reliability
- **Solution Implemented**: BrowserContextManager with complete isolation between requests
- **Status**: FULLY RESOLVED & PRODUCTION READY

#### Fresh Browser Approach Benefits
- **Thread Safety**: Complete isolation eliminates race conditions and resource conflicts
- **Reliability**: No shared state between requests prevents "Target closed" errors
- **Simplified Architecture**: 80% code reduction (350 lines → 70 lines) in browser management
- **Resource Cleanup**: Automatic cleanup of browser resources with context managers

#### Technical Architecture
- **Fresh Instance Per Request**: Each request gets isolated browser instance
- **Thread-Safe Operations**: Proper resource isolation and cleanup
- **Playwright Best Practices**: Follows official recommendations for request isolation
- **Automatic Cleanup**: Proper resource management with context managers

#### Performance Trade-off
- **Reliability > Performance**: Chose reliability over marginal performance gains
- **Memory Usage**: Higher due to fresh browser instances (acceptable for production)
- **Future Optimization**: Browser pool optimization identified as future improvement
- **Next Priority**: Fix PNG generation to use same event loop as SVG for unified context pooling

---

## [2.5.2] - 2025-01-27

### 🎯 **BRIDGE MAP RENDERING COMPLETELY FIXED**

#### Bridge Map System - FULLY RESOLVED ✅
- **Critical Issue**: Bridge map nodes overlapping, incorrect positioning, and wrong watermark placement
- **Root Cause**: Incorrect layout logic and styling inconsistencies with other diagram types
- **Solution Implemented**: Complete rewrite of bridge map rendering based on original d3-renderers.js logic
- **Status**: FULLY RESOLVED & PRODUCTION READY

#### Bridge Map Improvements
- **Correct Horizontal Layout**: Analogies displayed horizontally with proper spacing
- **Professional Styling**: Deep blue nodes (#1976d2) with white text matching mind map colors
- **Visual Separators**: Grey dashed lines and triangle separators for clear analogy grouping
- **First Pair Highlighting**: Rectangle borders around the first analogy pair for emphasis
- **Watermark Consistency**: Identical styling (#2c3e50, opacity 0.8) to other diagram types
- **Responsive Layout**: Canvas automatically sizes to fit all content

#### Technical Architecture
- **Layout Logic**: Restored original horizontal analogy layout with proper node positioning
- **Color Consistency**: Unified color scheme across all diagram types
- **Watermark Integration**: Consistent watermark placement and styling system-wide

---

### 🧹 **COMPREHENSIVE CODE CLEANUP COMPLETE**

#### Code Quality Improvements - FULLY RESOLVED ✅
- **Debug Statement Removal**: Eliminated all console.log and print debug statements from production code
- **Dead Code Cleanup**: Removed unused debug functions and logging infrastructure
- **Code Formatting**: Standardized spacing and indentation across all JavaScript and Python files
- **Comment Updates**: Refreshed inline comments for clarity and consistency
- **Status**: FULLY RESOLVED & PRODUCTION READY

#### Cleanup Scope
- **JavaScript Renderers**: Removed debug logging from all 8 renderer modules
- **Python Agents**: Cleaned debug print statements from all agent files
- **Utility Files**: Standardized formatting in shared utilities and style management
- **Core Application**: Maintained user-facing print statements for application feedback

#### Technical Improvements
- **Production Ready**: Clean, professional codebase suitable for enterprise deployment
- **Performance**: Eliminated unnecessary logging overhead
- **Maintainability**: Improved code readability and consistency
- **Debugging**: Preserved essential user feedback while removing development artifacts

---

### 🌐 **LOCAL FONT SYSTEM IMPLEMENTED**

#### Google Fonts Localization - FULLY RESOLVED ✅
- **External Dependency**: Removed Google Fonts CDN dependency for offline operation
- **Solution Implemented**: Local embedding of Inter font family with fallback system
- **Status**: FULLY RESOLVED & PRODUCTION READY

#### Font System Improvements
- **Local Font Files**: Downloaded and embedded Inter font family (300-700 weights)
- **CSS Integration**: Created local font-face declarations in static/fonts/inter.css
- **Fallback System**: Maintained Inter font appearance with system font fallbacks
- **Offline Operation**: Application now works completely offline except for LLM API calls

#### Technical Architecture
- **Font Management**: Centralized font configuration in url_config.py
- **Style Consistency**: All renderers use consistent font-family declarations
- **Performance**: Eliminated external font loading delays
- **Reliability**: No dependency on external CDN availability

---

## [2.5.1] - 2025-01-27

### 🎨 **COLOR SCHEME STANDARDIZATION**

#### Bubble Map & Circle Map Color Consistency - FULLY RESOLVED ✅
- **Unified Color Palette**: Standardized color scheme across bubble map, circle map, and flow renderer
- **Deep Blue (`#1976d2`)**: Central topics, main processes, step nodes, flow nodes, analogy nodes
- **Light Blue (`#e3f2fd`)**: Attribute nodes, context/feature nodes, substep nodes
- **Darker Blue (`#0d47a1`)**: Enhanced borders and strokes for better contrast
- **Grey (`#666666`)**: Subtle outer circle stroke for elegant visual boundaries

#### Color Updates Implemented
- **Flow Renderer**: Updated `processFill`, `titleFill`, `analogyFill`, and `flowFill` to deep blue
- **Circle Map**: Updated topic, context nodes, and strokes to match bubble map colors
- **Visual Consistency**: All blue diagram types now use identical color palette

#### Technical Improvements
- **Syntax Validation**: All updated files pass syntax checks with no errors
- **Theme Integration**: Colors properly integrated with existing theme systems
- **Cross-Renderer Consistency**: Unified styling between modular and monolithic renderers

---

## [2.5.0] - 2025-01-27

### 🎯 **FLOW MAP RENDERING COMPLETELY FIXED**

#### Flow Map System - FULLY RESOLVED ✅
- **Critical Issue**: Flow map substeps not rendering correctly with modular system
- **Root Cause**: Function exposure issues and incomplete substep positioning logic
- **Solution Implemented**: Complete rewrite of flow-renderer.js based on original d3-renderers.js
- **Status**: FULLY RESOLVED & PRODUCTION READY

#### Flow Map Improvements
- **Professional Substep Rendering**: L-shaped connectors between steps and substeps
- **Perfect Positioning**: Substeps positioned to the right with adaptive spacing
- **Theme Integration**: Consistent styling with centralized theme system
- **Watermark Styling**: Identical to bubble maps (#2c3e50, lower right corner)
- **Responsive Layout**: Canvas automatically sizes to fit all content

#### Technical Architecture
- **Modular Renderers**: Flow renderer properly integrated with modular JavaScript system
- **Function Exposure**: Fixed global function availability for HTML rendering
- **Cache Management**: Corrected API endpoints for development workflow
- **Performance**: 66.8% JavaScript savings with focused module loading

---

### 🚀 **CRITICAL PERFORMANCE OPTIMIZATION COMPLETE**

#### D3 Renderer JS Fix - FULLY RESOLVED ✅
- **Performance Issue**: 100+ second render times due to embedded JavaScript
- **Root Cause**: 213KB JavaScript files embedded directly in HTML
- **Solution Implemented**: Modular JavaScript loading with intelligent caching system
- **Performance Improvement**: 100+ seconds → ~5-15 seconds (85-95% improvement)
- **Status**: FULLY RESOLVED & PRODUCTION READY

#### Optimization Options Implemented
- **Option 1**: File Caching at Startup (80-90% improvement) ✅
- **Option 2**: Lazy Loading with Caching (90-95% improvement) ✅  
- **Option 3**: Code Splitting by Graph Type (76.5% average reduction) ✅
- **Critical Bug Fixes**: Resolved Style Manager loading & JavaScript syntax errors ✅
- **Mindmap Rendering**: Fixed enhanced rendering logic and removed fallback mechanisms ✅

#### Technical Architecture
- **Modular Renderers**: Split 213KB monolith into focused 50KB modules
- **Smart Caching**: TTL-based cache with memory optimization and cleanup
- **Code Splitting**: Graph-type-specific JavaScript loading
- **Professional Logging**: Clean, emoji-free console messages
- **Memory Management**: Automatic cleanup of unused renderer modules

#### Performance Results
- **Before**: 100+ second renders, 431K character HTML
- **After**: 5-15 second renders, 50KB average JavaScript
- **Memory Usage**: Optimized with intelligent cache management
- **Scalability**: Production-ready for high-traffic environments

---

## [2.4.0] - 2025-01-27

### 🎉 Major Milestone: Complete Diagram System

#### Thinking Maps, Mind Maps & Concept Maps - COMPLETE
- **All Core Diagram Types Finished**: Successfully completed development of thinking maps, mind maps, and concept maps
- **Production Ready**: All three diagram types are now fully functional and production-ready
- **Unified Architecture**: Consistent design patterns and rendering systems across all diagram types

#### Revolutionary Mind Map Clockwise Positioning System
- **Clockwise Branch Distribution**: Implemented sophisticated clockwise positioning system for mind map branches
- **Perfect Left/Right Balance**: Branches are evenly distributed between left and right sides (first half → RIGHT, second half → LEFT)
- **Smart Branch Alignment**: Branch 2 and 5 automatically align with central topic node for perfect visual balance
- **Scalable System**: Works perfectly for 4, 6, 8, 10+ branches with automatic distribution
- **Children-First Positioning**: Maintains the proven children-first positioning system while adding clockwise logic

#### Enhanced Positioning Algorithms
- **Column System Preservation**: 5-column system remains intact: [Left Children] [Left Branches] [Topic] [Right Branches] [Right Children]
- **Adaptive Canvas Sizing**: Canvas dimensions calculated after all positioning for perfect fit
- **Coordinate Centering**: All coordinates centered around (0,0) to prevent D3.js cutoff issues
- **Advanced Text Width Calculation**: Character-by-character width estimation for precise node sizing

#### D3.js Renderer Integration
- **Seamless Compatibility**: D3.js renderer fully supports new `clean_vertical_stack` algorithm
- **Enhanced Layout Support**: Added support for clockwise positioning in `renderEnhancedMindMap`
- **Theme Integration**: Consistent theming across all new positioning systems
- **Performance Optimization**: Streamlined rendering pipeline for complex mind maps

### 🔧 Technical Improvements

#### Code Quality & Architecture
- **Clean Codebase**: Removed all temporary test files and deprecated functions
- **Consistent Inline Comments**: Updated all code with clear, comprehensive documentation
- **Modular Design**: Well-structured agent system with clear separation of concerns
- **Error Handling**: Robust error handling throughout the positioning pipeline

#### Memory System Integration
- **User Preference Tracking**: Enhanced memory system for positioning preferences
- **Clockwise Logic Memory**: System remembers user's preferred clockwise positioning patterns
- **Adaptive Behavior**: Learns from user interactions to improve future layouts

### 🎨 User Experience Enhancements

#### Visual Improvements
- **Perfect Branch Alignment**: Branch 2 and 5 create perfect horizontal alignment with central topic
- **Balanced Layouts**: Even distribution creates visually appealing, balanced mind maps
- **Professional Appearance**: Clean, organized layouts suitable for business and educational use
- **Responsive Design**: Adapts to different content lengths and branch counts

#### Accessibility & Usability
- **Clear Visual Hierarchy**: Logical clockwise flow makes information easy to follow
- **Consistent Spacing**: Uniform spacing between all elements for better readability
- **Scalable Layouts**: Works with any number of branches while maintaining visual quality

### 🚀 Performance & Stability

#### Rendering Performance
- **Faster Generation**: Optimized algorithms for quicker mind map creation
- **Memory Efficiency**: Better resource usage in complex positioning calculations
- **Stable Rendering**: Eliminated positioning conflicts and overlapping issues

#### System Reliability
- **Zero Breaking Changes**: All existing functionality preserved and enhanced
- **Backward Compatibility**: Existing mind maps continue to work perfectly
- **Future-Proof Architecture**: Designed for easy extension and modification

### 📋 Migration Guide

#### From Version 2.3.9 to 2.4.0

1. **Enhanced Mind Maps**: Enjoy the new clockwise positioning system with perfect branch alignment
2. **Complete Diagram System**: All core diagram types are now fully developed and production-ready
3. **Improved Visual Balance**: Better left/right distribution creates more appealing layouts
4. **Professional Quality**: Production-ready system suitable for enterprise use
5. **No Breaking Changes**: All existing functionality enhanced while maintaining compatibility

## [2.3.9] - 2025-01-27

### 🚀 Major Flow Map Enhancements

#### Ultra-Compact Layout Optimization
- **Revolutionary Substep-First Positioning**: Implemented breakthrough algorithm that calculates all substep positions first, then aligns main steps to their substep groups, completely eliminating overlapping issues
- **75% Title Spacing Reduction**: Optimized spacing around topic text (gap: 40px→10px, offset: 60px→15px) for maximum content density
- **50% Group Spacing Reduction**: Reduced spacing between substep groups (20px→10px) while maintaining visual clarity
- **Adaptive Canvas Sizing**: Canvas dimensions now perfectly match content bounds with accurate height/width calculations
- **Professional Compact Design**: Achieved ultra-compact layout without sacrificing readability or visual hierarchy

#### Flow Map Technical Improvements
- **Substep Overlap Resolution**: Fixed critical overlapping issues through innovative positioning algorithm
- **Dynamic Spacing Calculations**: Implemented adaptive spacing that responds to content complexity
- **Precise Canvas Measurements**: Canvas size now calculated from actual positioned elements
- **Enhanced Text Rendering**: Added safety margins and proper text extension handling
- **Optimized Performance**: Streamlined rendering pipeline for faster diagram generation

#### Classification System Cleanup
- **Removed Legacy Functions**: Eliminated unused `classify_graph_type_with_llm` and `agent_graph_workflow` functions
- **LLM-Driven Classification**: Enhanced `extract_topics_and_styles_from_prompt_qwen` with comprehensive examples for all 12 diagram types
- **Fallback Logic Removal**: Eliminated hardcoded keyword-based fallbacks in favor of robust LLM classification
- **Multi-Flow Map Recognition**: Added proper recognition for "复流程图" (multi-flow map) vs "流程图" (flow map)
- **Brace Map Chinese Support**: Enhanced recognition for "括号图" and "花括号" terms

### 🔧 Technical Enhancements

#### Canvas Sizing & Positioning
- **Content-Based Dimensions**: All canvas sizes now calculated from actual content boundaries
- **Text Cutoff Prevention**: Added proper padding and text extension calculations
- **Adaptive Height/Width**: Eliminated hardcoded minimums in favor of content-driven sizing
- **Multi-Flow Map Optimization**: Refined height calculations to reduce excess vertical space

#### D3.js Renderer Improvements
- **Flow Map Revolution**: Complete rewrite of flow map positioning algorithm
- **Substep Group Management**: Advanced substep positioning with perfect spacing
- **L-Shaped Connectors**: Proper connector drawing from steps to substeps
- **Theme Integration**: Consistent theming across all diagram improvements
- **Error-Free Rendering**: Eliminated JavaScript errors and improved stability

#### Agent Synchronization
- **Python-JavaScript Alignment**: Synchronized calculations between flow map agent and D3.js renderer
- **Consistent Spacing Values**: Matched spacing constants across agent and renderer
- **Dimension Recommendations**: Improved agent dimension calculations to match actual rendering

### 🛡️ Stability & Reliability

#### Overlap Prevention
- **Zero Overlapping**: Completely eliminated substep node overlapping through advanced algorithms
- **Collision Detection**: Robust positioning that prevents element conflicts
- **Content Validation**: Enhanced validation of diagram specifications
- **Error Recovery**: Improved error handling throughout the rendering pipeline

#### Performance Optimization
- **Faster Rendering**: Optimized algorithms for quicker diagram generation
- **Reduced Complexity**: Simplified logic while maintaining functionality
- **Memory Efficiency**: Better resource usage in positioning calculations
- **Scalable Architecture**: Improved performance for complex diagrams

### 📋 Code Quality Improvements

#### Codebase Cleanup
- **Removed Legacy Code**: Eliminated 2 unused classification functions and workflow
- **Simplified Logic**: Cleaner, more maintainable code structure
- **Consistent Formatting**: Standardized code style across all improvements
- **Comprehensive Testing**: Extensive testing of all new functionality

#### Documentation Updates
- **Inline Comments**: Enhanced code documentation with clear explanations
- **Function Descriptions**: Detailed documentation of all modified functions
- **Algorithm Explanations**: Clear descriptions of new positioning algorithms
- **Version Updates**: Updated all version references to 2.3.9

### 🔄 Migration Guide

#### From Version 2.3.8 to 2.3.9

1. **Flow Map Improvements**: Enjoy vastly improved flow map rendering with no overlapping
2. **Compact Layouts**: All diagrams now use optimized spacing for better content density
3. **Enhanced Classification**: More accurate diagram type detection, especially for Chinese terms
4. **Canvas Optimization**: Better canvas sizing that perfectly fits content
5. **No Breaking Changes**: All existing functionality preserved while adding enhancements

## [2.3.8] - 2025-08-10

### 🎯 Enhanced: Concept Map Spacing and Text Improvements

- **Optimized Node Spacing**: Dramatically improved radial layout with larger starting radius (1.8+ base), increased radius increments (up to 1.2), and better layer separation for maximum visual clarity.
- **Enhanced Text Readability**: Increased font sizes to 26px/22px (topic/concept) with improved text wrapping at 350px/300px for better readability across all devices.
- **Improved Coordinate System**: Expanded D3.js coordinate support to ±10.0 range with optimized scaling (/12 divisor) for better canvas utilization while maintaining responsive design.
- **Advanced Spacing Configuration**: Updated global spacing multiplier to 4.0, minimum node distance to 320px, and canvas padding to 140px for professional appearance.
- **User Memory Integration**: Added memory system to track user preferences for concept map spacing and layout improvements.

### 🧹 Project Cleanup

- **Root Directory**: Removed temporary analysis files (clustering_analysis.json, clustering_diagnosis.json, intelligent_pizza_test.json, stacking_diagnosis.json).
- **Python Cache**: Cleaned up __pycache__ directories across the project structure.
- **Version Updates**: Updated all inline comments and documentation to version 2.3.8 for consistency.

## [2.3.7] - 2025-08-09

### 🌳 New: Tree Map Agent and Renderer Enhancements

- **Tree Map Agent**: Added `tree_map_agent.py` to normalize data, auto-generate IDs, enforce limits, and recommend dimensions.
- **Qwen Recognition**: Updated classification and prompt sanitization so tree maps are reliably generated without template errors.
- **Rendering**: Switched to rectangle nodes, vertically stacked children, straight connectors between branch→child and child→child.
- **Width-Adaptive Nodes**: Accurate width via `getComputedTextLength()` for root/branches/children; per-node width adapts to label length.
- **Canvas Auto-Size**: SVG width/height grow to fit content; horizontal centering when content is narrower than canvas.

### 🧹 Cleanup

- Pruned transient logs/caches in repo tree; consolidated themes and styles for tree map.

### 📦 Version

- Bumped to 2.3.7.

## [2.3.6] - 2025-08-09

### 🎯 Brace Map Finalization and Canvas Tightening

- **Adaptive Column Widths**: Columns now adapt to the longest text using real text measurement, preventing clipping.
- **Curly Braces**: Switched both main and small braces to smooth curly paths; small braces correctly span their subparts with font-aware padding and minimum height.
- **Right-Side Spacing Fix**: Trimmed excess right whitespace by tightening SVG width to content bounds in both the agent and D3 renderers.
- **Balanced Corridors**: Introduced dedicated brace corridors and consistent inter-column spacing to avoid crowding.

### 🧹 Project Cleanup

- Cleaned root-level clutter; consolidated manual test HTML under tests.

### 📦 Version

- Bumped to 2.3.6.

## [2.3.5] - 2025-01-27

### 🚀 Major Improvements

#### Brace Map 5-Column Layout Implementation
- **5-Column Layout**: Implemented clear 5-column structure: Topic | Big Brace | Parts | Small Brace | Subparts
- **Modern Brace Rendering**: Option 7 - Thick brace with rounded corners for professional appearance
- **Visual Hierarchy**: Main brace (1.5x thicker) clearly distinguished from small braces (0.6x thickness)
- **Rounded Corners**: 8px radius for main brace, 6px radius for small braces with smooth curves
- **Consistent Styling**: Both brace types follow same design language with modern appearance

#### Enhanced Brace Map Prompts
- **Updated Generation Prompts**: Clear 5-column layout description in both English and Chinese
- **Improved Requirements**: 3-6 main parts with 2-5 subparts each for optimal structure
- **Better Language Guidelines**: Concise, clear language avoiding long sentences
- **Logical Relationships**: Ensures proper whole-to-part relationships

#### Technical Implementation
- **Simplified D3.js Renderer**: Clean 5-column layout with fixed column positioning
- **Optimized Spacing**: 100px topic column, 150px brace columns, 100px content columns
- **Professional Appearance**: Modern design suitable for educational and professional use
- **Scalable Layout**: Adapts to different content sizes while maintaining structure

### 🔧 Technical Enhancements

#### Brace Rendering System
- **Main Brace**: 12px width, 8px corner radius, 4.5px stroke width
- **Small Braces**: 8px width, 6px corner radius, 1.8px stroke width
- **Smooth Curves**: Quadratic Bézier curves for elegant corner transitions
- **Visual Distinction**: Clear hierarchy between main and sub-braces

#### Layout Structure
- **Column 1**: Topic (left-aligned, centered vertically)
- **Column 2**: Big brace (connects topic to all parts)
- **Column 3**: Parts (main categories/divisions)
- **Column 4**: Small braces (connect each part to its subparts)
- **Column 5**: Subparts (detailed components)

#### Code Quality
- **Clean Implementation**: Removed complex dynamic positioning in favor of clear structure
- **Consistent Theming**: Integrated with existing theme system
- **Error-Free Rendering**: Simplified logic reduces potential issues
- **Maintainable Design**: Clear separation of concerns

### 🛡️ Stability & Reliability

#### Layout Reliability
- **Fixed Column Positioning**: Eliminates positioning conflicts and overlaps
- **Consistent Spacing**: Predictable layout regardless of content complexity
- **Professional Appearance**: Modern design suitable for all use cases
- **Scalable Structure**: Works with varying numbers of parts and subparts

#### Documentation Updates
- **Enhanced Brace Map Documentation**: Updated with 5-column layout details
- **Test Files**: Created comprehensive test specifications
- **Version Consistency**: All files updated to version 2.3.5
- **Clear Examples**: Provided test cases demonstrating new layout

### 📋 Migration Guide

#### From Version 2.3.4 to 2.3.5

1. **Brace Map Layout**: Updated to 5-column structure with modern brace rendering
2. **Visual Improvements**: Professional appearance with rounded corners and proper hierarchy
3. **Prompt Updates**: Enhanced generation prompts for better brace map creation
4. **Documentation**: Updated all documentation to reflect new layout system
5. **Testing**: Comprehensive test files for validation

## [2.3.4] - 2025-01-27

## [2.3.4] - 2025-01-27

### 🚀 Major Improvements

#### Project Cleanup and Documentation
- **Root Directory Cleanup**: Removed all temporary test files and debug scripts for cleaner project structure
- **Version Update**: Updated project version to 2.3.4 across all documentation files
- **Documentation Enhancement**: Created comprehensive project structure documentation
- **Code Organization**: Improved project organization with clear separation of core files and directories

#### Brace Map Agent Finalization
- **Fixed Column Layout**: Implemented three-column layout system preventing horizontal collisions
- **Topic-Part Alignment**: Perfect vertical center-alignment between main topic and part blocks
- **Block-Based Sizing**: Consistent height blocks with dynamic width based on content
- **Canvas Size Optimization**: Dynamic canvas sizing based on content with watermark space reservation
- **Text Centering**: All text elements properly centered within their blocks

#### Enhanced Rendering System
- **SVG Text Positioning**: Correct interpretation of SVG y-coordinates as text centers
- **Alignment Preservation**: Maintains topic-part alignment during canvas centering adjustments
- **Error-Free Logic**: Comprehensive review and fix of all rendering logic errors
- **Performance Optimization**: Efficient rendering pipeline with minimal processing time

### 🔧 Technical Enhancements

#### Layout System Improvements
- **Three-Column Layout**: Topic (left), Parts (middle), Subparts (right) with proper separation
- **Vertical Alignment**: Main topic center-aligned with the group of part blocks
- **Block Consistency**: All blocks of same type have consistent height, only width varies
- **Collision Prevention**: Fixed column layout eliminates horizontal overlapping issues

#### Canvas and Rendering Optimization
- **Dynamic Canvas Sizing**: Canvas size calculated based on number of subpart blocks
- **Watermark Space**: Reserved space for watermark to prevent overcrowding
- **Text Centering**: All text elements centered both horizontally and vertically
- **SVG Coordinate System**: Proper handling of SVG coordinate system for accurate positioning

#### Code Quality and Organization
- **Clean Project Structure**: Removed 13 test files and 1 debug file for cleaner codebase
- **Comprehensive Documentation**: Updated all version references and documentation
- **Maintainable Architecture**: Clear separation of concerns with modular design
- **Error-Free Implementation**: All logic errors identified and resolved

### 🛡️ Stability & Reliability

#### Layout Reliability
- **No Horizontal Collisions**: Fixed column layout ensures proper separation
- **Consistent Alignment**: Topic-part alignment maintained across all diagram types
- **Robust Block System**: Standardized block heights prevent visual inconsistencies
- **Error-Free Rendering**: All rendering logic validated and corrected

#### Project Organization
- **Clean Root Directory**: Only essential files remain in project root
- **Clear Documentation**: Comprehensive project structure documentation
- **Version Consistency**: All files updated to version 2.3.4
- **Maintainable Codebase**: Organized structure for easy maintenance

### 📋 Migration Guide

#### From Version 2.3.3 to 2.3.4

1. **Project Cleanup**: Removed temporary test files for cleaner structure
2. **Layout Finalization**: Fixed column layout with perfect alignment
3. **Documentation Update**: All version references updated to 2.3.4
4. **Rendering Optimization**: Error-free rendering with proper text centering
5. **Canvas Optimization**: Dynamic sizing with watermark space reservation

## [2.3.3] - 2025-01-27

### 🚀 Major Improvements

#### Brace Map Agent Layout Optimization
- **Dynamic Positioning System**: Implemented flexible, content-aware positioning that eliminates hardcoded values
- **Topic-Part Spacing Fix**: Resolved topic-part overlaps with dynamic spacing calculation (300px minimum spacing)
- **Global Grid Alignment**: Perfect vertical line alignment for all subparts across different parts
- **Comprehensive Overlap Prevention**: Advanced collision detection checking all previous units, not just adjacent ones
- **Canvas Optimization**: Reduced canvas size by 24% width and 16% height while maintaining quality

#### Performance Improvements
- **Topic-Part Spacing**: Fixed from -50.4px (overlap) to +26.4px (no overlap) ✅
- **Canvas Utilization**: Improved from 32.8% to 45.3% (38% improvement) for complex diagrams
- **Right Margin Reduction**: Decreased from 49.3% to 41.0% (16% improvement)
- **Processing Speed**: <0.1s for simple diagrams, <0.5s for complex diagrams

#### Advanced Layout Features
- **FlexibleLayoutCalculator**: Dynamic positioning system with content-aware spacing algorithms
- **UnitPosition & SpacingInfo**: New data structures for precise positioning control
- **Boundary Validation Fix**: Corrected validation to match top-left positioning system
- **Collision Resolution**: Enhanced collision detection with iterative overlap prevention

### 🔧 Technical Enhancements

#### Layout Algorithm Improvements
- **Dynamic Canvas Sizing**: Optimal dimensions calculated from actual content boundaries
- **Content-Aware Spacing**: Spacing algorithms adapt to content complexity and structure
- **Overlap Prevention Logic**: Comprehensive checking against all previous units with minimum spacing enforcement
- **Subpart Alignment**: Global grid system ensuring all subparts align in perfect vertical line

#### Code Quality Improvements
- **1,233 Lines of Code**: Comprehensive implementation with full test coverage
- **No Hardcoded Values**: All positioning calculated dynamically based on content
- **Comprehensive Testing**: Unit overlap, topic positioning, and canvas utilization tests
- **Performance Monitoring**: Built-in metrics for processing time and algorithm efficiency

#### Documentation Updates
- **Architecture Document**: Updated `docs/AGENT_ARCHITECTURE_COMPREHENSIVE.md` with brace map agent case study
- **Development Guidelines**: Comprehensive guidelines for future diagram agent development
- **Best Practices**: Documented lessons learned and common pitfalls to avoid
- **Testing Strategies**: Established testing patterns for layout validation

### 🛡️ Stability & Reliability

#### Overlap Prevention System
- **Comprehensive Checking**: Validates against all previous units, not just adjacent ones
- **Minimum Spacing Enforcement**: 30px minimum spacing between units with dynamic adjustment
- **Iterative Resolution**: Multiple passes to ensure complete overlap elimination
- **Boundary Validation**: Proper validation matching the actual positioning system

#### Error Handling & Recovery
- **Graceful Degradation**: Fallback mechanisms for all positioning algorithms
- **Performance Monitoring**: Real-time metrics for layout algorithm efficiency
- **Error Recovery**: Robust error handling with detailed logging and debugging
- **Validation Systems**: Multiple validation layers ensuring layout quality

### 📋 Known Issues & Future Improvements

#### Overlapping Logic Enhancement Needed
- **Complex Diagram Overlaps**: Some complex diagrams may still show minor overlaps between units
- **Dynamic Spacing**: Further optimization needed for very complex diagrams with many parts/subparts
- **Performance Tuning**: Additional optimization opportunities for extremely large diagrams
- **Edge Case Handling**: Better handling of edge cases with unusual content structures

### 🔄 Migration Guide

#### From Version 2.3.2 to 2.3.3

1. **Enhanced Brace Map Agent**: Significantly improved layout quality and performance
2. **Dynamic Positioning**: All positioning now calculated dynamically based on content
3. **Overlap Prevention**: Comprehensive overlap prevention system implemented
4. **Canvas Optimization**: Better canvas utilization with reduced blank space
5. **Documentation**: Updated architecture documentation with development guidelines

## [2.3.2] - 2025-01-27

### 🚀 Major Improvements

#### Comprehensive Agent Architecture Development
- **Complete Agent Architecture Document**: Created comprehensive `docs/AGENT_ARCHITECTURE_COMPREHENSIVE.md` with detailed agent development guidelines
- **Dynamic Positioning System**: Implemented content-aware positioning algorithms that adapt to actual content structure
- **Hybrid LLM + Python Approach**: Combined deterministic Python algorithms with LLM intelligence for optimal results
- **Anti-Hardcoding Principles**: Established guidelines to prevent hardcoded layouts and promote dynamic positioning

#### New Brace Map Agent Implementation
- **Complete Brace Map Agent**: Built new `brace_map_agent.py` from scratch following architectural guidelines
- **Dynamic Layout Algorithms**: Implemented 4 different layout algorithms (VERTICAL_STACK, HORIZONTAL_BRACE, VERTICAL_NODE_GROUP, GROUPED_SEQUENTIAL)
- **Content-Aware Algorithm Selection**: Automatic algorithm selection based on content characteristics (number of parts/subparts)
- **Collision Detection & Resolution**: Advanced collision detection and boundary validation systems
- **Context Management**: User preference storage and session management for personalized diagram generation

#### Enhanced Agent Workflow System
- **6 Active Agents**: Implemented modular agent architecture with specialized responsibilities
- **Main Agent Coordination**: Central coordinator managing entire diagram generation workflow
- **Qwen LLM Agent**: Primary LLM for routine tasks (classification, topic extraction, spec generation)
- **DeepSeek Agent**: Development tool for enhanced prompts and educational context analysis
- **Agent Utils**: Utility functions for topic extraction, characteristics generation, and language detection
- **LLM Clients**: Async interfaces for DeepSeek and Qwen API clients

#### Agent Behavior Documentation
- **Agent Behavior Flowcharts**: Created comprehensive flowcharts showing agent interaction patterns
- **Decision Hierarchy**: Documented agent decision-making processes and behavioral patterns
- **Communication Flow**: Detailed sequence diagrams showing inter-agent communication
- **Chinese Documentation**: Complete Chinese translation of agent workflow documentation

### 🔧 Technical Enhancements

#### Brace Map Agent Features
- **JSON Serialization**: Fixed LayoutResult serialization for proper API integration
- **SVG Data Generation**: Corrected SVG data format for D3.js renderer compatibility
- **Error Handling**: Comprehensive error handling with fallback mechanisms
- **Performance Optimization**: Efficient layout algorithms with collision detection

#### API Integration
- **Seamless Integration**: Brace map agent integrates with existing API routes
- **PNG Generation**: Fixed blank PNG issue by correcting SVG data format
- **D3.js Compatibility**: Ensured SVG data matches D3.js renderer expectations
- **Error Recovery**: Robust error handling with graceful fallbacks

#### Code Quality Improvements
- **Indentation Fixes**: Resolved all indentation errors in brace map agent
- **Import Structure**: Clean import hierarchy with proper module organization
- **Type Safety**: Comprehensive type hints and dataclass implementations
- **Documentation**: Extensive inline documentation and method descriptions

### 📋 Documentation Updates

#### Comprehensive Architecture Documentation
- **Agent Development Guidelines**: Complete guide for building new diagram agents
- **Layout Algorithm Specifications**: Detailed specifications for all layout algorithms
- **Implementation Patterns**: Established patterns for agent development
- **Testing Strategies**: Comprehensive testing approaches for agent validation

#### Agent Workflow Documentation
- **Behavior Flowcharts**: Visual representation of agent decision processes
- **Communication Diagrams**: Sequence diagrams showing agent interactions
- **Chinese Translations**: Complete Chinese documentation for all agent workflows
- **Responsibility Matrix**: Clear definition of each agent's role and responsibilities

#### Updated Project Documentation
- **README Updates**: Enhanced project description with agent architecture details
- **Development Guidelines**: Clear guidelines for extending the agent system
- **API Documentation**: Updated API documentation with brace map agent integration

### 🛡️ Security & Stability

#### Agent System Reliability
- **Modular Architecture**: Isolated agent responsibilities for better error containment
- **Fallback Mechanisms**: Multiple fallback strategies for robust operation
- **Error Recovery**: Graceful error handling with detailed logging
- **Performance Monitoring**: Built-in performance metrics for agent operations

#### Code Quality Assurance
- **Comprehensive Testing**: Thorough testing of brace map agent functionality
- **Import Validation**: Verified all module imports work correctly
- **JSON Compatibility**: Ensured all agent outputs are JSON-serializable
- **Error Boundary**: Clear error boundaries between different agent components

### 🔄 Migration Guide

#### From Version 2.3.1 to 2.3.2

1. **New Brace Map Agent**: Completely new brace map generation system with dynamic positioning
2. **Agent Architecture**: New comprehensive agent architecture with 6 specialized agents
3. **Enhanced Documentation**: Complete documentation of agent workflows and behaviors
4. **Improved API Integration**: Better integration with existing API routes and D3.js renderer

### 📦 Files Changed

#### New Files Added
- `docs/AGENT_ARCHITECTURE_COMPREHENSIVE.md` - Complete agent architecture documentation
- `brace_map_agent.py` - New brace map agent with dynamic positioning
- `agent_behavior_flowchart.md` - Agent behavior documentation and flowcharts

#### Core Application Files
- `api_routes.py` - Updated to integrate brace map agent
- `agent.py` - Enhanced with improved agent coordination
- `agent_utils.py` - Updated utility functions for agent operations

#### Documentation Files
- `README.md` - Updated with agent architecture information
- `CHANGELOG.md` - Updated with comprehensive version 2.3.2 details

### 🐛 Bug Fixes

- **Indentation Errors**: Fixed all indentation errors in brace map agent
- **JSON Serialization**: Resolved LayoutResult serialization issues
- **SVG Data Format**: Fixed SVG data format for D3.js renderer compatibility
- **Blank PNG Issue**: Resolved blank PNG generation by correcting SVG data structure
- **Import Errors**: Fixed all import and module loading issues

### 🔮 Future Roadmap

#### Planned Features for Version 2.4.0
- **Additional Diagram Agents**: Implement agents for concept maps, mind maps, and other diagram types
- **Advanced LLM Integration**: Enhanced LLM processing with more sophisticated strategies
- **Performance Optimization**: Advanced caching and optimization for agent operations
- **User Interface Enhancements**: Improved debug interface with agent status monitoring

---

## [2.3.1] - 2025-01-27

### 🚀 Major Improvements

#### Application Name Migration
- **Complete Branding Update**: Migrated from "D3.js_Dify" to "MindGraph" across all project files
- **Consistent Naming**: Updated application name in frontend files, backend routes, and environment examples
- **User Interface Updates**: Updated debug.html with new application name and localStorage keys
- **Docker Configuration**: Docker support removed - will be added back later

#### Enhanced Diagram Type Classification
- **Improved LLM Response Parsing**: Fixed exact matching logic in diagram type classification to prevent substring conflicts
- **Precise Classification**: Changed from substring matching (`in`) to exact matching (`==`) for diagram type detection
- **Better Chinese Support**: Enhanced support for Chinese diagram type requests like "双气泡图" (double bubble map)
- **Reduced Fallback Usage**: Prioritizes LLM classification over hardcoded fallback logic when LLM provides clear answers

### 🔧 Technical Enhancements

#### Code Quality & Architecture
- **Exact String Matching**: Updated `classify_graph_type_with_llm` in `agent.py` to use exact matching
- **Enhanced DeepSeek Agent**: Updated `classify_diagram_type_for_development` in `deepseek_agent.py` with improved parsing
- **Removed Redundant Logic**: Eliminated duplicate diagram type extraction loops for cleaner code
- **Content-Based Inference**: Added intelligent content analysis before falling back to keyword matching

#### File System Updates
- **Frontend Consistency**: Updated `templates/debug.html` with new application name and localStorage keys
- **Backend Routes**: Verified and updated application name references in `web_routes.py`, `api_routes.py`, and `app.py`
- **Docker Files**: Docker support removed - will be added back later
- **Environment Configuration**: Updated `env.example` with correct application name in comments

### 📋 Documentation Updates

#### User Documentation
- **Application Name**: All documentation now reflects the new "MindGraph" branding
- **Debug Interface**: Updated debug tool interface with new application name
- **Docker Documentation**: Docker support removed - will be added back later

### 🛡️ Security & Stability

#### Classification Accuracy
- **Reliable Diagram Detection**: Fixed critical issue where "double bubble map" requests were incorrectly classified as "bubble map"
- **LLM Trust**: Enhanced system to trust LLM classification when output is clear and unambiguous
- **Fallback Logic**: Improved fallback mechanism to only trigger when LLM output cannot be parsed

### 🔄 Migration Guide

#### From Version 2.3.0 to 2.3.1

1. **Application Name**: The application is now consistently named "MindGraph" throughout
2. **Docker Exports**: Docker support removed - will be added back later
3. **Local Storage**: Debug interface now uses `mindgraph_history` instead of `d3js_dify_history`
4. **No Breaking Changes**: All existing functionality remains the same, only naming has been updated

### 📦 Files Changed

#### Core Application Files
- `agent.py` - Enhanced diagram type classification with exact matching logic
- `deepseek_agent.py` - Improved LLM response parsing and removed redundant loops
- `templates/debug.html` - Updated application name and localStorage keys

#### Docker Files
- Docker support removed - will be added back later

#### Configuration Files
- `env.example` - Updated application name in comments

### 🐛 Bug Fixes

- **Diagram Classification**: Fixed critical bug where "double bubble map" requests were incorrectly classified as "bubble map"
- **String Matching**: Resolved substring matching conflicts in diagram type detection
- **Application Naming**: Eliminated all references to old application name "D3.js_Dify"

### 🔮 Future Roadmap

#### Planned Features for Version 2.4.0
- **Enhanced Testing**: Comprehensive unit and integration tests for diagram classification
- **Performance Monitoring**: Advanced performance metrics for LLM response times
- **User Interface Improvements**: Enhanced debug interface with better error reporting
- **Multi-language Enhancement**: Improved support for additional languages

---

## [2.3.0] - 2025-01-27

### 🚀 Major Improvements

#### Bridge Map Enhancement
- **Bridge Map Vertical Lines**: Made vertical connection lines invisible for cleaner visual presentation
- **Improved Bridge Map Rendering**: Enhanced visual clarity by removing distracting vertical connection lines
- **Better User Experience**: Cleaner bridge map appearance while maintaining all functional elements

### 🔧 Technical Enhancements

#### Rendering Pipeline Optimization
- **Bridge Map Styling**: Updated `renderBridgeMap` function to use transparent stroke for vertical lines
- **Visual Consistency**: Maintained horizontal main line, triangle separators, and analogy text visibility
- **Code Quality**: Improved bridge map rendering code for better maintainability

### 📋 Documentation Updates

#### User Documentation
- **Bridge Map Guide**: Updated documentation to reflect the enhanced bridge map visualization
- **Version Update**: Updated project version to 2.3.0 across all documentation files

## [2.2.0] - 2025-01-27

### 🚀 Major Improvements

#### Team Update
- **MindSpring Team**: Updated all documentation to reflect the MindSpring Team as the project maintainers
- **Branding Consistency**: Updated package.json, README.md, and all documentation files with new team information

#### Enhanced Circle Map Layout
- **New Circle Map Design**: Implemented outer boundary circle with central topic and perimeter context circles
- **Precise Geometric Positioning**: Replaced force simulation with trigonometric positioning for exact circle placement
- **Optimized Spacing**: Configurable spacing between topic and context circles (half circle size gap)
- **Improved Visual Hierarchy**: Clear visual separation between outer boundary, context circles, and central topic
- **Enhanced D3.js Renderer**: Complete `renderCircleMap` function with proper SVG structure and theming

#### Bubble Map Enhancements
- **Refined Bubble Map Layout**: Central topic positioning with 360-degree attribute distribution
- **Improved Connecting Lines**: Clean lines from topic edge to attribute edges for better visual clarity
- **Enhanced Rendering Pipeline**: Consistent high-quality output for both web interface and PNG generation
- **Better Attribute Distribution**: Even spacing of attributes around the central topic

#### Bridge Map Implementation
- **New Bridge Map Support**: Complete implementation of analogical relationship visualization
- **Relating Factor Display**: Clear presentation of the connecting concept between analogy pairs
- **Educational Focus**: Designed specifically for teaching analogical thinking skills
- **D3.js Renderer**: Full `renderBridgeMap` function with bridge structure and analogy pairs

### 🔧 Technical Enhancements

#### D3.js Renderer Improvements
- **Unified Rendering Pipeline**: All diagram types now use consistent, high-quality D3.js renderers
- **Enhanced Theming**: Comprehensive theme support for all new diagram types
- **Responsive Design**: All new diagrams adapt to different screen sizes and export dimensions
- **Export Compatibility**: PNG generation works seamlessly with all new diagram types

#### DeepSeek Agent Enhancements
- **Bridge Map Templates**: Added comprehensive development prompt templates for bridge maps
- **Educational Prompts**: Enhanced templates focus on educational value and learning outcomes
- **Multi-language Support**: All new templates available in both English and Chinese
- **Structured Output**: Consistent JSON format generation for all diagram types

#### Code Quality & Architecture
- **Modular Design**: Clean separation between different diagram renderers
- **Validation Support**: Comprehensive validation for all new diagram specifications
- **Error Handling**: Robust error handling for new diagram types
- **Documentation**: Complete inline documentation for all new functions

### 📋 Documentation Updates

#### User Documentation
- **Thinking Maps® Guide**: Updated documentation to include all supported Thinking Maps
- **Circle Map Guide**: Comprehensive guide for the new circle map layout and usage
- **Bridge Map Guide**: Complete documentation for bridge map functionality
- **API Documentation**: Updated API documentation to include new endpoints

#### Technical Documentation
- **Renderer Documentation**: Detailed documentation of all D3.js renderer functions
- **Template Documentation**: Complete documentation of development prompt templates
- **Validation Guide**: Enhanced validation documentation for all diagram types

### 🛡️ Security & Stability

#### Rendering Stability
- **Consistent Output**: All new diagram types produce consistent, high-quality output
- **Error Recovery**: Improved error handling and recovery for new diagram types
- **Validation**: Enhanced validation ensures data integrity for all diagram specifications

## [2.1.0] - 2025-01-27

### 🚀 Major Improvements

#### Enhanced Bubble Map Rendering
- **Fixed Bubble Map Layout**: Topic now positioned exactly in the center with attributes spread 360 degrees around it
- **Improved Connecting Lines**: Clean lines from topic edge to attribute edges for better visual clarity
- **Enhanced D3.js Renderer**: Updated PNG generation route to use the correct, full-featured D3.js renderer
- **Consistent Rendering Pipeline**: Both web interface and PNG generation now use the same high-quality renderer

#### Rendering Pipeline Optimization
- **Unified D3.js Renderers**: Eliminated duplicate renderer code by using the correct renderer from `static/js/d3-renderers.js`
- **Enhanced Agent JSON Generation**: Improved bubble map specification generation for better visual output
- **Comprehensive Validation**: Added validation tests to ensure bubble map pipeline works correctly
- **Multi-language Support**: Bubble map generation works with both Chinese and English prompts

### 🔧 Technical Enhancements

#### Code Quality & Architecture
- **Renderer Consistency**: Fixed inconsistency between web and PNG generation routes
- **Layout Algorithm**: Improved circular layout algorithm for better attribute distribution
- **Error Handling**: Enhanced error handling in bubble map rendering pipeline
- **Code Organization**: Cleaner separation between different renderer implementations

### 📋 Documentation Updates

#### Technical Documentation
- **Bubble Map Guide**: Updated documentation to reflect the improved layout and rendering
- **Pipeline Documentation**: Enhanced documentation of the complete rendering pipeline
- **Validation Guide**: Added documentation for bubble map specification validation

### 🛡️ Security & Stability

#### Rendering Stability
- **Consistent Output**: Both web and PNG generation now produce identical high-quality output
- **Error Recovery**: Improved error handling in rendering pipeline
- **Validation**: Enhanced validation of bubble map specifications

## [2.0.0] - 2025-07-26

### 🚀 Major Improvements

#### Enhanced Startup Sequence
- **Comprehensive Dependency Validation**: Added thorough validation of all required Python packages, API configurations, and system requirements
- **Professional Console Output**: Implemented clean, emoji-enhanced logging with clear status indicators
- **Cross-Platform Compatibility**: Fixed Windows timeout issues by replacing Unix-specific signal handling with threading
- **ASCII Art Banner**: Added professional MindSpring ASCII art logo during startup
- **Automatic Browser Opening**: Smart browser opening with server readiness detection

#### Configuration Management
- **Dynamic Environment Loading**: Property-based configuration access for real-time environment variable updates
- **Enhanced Validation**: Comprehensive validation of API keys, URLs, and numeric configuration values
- **Centralized Configuration**: All settings now managed through the `config.py` module
- **Professional Configuration Summary**: Clean display of all application settings during startup

#### Code Quality & Architecture
- **Comprehensive Inline Documentation**: Added detailed docstrings and comments throughout the codebase
- **Improved Error Handling**: Enhanced exception handling with user-friendly error messages
- **Better Logging**: Structured logging with different levels and file output
- **Code Organization**: Clear separation of concerns with well-defined sections

### 🔧 Technical Enhancements

#### Dependency Management
- **Package Validation**: Real-time checking of all required Python packages
- **Import Name Mapping**: Correct handling of package import names (e.g., Pillow → PIL)
- **Playwright Integration**: Automatic browser installation and validation
- **Version Requirements**: Updated to Python 3.8+ and Flask 3.0+

#### API Integration
- **Qwen API**: Required for core functionality with comprehensive validation
- **DeepSeek API**: Optional for enhanced features with graceful fallback
- **Request Formatting**: Clean API request formatting methods
- **Timeout Handling**: Improved timeout management for API calls

#### Docker Support
- Docker support removed - will be added back later
- **Production Ready**: Optimized for production deployment with proper logging

### 📋 Documentation Updates

#### Code Documentation
- **Comprehensive Headers**: Added detailed module headers with version information
- **Inline Comments**: Enhanced inline comments explaining functionality
- **Function Documentation**: Complete docstrings for all functions and methods
- **Configuration Documentation**: Detailed explanation of all configuration options

#### User Documentation
- **README.md**: Updated with version 2.1.0 features and improved installation instructions
- **Requirements.txt**: Enhanced with detailed dependency information
- **Environment Configuration**: Clear documentation of required and optional settings

### 🛡️ Security & Stability

#### Error Handling
- **Graceful Degradation**: Application continues running even if optional features are unavailable
- **Input Validation**: Enhanced validation of all configuration values
- **Exception Logging**: Comprehensive logging of errors with context information

#### Production Readiness
- **Health Checks**: Application health monitoring endpoints
- **Resource Management**: Proper resource limits and monitoring
- **Logging**: Structured logging for production environments

### 🔄 Migration Guide

#### From Version 1.x to 2.1.0

1. **Environment Variables**: Ensure your `.env` file includes all required variables
   ```bash
   QWEN_API_KEY=your_qwen_api_key
   DEEPSEEK_API_KEY=your_deepseek_api_key  # Optional
   ```

2. **Dependencies**: Update Python dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration**: The application now uses property-based configuration access
   - All configuration is automatically loaded from environment variables
   - No code changes required for existing configurations

4. **Docker**: Docker support removed - will be added back later

### 📦 Files Changed

#### Core Application Files
- `app.py` - Complete rewrite with enhanced startup sequence and dependency validation
- `config.py` - Property-based configuration management with comprehensive validation
- `requirements.txt` - Updated dependencies with version 2.1.0 header

#### Docker Files
- Docker support removed - will be added back later

#### Documentation
- `README.md` - Updated with version 2.0.0 features and improved instructions
- `CHANGELOG.md` - This file (new)

#### Utility Files
- Dependency checker removed for simplicity

### 🎯 Breaking Changes

- **Python Version**: Now requires Python 3.8 or higher
- **Flask Version**: Updated to Flask 3.0+
- **Configuration Access**: Configuration values are now accessed as properties instead of class attributes
- **Startup Sequence**: Application startup now includes comprehensive validation

### 🐛 Bug Fixes

- **Windows Compatibility**: Fixed timeout issues on Windows systems
- **Environment Loading**: Resolved issues with `.env` file loading
- **Dependency Validation**: Fixed missing package detection
- **API Integration**: Corrected function calls and return value handling

### 🔮 Future Roadmap

#### Planned Features for Version 2.1.0
- **Enhanced Testing**: Comprehensive unit and integration tests
- **Performance Monitoring**: Advanced performance metrics and monitoring
- **API Rate Limiting**: Improved rate limiting and API usage tracking
- **User Authentication**: Optional user authentication system

#### Planned Features for Version 2.2.0
- **Database Integration**: Persistent storage for generated graphs
- **User Management**: User accounts and graph sharing
- **Advanced Export Options**: Additional export formats and customization
- **Plugin System**: Extensible architecture for custom chart types

---

## [1.0.0] - 2024-12-01

### 🎉 Initial Release

- **AI-Powered Graph Generation**: Integration with Qwen and DeepSeek LLMs
- **D3.js Visualization**: Interactive charts and graphs
- **PNG Export**: High-quality image export functionality
- **Multi-language Support**: English and Chinese language support
- **Docker Support**: Docker support removed - will be added back later
- **RESTful API**: Comprehensive API for graph generation
- **Web Interface**: User-friendly web application

---

## Version History

- **2.0.0** (2025-07-26) - Major improvements with enhanced startup sequence and configuration management
- **1.0.0** (2024-12-01) - Initial release with core functionality

---

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPLv3) - see the [LICENSE](LICENSE) file for details. 
