# Node Palette × ThinkGuide Real-time Analysis
**Feature**: AI-powered educational insights when selecting nodes  
**Date**: October 14, 2025  
**Status**: Design Complete - Ready for Implementation

---

## 🎯 Vision

**Current**: User selects nodes → sees checkmark  
**Enhanced**: User selects nodes → ThinkGuide explains WHY it matters + asks critical thinking questions

### Example Flow
```
Topic: "Car" (Circle Map)
User selects: "Engine"

ThinkGuide streams (100 words):
┌─────────────────────────────────────────────────────────────┐
│ 💡 Great choice! The engine is the heart of a car.         │
│                                                              │
│ 🔍 Connection: Just like your heart pumps blood to power   │
│ your body, the engine converts fuel into mechanical energy  │
│ to move the car. It's the primary power source.            │
│                                                              │
│ 🤔 Critical Thinking Questions:                            │
│ • What happens if the engine stops working?                │
│ • Can you think of other "engines" in different machines?  │
│ • How does this relate to energy transformation?           │
│                                                              │
│ 📚 This connects to: Physics (Energy), Engineering         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture Design

### High-Level Flow
```
┌─────────────────────┐
│  User clicks node   │
│   in Node Palette   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│  Frontend: node-palette-manager.js                  │
│  - Detect selection                                 │
│  - Send to ThinkGuide                              │
└──────────┬──────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│  Frontend: thinking-mode-manager.js                 │
│  - Receive selection event                          │
│  - Send to backend via SSE                          │
└──────────┬──────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│  Backend: CircleMapThinkingAgent                    │
│  - Analyze: topic + selected node                   │
│  - Generate educational insight                      │
│  - Stream back to frontend                          │
└──────────┬──────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│  Frontend: ThinkGuide Panel                         │
│  - Display streaming analysis                        │
│  - Accumulate insights for all selections           │
└─────────────────────────────────────────────────────┘
```

---

## 📋 Implementation Plan

### Phase 1: Frontend - Node Selection Event (30 min)

#### 1.1 Update Node Palette Manager
**File**: `static/js/editor/node-palette-manager.js`

**Add method to notify ThinkGuide**:
```javascript
async notifyThinkGuideOfSelection(node, isSelected) {
    /**
     * Notify ThinkGuide when a node is selected/deselected.
     * ThinkGuide will provide educational analysis.
     * 
     * @param {Object} node - The selected node
     * @param {boolean} isSelected - True if selected, false if deselected
     */
    if (!window.thinkingModeManager) {
        return; // ThinkGuide not active
    }
    
    // Only send for NEW selections (not deselections)
    if (!isSelected) {
        return;
    }
    
    console.log(`[NodePalette] 💡 Notifying ThinkGuide of selection: "${node.text}"`);
    
    try {
        await window.thinkingModeManager.analyzeNodeSelection({
            centerTopic: this.centerTopic,
            selectedNode: node.text,
            nodeId: node.id,
            diagramType: this.diagramType,
            currentSelectionCount: this.selectedNodes.size,
            educationalContext: this.educationalContext
        });
    } catch (error) {
        console.warn('[NodePalette] Failed to notify ThinkGuide:', error);
        // Don't block user - this is enhancement, not critical
    }
}
```

**Update `toggleNodeSelection()` to call it**:
```javascript
// In toggleNodeSelection() method, after updating selection
async toggleNodeSelection(nodeId) {
    const node = this.nodes.find(n => n.id === nodeId);
    // ... existing selection logic ...
    
    const wasSelected = this.selectedNodes.has(nodeId);
    if (wasSelected) {
        this.selectedNodes.delete(nodeId);
        node.selected = false;
        card.classList.remove('selected');
        // Remove checkmark...
    } else {
        this.selectedNodes.add(nodeId);
        node.selected = true;
        card.classList.add('selected');
        // Add checkmark...
        
        // 🆕 NEW: Notify ThinkGuide of selection
        await this.notifyThinkGuideOfSelection(node, true);
    }
    
    this.updateSelectionCounter();
}
```

---

### Phase 2: Frontend - ThinkGuide Manager (30 min)

#### 2.1 Add Node Analysis Method
**File**: `static/js/editor/thinking-mode-manager.js`

```javascript
async analyzeNodeSelection(selectionData) {
    /**
     * Analyze a selected node from Node Palette.
     * Provides educational insights about the relationship between
     * the center topic and selected node.
     * 
     * @param {Object} selectionData - Selection context
     */
    if (!this.conversationId) {
        console.warn('[ThinkGuide] No active conversation for node analysis');
        return;
    }
    
    console.log('[ThinkGuide] 💡 Analyzing node selection:', selectionData);
    
    // Build analysis request message
    const analysisMessage = {
        type: 'node_selection_analysis',
        data: {
            center_topic: selectionData.centerTopic,
            selected_node: selectionData.selectedNode,
            diagram_type: selectionData.diagramType,
            selection_count: selectionData.currentSelectionCount,
            educational_context: selectionData.educationalContext
        }
    };
    
    // Stream the analysis
    try {
        const response = await auth.fetch('/thinking_mode/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                conversation_id: this.conversationId,
                message: JSON.stringify(analysisMessage),
                diagram_type: this.diagramType,
                diagram_data: this.currentDiagramData,
                language: this.language
            })
        });
        
        // Process SSE stream (reuse existing stream processing logic)
        await this.processStreamResponse(response);
        
    } catch (error) {
        console.error('[ThinkGuide] Node analysis failed:', error);
    }
}
```

---

### Phase 3: Backend - ThinkGuide Agent Enhancement (45 min)

#### 3.1 Update CircleMapThinkingAgent
**File**: `agents/thinking_modes/circle_map_thinking_agent.py`

**Add new intent detection**:
```python
# In _classify_intent() method
def _classify_intent(self, message: str) -> str:
    """Classify user intent or system event."""
    
    # Check for system events (JSON)
    try:
        msg_data = json.loads(message)
        if isinstance(msg_data, dict):
            if msg_data.get('type') == 'node_selection_analysis':
                return 'analyze_node_selection'  # 🆕 NEW intent
    except:
        pass
    
    # ... existing intent classification ...
```

**Add new action handler**:
```python
# In _decide_action() method
def _decide_action(self, intent: str, message: str) -> str:
    """Decide what action to take based on intent."""
    
    if intent == 'analyze_node_selection':
        return 'provide_node_insight'  # 🆕 NEW action
    
    # ... existing action decisions ...
```

**Add new action implementation**:
```python
# In _execute_action() method
async def _execute_action(self, action: str, message: str):
    """Execute the decided action."""
    
    if action == 'provide_node_insight':
        await self._provide_node_insight(message)
        return
    
    # ... existing actions ...

async def _provide_node_insight(self, message: str):
    """
    Provide educational insight about a selected node.
    Explains the relationship and asks critical thinking questions.
    """
    try:
        # Parse the selection data
        msg_data = json.loads(message)
        selection_data = msg_data.get('data', {})
        
        center_topic = selection_data.get('center_topic', 'topic')
        selected_node = selection_data.get('selected_node', 'node')
        diagram_type = selection_data.get('diagram_type', 'circle_map')
        selection_count = selection_data.get('selection_count', 1)
        
        self.logger.info(f"[NodeInsight] Analyzing: {center_topic} → {selected_node}")
        
        # Build educational analysis prompt
        if self.language == 'zh':
            prompt = self._build_chinese_insight_prompt(
                center_topic, selected_node, selection_count
            )
        else:
            prompt = self._build_english_insight_prompt(
                center_topic, selected_node, selection_count
            )
        
        # Stream the insight
        async for chunk in self.llm_service.chat_stream(
            model='qwen-plus',
            messages=[
                {'role': 'system', 'content': self._get_insight_system_message()},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.7
        ):
            yield {
                'event': 'message',
                'content': chunk,
                'done': False
            }
        
        yield {
            'event': 'message',
            'content': '',
            'done': True
        }
        
    except Exception as e:
        self.logger.error(f"[NodeInsight] Error: {e}")
        yield {
            'event': 'error',
            'message': str(e)
        }

def _get_insight_system_message(self) -> str:
    """System message for node insight generation."""
    if self.language == 'zh':
        return """你是一位优秀的K12教育专家。当学生选择一个节点时，你需要：

1. 解释这个节点与中心主题的关系（教育视角）
2. 提供2-3个批判性思考问题，引导深入理解
3. 连接到相关学科知识

要求：
- 100字左右，简洁有力
- 使用教育性语言，激发好奇心
- 鼓励批判性思维
- 适合K12学生理解水平
"""
    else:
        return """You are an excellent K12 education expert. When a student selects a node, you should:

1. Explain the relationship between this node and the central topic (educational perspective)
2. Provide 2-3 critical thinking questions to guide deeper understanding
3. Connect to relevant subject knowledge

Requirements:
- Around 100 words, concise and powerful
- Use educational language that sparks curiosity
- Encourage critical thinking
- Appropriate for K12 student comprehension level
"""

def _build_english_insight_prompt(self, center_topic: str, selected_node: str, count: int) -> str:
    """Build English prompt for node insight."""
    ordinal = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth'][min(count-1, 5)]
    
    return f"""The student is building a Circle Map about "{center_topic}".

They just selected their {ordinal} context node: "{selected_node}"

Provide educational insight:
1. 💡 Why this matters (connection to center topic)
2. 🤔 2-3 critical thinking questions
3. 📚 Related subject areas

Keep it engaging and thought-provoking! ~100 words.
"""

def _build_chinese_insight_prompt(self, center_topic: str, selected_node: str, count: int) -> str:
    """Build Chinese prompt for node insight."""
    ordinals = ['第一个', '第二个', '第三个', '第四个', '第五个', '第六个']
    ordinal = ordinals[min(count-1, 5)]
    
    return f"""学生正在创建关于"{center_topic}"的圆圈图。

他们刚刚选择了{ordinal}背景节点："{selected_node}"

请提供教育性见解：
1. 💡 为什么重要（与中心主题的关联）
2. 🤔 2-3个批判性思考问题
3. 📚 相关学科领域

保持有趣且引人深思！约100字。
"""
```

---

### Phase 4: UI Enhancement (30 min)

#### 4.1 Visual Feedback in ThinkGuide Panel
**File**: `static/js/editor/thinking-mode-manager.js`

**Add visual indicator when analyzing**:
```javascript
// In analyzeNodeSelection() method
async analyzeNodeSelection(selectionData) {
    // ... existing code ...
    
    // Add visual indicator
    this.showNodeAnalysisIndicator(selectionData.selectedNode);
    
    // Stream the analysis
    await this.processStreamResponse(response);
    
    // Remove indicator when done
    this.hideNodeAnalysisIndicator();
}

showNodeAnalysisIndicator(nodeName) {
    const panel = document.getElementById('thinking-messages');
    if (!panel) return;
    
    // Add a subtle "analyzing..." message
    const indicator = document.createElement('div');
    indicator.id = 'node-analysis-indicator';
    indicator.className = 'analysis-indicator';
    indicator.innerHTML = `
        <div class="analysis-indicator-content">
            <span class="spinner">🔄</span>
            <span>Analyzing "${nodeName}"...</span>
        </div>
    `;
    panel.appendChild(indicator);
}

hideNodeAnalysisIndicator() {
    const indicator = document.getElementById('node-analysis-indicator');
    if (indicator) {
        indicator.classList.add('fade-out');
        setTimeout(() => indicator.remove(), 300);
    }
}
```

#### 4.2 CSS for Analysis Indicator
**File**: `static/css/thinking-panel.css`

```css
.analysis-indicator {
    padding: 8px 12px;
    margin: 8px 0;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 8px;
    opacity: 1;
    transition: opacity 0.3s ease;
}

.analysis-indicator-content {
    display: flex;
    align-items: center;
    gap: 8px;
    color: white;
    font-size: 13px;
    font-weight: 500;
}

.analysis-indicator .spinner {
    animation: spin 1s linear infinite;
}

.analysis-indicator.fade-out {
    opacity: 0;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
```

---

## 🎨 User Experience Flow

### Scenario: Student Building "Car" Circle Map

**Step 1: Select First Node**
```
User clicks: "Engine"
→ Checkmark appears ✓
→ ThinkGuide streams:

"💡 Great start! The engine is the heart of any car. It converts 
fuel into mechanical energy, similar to how your heart pumps blood 
to power your body.

🤔 Think about:
• What would happen if the engine had a problem?
• How is an engine different from an electric motor?
• Can you name the energy transformation happening?

📚 Connects to: Physics (Energy), Engineering"
```

**Step 2: Select Second Node**
```
User clicks: "Wheels"
→ Checkmark appears ✓
→ ThinkGuide streams:

"🎯 Excellent addition! Wheels transfer the engine's power to 
movement. Notice the connection: engine creates power → wheels 
use it for motion.

🤔 Critical thinking:
• Could a car work with just an engine but no wheels?
• How do wheels and engine work together as a system?
• What role does friction play?

📚 Connects to: Physics (Forces & Motion), Systems Thinking"
```

**Step 3: Continue Selecting**
Each selection gets contextualized analysis, building understanding!

---

## 📊 Benefits

### Educational
- ✅ **Active Learning**: Students think while selecting
- ✅ **Critical Thinking**: Questions prompt deeper analysis
- ✅ **Connections**: Links to subject areas
- ✅ **Scaffolding**: Builds understanding step-by-step

### Technical
- ✅ **Non-blocking**: Analysis happens in background
- ✅ **Incremental**: Each selection analyzed separately
- ✅ **Contextual**: Uses ThinkGuide session context
- ✅ **Elegant**: Reuses existing SSE infrastructure

---

## 🚀 Implementation Order

### Phase 1: Core Functionality (1.5 hours)
1. ✅ Add `notifyThinkGuideOfSelection()` to Node Palette
2. ✅ Add `analyzeNodeSelection()` to ThinkGuide Manager
3. ✅ Update CircleMapThinkingAgent with new intent/action
4. ✅ Test basic flow

### Phase 2: Polish (30 min)
5. ✅ Add visual indicators
6. ✅ Add CSS styling
7. ✅ Test edge cases

### Phase 3: Enhancement (Optional)
8. 💡 Add "Skip Analysis" toggle for advanced users
9. 💡 Add analysis summary after all selections
10. 💡 Store insights for later review

---

## 🧪 Testing Checklist

### Functional Tests
- [ ] Single node selection → Analysis streams
- [ ] Multiple node selections → Each analyzed separately
- [ ] Deselection → No analysis (correct)
- [ ] ThinkGuide closed → No errors (graceful degradation)
- [ ] Network error → Doesn't block selection
- [ ] Chinese language → Chinese analysis
- [ ] English language → English analysis

### Educational Quality Tests
- [ ] Analysis is age-appropriate (K12)
- [ ] Questions encourage critical thinking
- [ ] Connections to subjects are accurate
- [ ] ~100 words length (readable)
- [ ] Engaging language

### Performance Tests
- [ ] Doesn't slow down selection UX
- [ ] Streams smoothly (no lag)
- [ ] Multiple rapid selections handled gracefully
- [ ] Memory usage acceptable

---

## 💡 Future Enhancements

### V2 Features
1. **Comparison Mode**: "You selected Engine and Wheels. How do these work together as a system?"
2. **Learning Path**: Track which nodes lead to deeper insights
3. **Quiz Mode**: After selecting, ask a question before showing answer
4. **Peer Examples**: "Students who selected Engine also often choose Transmission"

### V3 Features
1. **Voice Analysis**: Read insights aloud
2. **Visual Connections**: Draw lines between related nodes
3. **Concept Maps**: Auto-generate concept map from selections
4. **Teacher Dashboard**: See what students are selecting and learning

---

## 📝 Code Quality Standards

### Logging
- Frontend: `[NodePalette] 💡 Notifying ThinkGuide...`
- Backend: `[NodeInsight] Analyzing: car → engine`

### Error Handling
- Frontend: Fail gracefully, don't block selection
- Backend: Log errors, return friendly message

### Performance
- Max 2 seconds for insight generation
- Non-blocking UI (async all the way)
- Debounce rapid selections (100ms)

---

**Design Status**: ✅ Complete  
**Ready to Implement**: Yes  
**Estimated Time**: 2 hours  
**Expected Impact**: 🚀 Transform Node Palette from selection tool to **learning experience**!

