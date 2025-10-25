# Brace Map & Flow Map Code Review and Fix Plan

**Date:** 2025-10-19  
**Status:** 🔍 CODE REVIEW COMPLETE - FIXES NEEDED  
**Purpose:** Detailed analysis of Brace Map and Flow Map issues with fix recommendations based on Tree Map and Double Bubble Map implementations

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Brace Map Code Review](#brace-map-code-review)
4. [Flow Map Code Review](#flow-map-code-review)
5. [Comparison with Working Implementations](#comparison-with-working-implementations)
6. [Fix Plan for Brace Map](#fix-plan-for-brace-map)
7. [Fix Plan for Flow Map](#fix-plan-for-flow-map)
8. [Implementation Checklist](#implementation-checklist)

---

## Executive Summary

### Current Status

**Brace Map**: ❌ Missing Multi-Stage Workflow  
**Flow Map**: ❌ Missing Multi-Stage Workflow

Both diagram types have the same fundamental issues that Tree Map had before its multi-stage implementation. They lack:
- Stage-based generation workflow
- Dynamic tab management
- Stage persistence on reopen
- Structured node assembly

### Issues Identified

| Issue | Brace Map | Flow Map | Tree Map (Reference) |
|-------|-----------|----------|----------------------|
| Multi-stage workflow | ❌ No | ❌ No | ✅ Yes (3 stages) |
| Tab support | ❌ No | ❌ No | ✅ Yes (dynamic) |
| Stage persistence | ❌ No | ❌ No | ✅ Yes |
| Node routing | ❌ Basic | ❌ Basic | ✅ Advanced |
| ThinkGuide stage awareness | ❌ No | ❌ No | ✅ Yes |
| Auto-loading | ❌ No | ❌ No | ✅ Yes |
| Smart node assembly | ❌ Basic | ❌ Basic | ✅ Advanced |

---

## Problem Statement

### The Core Issue

Brace Map and Flow Map suffer from the same problems that Tree Map had:

1. **Single-stage generation**: All nodes generated in one batch, no progressive workflow
2. **No structure guidance**: Users can't define the decomposition approach first
3. **No incremental building**: Must restart from scratch if palette is reopened
4. **No stage persistence**: State is lost when palette closes
5. **Basic node assembly**: No hierarchical structure building

### Why This Matters

**Pedagogical Impact**:
- Brace Maps should guide "whole → parts → sub-parts" thinking
- Flow Maps should guide "process definition → step sequence" thinking
- Without stages, users can't follow proper thinking frameworks

**User Experience Impact**:
- Frustration from restarting workflows
- Lost context when reopening palette
- No clear guidance on thinking progression

---

## Brace Map Code Review

### Current Implementation Analysis

#### 1. Frontend Configuration

**Location**: `static/js/editor/node-palette-manager.js` (lines 141-146)

**Current State**:
```javascript
'brace_map': {
    arrayName: 'parts',
    nodeName: 'part',
    nodeNamePlural: 'parts',
    nodeType: 'part'
}
```

**Issues**:
- ❌ No `useTabs: true`
- ❌ No `useStages: true`
- ❌ No `arrays` object for multi-array support
- ❌ Single flat array, no structure

**What's Missing**:
```javascript
// Should be:
'brace_map': {
    arrays: {
        'whole': { nodeName: 'whole', ... },
        'parts': { nodeName: 'part', ... },
        // Dynamic tabs for sub-parts per part
    },
    useTabs: true,
    useStages: true  // ❌ MISSING
}
```

---

#### 2. Backend Palette Generator

**Location**: `agents/thinking_modes/node_palette/brace_map_palette.py`

**Current State**:
```python
class BraceMapPaletteGenerator(BasePaletteGenerator):
    """
    Brace Map specific palette generator.
    
    Generates part/component nodes for Brace Maps.
    """
    
    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        # Single-stage prompt only
        # No stage parameter
        # No stage_data handling
```

**Issues**:
- ❌ No `generate_batch()` override with `stage` and `stage_data` parameters
- ❌ No stage-specific prompt methods (`_build_whole_prompt`, `_build_parts_prompt`, `_build_subparts_prompt`)
- ❌ No `session_stages` tracking (like Tree Map)
- ❌ No node tagging with `mode` field for dynamic tab routing
- ❌ No `end_session()` override for cleanup

**Comparison with Tree Map**:

| Feature | Brace Map | Tree Map |
|---------|-----------|----------|
| `generate_batch` override | ❌ No | ✅ Yes (lines 41-100) |
| `session_stages` tracking | ❌ No | ✅ Yes (line 39) |
| Stage-specific prompts | ❌ No | ✅ Yes (3 methods) |
| Node `mode` tagging | ❌ No | ✅ Yes (lines 89-99) |
| Stage data persistence | ❌ No | ✅ Yes |

---

#### 3. ThinkGuide Agent

**Location**: `agents/thinking_modes/brace_map_agent_react.py`

**Current State**:
```python
async def _handle_open_node_palette(self, session: Dict):
    """Handle opening Node Palette for Brace Map"""
    diagram_data = session['diagram_data']
    language = session.get('language', 'en')
    center_topic = diagram_data.get('whole', 'Unknown Whole')
    current_node_count = len(diagram_data.get('parts', []))
    
    # Generic acknowledgment - no stage awareness
    if language == 'zh':
        ack_prompt = f"用户想要打开节点选择板，为「{center_topic}」头脑风暴更多组成部分。"
```

**Issues**:
- ❌ No stage detection (no check for whole vs parts vs subparts)
- ❌ No stage-specific guidance messages
- ❌ No stage data passed to Node Palette action
- ❌ Generic message regardless of diagram state

**Comparison with Tree Map**:

| Feature | Brace Map | Tree Map |
|---------|-----------|----------|
| Stage detection | ❌ No | ✅ Yes (checks dimension, categories) |
| Stage-specific messages | ❌ No | ✅ Yes (3 different messages) |
| Stage data in action | ❌ No | ✅ Yes (dimension, categories) |
| User guidance clarity | ❌ Low | ✅ High |

---

### Brace Map Architectural Problems

#### Problem 1: No Whole-Parts Hierarchy

**Current Flow**:
1. User opens palette
2. Generates "parts" in one batch
3. Adds parts to diagram
4. **No guidance on decomposition dimension**

**Should Be** (Like Tree Map):
1. Stage 1: Define the whole (or select decomposition approach)
2. Stage 2: Generate main parts
3. Stage 3: For each part, generate sub-parts (dynamic tabs)

**Pedagogical Issue**: 
- Brace Maps teach "whole-to-parts" decomposition
- Without stages, users don't follow this thinking pattern
- Missing the "decomposition dimension" selection (like "by physical structure" vs "by function")

---

#### Problem 2: No Persistence

**Current Behavior**:
1. User creates Brace Map: whole="汽车", parts=["发动机", "车身", "底盘"]
2. User closes palette
3. User reopens palette
4. **❌ Palette resets to empty state**

**Should Be** (Like Tree Map Stage 3):
1. Reopen should detect existing parts
2. Should open directly to "add sub-parts" stage
3. Should show tabs for each part (发动机, 车身, 底盘)
4. Allow incremental additions to each part

---

## Flow Map Code Review

### Current Implementation Analysis

#### 1. Frontend Configuration

**Location**: `static/js/editor/node-palette-manager.js` (approx lines 147-152)

**Expected State** (need to verify):
```javascript
'flow_map': {
    arrayName: 'steps',
    nodeName: 'step',
    nodeNamePlural: 'steps',
    nodeType: 'step'
}
```

**Issues** (likely same as Brace Map):
- ❌ No `useTabs: true`
- ❌ No `useStages: true`
- ❌ No stage-based workflow
- ❌ No step ordering mechanism

---

#### 2. Backend Palette Generator

**Location**: `agents/thinking_modes/node_palette/flow_map_palette.py`

**Current State**:
```python
class FlowMapPaletteGenerator(BasePaletteGenerator):
    """
    Flow Map specific palette generator.
    
    Generates process step nodes for Flow Maps.
    """
    
    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        # Single-stage prompt only
        # No sequence number handling
        # No process definition stage
```

**Issues**:
- ❌ No multi-stage support
- ❌ No step sequencing/ordering
- ❌ No process definition stage
- ❌ Steps generated without clear process context

**Critical Missing Feature**: **Step Ordering**
- Flow Maps are sequential by nature
- Currently no mechanism to maintain step order
- Should have sequence numbers or drag-and-drop reordering

---

#### 3. ThinkGuide Agent

**Location**: `agents/thinking_modes/flow_map_agent_react.py`

**Current State**:
```python
async def _handle_open_node_palette(self, session: Dict):
    """Handle opening Node Palette for Flow Map"""
    diagram_data = session['diagram_data']
    center_topic = diagram_data.get('title', 'Unknown Event')
    current_node_count = len(diagram_data.get('steps', []))
    
    # Generic acknowledgment
    if language == 'zh':
        ack_prompt = f"用户想要打开节点选择板，为「{center_topic}」头脑风暴更多流程步骤。"
```

**Issues**:
- ❌ No stage detection
- ❌ No process definition guidance
- ❌ No mention of step ordering importance
- ❌ Generic message regardless of state

---

### Flow Map Architectural Problems

#### Problem 1: No Process-Steps Hierarchy

**Current Flow**:
1. User opens palette
2. Generates "steps" in one batch
3. **No clear process definition**
4. **No step ordering guidance**

**Should Be**:
1. Stage 1: Define the process/event clearly
2. Stage 2: Generate sequential steps with ordering
3. Stage 3 (optional): Add sub-steps or details per step

**Pedagogical Issue**:
- Flow Maps teach sequential, procedural thinking
- Without process definition, steps may be incoherent
- Without ordering, sequence is lost

---

#### Problem 2: No Step Sequencing

**Critical Issue**:
- Steps must be ordered (1 → 2 → 3 → ...)
- Current implementation has no sequence tracking
- Users can't reorder steps after generation
- Drag-and-drop reordering not implemented

**Should Have**:
```javascript
// Each node should have sequence number
node['sequence'] = 1, 2, 3, ...

// Frontend should support:
- Drag-and-drop reordering
- Visual sequence indicators
- Auto-numbering on add
```

---

## Comparison with Working Implementations

### Tree Map (Multi-Stage) - Reference Implementation

**What Works Well**:

1. **Stage Management**:
   - ✅ 3 clear stages (dimensions → categories → children)
   - ✅ Stage detection on reopen
   - ✅ Stage data persistence
   - ✅ Stage progression with validation

2. **Dynamic Tabs**:
   - ✅ Creates tabs based on user selections (Stage 3)
   - ✅ Tab locking prevents modifications
   - ✅ Per-tab scroll position memory
   - ✅ Per-tab node storage

3. **Node Tagging**:
   - ✅ Nodes tagged with `mode` field
   - ✅ Routes nodes to correct tabs
   - ✅ Supports dynamic tab names (not hardcoded)

4. **ThinkGuide Integration**:
   - ✅ Stage-specific guidance messages
   - ✅ Clear instructions per stage
   - ✅ Sets proper expectations

**Code Patterns to Replicate**:

```python
# Backend: Stage-based generation
async def generate_batch(
    self,
    session_id: str,
    center_topic: str,
    educational_context: Optional[Dict[str, Any]] = None,
    nodes_per_llm: int = 15,
    stage: str = 'categories',  # ✅ Stage parameter
    stage_data: Optional[Dict[str, Any]] = None  # ✅ Stage data
):
    # Store stage info
    self.session_stages[session_id] = {'stage': stage, **stage_data}
    
    # Tag nodes with mode
    node['mode'] = stage_data.get('category_name') if stage == 'children' else stage
```

```javascript
// Frontend: Stage detection
if (!hasDimension) {
    this.currentStage = 'dimensions';
} else if (realCategories.length === 0) {
    this.currentStage = 'categories';
} else {
    this.currentStage = 'children';
    // Extract category names and create dynamic tabs
}
```

---

### Double Bubble Map (2-Tab) - Reference for Brace/Flow

**What Works Well**:

1. **Mode-Based Generation**:
   - ✅ 2 modes: similarities and differences
   - ✅ Mode passed through `educational_context` (thread-safe)
   - ✅ Nodes tagged with `mode` field
   - ✅ Concurrent loading for both tabs

2. **Tab Management**:
   - ✅ 2 fixed tabs (not dynamic)
   - ✅ Per-tab node storage
   - ✅ Per-tab selection tracking
   - ✅ Per-tab scroll position

3. **Node Routing**:
   - ✅ Validates `node.mode` matches `targetMode`
   - ✅ Skips mismatched nodes
   - ✅ Adds to correct tab storage

**Why This Is Relevant for Brace/Flow**:
- Brace Map could use 2 tabs: "Main Parts" and "Sub-Parts" 
- Flow Map could use 2 tabs: "Process" and "Steps"
- Both can learn from Double Bubble's tab management

**Code Pattern to Replicate**:

```python
# Double Bubble: Mode handling
def generate_batch(self, session_id, center_topic, mode='similarities'):
    # Pass mode through educational_context (thread-safe!)
    educational_context['_mode'] = mode
    
    # In _build_prompt:
    mode = educational_context.get('_mode', 'similarities')
    
    # Tag nodes
    node['mode'] = mode
```

```javascript
// Frontend: Tab switching with node routing
switchTab(tabName) {
    // Save current tab scroll position
    this.tabScrollPositions[this.currentTab] = container.scrollTop;
    
    // Switch tab
    this.currentTab = tabName;
    
    // Restore scroll position
    container.scrollTop = this.tabScrollPositions[tabName] || 0;
}
```

---

## Fix Plan for Brace Map

### Recommended Architecture: 2-Stage Workflow

**Stage 1: Whole Definition** (Optional, for clarity)
- Generate clear "whole" descriptions or decomposition approaches
- User selects 1 whole definition
- Example: "汽车" → Decompose by "Physical Structure" vs "Functional Systems"

**Stage 2: Main Parts Generation**
- Generate main parts for the whole
- User selects multiple parts
- Lock Stage 1

**Stage 3: Sub-Parts Generation** (Dynamic Tabs)
- Create dynamic tabs (one per selected part)
- Generate sub-parts for each part
- Concurrent loading (N parts × 4 LLMs)

**Alternative Simpler Approach**: 2-Stage

**Stage 1: Main Parts** (Current behavior, but structured)
- Generate main parts
- User selects parts

**Stage 2: Sub-Parts per Part** (Dynamic Tabs)
- Dynamic tabs for each selected part
- Generate sub-parts for specific part

---

### Implementation Steps for Brace Map

#### Step 1: Update Backend Palette Generator

**File**: `agents/thinking_modes/node_palette/brace_map_palette.py`

**Changes Needed**:

```python
class BraceMapPaletteGenerator(BasePaletteGenerator):
    """
    Brace Map specific palette generator with multi-stage workflow.
    
    Stages:
    - parts: Generate main parts (default stage)
    - subparts: Generate sub-parts for specific part
    """
    
    def __init__(self):
        super().__init__()
        # Track stage data per session
        self.session_stages = {}  # ✅ ADD THIS
    
    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        stage: str = 'parts',  # ✅ ADD STAGE PARAMETER
        stage_data: Optional[Dict[str, Any]] = None  # ✅ ADD STAGE_DATA
    ) -> AsyncGenerator[Dict, None]:
        """Generate batch with stage-specific logic."""
        
        # Store stage info
        if session_id not in self.session_stages:
            self.session_stages[session_id] = {}
        self.session_stages[session_id]['stage'] = stage
        if stage_data:
            self.session_stages[session_id].update(stage_data)
        
        # Pass session_id through educational_context
        if educational_context is None:
            educational_context = {}
        educational_context = {**educational_context, '_session_id': session_id}
        
        # Call parent
        async for event in super().generate_batch(
            session_id=session_id,
            center_topic=center_topic,
            educational_context=educational_context,
            nodes_per_llm=nodes_per_llm
        ):
            # Tag nodes with mode
            if event.get('event') == 'node_generated':
                node = event.get('node', {})
                
                # For subparts stage, use part_name as mode
                if stage == 'subparts' and stage_data and stage_data.get('part_name'):
                    node_mode = stage_data['part_name']
                else:
                    node_mode = stage
                
                node['mode'] = node_mode
            
            yield event
    
    def _build_prompt(self, center_topic, educational_context, count, batch_num):
        """Build stage-specific prompt."""
        
        # Get session_id from context
        session_id = educational_context.get('_session_id') if educational_context else None
        stage = 'parts'  # default
        stage_data = {}
        
        if session_id and session_id in self.session_stages:
            stage = self.session_stages[session_id].get('stage', 'parts')
            stage_data = self.session_stages[session_id]
        
        # Build stage-specific prompt
        if stage == 'parts':
            return self._build_parts_prompt(center_topic, educational_context, count, batch_num)
        elif stage == 'subparts':
            part_name = stage_data.get('part_name', '')
            return self._build_subparts_prompt(center_topic, part_name, educational_context, count, batch_num)
        else:
            return self._build_parts_prompt(center_topic, educational_context, count, batch_num)
    
    def _build_parts_prompt(self, center_topic, educational_context, count, batch_num):
        """Build prompt for generating main parts."""
        # EXISTING CODE (keep as is)
        pass
    
    def _build_subparts_prompt(self, center_topic, part_name, educational_context, count, batch_num):
        """Build prompt for generating sub-parts for specific part."""
        language = educational_context.get('language', 'en') if educational_context else 'en'
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'
        
        if language == 'zh':
            prompt = f"""为整体"{center_topic}"的部分"{part_name}"生成{count}个子部件或组成成分

教学背景：{context_desc}

你能够绘制括号图，进一步分解"{part_name}"这个部分，展示它的更细致的组成。

要求：
1. 所有子部件必须属于"{part_name}"这个部分
2. 子部件要具体、清晰、有代表性
3. 使用名词或名词短语，2-8个字
4. 只输出子部件名称，每行一个，不要编号

为"{part_name}"生成{count}个子部件："""
        else:
            prompt = f"""Generate {count} sub-components for part "{part_name}" of whole: {center_topic}

Educational Context: {context_desc}

You can draw a brace map to further decompose the part "{part_name}" and show its finer components.

Requirements:
1. All sub-components MUST belong to the part "{part_name}"
2. Sub-components should be specific, clear, and representative
3. Use nouns or noun phrases, 2-8 words
4. Output only sub-component names, one per line, no numbering

Generate {count} sub-components for "{part_name}":"""
        
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。提供更多不同的子部件，避免重复。"
            else:
                prompt += f"\n\nNote: Batch {batch_num}. Provide more diverse sub-components, avoid repetition."
        
        return prompt
    
    def end_session(self, session_id: str, reason: str = "complete"):
        """Clean up session including stage tracking."""
        self.session_stages.pop(session_id, None)
        super().end_session(session_id, reason)
```

---

#### Step 2: Update Frontend Configuration

**File**: `static/js/editor/node-palette-manager.js`

**Change**:
```javascript
// BEFORE:
'brace_map': {
    arrayName: 'parts',
    nodeName: 'part',
    nodeNamePlural: 'parts',
    nodeType: 'part'
}

// AFTER:
'brace_map': {
    arrays: {
        'parts': {
            nodeName: 'part',
            nodeNamePlural: 'parts',
            nodeType: 'part'
        }
        // Dynamic tabs for sub-parts will be added at runtime
    },
    arrayName: 'parts',  // Default for backward compatibility
    nodeName: 'part',
    nodeNamePlural: 'parts',
    nodeType: 'part',
    useTabs: true,  // ✅ ENABLE TABS
    useStages: true  // ✅ ENABLE STAGES
}
```

---

#### Step 3: Add Stage Detection in `start()`

**Location**: `static/js/editor/node-palette-manager.js` (in `start()` method, after tree_map stage detection)

**Add**:
```javascript
// Add after tree_map stage detection (around line 1000)
else if (this.diagramType === 'brace_map') {
    // Brace map: 2-stage workflow (parts → subparts per part)
    firstTab = 'parts';
    
    // Determine initial stage based on diagram data
    const hasParts = diagramData && diagramData.parts && diagramData.parts.length > 0;
    
    // Filter out empty parts
    const realParts = hasParts 
        ? diagramData.parts.filter(part => part.text && part.text.trim().length > 0)
        : [];
    
    if (realParts.length === 0) {
        // Stage 1: Main Parts Generation
        this.currentStage = 'parts';
        this.currentTab = 'parts';
    } else {
        // Stage 2: Sub-Parts Generation (REOPEN CASE)
        this.currentStage = 'subparts';
        
        // Extract part names from diagram data
        const partNames = realParts.map(part => part.text);
        this.stageData.parts = partNames;
        
        // Set current tab to first part
        this.currentTab = partNames[0];
        
        console.log(`[NodePalette-BraceMap] Reopening at Stage 2 (subparts) with ${partNames.length} parts`);
    }
}
```

---

#### Step 4: Add Dynamic Tab Creation for Brace Map

**Location**: Same `start()` method, in tab initialization section (around line 1016)

**Add**:
```javascript
// Add in the tab initialization section
if (this.diagramType === 'brace_map' && this.currentStage === 'subparts' && this.stageData.parts && this.stageData.parts.length > 0) {
    // Stage 2: Initialize dynamic part tabs
    const partNames = this.stageData.parts;
    const dynamicTabNodes = {};
    const dynamicTabSelectedNodes = {};
    const dynamicTabScrollPositions = {};
    
    partNames.forEach(partName => {
        dynamicTabNodes[partName] = [];
        dynamicTabSelectedNodes[partName] = new Set();
        dynamicTabScrollPositions[partName] = 0;
    });
    
    // Include locked tabs from previous stage
    this.tabNodes = {
        parts: [],
        ...dynamicTabNodes  // ✅ 发动机, 车身, 底盘, etc.
    };
    
    this.tabSelectedNodes = {
        parts: new Set(),
        ...dynamicTabSelectedNodes
    };
    
    this.tabScrollPositions = {
        parts: 0,
        ...dynamicTabScrollPositions
    };
    
    console.log(`[NodePalette-BraceMap] Created ${partNames.length} dynamic tabs: ${partNames.join(', ')}`);
}
```

---

#### Step 5: Update ThinkGuide Agent

**File**: `agents/thinking_modes/brace_map_agent_react.py`

**Update `_handle_open_node_palette` method**:

```python
async def _handle_open_node_palette(self, session: Dict) -> AsyncGenerator[Dict, None]:
    """Handle opening Node Palette for Brace Map with stage awareness"""
    diagram_data = session['diagram_data']
    language = session.get('language', 'en')
    center_topic = diagram_data.get('whole', 'Unknown Whole')
    parts = diagram_data.get('parts', [])
    
    # Detect current stage
    has_parts = len(parts) > 0
    real_parts = [p for p in parts if p.get('text') and p['text'].strip()]
    has_real_parts = len(real_parts) > 0
    
    if not has_real_parts:
        # Stage 1: Main Parts Generation
        if language == 'zh':
            ack_prompt = f"好的！节点调色板即将打开。\n\n让我们为整体「{center_topic}」生成主要组成部分。请选择你想要的部分，然后点击\"完成\"添加到图中。\n\n系统将使用4个AI模型同时生成创意想法。"
        else:
            ack_prompt = f"Okay! Opening Node Palette.\n\nLet's generate main parts for \"{center_topic}\". Select the parts you want, then click \"Finish\" to add them to the diagram.\n\nThe system will use 4 AI models simultaneously to generate creative ideas."
    else:
        # Stage 2: Sub-Parts Generation
        part_count = len(real_parts)
        part_names = [p['text'] for p in real_parts]
        
        if language == 'zh':
            ack_prompt = f"好的！节点调色板即将打开。\n\n你已经有{part_count}个主要部分。现在让我们为每个部分生成更细致的子部件。\n\n系统将为每个部分创建独立的标签页：\n"
            ack_prompt += "\n".join(f"- {name}" for name in part_names)
            ack_prompt += f"\n\n点击标签页切换，为每个部分选择子部件。完成后点击\"完成\"。"
        else:
            ack_prompt = f"Okay! Opening Node Palette.\n\nYou already have {part_count} main parts. Now let's generate finer sub-components for each part.\n\nThe system will create separate tabs for each part:\n"
            ack_prompt += "\n".join(f"- {name}" for name in part_names)
            ack_prompt += f"\n\nSwitch between tabs to select sub-components for each part. Click \"Finish\" when done."
    
    async for chunk in self._stream_llm_response(ack_prompt, session):
        yield chunk
    
    # Extract educational context
    context = session.get('context', {})
    educational_context = {
        'grade_level': context.get('grade_level', '5th grade'),
        'subject': context.get('subject', 'General'),
        'objective': context.get('objective', ''),
        'raw_message': context.get('raw_message', ''),
        'language': language
    }
    
    # Yield action event
    yield {
        'event': 'action',
        'action': 'open_node_palette',
        'data': {
            'center_topic': center_topic,
            'current_node_count': len(parts),
            'diagram_data': diagram_data,
            'session_id': session['session_id'],
            'educational_context': educational_context,
            # ✅ ADD STAGE INFO
            'stage': 'subparts' if has_real_parts else 'parts',
            'stage_data': {'parts': part_names} if has_real_parts else {}
        }
    }
```

---

## Fix Plan for Flow Map

### Recommended Architecture: 2-Stage Workflow + Ordering

**Stage 1: Process Definition** (Optional but recommended)
- Generate clear process/event descriptions
- User selects 1 process definition
- Sets context for step generation

**Stage 2: Steps Generation with Ordering**
- Generate sequential steps
- User selects steps
- **CRITICAL**: Add sequence numbers or drag-and-drop ordering
- Steps must maintain order (1 → 2 → 3 → ...)

---

### Implementation Steps for Flow Map

#### Step 1: Update Backend Palette Generator

**File**: `agents/thinking_modes/node_palette/flow_map_palette.py`

**Changes Needed**:

```python
class FlowMapPaletteGenerator(BasePaletteGenerator):
    """
    Flow Map specific palette generator with stage workflow.
    
    Stages:
    - process: Generate process definition (optional)
    - steps: Generate sequential steps with ordering
    """
    
    def __init__(self):
        super().__init__()
        self.session_stages = {}
        self.step_sequences = {}  # Track next sequence number per session
    
    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        stage: str = 'steps',  # ✅ ADD STAGE
        stage_data: Optional[Dict[str, Any]] = None  # ✅ ADD STAGE_DATA
    ) -> AsyncGenerator[Dict, None]:
        """Generate batch with stage-specific logic and sequence numbers."""
        
        # Store stage info
        if session_id not in self.session_stages:
            self.session_stages[session_id] = {}
            self.step_sequences[session_id] = 1  # Start sequence at 1
        self.session_stages[session_id]['stage'] = stage
        if stage_data:
            self.session_stages[session_id].update(stage_data)
        
        # Pass session_id through context
        if educational_context is None:
            educational_context = {}
        educational_context = {**educational_context, '_session_id': session_id}
        
        # Call parent
        async for event in super().generate_batch(
            session_id=session_id,
            center_topic=center_topic,
            educational_context=educational_context,
            nodes_per_llm=nodes_per_llm
        ):
            # Tag nodes with mode and sequence
            if event.get('event') == 'node_generated':
                node = event.get('node', {})
                
                # Tag with stage
                node['mode'] = stage
                
                # ✅ CRITICAL: Add sequence number for steps
                if stage == 'steps':
                    node['sequence'] = self.step_sequences[session_id]
                    self.step_sequences[session_id] += 1
                    logger.info(f"[FlowMapPalette] Step node tagged with sequence={node['sequence']}")
            
            yield event
    
    def _build_prompt(self, center_topic, educational_context, count, batch_num):
        """Build stage-specific prompt."""
        
        session_id = educational_context.get('_session_id') if educational_context else None
        stage = 'steps'
        stage_data = {}
        
        if session_id and session_id in self.session_stages:
            stage = self.session_stages[session_id].get('stage', 'steps')
            stage_data = self.session_stages[session_id]
        
        if stage == 'process':
            return self._build_process_prompt(center_topic, educational_context, count, batch_num)
        elif stage == 'steps':
            process_desc = stage_data.get('process', center_topic)
            return self._build_steps_prompt(process_desc, educational_context, count, batch_num)
        else:
            return self._build_steps_prompt(center_topic, educational_context, count, batch_num)
    
    def _build_process_prompt(self, center_topic, educational_context, count, batch_num):
        """Build prompt for generating process descriptions."""
        language = educational_context.get('language', 'en') if educational_context else 'en'
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'
        
        if language == 'zh':
            prompt = f"""为主题"{center_topic}"生成{count}个清晰的流程/事件描述

教学背景：{context_desc}

流程图用于展示事件的顺序和步骤。首先需要明确要分析的流程或事件。

要求：
1. 每个描述要清晰、完整地定义一个流程或事件
2. 使用名词短语，3-10个字
3. 描述要具体，不要太抽象
4. 只输出流程描述，每行一个，不要编号

生成{count}个流程描述："""
        else:
            prompt = f"""Generate {count} clear process/event descriptions for: {center_topic}

Educational Context: {context_desc}

Flow maps show the sequence of events and steps. First, we need to clearly define the process or event to analyze.

Requirements:
1. Each description should clearly and completely define a process or event
2. Use noun phrases, 3-10 words
3. Descriptions should be specific, not too abstract
4. Output only process descriptions, one per line, no numbering

Generate {count} process descriptions:"""
        
        return prompt
    
    def _build_steps_prompt(self, process_desc, educational_context, count, batch_num):
        """Build prompt for generating sequential steps."""
        # EXISTING CODE (keep as is, but emphasize sequence)
        language = educational_context.get('language', 'en') if educational_context else 'en'
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'
        
        if language == 'zh':
            # Add sequence emphasis
            prompt = f"""为流程"{process_desc}"生成{count}个按时间顺序排列的步骤

教学背景：{context_desc}

你能够绘制流程图，展示过程的各个步骤。
思维方式：顺序、流程
1. 步骤要按时间顺序排列（从早到晚，从开始到结束）
2. 每个步骤要简洁明了，不要使用完整句子
3. 使用动宾短语或名词短语描述步骤
4. 步骤之间要有逻辑关联

要求：每个步骤要简洁明了（1-6个词），不要标点符号，不要编号前缀。只输出步骤文本，每行一个。**请按照时间顺序从早到晚排列步骤**。

生成{count}个按顺序的步骤："""
        else:
            prompt = f"""Generate {count} chronologically ordered steps for: {process_desc}

Educational Context: {context_desc}

You can draw a flow map to show the steps of a process.
Thinking approach: Sequential, Procedural
1. Steps should follow chronological order (from beginning to end)
2. Each step should be concise and clear, avoid full sentences
3. Use action phrases or noun phrases to describe steps
4. Steps should be logically connected

Requirements: Each step should be concise (1-6 words), no punctuation, no numbering prefixes. Output only the step text, one per line. **Please arrange steps in chronological order from earliest to latest**.

Generate {count} ordered steps:"""
        
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保步骤仍然按照时间顺序排列，提供新的角度或细节。"
            else:
                prompt += f"\n\nNote: Batch {batch_num}. Ensure steps remain in chronological order with new angles or details."
        
        return prompt
    
    def end_session(self, session_id: str, reason: str = "complete"):
        """Clean up session."""
        self.session_stages.pop(session_id, None)
        self.step_sequences.pop(session_id, None)
        super().end_session(session_id, reason)
```

---

#### Step 2: Update Frontend Configuration

**File**: `static/js/editor/node-palette-manager.js`

**Change**:
```javascript
// Add after brace_map config
'flow_map': {
    arrays: {
        'steps': {
            nodeName: 'step',
            nodeNamePlural: 'steps',
            nodeType: 'step'
        }
    },
    arrayName: 'steps',
    nodeName: 'step',
    nodeNamePlural: 'steps',
    nodeType: 'step',
    useTabs: false,  // Single tab, but with ordering
    useStages: true  // ✅ ENABLE STAGES
}
```

---

#### Step 3: Add Step Ordering UI

**Location**: `static/js/editor/node-palette-manager.js`

**New Method**:
```javascript
/**
 * Enable drag-and-drop reordering for flow map steps
 */
enableStepReordering(container) {
    if (this.diagramType !== 'flow_map') return;
    
    const nodeCards = container.querySelectorAll('.node-card');
    
    nodeCards.forEach((card, index) => {
        card.setAttribute('draggable', 'true');
        
        card.addEventListener('dragstart', (e) => {
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', index);
            card.classList.add('dragging');
        });
        
        card.addEventListener('dragend', (e) => {
            card.classList.remove('dragging');
        });
        
        card.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        });
        
        card.addEventListener('drop', (e) => {
            e.preventDefault();
            const fromIndex = parseInt(e.dataTransfer.getData('text/plain'));
            const toIndex = index;
            
            if (fromIndex !== toIndex) {
                // Reorder nodes array
                const [movedNode] = this.nodes.splice(fromIndex, 1);
                this.nodes.splice(toIndex, 0, movedNode);
                
                // Update sequence numbers
                this.nodes.forEach((node, idx) => {
                    node.sequence = idx + 1;
                });
                
                // Re-render
                this.renderNodeCards();
            }
        });
    });
}

/**
 * Show sequence numbers on flow map node cards
 */
renderNodeCardOnly(node) {
    // ... existing code ...
    
    // Add sequence number for flow map
    if (this.diagramType === 'flow_map' && node.sequence) {
        const sequenceBadge = document.createElement('div');
        sequenceBadge.className = 'sequence-badge';
        sequenceBadge.textContent = node.sequence;
        cardDiv.insertBefore(sequenceBadge, cardDiv.firstChild);
    }
    
    // ... rest of existing code ...
}
```

**CSS** (add to `static/css/node-palette.css`):
```css
/* Flow map step ordering */
.node-card.dragging {
    opacity: 0.5;
}

.sequence-badge {
    position: absolute;
    top: 8px;
    left: 8px;
    background: #4a90e2;
    color: white;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: bold;
    z-index: 1;
}
```

---

#### Step 4: Update ThinkGuide Agent

**File**: `agents/thinking_modes/flow_map_agent_react.py`

**Update `_handle_open_node_palette`**:

```python
async def _handle_open_node_palette(self, session: Dict) -> AsyncGenerator[Dict, None]:
    """Handle opening Node Palette for Flow Map with stage awareness"""
    diagram_data = session['diagram_data']
    language = session.get('language', 'en')
    center_topic = diagram_data.get('title', 'Unknown Event')
    steps = diagram_data.get('steps', [])
    step_count = len(steps)
    
    # Acknowledge request with step ordering emphasis
    if language == 'zh':
        ack_prompt = f"好的！节点调色板即将打开。\n\n让我们为流程「{center_topic}」生成更多步骤。目前有{step_count}个步骤。\n\n**重要提示**：流程图的步骤需要按照时间顺序排列。系统将生成有序的步骤，你可以通过拖拽调整顺序。\n\n系统将使用4个AI模型同时生成创意步骤想法。"
    else:
        ack_prompt = f"Okay! Opening Node Palette.\n\nLet's generate more steps for process \"{center_topic}\". Currently {step_count} steps.\n\n**Important**: Flow map steps need to be in chronological order. The system will generate ordered steps, and you can drag-and-drop to adjust the order.\n\nThe system will use 4 AI models simultaneously to generate creative step ideas."
    
    async for chunk in self._stream_llm_response(ack_prompt, session):
        yield chunk
    
    # ... rest of method ...
    
    yield {
        'event': 'action',
        'action': 'open_node_palette',
        'data': {
            'center_topic': center_topic,
            'current_node_count': step_count,
            'diagram_data': diagram_data,
            'session_id': session['session_id'],
            'educational_context': educational_context,
            'stage': 'steps',  # ✅ Always steps stage for now
            'stage_data': {}
        }
    }
```

---

## Implementation Checklist

### Brace Map Implementation

**Backend**:
- [ ] Add `session_stages` dict to `BraceMapPaletteGenerator`
- [ ] Override `generate_batch()` with `stage` and `stage_data` parameters
- [ ] Create `_build_parts_prompt()` method (keep existing)
- [ ] Create `_build_subparts_prompt()` method
- [ ] Tag nodes with `mode` field (part name for subparts)
- [ ] Override `end_session()` for cleanup

**Frontend**:
- [ ] Update diagram metadata: add `useTabs: true`, `useStages: true`
- [ ] Add stage detection in `start()` method
- [ ] Add dynamic tab creation for Stage 2 (subparts)
- [ ] Add stage progression logic (if implementing multi-stage)
- [ ] Test tab switching and node routing

**ThinkGuide**:
- [ ] Add stage detection in `_handle_open_node_palette`
- [ ] Add stage-specific guidance messages
- [ ] Pass `stage` and `stage_data` in action event

**Testing**:
- [ ] Test Stage 1: Parts generation
- [ ] Test Stage 2: Sub-parts generation with dynamic tabs
- [ ] Test stage persistence on reopen
- [ ] Test concurrent loading (N parts × 4 LLMs)
- [ ] Test node assembly and diagram update

---

### Flow Map Implementation

**Backend**:
- [ ] Add `session_stages` and `step_sequences` dicts
- [ ] Override `generate_batch()` with stage and sequence handling
- [ ] Create `_build_process_prompt()` (optional)
- [ ] Update `_build_steps_prompt()` to emphasize ordering
- [ ] Tag nodes with `mode` and `sequence` fields
- [ ] Override `end_session()` for cleanup

**Frontend**:
- [ ] Update diagram metadata: add `useStages: true`
- [ ] Add step ordering UI (drag-and-drop)
- [ ] Add sequence badges to node cards
- [ ] Enable reordering in node palette
- [ ] Preserve sequence numbers when adding to diagram

**ThinkGuide**:
- [ ] Add step ordering guidance in messages
- [ ] Emphasize chronological sequence importance
- [ ] Pass `stage` in action event

**Testing**:
- [ ] Test step generation with sequence numbers
- [ ] Test drag-and-drop reordering
- [ ] Test sequence preservation
- [ ] Test stage persistence on reopen
- [ ] Verify steps maintain order in diagram

---

## Conclusion

Both Brace Map and Flow Map need multi-stage workflow implementations similar to Tree Map. The key patterns to replicate are:

1. **Backend Stage Management**: Session-based stage tracking, stage-specific prompts, node tagging
2. **Frontend Tab/Stage Management**: Stage detection, dynamic tab creation, stage progression
3. **ThinkGuide Integration**: Stage-aware guidance, clear instructions, pedagogical alignment

**Priority**: Brace Map should be implemented first (simpler, no ordering complexity), followed by Flow Map (requires additional ordering UI).

**Timeline Estimate**:
- Brace Map: 1-2 days for full implementation + testing
- Flow Map: 2-3 days for full implementation + testing (ordering adds complexity)

**Reference Implementations**:
- Use Tree Map as primary reference for multi-stage workflow
- Use Double Bubble Map as reference for tab management
- Study existing stage detection and progression logic in `node-palette-manager.js` (lines 966-1200)

---

**Author**: AI Assistant  
**Date**: 2025-10-19  
**Status**: 🔍 REVIEW COMPLETE - READY FOR IMPLEMENTATION  
**Reference Documents**: TREE_MAP_COMPLETE_REFERENCE.md

