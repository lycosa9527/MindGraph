# Thinking Mode - Implementation Guide

**Author:** lycosa9527  
**Made by:** MindSpring Team  
**Date:** October 9, 2025  
**Version:** 4.1 - Complete Implementation Guide  
**Status:** ✅ Ready for Implementation  

---

## 🎓 Agent Name: **ThinkGuide** (思维向导)

**ThinkGuide** is a Socratic teaching assistant that guides K12 teachers through diagram refinement using critical thinking.

**Name Meaning:**
- **English:** "ThinkGuide" - Emphasizes guidance for thinking, not just answers
- **Chinese:** 思维向导 (Sīwéi Xiàngdǎo) - "Thinking Navigator/Guide"

**UI Usage:**
- Button label: "ThinkGuide" / "思维向导"
- Panel header: "ThinkGuide - Thinking Guide" / "思维向导"
- Messages: "ThinkGuide is analyzing your diagram..."
- Progress: "ThinkGuide is helping you refine to 5 core concepts..."

**Why ThinkGuide:**
- ✅ Clear purpose - guides thinking, doesn't give answers
- ✅ Professional - suitable for K12 educators
- ✅ Distinctive - different from "MindMate AI" (general chat)
- ✅ Memorable - easy to understand and remember
- ✅ Action-oriented - emphasizes the guiding process

---

## 📖 Document Overview

**This is the COMPLETE reference for building ThinkGuide (Thinking Mode).** Everything you need is in this one document:

| Section | What's Inside | Lines |
|---------|--------------|-------|
| **Quick Start** | What we're building, key features, chat-diagram sync | 10-48 |
| **All 8 Maps** | Shared workflow, unique prompts per map | 49-140 |
| **Race Conditions** | 3-layer defense, session locking, testing | 141-390 |
| **Chat-Diagram Sync** | How highlights work in real-time | 391-673 |
| **Checklist** | Phase-by-phase tasks with time estimates | 674-760 |
| **Build Guide** | Step-by-step instructions with acceptance criteria | 761-1369 |
| **Code Templates** | 9 copy-paste ready templates | 1370-3082 |
| **Reference** | Key concepts, Socratic method, patterns | 3083-3107 |
| **Definition of Done** | Success criteria for each phase | 3108-3141 |

**Quick Navigation:**
- 🚀 Start here: [Quick Start](#quick-start)
- 📋 See tasks: [Implementation Checklist](#implementation-checklist)
- 💻 Get code: [Code Templates](#code-templates)
- 🏗️ Build it: [Step-by-Step Guide](#step-by-step-build-guide)

---

## 🎯 Quick Start - What We're Building

**ThinkGuide (Thinking Mode)** is a Socratic teaching assistant that helps K12 teachers refine their diagrams through guided critical thinking.

### Key Features:
- ✅ Validates diagrams (no placeholders)
- ✅ Educational Analysis phase (teaches node relationships BEFORE refinement)
- ✅ Socratic questioning (asks questions, doesn't give answers)
- ✅ Iterative refinement (10 → 8 → 6 → 5 core nodes)
- ✅ **Chat-Diagram Sync** - Nodes glow in real-time when mentioned in chat! 🎨
- ✅ Visual node highlighting (4 types: remove, keep, analyze, question)
- ✅ Hover tooltips (see learning material anytime)
- ✅ Diagram-specific (Circle Map ≠ Bubble Map workflows)

### 🎨 The Magic: Chat ↔ Diagram Synchronization

**This is NOT a regular chat!** When the agent talks about nodes, those nodes **glow in the diagram simultaneously**:

```
Agent says: "I notice 'Chlorophyll' and 'Green Color'..."
              ↓
Diagram:     [Chlorophyll] ← GLOWS BLUE
             [Green Color] ← GLOWS BLUE

Agent says: "Consider removing 'Plants' and 'Energy'..."
              ↓
Diagram:     [Plants] ← PULSES RED
             [Energy] ← PULSES RED
```

**Result:** Users instantly see WHICH nodes are being discussed. Chat and diagram feel like ONE integrated experience, not two separate things!

### Tech Stack:
- **Backend:** FastAPI + LangChain + Qwen-Plus (Dashscope)
- **Frontend:** Vanilla JS + D3.js + SSE streaming
- **Pattern:** Factory Pattern (one endpoint, multiple diagram types)

---

## 🗺️ All 8 Thinking Maps - Shared Workflow, Unique Prompts

**Critical Understanding:** All 8 thinking map types share the SAME workflow structure, only the prompts differ!

### Thinking Maps Overview

| Map Type | Purpose | Example Refinement Focus |
|----------|---------|-------------------------|
| **Circle Map** | Brainstorming & Defining | Breadth, relevance to center concept |
| **Bubble Map** | Describing with Adjectives | Precision, variety (sensory, emotional, factual) |
| **Double Bubble Map** | Comparing & Contrasting | Balance, meaningful differences/similarities |
| **Tree Map** | Classifying & Categorizing | Logical grouping, hierarchy clarity |
| **Brace Map** | Whole-to-Part Analysis | Complete breakdown, no missing parts |
| **Flow Map** | Sequencing & Steps | Logical order, essential steps only |
| **Multi-Flow Map** | Cause & Effect | Strong causal links, balanced causes/effects |
| **Bridge Map** | Seeing Analogies | Accurate analogies, consistent relating factor |

### Shared Workflow (7 States)

**All maps follow the SAME state machine:**

```python
class ThinkingMapState(Enum):
    CONTEXT_GATHERING = "CONTEXT_GATHERING"        # Step 1: Get educational context
    EDUCATIONAL_ANALYSIS = "EDUCATIONAL_ANALYSIS"  # Step 2: Teach relationships
    ANALYSIS = "ANALYSIS"                          # Step 3: Socratic questions
    REFINEMENT_1 = "REFINEMENT_1"                  # Step 4: N → 8 nodes
    REFINEMENT_2 = "REFINEMENT_2"                  # Step 5: 8 → 6 nodes
    FINAL_REFINEMENT = "FINAL_REFINEMENT"          # Step 6: 6 → 5 nodes
    COMPLETE = "COMPLETE"                          # Step 7: Summary
```

### What's Different Per Map?

**Only the prompts change!** Each map type asks different Socratic questions:

**Circle Map (Brainstorming):**
- "Are these ideas broad enough?"
- "Do they all relate to the center concept?"
- "Which are most foundational for understanding?"

**Bubble Map (Describing):**
- "Are these adjectives precise?"
- "Do you have a variety of descriptors (sensory, emotional, factual)?"
- "Which descriptors are most essential for understanding the topic?"

**Tree Map (Classifying):**
- "Are your categories logically grouped?"
- "Do any items belong in multiple categories?"
- "Which categories are most essential for this classification?"

**Multi-Flow Map (Cause & Effect):**
- "Are these true causal relationships?"
- "Which causes have the strongest effect?"
- "Are causes balanced with effects?"

### Implementation Strategy

**Same agent base class, different prompt files:**

```
prompts/thinking_modes/
├── circle_map.py          # 6 prompts for Circle Map
├── bubble_map.py          # 6 prompts for Bubble Map (same structure!)
├── double_bubble_map.py   # 6 prompts for Double Bubble Map
├── tree_map.py            # 6 prompts for Tree Map
├── brace_map.py           # 6 prompts for Brace Map
├── flow_map.py            # 6 prompts for Flow Map
├── multi_flow_map.py      # 6 prompts for Multi-Flow Map
└── bridge_map.py          # 6 prompts for Bridge Map

agents/thinking_modes/
├── base_agent.py          # SHARED base class with workflow logic
├── circle_map_agent.py    # Extends base, uses circle_map.py prompts
├── bubble_map_agent.py    # Extends base, uses bubble_map.py prompts
├── double_bubble_map_agent.py
├── tree_map_agent.py
├── brace_map_agent.py
├── flow_map_agent.py
├── multi_flow_map_agent.py
├── bridge_map_agent.py
└── factory.py             # Routes to correct agent
```

**Benefits:**
- ✅ Write workflow logic once (base class)
- ✅ Easy to add new maps (new prompt file + simple agent class)
- ✅ Consistent UX across all map types
- ✅ Only ~200 lines per new map (prompts + agent wrapper)

---

## 🔒 Race Condition Handling - CRITICAL!

### The Problem

**Without proper concurrency control, these race conditions can occur:**

1. **User sends message while LLM is streaming:**
   ```
   T0: User sends "5th grade science"
   T1: Backend starts LLM streaming
   T2: User clicks send again (impatient!)
   T3: Second request arrives while first is streaming
   → RACE CONDITION: Session state corrupted!
   ```

2. **Multiple browser tabs:**
   ```
   Tab 1: Sends message at T0
   Tab 2: Sends message at T1 (same session_id)
   → RACE CONDITION: Both processing same session!
   ```

3. **State changes mid-stream:**
   ```
   T0: Start streaming in ANALYSIS state
   T1: User sends message that transitions to REFINEMENT_1
   T2: First stream still going, state changed
   → RACE CONDITION: Response doesn't match state!
   ```

### The Solution

**3-Layer Defense:**

#### Layer 1: Session Locking (Backend)

```python
import asyncio
from typing import Dict

class CircleMapThinkingAgent:
    def __init__(self):
        self.llm = LLMClient(...)
        self.sessions: Dict[str, Dict] = {}
        self.session_locks: Dict[str, asyncio.Lock] = {}  # NEW: Per-session locks
    
    async def process_step(self, message, session_id, ...):
        """Process with session locking to prevent race conditions"""
        
        # Get or create lock for this session
        if session_id not in self.session_locks:
            self.session_locks[session_id] = asyncio.Lock()
        
        lock = self.session_locks[session_id]
        
        # Try to acquire lock (non-blocking)
        if lock.locked():
            # Session is busy! Reject this request
            yield {
                'event': 'error',
                'message': 'Session busy. Please wait for current response to complete.',
                'code': 'SESSION_BUSY'
            }
            return
        
        # Acquire lock for this processing
        async with lock:
            # Get or create session
            if session_id not in self.sessions:
                self.sessions[session_id] = {
                    'session_id': session_id,
                    'state': CircleMapState.CONTEXT_GATHERING,
                    'is_processing': False,  # Redundant check
                    ...
                }
            
            session = self.sessions[session_id]
            
            # Double-check not processing (redundant safety)
            if session.get('is_processing', False):
                yield {
                    'event': 'error',
                    'message': 'Session already processing',
                    'code': 'SESSION_BUSY'
                }
                return
            
            # Mark as processing
            session['is_processing'] = True
            
            try:
                # Route to handler (now safe from concurrent access)
                state = CircleMapState(current_state)
                if state == CircleMapState.CONTEXT_GATHERING:
                    async for chunk in self._handle_context_gathering(session, message):
                        yield chunk
                # ... other handlers
            
            finally:
                # Always release processing flag
                session['is_processing'] = False
                # Lock automatically released by 'async with'
```

**Key Points:**
- ✅ One `asyncio.Lock` per session
- ✅ Non-blocking check: Reject immediately if busy
- ✅ `async with` ensures lock always released
- ✅ `is_processing` flag as backup check

#### Layer 2: Frontend UI State (Prevent Multiple Sends)

```javascript
class ThinkingModeManager {
    constructor(diagramType, canvasManager) {
        // ...
        this.isStreaming = false;  // NEW: Track streaming state
    }
    
    async sendMessage() {
        const message = this.input.value.trim();
        if (!message) return;
        
        // Prevent sending while streaming
        if (this.isStreaming) {
            console.warn('Already streaming, please wait...');
            return;
        }
        
        // Disable UI
        this.isStreaming = true;
        this.sendBtn.disabled = true;
        this.input.disabled = true;
        
        try {
            // Render user message
            this.renderMessage('user', message);
            this.input.value = '';
            
            // Send to backend
            const diagramData = this.extractDiagramData();
            await this.streamResponse(message, diagramData, this.currentState);
        }
        finally {
            // Re-enable UI (even if error)
            this.isStreaming = false;
            this.sendBtn.disabled = false;
            this.input.disabled = false;
            this.input.focus();
        }
    }
    
    async streamResponse(message, diagramData, currentState) {
        try {
            // ... SSE streaming code
            
            // Handle SESSION_BUSY error from backend
            if (data.event === 'error' && data.code === 'SESSION_BUSY') {
                this.showError('Please wait for the current response to complete.');
                return; // Don't retry
            }
        }
        catch (error) {
            // ... error handling
        }
    }
}
```

**Key Points:**
- ✅ `isStreaming` flag prevents multiple sends
- ✅ Disable send button while streaming
- ✅ Disable input while streaming
- ✅ Always re-enable in `finally` block

#### Layer 3: Request Deduplication (Optional - Advanced)

For multi-tab scenarios, use a request ID:

```python
# Backend
class ThinkingModeRequest(BaseModel):
    message: str
    session_id: str
    request_id: str  # NEW: Unique per request
    # ...

class CircleMapThinkingAgent:
    def __init__(self):
        # ...
        self.processed_requests: Dict[str, Set[str]] = {}  # session_id -> set of request_ids
    
    async def process_step(self, message, session_id, request_id, ...):
        # Check if request already processed
        if session_id in self.processed_requests:
            if request_id in self.processed_requests[session_id]:
                yield {
                    'event': 'error',
                    'message': 'Request already processed',
                    'code': 'DUPLICATE_REQUEST'
                }
                return
        
        # ... rest of processing
        
        # Mark request as processed
        if session_id not in self.processed_requests:
            self.processed_requests[session_id] = set()
        self.processed_requests[session_id].add(request_id)
```

### Testing Race Conditions

**Test Cases:**

```python
# Test 1: Rapid consecutive requests
async def test_race_condition_rapid_requests():
    agent = CircleMapThinkingAgent()
    session_id = "test_123"
    
    # Send two requests simultaneously
    task1 = asyncio.create_task(agent.process_step("msg1", session_id, ...))
    task2 = asyncio.create_task(agent.process_step("msg2", session_id, ...))
    
    results = await asyncio.gather(task1, task2, return_exceptions=True)
    
    # One should succeed, one should get SESSION_BUSY error
    assert any('SESSION_BUSY' in str(r) for r in results)
```

**Manual Testing:**

1. **Double-click send button** → Second click ignored
2. **Send while streaming** → Button disabled, no second request
3. **Open two tabs, send from both** → One succeeds, one gets busy error
4. **Slow network, click send 5 times** → Only first processes

### Summary: Concurrency Strategy

| Layer | Protection | Where | Status |
|-------|-----------|-------|--------|
| **Session Locking** | `asyncio.Lock` per session | Backend agent | ✅ CRITICAL |
| **UI State** | Disable send while streaming | Frontend manager | ✅ CRITICAL |
| **Request Dedup** | Track processed request IDs | Backend (optional) | ⚪ Nice-to-have |

**Result:** No race conditions, clean user experience, predictable state! 🔒

---

## 🎨 Chat-Diagram Synchronization - How It Works

### The Core Concept

**Traditional Chat:**
```
User: "What about chlorophyll?"
Agent: "Chlorophyll is important because..."
         ↓
User reads text ← DISCONNECT → User looks at diagram
(Which node were we talking about again?)
```

**ThinkGuide (Synchronized):**
```
User: "What about chlorophyll?"
ThinkGuide: "Chlorophyll is important because..."
         ↓
[Chlorophyll] node GLOWS BLUE in diagram ← INSTANT VISUAL CONNECTION
User sees text + visual highlight simultaneously!
```

### Technical Implementation Flow

#### Step 1: Agent Identifies Nodes in Response

When the agent generates a response mentioning nodes, it identifies which nodes to highlight:

```python
# In BaseThinkingAgent._stream_llm_response()

async def _stream_llm_response(self, prompt, session):
    """Stream LLM response with automatic node highlighting"""
    
    full_content = ""
    async for chunk in self.llm.stream_chat(prompt):
        content = chunk.get('content', '')
        full_content += content
        
        # Stream text chunk
        yield {
            'event': 'message_chunk',
            'content': content
        }
    
    # After complete message, identify mentioned nodes
    mentioned_nodes = self._extract_mentioned_nodes(
        full_content, 
        session['diagram_data']['children']
    )
    
    # Send highlight event!
    if mentioned_nodes:
        highlight_type = self._determine_highlight_type(full_content)
        yield {
            'event': 'highlight_nodes',
            'node_ids': mentioned_nodes,
            'type': highlight_type  # 'remove', 'keep', 'analyze', or 'question'
        }
```

**Node Detection Methods:**

```python
def _extract_mentioned_nodes(self, text: str, nodes: List[Dict]) -> List[str]:
    """
    Extract which nodes are mentioned in the text.
    Uses fuzzy matching to handle variations.
    """
    mentioned = []
    
    # Convert text to lowercase for matching
    text_lower = text.lower()
    
    for node in nodes:
        node_text = node['text'].lower()
        
        # Check if node text is in response
        # Also check for quoted versions: "Chlorophyll", 'Chlorophyll'
        if (node_text in text_lower or 
            f'"{node["text"]}"' in text or 
            f"'{node['text']}'" in text):
            mentioned.append(node['id'])
    
    return mentioned

def _determine_highlight_type(self, text: str) -> str:
    """
    Determine highlight type based on context in text.
    """
    text_lower = text.lower()
    
    # Check for removal keywords
    if any(word in text_lower for word in ['remove', 'delete', 'eliminate', 'refine away']):
        return 'remove'  # RED pulse
    
    # Check for keep/strengthen keywords
    elif any(word in text_lower for word in ['keep', 'essential', 'core', 'foundational']):
        return 'keep'  # GREEN glow
    
    # Check for questioning keywords
    elif any(word in text_lower for word in ['why', 'how', 'what if', 'consider', 'think about']):
        return 'question'  # ORANGE pulse
    
    # Default to analysis
    else:
        return 'analyze'  # BLUE glow
```

#### Step 2: SSE Event Sent to Frontend

The backend streams the highlight event via SSE:

```python
# In routers/thinking.py

async def generate():
    async for chunk in agent.process_step(...):
        # Regular message chunks
        if chunk.get('event') == 'message_chunk':
            yield f"data: {json.dumps(chunk)}\n\n"
        
        # HIGHLIGHT EVENT! ← NEW
        elif chunk.get('event') == 'highlight_nodes':
            yield f"data: {json.dumps({
                'event': 'highlight_nodes',
                'node_ids': chunk['node_ids'],
                'type': chunk['type']
            })}\n\n"
```

#### Step 3: Frontend Receives and Applies Highlights

```javascript
// In ThinkingModeManager.streamResponse()

async streamResponse(message, diagramData, currentState) {
    const reader = response.body.getReader();
    
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        // Parse SSE data
        const data = JSON.parse(line.slice(6));
        
        if (data.event === 'message_chunk') {
            // Display text in chat
            this.updateCurrentMessage(data.content);
        }
        
        // HIGHLIGHT EVENT RECEIVED! ← NEW
        else if (data.event === 'highlight_nodes') {
            // Immediately highlight nodes in diagram
            this.highlightNodes(data.node_ids, data.type);
        }
    }
}

highlightNodes(nodeIds, type) {
    // Clear previous highlights
    this.clearAllHighlights();
    
    // Apply new highlights to diagram
    nodeIds.forEach(nodeId => {
        const nodeElement = this.findNodeInDiagram(nodeId);
        if (nodeElement) {
            // Add CSS class for visual effect
            nodeElement.classList.add(`node-highlight-${type}`);
        }
    });
}

findNodeInDiagram(nodeId) {
    // Find node in SVG diagram
    // Could use D3 selector or data attribute
    return d3.select(`[data-node-id="${nodeId}"]`).node();
    // Or: return document.querySelector(`#node-${nodeId}`);
}
```

#### Step 4: CSS Creates Visual Effects

```css
/* 4 types of highlights, each with distinct visual */

/* RED pulse - Nodes to remove */
.node-highlight-remove {
    filter: drop-shadow(0 0 8px rgba(255, 68, 68, 0.8));
    animation: pulse-remove 1.5s ease-in-out infinite;
}

@keyframes pulse-remove {
    0%, 100% { filter: drop-shadow(0 0 8px rgba(255, 68, 68, 0.8)); }
    50% { filter: drop-shadow(0 0 16px rgba(255, 68, 68, 1)); }
}

/* GREEN glow - Nodes to keep */
.node-highlight-keep {
    filter: drop-shadow(0 0 10px rgba(76, 175, 80, 0.9));
    stroke: #4CAF50 !important;
    stroke-width: 3px !important;
}

/* BLUE glow - Nodes under analysis */
.node-highlight-analyze {
    filter: drop-shadow(0 0 6px rgba(33, 150, 243, 0.7));
    animation: pulse-analyze 2s ease-in-out infinite;
}

/* ORANGE pulse - Nodes being questioned */
.node-highlight-question {
    filter: drop-shadow(0 0 10px rgba(255, 152, 0, 0.9));
    animation: pulse-question 1s ease-in-out 3; /* Pulse 3 times */
}
```

### Real-World Example Flow

**Scenario:** Agent asks about "Chlorophyll" and "Green Color"

```
T0: Agent generates: "I notice 'Chlorophyll' and 'Green Color'. How are these related?"
    ↓
T1: Backend streams text chunks: "I notice ", "'Chlorophyll'", " and ", "'Green Color'"...
    Frontend displays text in chat panel (left side)
    ↓
T2: Backend detects mentioned nodes: ['chlorophyll_id', 'green_color_id']
    Backend determines type: 'question' (contains "How")
    ↓
T3: Backend sends SSE event:
    {
      event: 'highlight_nodes',
      node_ids: ['chlorophyll_id', 'green_color_id'],
      type: 'question'
    }
    ↓
T4: Frontend receives event
    Finds nodes in diagram (right side)
    Applies CSS class: node-highlight-question
    ↓
T5: USER SEES:
    Left panel (chat): "I notice 'Chlorophyll' and 'Green Color'..."
    Right panel (diagram): [Chlorophyll] GLOWING ORANGE
                           [Green Color] GLOWING ORANGE
    ↓
    SYNCHRONIZED! User instantly knows which nodes the agent is discussing!
```

### Timing & UX Considerations

**Highlight Timing:**
- Highlight appears AFTER message complete (not during streaming)
- Why: Prevents flickering as text builds up
- Duration: Highlights persist until next message or user action

**Multiple Highlights:**
- Can highlight multiple nodes simultaneously
- Example: "Remove 'Plants', 'Energy', and 'Leaves'" → 3 RED pulses

**Clear & Reset:**
- Previous highlights cleared before new ones applied
- Prevents confusion from stale highlights
- User can manually clear by clicking elsewhere

**Mobile/Accessibility:**
- Highlights also add ARIA labels for screen readers
- Touch devices: Tap highlighted node for details
- High contrast mode: Stronger stroke instead of glow

### Benefits of This Approach

✅ **Instant Visual Feedback** - No mental mapping needed  
✅ **Reduced Cognitive Load** - See + read simultaneously  
✅ **Better Learning** - Visual reinforcement of concepts  
✅ **Engagement** - Interactive, not just passive reading  
✅ **Accessibility** - Multiple channels (visual + text)  
✅ **Scalability** - Works with any number of nodes  

**This is what transforms Thinking Mode from a chat into a visual thinking tool!** 🎨

---

## 📋 Implementation Checklist

### Phase 1: Backend - Circle Map MVP (10-14 hours)
- [ ] 1.0 Create base agent (`agents/thinking_modes/base_agent.py`) with race condition handling
- [ ] 1.1 Create Circle Map prompts (`prompts/thinking_modes/circle_map.py`)
- [ ] 1.2 Create Circle Map agent (`agents/thinking_modes/circle_map_agent.py`)
- [ ] 1.3 Create agent factory (`agents/thinking_modes/factory.py`)
- [ ] 1.4 Create API router (`routers/thinking.py`) with 2 endpoints
- [ ] 1.5 Add request model (`models/requests.py`)
- [ ] 1.6 Register router in `main.py`
- [ ] 1.7 Test backend with Postman/curl
- [ ] 1.8 Test race condition handling (double-click, rapid sends)

### Phase 2: Frontend (10-14 hours)
- [ ] 2.1 Add "Thinking" button to toolbar (`templates/editor.html`)
- [ ] 2.2 Add panel HTML (`templates/editor.html`)
- [ ] 2.3 Style button (`static/css/editor-toolbar.css`)
- [ ] 2.4 Style panel + highlighting + tooltips (`static/css/editor.css`)
- [ ] 2.5 Create ThinkingModeManager with streaming state (`static/js/editor/thinking-mode-manager.js`)
- [ ] 2.6 Add node hover event listeners (for tooltips)
- [ ] 2.7 Integrate with toolbar manager
- [ ] 2.8 Add diagram validation
- [ ] 2.9 Load script in editor.html

### Phase 3: Integration & Testing - Circle Map (6-8 hours)
- [ ] 3.1 End-to-end test: Complete workflow (10 → 5 nodes)
- [ ] 3.2 Test node highlighting (all 4 types)
- [ ] 3.3 Test hover tooltips
- [ ] 3.4 Test race conditions (double-click, rapid sends, multi-tab)
- [ ] 3.5 Test multi-language support
- [ ] 3.6 Fix bugs and polish UX

### Phase 4: All 7 Remaining Thinking Maps (2-3 hours each = 14-21 hours total)

**Per diagram workflow (super fast with base agent!):**

#### Bubble Map (2-3 hours)
- [ ] 4.1.1 Create `prompts/thinking_modes/bubble_map.py` (6 prompts for describing)
- [ ] 4.1.2 Create `agents/thinking_modes/bubble_map_agent.py` (extends base, ~50 lines!)
- [ ] 4.1.3 Add to factory.py (1 line!)
- [ ] 4.1.4 Test workflow

#### Double Bubble Map (2-3 hours)
- [ ] 4.2.1 Create `prompts/thinking_modes/double_bubble_map.py` (comparing/contrasting)
- [ ] 4.2.2 Create `agents/thinking_modes/double_bubble_map_agent.py`
- [ ] 4.2.3 Add to factory.py
- [ ] 4.2.4 Test workflow

#### Tree Map (2-3 hours)
- [ ] 4.3.1 Create `prompts/thinking_modes/tree_map.py` (classifying)
- [ ] 4.3.2 Create `agents/thinking_modes/tree_map_agent.py`
- [ ] 4.3.3 Add to factory.py
- [ ] 4.3.4 Test workflow

#### Brace Map (2-3 hours)
- [ ] 4.4.1 Create `prompts/thinking_modes/brace_map.py` (whole-to-part)
- [ ] 4.4.2 Create `agents/thinking_modes/brace_map_agent.py`
- [ ] 4.4.3 Add to factory.py
- [ ] 4.4.4 Test workflow

#### Flow Map (2-3 hours)
- [ ] 4.5.1 Create `prompts/thinking_modes/flow_map.py` (sequencing)
- [ ] 4.5.2 Create `agents/thinking_modes/flow_map_agent.py`
- [ ] 4.5.3 Add to factory.py
- [ ] 4.5.4 Test workflow

#### Multi-Flow Map (2-3 hours)
- [ ] 4.6.1 Create `prompts/thinking_modes/multi_flow_map.py` (cause & effect)
- [ ] 4.6.2 Create `agents/thinking_modes/multi_flow_map_agent.py`
- [ ] 4.6.3 Add to factory.py
- [ ] 4.6.4 Test workflow

#### Bridge Map (2-3 hours)
- [ ] 4.7.1 Create `prompts/thinking_modes/bridge_map.py` (analogies)
- [ ] 4.7.2 Create `agents/thinking_modes/bridge_map_agent.py`
- [ ] 4.7.3 Add to factory.py
- [ ] 4.7.4 Test workflow

### Total Estimated Time:
- **Phase 1 (Backend MVP):** 10-14 hours
- **Phase 2 (Frontend):** 10-14 hours
- **Phase 3 (Testing):** 6-8 hours
- **Phase 4 (7 more maps):** 14-21 hours
- **GRAND TOTAL:** 40-57 hours for ALL 8 thinking maps! 🎯

---

## 🏗️ Step-by-Step Build Guide

### PHASE 1: BACKEND

---

#### Step 1.0: Create Base Agent (NEW! - Shared by All 8 Maps)

**File:** `agents/thinking_modes/base_agent.py`

**What:** Shared base class containing workflow logic and race condition handling for ALL thinking maps

**Why This First:**
- Contains the core state machine (7 states)
- Implements session locking to prevent race conditions
- Has all handler methods that child agents will use
- Written ONCE, used by all 8 map types!

**Tasks:**
1. Create directory: `mkdir -p agents/thinking_modes`
2. Create `__init__.py`: `touch agents/thinking_modes/__init__.py`
3. Create base agent file (see Code Template 9 below - NEW!)

**Key Components:**
```python
class BaseThinkingAgent:
    """
    Base class for all thinking map agents.
    Handles workflow, state management, and race condition prevention.
    """
    
    # Race condition handling
    self.session_locks: Dict[str, asyncio.Lock] = {}
    
    # Session management
    self.sessions: Dict[str, Dict] = {}
    
    # Abstract methods (to be implemented by child classes)
    def get_prompts(self):
        """Return prompts dict - implemented by Circle/Bubble/Tree agents"""
        raise NotImplementedError
    
    def get_state_enum(self):
        """Return state enum class - same for all maps"""
        return ThinkingMapState
    
    # Workflow methods (shared by all!)
    async def process_step(...)  # Main entry with locking
    async def _handle_context_gathering(...)
    async def _handle_educational_analysis(...)
    async def _handle_analysis(...)
    async def _handle_refinement_1(...)
    async def _handle_refinement_2(...)
    async def _handle_final_refinement(...)
    async def _stream_llm_response(...)
```

**Race Condition Features:**
- ✅ `asyncio.Lock` per session
- ✅ Non-blocking check with immediate rejection
- ✅ `is_processing` flag as backup
- ✅ `async with` ensures lock always released
- ✅ Detailed error responses with `SESSION_BUSY` code

**Acceptance Criteria:**
- [ ] Base class can be imported
- [ ] Has all 7 state handlers
- [ ] Implements session locking correctly
- [ ] Abstract methods defined for child classes
- [ ] Can be tested in isolation

**Child Agent Example:**
```python
# Circle Map agent becomes super simple!
from agents.thinking_modes.base_agent import BaseThinkingAgent
from prompts.thinking_modes.circle_map import (
    CONTEXT_GATHERING_PROMPT,
    EDUCATIONAL_ANALYSIS_PROMPT,
    # ... other prompts
)

class CircleMapThinkingAgent(BaseThinkingAgent):
    """Circle Map agent - only needs to provide prompts!"""
    
    def get_prompts(self):
        """Return Circle Map specific prompts"""
        return {
            'CONTEXT_GATHERING': CONTEXT_GATHERING_PROMPT,
            'EDUCATIONAL_ANALYSIS': EDUCATIONAL_ANALYSIS_PROMPT,
            'ANALYSIS': ANALYSIS_PROMPT,
            'REFINEMENT_1': REFINEMENT_1_PROMPT,
            'REFINEMENT_2': REFINEMENT_2_PROMPT,
            'FINAL_REFINEMENT': FINAL_REFINEMENT_PROMPT,
            'EVALUATE': EVALUATE_REASONING_PROMPT
        }
    
    # That's it! All workflow logic in base class!
```

**Why This Matters:**
- Circle Map agent: ~300 lines → Now ~50 lines!
- Adding Bubble Map: Just prompts + 50 line wrapper
- Consistency: All maps behave identically
- Testing: Test base once, works for all

---

#### Step 1.1: Create Prompt File

**File:** `prompts/thinking_modes/circle_map.py`

**What:** Contains all 6 prompts for Circle Map workflow

**Tasks:**
1. Create directory: `mkdir -p prompts/thinking_modes`
2. Create `__init__.py`: `touch prompts/thinking_modes/__init__.py`
3. Create prompt file (see Code Template 1 below)

**Acceptance Criteria:**
- File exists and can be imported
- All 6 prompts defined as module-level variables
- Prompts use Socratic questioning (not directive)

---

#### Step 1.2: Create Circle Map Agent

**File:** `agents/thinking_modes/circle_map_agent.py`

**What:** Main agent class that handles Circle Map workflow

**Dependencies:**
- Study `agents/learning/learning_agent_v3.py` first (LangChain pattern!)
- Uses existing `clients/llm.py` for Qwen-Plus
- Uses prompts from Step 1.1

**Tasks:**
1. Create directory: `mkdir -p agents/thinking_modes`
2. Create `__init__.py`: `touch agents/thinking_modes/__init__.py`
3. Create agent file (see Code Template 2 below)

**Key Components:**
- State machine: `CircleMapState` enum (7 states)
- Session management: In-memory dict (MVP)
- LLM client: Qwen-Plus via Dashscope
- Methods:
  - `process_step()` - Main entry point (SSE streaming)
  - `_handle_context_gathering()` - Step 1
  - `_handle_educational_analysis()` - Step 2 (NEW!)
  - `_handle_analysis()` - Step 3 (Socratic questions)
  - `_handle_refinement_1()` - Step 4 (N → 8)
  - `_handle_refinement_2()` - Step 5 (8 → 6)
  - `_handle_final_refinement()` - Step 6 (6 → 5)
  - `_stream_llm_response()` - LLM streaming helper

**Acceptance Criteria:**
- Agent can be instantiated
- All state handlers implemented
- Uses Qwen-Plus model
- Stores `node_learning_material` in session (for tooltips!)

---

#### Step 1.3: Create Agent Factory

**File:** `agents/thinking_modes/factory.py`

**What:** Routes diagram types to correct agent (Factory Pattern)

**Tasks:**
1. Create factory class (see Code Template 3 below)
2. Add Circle Map routing
3. Add error handling for unknown diagram types

**Acceptance Criteria:**
- `ThinkingAgentFactory.get_agent('circle_map')` returns `CircleMapThinkingAgent`
- Raises `ValueError` for unknown diagram types
- Easy to add new diagram types

---

#### Step 1.4: Create API Router

**File:** `routers/thinking.py`

**What:** FastAPI router with 2 endpoints for ALL diagram types

**Endpoints:**
1. `POST /api/thinking_mode/stream` - Main SSE streaming (all diagrams)
2. `GET /api/thinking_mode/node_learning/{session_id}/{node_id}` - Hover tooltips

**Tasks:**
1. Create router file (see Code Template 4 below)
2. Add SSE streaming endpoint
3. Add tooltip endpoint
4. Add error handling and logging

**Acceptance Criteria:**
- Both endpoints accessible
- Factory pattern used (no diagram-specific endpoints!)
- SSE headers set correctly
- Error responses are JSON

---

#### Step 1.5: Add Request Model

**File:** `models/requests.py`

**What:** Pydantic model for request validation

**Tasks:**
1. Open `models/requests.py`
2. Add `ThinkingModeRequest` class (see Code Template 5 below)

**Acceptance Criteria:**
- Model validates required fields
- `diagram_type` validates against known types
- `selected_node` is optional

---

#### Step 1.6: Register Router in Main

**File:** `main.py`

**What:** Include thinking router in FastAPI app

**Tasks:**
1. Import thinking router
2. Include router with prefix

```python
# Add to imports
from routers import api, pages, learning, thinking

# Add after other routers
app.include_router(thinking.router, prefix='/api', tags=['thinking'])
```

**Acceptance Criteria:**
- Server starts without errors
- Endpoints show in OpenAPI docs at `/docs`

---

#### Step 1.7: Test Backend

**Manual Testing:**
1. Start server: `python run_server.py`
2. Check OpenAPI docs: `http://localhost:8000/docs`
3. Test with curl or Postman:

```bash
# Test SSE endpoint
curl -X POST http://localhost:8000/api/thinking_mode/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "",
    "user_id": "test_user",
    "session_id": "test_123",
    "diagram_type": "circle_map",
    "diagram_data": {
      "center": {"text": "Photosynthesis"},
      "children": [
        {"id": "1", "text": "Sunlight"},
        {"id": "2", "text": "Water"}
      ]
    },
    "current_state": "CONTEXT_GATHERING"
  }'
```

**Expected:** SSE stream with context gathering prompt

**Acceptance Criteria:**
- No Python errors
- SSE stream starts
- Agent asks for context (grade level, objective, etc.)

---

### PHASE 2: FRONTEND

---

#### Step 2.1: Add Thinking Button

**File:** `templates/editor.html`

**Location:** Around line 424 (after Learning button)

**Add:**
```html
<!-- ThinkGuide Button -->
<button id="thinking-btn" class="btn-tool btn-thinking" title="ThinkGuide (思维向导)" disabled>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2a4 4 0 0 0-4 4v1a4 4 0 0 0-4 4v2a4 4 0 0 0 4 4h8a4 4 0 0 0 4-4V11a4 4 0 0 0-4-4V6a4 4 0 0 0-4-4z"/>
        <circle cx="8" cy="10" r="1"/>
        <circle cx="16" cy="10" r="1"/>
    </svg>
    <span id="thinking-btn-text">ThinkGuide</span>
</button>
```

**Acceptance Criteria:**
- Button appears in toolbar next to Learning button
- Button is disabled by default (no diagram yet)

---

#### Step 2.2: Add Panel HTML

**File:** `templates/editor.html`

**Location:** Around line 544 (after AI Assistant panel)

**Add:** ThinkGuide panel HTML (See Code Template 6 below for full structure)

**Acceptance Criteria:**
- Panel exists in DOM with "ThinkGuide" branding
- Panel is collapsed by default (off-screen left)
- Header shows "ThinkGuide" / "思维向导"

---

#### Step 2.3: Style Button

**File:** `static/css/editor-toolbar.css`

**Add:**
```css
/* Thinking Mode Button - Purple Gradient */
.btn-thinking {
    background: linear-gradient(135deg, #9C27B0, #7B1FA2);
    color: white;
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(156, 39, 176, 0.3);
    transition: all 0.3s ease;
}

.btn-thinking:not(:disabled):hover {
    background: linear-gradient(135deg, #7B1FA2, #6A1B9A);
    box-shadow: 0 4px 12px rgba(156, 39, 176, 0.5);
    transform: translateY(-1px);
}

.btn-thinking:disabled {
    background: linear-gradient(135deg, #e0e0e0, #bdbdbd);
    color: #757575;
    cursor: not-allowed;
    box-shadow: none;
}

.btn-thinking.active {
    background: linear-gradient(135deg, #6A1B9A, #4A148C);
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);
}
```

**Acceptance Criteria:**
- Button has purple gradient
- Hover effect works
- Disabled state is gray

---

#### Step 2.4: Style Panel, Highlights, and Tooltips

**File:** `static/css/editor.css`

**Add:** (See Code Template 7 below - includes)
- Panel styles (slide from left)
- Progress bar styles
- Message styles
- **Node highlighting styles** (4 types: remove, keep, analyze, question)
- **Tooltip styles** (hover to see learning material)

**Acceptance Criteria:**
- Panel slides smoothly from left (400ms)
- All 4 highlight types render correctly
- Tooltip has purple gradient and smooth fade-in

---

#### Step 2.5: Create ThinkingModeManager

**File:** `static/js/editor/thinking-mode-manager.js`

**What:** Main JavaScript class that manages Thinking Mode UI and communication

**Key Methods:**
- Constructor: Initialize state
- `startThinkingMode()`: Begin workflow
- `extractDiagramData()`: Get diagram structure + selected node
- `sendMessage(message)`: Send user message to backend
- `streamResponse()`: Handle SSE streaming
- `updateProgress(percent)`: Update progress bar
- `handleStateTransition(newState)`: State machine transitions
- `highlightNodes(nodeIds, type)`: Visual highlighting 🎨
- `showNodeLearningTooltip(nodeId)`: Show hover tooltip 📚
- `hideNodeLearningTooltip()`: Hide tooltip
- `renderMessage(role, content)`: Render chat message with Markdown

**Tasks:**
1. Create file (see Code Template 8 below)
2. Implement all methods
3. Test in isolation

**Acceptance Criteria:**
- Class can be instantiated
- SSE streaming works
- Messages render with Markdown
- Node highlighting applies CSS classes
- Tooltip fetches and displays learning material

---

#### Step 2.6: Add Node Hover Event Listeners

**File:** `static/js/editor/interactive-editor.js` (or wherever nodes are created)

**What:** Add mouseenter/mouseleave to all diagram nodes for tooltips

**Add to node creation logic:**
```javascript
// After creating a node element
function setupNodeForThinking(nodeElement, nodeId) {
    nodeElement.on('mouseenter', function() {
        if (window.thinkingModeManager && 
            window.thinkingModeManager.isActive() &&
            window.thinkingModeManager.hasLearningMaterial()) {
            window.thinkingModeManager.showNodeLearningTooltip(nodeId);
        }
    });
    
    nodeElement.on('mouseleave', function() {
        window.thinkingModeManager?.hideNodeLearningTooltip();
    });
}
```

**Acceptance Criteria:**
- All nodes have hover listeners
- Tooltip only shows when Thinking Mode active
- Tooltip hides on mouseleave

---

#### Step 2.7: Integrate with Toolbar Manager

**File:** `static/js/editor/toolbar-manager.js`

**Add to constructor:**
```javascript
this.thinkingModeManager = null;
```

**Add button handler:**
```javascript
// In bindEvents() method
const thinkingBtn = document.getElementById('thinking-btn');
if (thinkingBtn) {
    thinkingBtn.addEventListener('click', () => this.handleThinkingMode());
}
```

**Add method:**
```javascript
async handleThinkingMode() {
    if (!this.thinkingModeManager) {
        this.thinkingModeManager = new ThinkingModeManager(
            this.diagramType,
            this.canvasManager
        );
    }
    
    await this.thinkingModeManager.startThinkingMode();
}
```

**Acceptance Criteria:**
- Button click triggers Thinking Mode
- Panel opens on click

---

#### Step 2.8: Add Diagram Validation

**File:** `static/js/editor/diagram-validator.js`

**Add method:**
```javascript
validateForThinkingMode(diagramType) {
    const result = this.validateDiagram(diagramType);
    const thinkingBtn = document.getElementById('thinking-btn');
    
    if (result.isValid && !result.hasPlaceholders) {
        thinkingBtn.disabled = false;
    } else {
        thinkingBtn.disabled = true;
    }
    
    return result;
}
```

**Call from interactive-editor.js:**
```javascript
// After diagram changes
diagramValidator.validateForThinkingMode(currentDiagramType);
```

**Acceptance Criteria:**
- Button enables when diagram valid
- Button disables when diagram has placeholders

---

#### Step 2.9: Load Script

**File:** `templates/editor.html`

**Location:** Around line 651 (after other editor scripts)

**Add:**
```html
<script src="/static/js/editor/thinking-mode-manager.js"></script>
```

**Acceptance Criteria:**
- Script loads without errors
- `ThinkingModeManager` class available globally

---

### PHASE 3: INTEGRATION & TESTING

#### Test 3.1: Complete Workflow

**Scenario:** Circle Map - "Photosynthesis" with 10 nodes

**Steps:**
1. Create Circle Map with center "Photosynthesis"
2. Add 10 children: sunlight, water, CO2, oxygen, glucose, chlorophyll, leaves, energy, plants, green color
3. Click "Thinking" button
4. **Context Gathering:** Provide "5th grade science, identify core photosynthesis components"
5. **Educational Analysis:** Read analysis of all 10 nodes
6. **Hover Test:** Hover over "Chlorophyll" → See tooltip with learning material
7. **Socratic Analysis:** Answer questions about node relationships
8. **Refinement 1:** Remove 2 nodes (10 → 8), explain reasoning
9. **Refinement 2:** Remove 2 nodes (8 → 6), explain reasoning
10. **Final Refinement:** Remove 1 node (6 → 5), explain reasoning
11. **Completion:** Review summary

**Expected Results:**
✅ All state transitions automatic  
✅ Progress bar: 0% → 25% → 40% → 60% → 75% → 90% → 100%  
✅ Nodes highlight when discussed (RED/GREEN/BLUE glows)  
✅ Tooltips show on hover (after Educational Analysis)  
✅ Messages render with Markdown  
✅ Agent uses Socratic questions (not directives)  

---

#### Test 3.2: Node Highlighting

**Test Cases:**
1. Agent mentions node → Node glows
2. Agent recommends removal → RED pulse
3. Agent suggests keeping → GREEN glow
4. Agent asks about node → ORANGE pulse
5. Multiple nodes mentioned → All highlight correctly
6. State change → Previous highlights clear

---

#### Test 3.3: Hover Tooltips

**Test Cases:**
1. Before Educational Analysis → No tooltips
2. After Educational Analysis → Tooltips work
3. Hover over "Sunlight" → See relationship, value, depth
4. Hover over "Green Color" → See it's "surface observation"
5. Move mouse away → Tooltip disappears
6. Tooltip doesn't block node clicks
7. Works on all nodes, not just discussed ones

---

#### Test 3.4: Multi-Language

**Test Cases:**
1. Switch to Chinese → Button shows "思维向导" (ThinkGuide)
2. Panel header shows "思维向导"
3. Agent messages in Chinese
4. Tooltips in Chinese
5. Progress labels in Chinese

---

#### Test 3.5: Error Handling

**Test Cases:**
1. Network error during SSE → Error message shown
2. Invalid diagram type → Validation error
3. Server error → User-friendly message
4. Empty message → No request sent

---

## 💻 Code Templates

### Template 1: Prompts File

**File:** `prompts/thinking_modes/circle_map.py`

```python
"""
Circle Map Thinking Mode Prompts
Uses Socratic questioning to guide critical thinking
"""

# Step 1: Context Gathering
CONTEXT_GATHERING_PROMPT = """
Welcome! I'm here to help you refine your Circle Map on "{center_node}" through guided thinking.

To provide the best guidance, I need to understand your educational context:

1. **Grade Level:** What grade level is this for? (e.g., 3rd grade, 8th grade)
2. **Learning Objective:** What should students learn from this Circle Map?
3. **Lesson Context:** How will this be used? (e.g., introduction, review, assessment)
4. **Subject/Topic:** What subject area is this for?

Please share this context so we can begin our thinking journey together!
"""

# Step 2: Educational Analysis (NEW!)
EDUCATIONAL_ANALYSIS_PROMPT = """
You are providing EDUCATIONAL CONTENT about each node's relationship to "{center_node}".

**Context:**
- Grade Level: {grade_level}
- Objective: {objective}
- Center Topic: {center_node}

**Current Nodes ({node_count}):**
{nodes}

**Your Task:** TEACH the teacher about each node BEFORE refinement begins.

For EACH node, analyze:
1. **Relationship to {center_node}:** Direct? Indirect? Component? Input? Output? Example?
2. **Educational Value:** Why would students need to know this?
3. **Depth Level:** Surface detail, Core concept, or Foundational understanding?
4. **For {grade_level}:** Is this appropriate complexity? Essential or supplementary?

**Format:**
Group similar nodes (e.g., "Inputs", "Outputs", "Processes", "Observations") and provide 2-3 sentences per node.

**Example:**
**Essential Inputs (Foundational):**
- **Sunlight:** Primary energy source; absolutely foundational for understanding photosynthesis. Students must grasp this to understand the process.
- **Water:** Critical INPUT absorbed through roots; needed for the chemical reaction. Age-appropriate and essential.

**Observable Characteristics:**
- **Green Color:** Visible result of chlorophyll; engaging but not essential to the process itself. More of a surface observation than a core concept.

**Tone:** Educational, informative, supportive. You're sharing expertise with a colleague.

**Closing:** Ask "What surprises you? What becomes clearer?" to invite reflection.
"""

# Step 3: Socratic Analysis
ANALYSIS_PROMPT = """
You are a SOCRATIC GUIDE helping a K12 teacher think critically about their Circle Map on "{center_node}".

**Context:**
- Grade Level: {grade_level}
- Objective: {objective}
- Center: {center_node}
- Nodes ({node_count}): {nodes}

**CRITICAL - Use Socratic Method:**

DO NOT tell the teacher what to do. ASK QUESTIONS that help them discover insights.

**Socratic Question Types:**

1. **Clarifying Questions:**
   - "What do you mean by [node]?"
   - "Can you explain how [node A] and [node B] are related?"

2. **Probing Assumptions:**
   - "Why did you include [node]?"
   - "What assumption are you making about [concept]?"

3. **Examining Evidence:**
   - "Looking at your {grade_level} objective, which nodes feel most central?"
   - "If students understood only 5 concepts, which would create the deepest understanding?"

4. **Exploring Implications:**
   - "If you combine [node A] and [node B], what would that tell you?"
   - "How does including [node] affect what students will focus on?"

**Your Response:**

1. **Opening:** Acknowledge their work: "I see you have {node_count} nodes here. Let's think about these together."

2. **Ask 3-4 Socratic Questions:**
   - Focus on relationships, overlaps, and hierarchies
   - Help them see patterns they might not have noticed
   - Guide toward distinctions (inputs vs. outputs, core vs. supporting, etc.)

3. **Invitation:** "Take a moment - what patterns do you notice?"

**Tone:** Curious, supportive, thought-provoking. You're a thinking partner, not an instructor.

**Goal:** Teacher develops their own insights about node quality and relationships.
"""

# Step 4: Refinement 1 (N → 8)
REFINEMENT_1_PROMPT = """
You're helping refine from {node_count} to 8 nodes using the Socratic method.

**Context:**
- Grade Level: {grade_level}
- Objective: {objective}
- Current nodes: {node_count}
- Target: 8 core nodes

**Use Socratic Questioning:**

1. **Frame the Challenge:**
   "You've identified {node_count} aspects. Now let's think about what's truly essential..."
   
2. **Guiding Questions:**
   - "If you could only keep 8 - the most essential for {grade_level} - which would you choose?"
   - "What makes something 'essential'? Is it importance? Foundational understanding? Testability?"
   - "Looking at all {node_count}, which ones feel like 'nice to know' versus 'need to know'?"

3. **Metacognitive Prompt:**
   "Before you decide, ask yourself: What principle will guide my choice?"

4. **Request Reasoning:**
   "Which {removals} would you refine away? What's your reasoning?"

**Tone:** Encouraging, thought-provoking. Help them discover their own criteria.

**Goal:** Teacher articulates WHY they're removing nodes, not just WHICH nodes.
"""

# Step 5: Refinement 2 (8 → 6)
REFINEMENT_2_PROMPT = """
You're guiding the second refinement from 8 to 6 nodes.

**Previous Refinement:** Teacher removed nodes based on [their stated principle]

**Socratic Approach:**

1. **Acknowledge Progress:**
   "Good thinking on that first refinement. You removed nodes based on [principle]."

2. **Deepen the Inquiry:**
   - "Now we're narrowing to 6 - only the MOST core concepts. How does your criteria need to evolve?"
   - "Looking at your remaining 8, which are 'need to know' versus 'nice to know' for {grade_level}?"
   - "Notice how your thinking might be shifting. What makes something essential at 6 nodes vs. at 8?"

3. **Challenge Assumptions:**
   - "Are you choosing based on what's testable, or what's foundational? Is there a difference?"
   - "If students only learned these 6, could they build toward the other concepts on their own?"

4. **Probe Difficulty:**
   "What's making this decision harder than the last one? What does that tell you?"

**Goal:** Help teacher recognize they're developing increasingly sophisticated criteria.
"""

# Step 6: Final Refinement (6 → 5)
FINAL_REFINEMENT_PROMPT = """
You're guiding the final, hardest refinement: 6 to 5 core nodes.

**Socratic Approach for Final Decision:**

1. **Frame the Challenge:**
   "You've done excellent thinking to get here. These 6 nodes are all strong. Now comes the hardest question..."

2. **Ultimate Question:**
   "If you could only teach 5 concepts about {center_node} that would create the deepest, most lasting understanding, which 5 would you choose?"

3. **Alternative Framings:**
   - "Which single node, if removed, would be least missed?"
   - "Or: Which 5 together form a complete picture?"
   - "If students understood only these 5, could they build toward the 6th on their own?"

4. **Acknowledge Difficulty:**
   "There may not be one 'right' answer. What matters is your reasoning."

5. **Metacognitive Reflection:**
   "Take your time. What does this final decision reveal about what you believe is essential?"

**Goal:** Teacher makes a deeply reasoned choice and understands their own thinking process.
"""

# Step 7: Evaluate Reasoning (Used after each refinement)
EVALUATE_REASONING_PROMPT = """
The teacher removed nodes: {removed_nodes}
Their reasoning: {user_reasoning}

**Your Socratic Response:**

1. **Acknowledge Their Thinking:**
   "Interesting [distinction/principle/insight] - [quote their key idea]."

2. **Probe Deeper:**
   - "How did you arrive at that principle?"
   - "What does this decision tell you about how you understand {center_node}?"
   - "You're [identifying pattern]. Does that align with your {objective}?"

3. **Explore Implications:**
   - If they made a sophisticated distinction: "That's advanced thinking - separating [X] from [Y]."
   - If they seem uncertain: "What's making you uncertain about this choice?"

4. **Build Confidence:**
   Acknowledge growth: "You're developing [skill/insight] through this process."

**DO NOT:**
- Judge as right/wrong
- Tell them what they should have done
- Give direct answers

**DO:**
- Ask questions that deepen their reasoning
- Help them see patterns in their own thinking
- Build metacognitive awareness

**Tone:** Supportive, curious, respectful of their expertise.
"""
```

---

### Template 2: Circle Map Agent

**File:** `agents/thinking_modes/circle_map_agent.py`

```python
"""
Circle Map Thinking Mode Agent
Guides teachers through Socratic refinement of Circle Maps
"""

import logging
import json
import uuid
from enum import Enum
from typing import Dict, List, AsyncGenerator, Optional

from clients.llm import LLMClient
from config.settings import settings
from prompts.thinking_modes.circle_map import (
    CONTEXT_GATHERING_PROMPT,
    EDUCATIONAL_ANALYSIS_PROMPT,
    ANALYSIS_PROMPT,
    REFINEMENT_1_PROMPT,
    REFINEMENT_2_PROMPT,
    FINAL_REFINEMENT_PROMPT,
    EVALUATE_REASONING_PROMPT
)

logger = logging.getLogger(__name__)


class CircleMapState(Enum):
    """State machine for Circle Map thinking workflow"""
    CONTEXT_GATHERING = "CONTEXT_GATHERING"
    EDUCATIONAL_ANALYSIS = "EDUCATIONAL_ANALYSIS"
    ANALYSIS = "ANALYSIS"
    REFINEMENT_1 = "REFINEMENT_1"
    REFINEMENT_2 = "REFINEMENT_2"
    FINAL_REFINEMENT = "FINAL_REFINEMENT"
    COMPLETE = "COMPLETE"


class CircleMapThinkingAgent:
    """
    Thinking Mode agent for Circle Maps.
    Uses Socratic method to guide critical thinking.
    """
    
    def __init__(self):
        """Initialize agent with Qwen-Plus LLM"""
        # Use Qwen-Plus for better reasoning
        self.llm = LLMClient(
            api_url=settings.DASHSCOPE_API_URL,
            api_key=settings.DASHSCOPE_API_KEY,
            model='qwen-plus',  # Better than qwen-turbo for Socratic dialogue
            temperature=0.7,
            stream=True
        )
        
        # Session storage (in-memory for MVP, move to Redis for production)
        self.sessions: Dict[str, Dict] = {}
    
    async def process_step(
        self,
        message: str,
        session_id: str,
        diagram_data: Dict,
        current_state: str,
        user_id: str = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Main entry point - processes one step of the workflow.
        Yields SSE events.
        """
        
        # Get or create session
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'session_id': session_id,
                'user_id': user_id,
                'state': CircleMapState.CONTEXT_GATHERING,
                'diagram_data': diagram_data,
                'history': [],
                'context': {},
                'node_count': len(diagram_data.get('children', [])),
                'node_learning_material': {}  # For hover tooltips!
            }
        
        session = self.sessions[session_id]
        
        # Update diagram data if provided
        if diagram_data:
            session['diagram_data'] = diagram_data
        
        # Route to appropriate handler based on state
        state = CircleMapState(current_state)
        
        if state == CircleMapState.CONTEXT_GATHERING:
            async for chunk in self._handle_context_gathering(session, message):
                yield chunk
        
        elif state == CircleMapState.EDUCATIONAL_ANALYSIS:
            async for chunk in self._handle_educational_analysis(session, message):
                yield chunk
        
        elif state == CircleMapState.ANALYSIS:
            async for chunk in self._handle_analysis(session, message):
                yield chunk
        
        elif state == CircleMapState.REFINEMENT_1:
            async for chunk in self._handle_refinement_1(session, message):
                yield chunk
        
        elif state == CircleMapState.REFINEMENT_2:
            async for chunk in self._handle_refinement_2(session, message):
                yield chunk
        
        elif state == CircleMapState.FINAL_REFINEMENT:
            async for chunk in self._handle_final_refinement(session, message):
                yield chunk
        
        else:
            yield {
                'event': 'error',
                'message': f'Unknown state: {state}'
            }
    
    async def _handle_context_gathering(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 1: Gather educational context"""
        
        if not message:
            # First time - ask for context
            prompt = CONTEXT_GATHERING_PROMPT.format(
                center_node=session['diagram_data']['center']['text']
            )
            
            async for chunk in self._stream_llm_response(prompt, session):
                yield chunk
        
        else:
            # User provided context - parse and store
            session['history'].append({
                'role': 'user',
                'content': message,
                'state': 'CONTEXT_GATHERING'
            })
            
            # Store context (simplified - could use LLM to parse)
            session['context'] = {
                'grade_level': 'extracted from message',  # TODO: Parse properly
                'objective': 'extracted from message',
                'lesson_context': 'extracted from message'
            }
            
            # Transition to EDUCATIONAL_ANALYSIS
            session['state'] = CircleMapState.EDUCATIONAL_ANALYSIS
            
            yield {
                'event': 'state_transition',
                'new_state': 'EDUCATIONAL_ANALYSIS',
                'progress': 25
            }
            
            # Automatically start educational analysis
            async for chunk in self._handle_educational_analysis(session, ''):
                yield chunk
    
    async def _handle_educational_analysis(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 2: Provide educational content about each node"""
        
        nodes = session['diagram_data']['children']
        context = session['context']
        
        # Build educational analysis prompt
        prompt = EDUCATIONAL_ANALYSIS_PROMPT.format(
            center_node=session['diagram_data']['center']['text'],
            nodes='\n'.join([f"- {node['text']}" for node in nodes]),
            node_count=len(nodes),
            grade_level=context.get('grade_level', 'not specified'),
            objective=context.get('objective', 'not specified')
        )
        
        # Stream educational content
        full_response = ""
        async for chunk in self._stream_llm_response(prompt, session):
            if chunk.get('event') == 'message_chunk':
                full_response += chunk.get('content', '')
            yield chunk
        
        # TODO: Parse response and store per-node learning material
        # For now, store full response
        # In production, use LLM to extract structured data per node
        for node in nodes:
            session['node_learning_material'][node['id']] = {
                'node_name': node['text'],
                'full_analysis': full_response  # Simplified
                # TODO: Extract specific fields:
                # 'relationship': '...',
                # 'educational_value': '...',
                # 'depth_level': '...',
                # 'age_appropriateness': '...'
            }
        
        # Transition to ANALYSIS (Socratic questions)
        session['state'] = CircleMapState.ANALYSIS
        
        yield {
            'event': 'state_transition',
            'new_state': 'ANALYSIS',
            'progress': 40
        }
        
        # Automatically start Socratic analysis
        async for chunk in self._handle_analysis(session, ''):
            yield chunk
    
    async def _handle_analysis(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 3: Socratic questioning about nodes"""
        
        nodes = session['diagram_data']['children']
        context = session['context']
        
        prompt = ANALYSIS_PROMPT.format(
            center_node=session['diagram_data']['center']['text'],
            nodes=', '.join([node['text'] for node in nodes]),
            node_count=len(nodes),
            grade_level=context.get('grade_level', 'not specified'),
            objective=context.get('objective', 'not specified')
        )
        
        async for chunk in self._stream_llm_response(prompt, session):
            yield chunk
        
        # Transition to REFINEMENT_1
        session['state'] = CircleMapState.REFINEMENT_1
        
        yield {
            'event': 'state_transition',
            'new_state': 'REFINEMENT_1',
            'progress': 60
        }
        
        # Ask refinement question
        refinement_prompt = REFINEMENT_1_PROMPT.format(
            node_count=len(nodes),
            grade_level=context.get('grade_level', ''),
            objective=context.get('objective', ''),
            removals=len(nodes) - 8
        )
        
        async for chunk in self._stream_llm_response(refinement_prompt, session):
            yield chunk
    
    async def _handle_refinement_1(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 4: First refinement (N → 8)"""
        
        session['history'].append({
            'role': 'user',
            'content': message,
            'state': 'REFINEMENT_1'
        })
        
        # Evaluate reasoning
        evaluation_prompt = EVALUATE_REASONING_PROMPT.format(
            removed_nodes='extracted from message',  # TODO: Parse
            user_reasoning=message,
            center_node=session['diagram_data']['center']['text'],
            objective=session['context'].get('objective', '')
        )
        
        async for chunk in self._stream_llm_response(evaluation_prompt, session):
            yield chunk
        
        # Update node count
        session['node_count'] = 8
        
        # Transition to REFINEMENT_2
        session['state'] = CircleMapState.REFINEMENT_2
        
        yield {
            'event': 'state_transition',
            'new_state': 'REFINEMENT_2',
            'progress': 75
        }
        
        # Ask next refinement
        refinement_prompt = REFINEMENT_2_PROMPT.format(
            grade_level=session['context'].get('grade_level', '')
        )
        
        async for chunk in self._stream_llm_response(refinement_prompt, session):
            yield chunk
    
    async def _handle_refinement_2(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 5: Second refinement (8 → 6)"""
        
        session['history'].append({
            'role': 'user',
            'content': message,
            'state': 'REFINEMENT_2'
        })
        
        # Evaluate reasoning
        evaluation_prompt = EVALUATE_REASONING_PROMPT.format(
            removed_nodes='extracted',
            user_reasoning=message,
            center_node=session['diagram_data']['center']['text'],
            objective=session['context'].get('objective', '')
        )
        
        async for chunk in self._stream_llm_response(evaluation_prompt, session):
            yield chunk
        
        session['node_count'] = 6
        
        # Transition to FINAL_REFINEMENT
        session['state'] = CircleMapState.FINAL_REFINEMENT
        
        yield {
            'event': 'state_transition',
            'new_state': 'FINAL_REFINEMENT',
            'progress': 90
        }
        
        # Ask final refinement
        final_prompt = FINAL_REFINEMENT_PROMPT.format(
            center_node=session['diagram_data']['center']['text']
        )
        
        async for chunk in self._stream_llm_response(final_prompt, session):
            yield chunk
    
    async def _handle_final_refinement(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 6: Final refinement (6 → 5)"""
        
        session['history'].append({
            'role': 'user',
            'content': message,
            'state': 'FINAL_REFINEMENT'
        })
        
        # Final evaluation and completion
        completion_prompt = f"""
The teacher's final decision: {message}

Acknowledge their deep thinking and provide a brief summary:
1. The 5 core nodes they've identified
2. The thinking process they demonstrated
3. How this refined map serves their educational objective

End with encouragement about their critical thinking journey.
"""
        
        async for chunk in self._stream_llm_response(completion_prompt, session):
            yield chunk
        
        # Mark complete
        session['state'] = CircleMapState.COMPLETE
        
        yield {
            'event': 'state_transition',
            'new_state': 'COMPLETE',
            'progress': 100
        }
        
        yield {
            'event': 'complete',
            'summary': {
                'final_node_count': 5,
                'history': session['history']
            }
        }
    
    async def _stream_llm_response(
        self,
        prompt: str,
        session: Dict
    ) -> AsyncGenerator[Dict, None]:
        """Helper: Stream LLM response as SSE chunks"""
        
        try:
            full_content = ""
            
            async for chunk in self.llm.stream_chat(prompt):
                content = chunk.get('content', '')
                full_content += content
                
                yield {
                    'event': 'message_chunk',
                    'content': content
                }
            
            # Store in history
            session['history'].append({
                'role': 'assistant',
                'content': full_content,
                'state': session['state'].value
            })
            
            yield {
                'event': 'message_complete',
                'full_content': full_content
            }
        
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            yield {
                'event': 'error',
                'message': str(e)
            }
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID (for tooltip endpoint)"""
        return self.sessions.get(session_id)
```

---

### Template 3: Agent Factory

**File:** `agents/thinking_modes/factory.py`

```python
"""
Thinking Mode Agent Factory
Routes diagram types to appropriate agents

ONE ENDPOINT FOR ALL 8 THINKING MAPS!
"""

# Import all 8 thinking map agents
from agents.thinking_modes.circle_map_agent import CircleMapThinkingAgent
from agents.thinking_modes.bubble_map_agent import BubbleMapThinkingAgent
from agents.thinking_modes.double_bubble_map_agent import DoubleBubbleMapThinkingAgent
from agents.thinking_modes.tree_map_agent import TreeMapThinkingAgent
from agents.thinking_modes.brace_map_agent import BraceMapThinkingAgent
from agents.thinking_modes.flow_map_agent import FlowMapThinkingAgent
from agents.thinking_modes.multi_flow_map_agent import MultiFlowMapThinkingAgent
from agents.thinking_modes.bridge_map_agent import BridgeMapThinkingAgent


class ThinkingAgentFactory:
    """
    Factory pattern for creating diagram-specific thinking agents.
    
    Benefits:
    - Single endpoint can handle all 8 diagram types
    - Easy to add new diagram types (just add elif!)
    - Centralized routing logic
    - All agents share same workflow, different prompts
    """
    
    @staticmethod
    def get_agent(diagram_type: str):
        """
        Get the appropriate agent for the diagram type.
        
        Args:
            diagram_type: One of the 8 thinking map types
        
        Returns:
            Agent instance for that diagram type (extends BaseThinkingAgent)
        
        Raises:
            ValueError: If diagram type is unknown
        """
        
        # All 8 Thinking Maps supported!
        if diagram_type == 'circle_map':
            return CircleMapThinkingAgent()
        
        elif diagram_type == 'bubble_map':
            return BubbleMapThinkingAgent()
        
        elif diagram_type == 'double_bubble_map':
            return DoubleBubbleMapThinkingAgent()
        
        elif diagram_type == 'tree_map':
            return TreeMapThinkingAgent()
        
        elif diagram_type == 'brace_map':
            return BraceMapThinkingAgent()
        
        elif diagram_type == 'flow_map':
            return FlowMapThinkingAgent()
        
        elif diagram_type == 'multi_flow_map':
            return MultiFlowMapThinkingAgent()
        
        elif diagram_type == 'bridge_map':
            return BridgeMapThinkingAgent()
        
        else:
            supported = self.get_supported_types()
            raise ValueError(
                f"Unknown diagram type: {diagram_type}. "
                f"Supported types: {', '.join(supported)}"
            )
    
    @staticmethod
    def get_supported_types():
        """Get list of all 8 supported diagram types"""
        return [
            'circle_map',           # Brainstorming & Defining
            'bubble_map',           # Describing with Adjectives
            'double_bubble_map',    # Comparing & Contrasting
            'tree_map',             # Classifying & Categorizing
            'brace_map',            # Whole-to-Part Analysis
            'flow_map',             # Sequencing & Steps
            'multi_flow_map',       # Cause & Effect
            'bridge_map'            # Seeing Analogies
        ]
```

---

### Template 4: API Router

**File:** `routers/thinking.py`

```python
"""
Thinking Mode API Router
Handles ALL diagram types through factory pattern
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json

from agents.thinking_modes.factory import ThinkingAgentFactory
from models.requests import ThinkingModeRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post('/thinking_mode/stream')
async def thinking_mode_stream(req: ThinkingModeRequest):
    """
    Universal SSE streaming endpoint for ALL diagram types.
    Uses factory pattern to route to correct agent.
    
    Supports: circle_map (more coming: bubble_map, tree_map, etc.)
    """
    
    try:
        # Validate diagram type
        supported = ThinkingAgentFactory.get_supported_types()
        if req.diagram_type not in supported:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported diagram type: {req.diagram_type}. Supported: {supported}"
            )
        
        # Get agent from factory
        agent = ThinkingAgentFactory.get_agent(req.diagram_type)
        
        logger.info(f"Starting Thinking Mode: {req.diagram_type}, session: {req.session_id}")
        
        # SSE generator
        async def generate():
            """Async generator for SSE streaming"""
            try:
                async for chunk in agent.process_step(
                    message=req.message,
                    session_id=req.session_id,
                    diagram_data=req.diagram_data,
                    current_state=req.current_state,
                    user_id=req.user_id
                ):
                    # Format as SSE
                    yield f"data: {json.dumps(chunk)}\n\n"
                
            except Exception as e:
                logger.error(f"Streaming error: {e}", exc_info=True)
                yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
        
        # Return SSE stream
        return StreamingResponse(
            generate(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
    
    except ValueError as e:
        # Invalid diagram type
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Thinking Mode error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get('/thinking_mode/node_learning/{session_id}/{node_id}')
async def get_node_learning_material(session_id: str, node_id: str):
    """
    Get learning material for a specific node (for hover tooltip).
    
    Called when user hovers over a node during Thinking Mode.
    Works for ALL diagram types (session stores the data).
    """
    
    try:
        # Get session from any agent that has it
        # For MVP, check Circle Map agent
        agent = CircleMapThinkingAgent()
        session = agent.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get learning material for this node
        material = session.get('node_learning_material', {}).get(node_id)
        
        if not material:
            raise HTTPException(
                status_code=404,
                detail=f"Learning material not found for node: {node_id}"
            )
        
        return material
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching node learning material: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

### Template 5: Request Model

**File:** `models/requests.py` (add to existing file)

```python
# Add this class to existing models/requests.py

class ThinkingModeRequest(BaseModel):
    """Request for Thinking Mode API"""
    message: str
    user_id: str
    session_id: str
    diagram_type: str  # 'circle_map', 'bubble_map', etc.
    diagram_data: dict  # Complete diagram structure
    current_state: str  # Current workflow state
    selected_node: Optional[dict] = None  # Selected node info (optional)
    
    class Config:
        schema_extra = {
            "example": {
                "message": "5th grade science, understanding photosynthesis",
                "user_id": "user123",
                "session_id": "session_abc",
                "diagram_type": "circle_map",
                "diagram_data": {
                    "center": {"text": "Photosynthesis"},
                    "children": [
                        {"id": "1", "text": "Sunlight"},
                        {"id": "2", "text": "Water"}
                    ]
                },
                "current_state": "CONTEXT_GATHERING",
                "selected_node": {
                    "id": "1",
                    "text": "Sunlight",
                    "type": "circle",
                    "color": "#4CAF50"
                }
            }
        }
```

---

### Template 6: Panel HTML

**File:** `templates/editor.html` (add after AI Assistant panel)

```html
<!-- ThinkGuide Panel -->
<div class="thinking-panel collapsed" id="thinking-panel">
    <!-- Header -->
    <div class="thinking-header">
        <div class="thinking-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2a4 4 0 0 0-4 4v1a4 4 0 0 0-4 4v2a4 4 0 0 0 4 4h8a4 4 0 0 0 4-4V11a4 4 0 0 0-4-4V6a4 4 0 0 0-4-4z"/>
                <circle cx="8" cy="10" r="1"/>
                <circle cx="16" cy="10" r="1"/>
            </svg>
            <span id="thinking-title-text">ThinkGuide</span>
        </div>
        <button class="thinking-close" id="thinking-close-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </button>
    </div>
    
    <!-- Progress Indicator -->
    <div class="thinking-progress">
        <div class="progress-bar">
            <div class="progress-fill" id="thinking-progress-fill" style="width: 0%"></div>
        </div>
        <div class="progress-label" id="thinking-progress-label">Starting...</div>
    </div>
    
    <!-- Messages Container -->
    <div class="thinking-messages" id="thinking-messages">
        <!-- Messages will be rendered here -->
    </div>
    
    <!-- Input Area -->
    <div class="thinking-input-area">
        <textarea 
            id="thinking-input" 
            class="thinking-input" 
            placeholder="Type your response..."
            rows="3"
        ></textarea>
        <button id="thinking-send-btn" class="thinking-send-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
            <span id="thinking-send-text">Send</span>
        </button>
    </div>
</div>
```

---

### Template 7: CSS Styles

**File:** `static/css/editor.css` (add to end)

```css
/* ============================================
   THINKING MODE PANEL
   ============================================ */

/* Panel Container */
.thinking-panel {
    position: fixed;
    left: 0;
    top: 60px; /* Below toolbar */
    bottom: 30px; /* Above status bar */
    width: 380px;
    background: white;
    border-right: 1px solid #e0e0e0;
    display: flex;
    flex-direction: column;
    transform: translateX(0);
    transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 100;
    box-shadow: 2px 0 8px rgba(0,0,0,0.1);
}

.thinking-panel.collapsed {
    transform: translateX(-100%);
}

/* Header */
.thinking-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    background: linear-gradient(135deg, #9C27B0, #7B1FA2);
    color: white;
    flex-shrink: 0;
}

.thinking-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 700;
}

.thinking-close {
    background: none;
    border: none;
    color: white;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: background 0.2s;
}

.thinking-close:hover {
    background: rgba(255,255,255,0.2);
}

/* Progress Indicator */
.thinking-progress {
    padding: 12px 16px;
    background: #f5f5f5;
    border-bottom: 1px solid #e0e0e0;
    flex-shrink: 0;
}

.progress-bar {
    height: 6px;
    background: #e0e0e0;
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 8px;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #9C27B0, #7B1FA2);
    border-radius: 3px;
    transition: width 0.5s ease-out;
}

.progress-label {
    font-size: 12px;
    color: #666;
    text-align: center;
}

/* Messages */
.thinking-messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.thinking-message {
    padding: 12px 16px;
    border-radius: 12px;
    max-width: 90%;
    line-height: 1.6;
    font-size: 14px;
}

.thinking-message.assistant {
    background: linear-gradient(135deg, #f5f7fa 0%, #e8eaf6 100%);
    border: 1px solid #9C27B0;
    align-self: flex-start;
    margin-right: auto;
}

.thinking-message.user {
    background: linear-gradient(135deg, #9C27B0, #7B1FA2);
    color: white;
    align-self: flex-end;
    margin-left: auto;
}

.thinking-message p {
    margin: 8px 0;
}

.thinking-message ul,
.thinking-message ol {
    margin: 8px 0;
    padding-left: 20px;
}

.thinking-message code {
    background: rgba(0,0,0,0.1);
    padding: 2px 6px;
    border-radius: 3px;
    font-family: monospace;
    font-size: 13px;
}

.thinking-message strong {
    font-weight: 700;
    color: #9C27B0;
}

.thinking-message.user strong {
    color: white;
}

/* Input Area */
.thinking-input-area {
    padding: 16px;
    background: #f5f5f5;
    border-top: 1px solid #e0e0e0;
    flex-shrink: 0;
}

.thinking-input {
    width: 100%;
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 8px;
    font-size: 14px;
    font-family: 'Inter', sans-serif;
    resize: vertical;
    min-height: 60px;
    margin-bottom: 8px;
}

.thinking-input:focus {
    outline: none;
    border-color: #9C27B0;
    box-shadow: 0 0 0 2px rgba(156, 39, 176, 0.1);
}

.thinking-send-btn {
    width: 100%;
    padding: 10px;
    background: linear-gradient(135deg, #9C27B0, #7B1FA2);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.2s;
}

.thinking-send-btn:hover {
    background: linear-gradient(135deg, #7B1FA2, #6A1B9A);
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(156, 39, 176, 0.3);
}

.thinking-send-btn:active {
    transform: translateY(0);
}

.thinking-send-btn:disabled {
    background: #bdbdbd;
    cursor: not-allowed;
    transform: none;
}


/* ============================================
   NODE HIGHLIGHTING (VISUAL FEEDBACK)
   ============================================ */

.node-highlight-remove {
    filter: drop-shadow(0 0 8px rgba(255, 68, 68, 0.8));
    animation: pulse-remove 1.5s ease-in-out infinite;
}

@keyframes pulse-remove {
    0%, 100% {
        filter: drop-shadow(0 0 8px rgba(255, 68, 68, 0.8));
    }
    50% {
        filter: drop-shadow(0 0 16px rgba(255, 68, 68, 1));
    }
}

.node-highlight-keep {
    filter: drop-shadow(0 0 10px rgba(76, 175, 80, 0.9));
    stroke: #4CAF50 !important;
    stroke-width: 3px !important;
}

.node-highlight-analyze {
    filter: drop-shadow(0 0 6px rgba(33, 150, 243, 0.7));
    animation: pulse-analyze 2s ease-in-out infinite;
}

@keyframes pulse-analyze {
    0%, 100% {
        filter: drop-shadow(0 0 6px rgba(33, 150, 243, 0.7));
    }
    50% {
        filter: drop-shadow(0 0 12px rgba(33, 150, 243, 1));
    }
}

.node-highlight-question {
    filter: drop-shadow(0 0 10px rgba(255, 152, 0, 0.9));
    animation: pulse-question 1s ease-in-out 3;
}

@keyframes pulse-question {
    0%, 100% {
        filter: drop-shadow(0 0 10px rgba(255, 152, 0, 0.9));
    }
    50% {
        filter: drop-shadow(0 0 18px rgba(255, 152, 0, 1));
    }
}


/* ============================================
   HOVER TOOLTIP (LEARNING MATERIAL)
   ============================================ */

.thinking-node-tooltip {
    position: absolute;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    border: 2px solid #9C27B0;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 8px 24px rgba(156, 39, 176, 0.3);
    max-width: 400px;
    z-index: 10000;
    font-family: 'Inter', sans-serif;
    pointer-events: none;
    animation: tooltipFadeIn 0.2s ease-out;
}

.thinking-node-tooltip .tooltip-header {
    font-size: 18px;
    font-weight: 700;
    color: #9C27B0;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.thinking-node-tooltip .tooltip-section {
    margin-bottom: 10px;
    font-size: 14px;
    line-height: 1.6;
}

.thinking-node-tooltip .tooltip-label {
    font-weight: 600;
    color: #555;
    display: block;
    margin-bottom: 4px;
}

.thinking-node-tooltip .tooltip-content {
    color: #333;
}

@keyframes tooltipFadeIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}


/* ============================================
   SCROLLBAR STYLING
   ============================================ */

.thinking-messages::-webkit-scrollbar {
    width: 6px;
}

.thinking-messages::-webkit-scrollbar-track {
    background: #f5f5f5;
}

.thinking-messages::-webkit-scrollbar-thumb {
    background: #9C27B0;
    border-radius: 3px;
}

.thinking-messages::-webkit-scrollbar-thumb:hover {
    background: #7B1FA2;
}
```

---

### Template 8: ThinkingModeManager (Frontend)

**File:** `static/js/editor/thinking-mode-manager.js`

This is a large file - showing key structure:

```javascript
/**
 * ThinkingModeManager
 * Manages Thinking Mode UI, state, and communication
 */

class ThinkingModeManager {
    constructor(diagramType, canvasManager) {
        this.diagramType = diagramType;
        this.canvasManager = canvasManager;
        this.sessionId = this.generateSessionId();
        this.currentState = 'CONTEXT_GATHERING';
        this.isActiveFlag = false;
        this.currentTooltip = null;
        
        // DOM elements
        this.panel = document.getElementById('thinking-panel');
        this.messagesContainer = document.getElementById('thinking-messages');
        this.input = document.getElementById('thinking-input');
        this.sendBtn = document.getElementById('thinking-send-btn');
        this.closeBtn = document.getElementById('thinking-close-btn');
        this.progressFill = document.getElementById('thinking-progress-fill');
        this.progressLabel = document.getElementById('thinking-progress-label');
        
        this.bindEvents();
    }
    
    generateSessionId() {
        return `thinking_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    bindEvents() {
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.closeBtn.addEventListener('click', () => this.close());
    }
    
    async startThinkingMode() {
        // Validate diagram
        const validation = this.validateDiagram();
        if (!validation.isValid) {
            this.showError(validation.error);
            return;
        }
        
        // Open panel
        this.panel.classList.remove('collapsed');
        this.isActiveFlag = true;
        
        // Extract diagram data
        const diagramData = this.extractDiagramData();
        
        // Start SSE stream
        await this.streamResponse('', diagramData, 'CONTEXT_GATHERING');
    }
    
    extractDiagramData() {
        // Get diagram structure from canvasManager
        const center = this.canvasManager.getCenterNode();
        const children = this.canvasManager.getChildNodes();
        const selected = this.canvasManager.getSelectedNode();
        
        return {
            center: {
                text: center.text || ''
            },
            children: children.map(child => ({
                id: child.id,
                text: child.text || ''
            })),
            selected_node: selected ? {
                id: selected.id,
                text: selected.text || ''
            } : null
        };
    }
    
    async sendMessage() {
        const message = this.input.value.trim();
        if (!message) return;
        
        // Render user message
        this.renderMessage('user', message);
        
        // Clear input
        this.input.value = '';
        
        // Send to backend
        const diagramData = this.extractDiagramData();
        await this.streamResponse(message, diagramData, this.currentState);
    }
    
    async streamResponse(message, diagramData, currentState) {
        try {
            const response = await fetch('/api/thinking_mode/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    user_id: 'user123', // TODO: Get from auth
                    session_id: this.sessionId,
                    diagram_type: this.diagramType,
                    diagram_data: diagramData,
                    current_state: currentState
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let currentMessage = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.event === 'message_chunk') {
                            currentMessage += data.content;
                            this.updateCurrentMessage(currentMessage);
                        }
                        else if (data.event === 'message_complete') {
                            this.finalizeMessage(currentMessage);
                            currentMessage = '';
                        }
                        else if (data.event === 'state_transition') {
                            this.handleStateTransition(data.new_state, data.progress);
                        }
                        else if (data.event === 'highlight_nodes') {
                            this.highlightNodes(data.node_ids, data.type);
                        }
                        else if (data.event === 'error') {
                            this.showError(data.message);
                        }
                    }
                }
            }
        }
        catch (error) {
            console.error('SSE error:', error);
            this.showError('Connection error. Please try again.');
        }
    }
    
    renderMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `thinking-message ${role}`;
        
        // Render Markdown
        if (window.markdownit) {
            const md = window.markdownit();
            const html = md.render(content);
            messageDiv.innerHTML = window.DOMPurify ? 
                window.DOMPurify.sanitize(html) : html;
        } else {
            messageDiv.textContent = content;
        }
        
        this.messagesContainer.appendChild(messageDiv);
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    updateCurrentMessage(content) {
        let currentMsg = this.messagesContainer.querySelector('.thinking-message.streaming');
        if (!currentMsg) {
            currentMsg = document.createElement('div');
            currentMsg.className = 'thinking-message assistant streaming';
            this.messagesContainer.appendChild(currentMsg);
        }
        
        if (window.markdownit) {
            const md = window.markdownit();
            const html = md.render(content);
            currentMsg.innerHTML = window.DOMPurify ?
                window.DOMPurify.sanitize(html) : html;
        } else {
            currentMsg.textContent = content;
        }
        
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    finalizeMessage(content) {
        const streamingMsg = this.messagesContainer.querySelector('.streaming');
        if (streamingMsg) {
            streamingMsg.classList.remove('streaming');
        }
    }
    
    handleStateTransition(newState, progress) {
        this.currentState = newState;
        this.updateProgress(progress);
        
        // State labels
        const labels = {
            'CONTEXT_GATHERING': 'Gathering Context',
            'EDUCATIONAL_ANALYSIS': 'Learning Analysis',
            'ANALYSIS': 'Critical Analysis',
            'REFINEMENT_1': 'Refinement 1',
            'REFINEMENT_2': 'Refinement 2',
            'FINAL_REFINEMENT': 'Final Refinement',
            'COMPLETE': 'Complete!'
        };
        
        this.progressLabel.textContent = labels[newState] || newState;
    }
    
    updateProgress(percent) {
        this.progressFill.style.width = `${percent}%`;
    }
    
    highlightNodes(nodeIds, type) {
        // Clear previous highlights
        this.clearAllHighlights();
        
        // Apply new highlights
        nodeIds.forEach(nodeId => {
            const nodeElement = this.findNodeElement(nodeId);
            if (nodeElement) {
                nodeElement.classList.add(`node-highlight-${type}`);
            }
        });
    }
    
    clearAllHighlights() {
        const highlighted = document.querySelectorAll('[class*="node-highlight-"]');
        highlighted.forEach(node => {
            node.className = node.className.replace(/node-highlight-\w+/g, '').trim();
        });
    }
    
    findNodeElement(nodeId) {
        // Find node in SVG by ID or text
        // Implementation depends on your diagram structure
        return document.querySelector(`[data-node-id="${nodeId}"]`);
    }
    
    async showNodeLearningTooltip(nodeId) {
        try {
            const response = await fetch(
                `/api/thinking_mode/node_learning/${this.sessionId}/${nodeId}`
            );
            
            if (!response.ok) return;
            
            const material = await response.json();
            this.displayTooltip(nodeId, material);
        }
        catch (error) {
            console.error('Tooltip error:', error);
        }
    }
    
    displayTooltip(nodeId, material) {
        // Remove existing tooltip
        this.hideNodeLearningTooltip();
        
        // Create tooltip
        const tooltip = document.createElement('div');
        tooltip.className = 'thinking-node-tooltip';
        tooltip.innerHTML = `
            <div class="tooltip-header">
                📚 ${material.node_name}
            </div>
            <div class="tooltip-section">
                <span class="tooltip-label">Relationship:</span>
                <span class="tooltip-content">${material.relationship || 'N/A'}</span>
            </div>
            <div class="tooltip-section">
                <span class="tooltip-label">Educational Value:</span>
                <span class="tooltip-content">${material.educational_value || 'N/A'}</span>
            </div>
            <div class="tooltip-section">
                <span class="tooltip-label">Depth Level:</span>
                <span class="tooltip-content">${material.depth_level || 'N/A'}</span>
            </div>
        `;
        
        // Position above node
        const nodeElement = this.findNodeElement(nodeId);
        if (nodeElement) {
            const rect = nodeElement.getBoundingClientRect();
            tooltip.style.left = `${rect.left}px`;
            tooltip.style.top = `${rect.top - tooltip.offsetHeight - 10}px`;
        }
        
        document.body.appendChild(tooltip);
        this.currentTooltip = tooltip;
    }
    
    hideNodeLearningTooltip() {
        if (this.currentTooltip) {
            this.currentTooltip.remove();
            this.currentTooltip = null;
        }
    }
    
    hasLearningMaterial() {
        // Check if Educational Analysis phase is complete
        return this.currentState !== 'CONTEXT_GATHERING';
    }
    
    isActive() {
        return this.isActiveFlag;
    }
    
    close() {
        this.panel.classList.add('collapsed');
        this.isActiveFlag = false;
        this.clearAllHighlights();
        this.hideNodeLearningTooltip();
    }
    
    validateDiagram() {
        // Basic validation
        const children = this.canvasManager.getChildNodes();
        if (children.length < 3) {
            return {
                isValid: false,
                error: 'Diagram needs at least 3 nodes for Thinking Mode'
            };
        }
        
        // Check for placeholders
        const hasPlaceholders = children.some(child => 
            !child.text || child.text.includes('Click to edit')
        );
        
        if (hasPlaceholders) {
            return {
                isValid: false,
                error: 'Please complete all nodes before starting Thinking Mode'
            };
        }
        
        return { isValid: true };
    }
    
    showError(message) {
        this.renderMessage('assistant', `❌ **Error:** ${message}`);
    }
}

// Export for global use
window.ThinkingModeManager = ThinkingModeManager;
```

---

## 📚 Reference: Key Concepts

### ThinkGuide vs MindMate AI

**MindMate AI:**
- General-purpose chat assistant
- Answers questions
- Provides information
- Friendly companion for learning

**ThinkGuide:**
- Socratic thinking guide
- Asks questions (doesn't give answers)
- Guides diagram refinement
- Builds critical thinking skills
- Diagram-specific workflows

**Key Difference:** MindMate AI helps you learn. ThinkGuide helps you **think**.

### Socratic Method
- **DON'T:** Tell users what to do
- **DO:** Ask questions that help them discover
- **Goal:** Build critical thinking skills

### Educational Analysis Phase
- Provides learning material BEFORE refinement
- Analyzes each node's relationship to main topic
- Stored in session for hover tooltips
- Gives users knowledge to make informed decisions

### Visual Feedback
- **Node Highlighting:** 4 types (remove, keep, analyze, question)
- **Hover Tooltips:** Learning material accessible anytime
- **Progress Bar:** Shows workflow progress

### One Endpoint for All Diagrams
- `/api/thinking_mode/stream` handles ALL diagram types
- Factory pattern routes to correct agent
- Easy to add new diagram types

---

## ✅ Definition of Done

### Backend Complete When:
- [ ] All endpoints respond correctly
- [ ] SSE streaming works
- [ ] Session management functional
- [ ] Qwen-Plus model integrated
- [ ] Learning material stored for tooltips
- [ ] Manual tests pass

### Frontend Complete When:
- [ ] Button appears and validates correctly
- [ ] Panel slides smoothly
- [ ] SSE streaming displays messages
- [ ] Markdown renders properly
- [ ] Node highlighting works (all 4 types)
- [ ] Hover tooltips display learning material
- [ ] Progress bar updates correctly

### Integration Complete When:
- [ ] Full workflow (10 → 5 nodes) completes successfully
- [ ] Agent uses Socratic questions (not directives)
- [ ] Educational analysis provides useful insights
- [ ] Visual highlighting matches conversation
- [ ] Tooltips persist throughout workflow
- [ ] Multi-language support works

---

**End of Implementation Guide**

This guide provides everything needed to build Thinking Mode for Circle Maps. Future diagram types follow the same pattern!

