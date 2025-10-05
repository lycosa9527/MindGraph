# Learning Mode Design Document | 学习模式设计文档

**Feature Name**: Interactive Learning Mode | 交互式学习模式  
**Version**: 2.0 (Prerequisite-First Approach) 🧠  
**Date**: 2025-10-05  
**Status**: Design Phase 🎨

**🆕 MAJOR UPDATE**: Prerequisite Knowledge Testing  
Instead of giving progressive hints about the same question, the system now:
1. Identifies missing prerequisite knowledge when student answers wrong
2. Tests that prerequisite with simpler, domain-independent questions
3. Teaches the prerequisite if needed
4. Returns to original question with foundational understanding

This transforms the system from a "hint-based quiz" to an **Intelligent Tutoring System** that builds foundational knowledge.

---

## 📋 Table of Contents

1. [Feature Overview](#feature-overview)
2. [User Experience Flow](#user-experience-flow)
3. [UI/UX Design](#uiux-design)
4. [Technical Architecture](#technical-architecture)
5. [LLM Integration](#llm-integration)
6. [Data Structures](#data-structures)
7. [Implementation Phases](#implementation-phases)
8. [Potential Challenges](#potential-challenges)
9. [Future Enhancements](#future-enhancements)

---

## 🎯 Feature Overview

### Purpose | 目的

Transform MindGraph diagrams into interactive learning exercises where users actively recall and type node content, reinforced by AI-generated contextual hints.

将MindGraph图表转换为交互式学习练习，用户主动回忆并输入节点内容，由AI生成的上下文提示进行强化。

### Key Differences from Existing "Learning Sheets (半成品)"

| Feature | Learning Sheets (半成品) | **NEW: Learning Mode** |
|---------|-------------------------|------------------------|
| **Interaction** | Static PNG export | Interactive canvas-based |
| **User Input** | Manual paper/pen | Type answers in browser |
| **Feedback** | None | Real-time AI hints |
| **Validation** | None | Automatic answer checking |
| **Hints** | None | AI-generated contextual hints |
| **Difficulty** | Fixed 20% knockout | Adaptive (future: adjustable %) |
| **Context** | No relationships | Shows node relationships |

### Core Concept | 核心概念

**Active Recall + AI-Powered Hints = Enhanced Memory Retention**

1. **20% Random Knockout**: Hide text from 20% of nodes (similar to existing feature)
2. **Contextual Questions**: LLM generates questions based on:
   - Node relationships (parent-child, siblings, connections)
   - Diagram structure (position, hierarchy, associations)
   - Content semantics (what the node represents)
3. **User Interaction**: Users type answers into blank nodes
4. **Smart Validation**: System checks if answer matches (exact or semantic)
5. **Adaptive Hints**: If wrong, LLM generates progressive hints

---

## 🎨 User Experience Flow

### Step 1: Pre-Validation | 预验证检查

**CRITICAL REQUIREMENT**: Before entering Learning Mode, system MUST validate:

```
User clicks "Learning" button (学习)
            ↓
System validates diagram completeness:
  ✓ All nodes have text content
  ✓ No placeholder patterns detected
  ✓ No empty/blank nodes
            ↓
    ┌─── PASS ───┐         ┌─── FAIL ───┐
    ↓             ↓         ↓             ↓
Enter Learning  Stay in Editor with notification
    Mode
```

**Validation Rules:**

1. **No Empty Nodes**: Every node must have text (length > 0)
2. **No Placeholders**: Detect and reject common placeholder patterns:
   - Chinese: "分支1", "分支2", "子项1.1", "新节点", "节点", "主题", "属性1"
   - English: "Branch 1", "Child 1.1", "New Node", "Node", "Topic", "Attribute 1"
   - Pattern matching: `/^(分支|Branch|子项|Child|节点|Node|属性|Attribute)\s*\d+/i`
3. **Minimum Content**: Each node should have meaningful text (not just "a", "test", etc.)

**Validation Failure Response:**

```
❌ Cannot Start Learning Mode

Your diagram contains placeholder or empty nodes.
Please fill in all nodes with meaningful content first.

Incomplete nodes found:
• Branch 2 (placeholder)
• 子项3.1 (placeholder)
• Attribute 5 (empty)

[Edit Diagram] [Cancel]
```

**Button State Management:**

- **Enabled** (clickable, rainbow glow active): All nodes validated ✅
- **Disabled** (grayed out, rainbow glow paused): Validation fails ❌
- **Tooltip when enabled**: "Start Interactive Learning Mode"
- **Tooltip when disabled**: "Fill in all nodes before starting Learning Mode"

**Real-Time Validation:**

The button state should update automatically when:
- User edits any node text (double-click edit)
- User adds a new node
- User deletes a node
- Diagram is first loaded/rendered

Validation should run:
- On `diagram-rendered` event
- After any text update operation
- Debounced (100ms) to avoid excessive checks

### Step 2: Activation | 激活学习模式

```
✅ Validation passed
            ↓
User clicks "Learning" button (学习)
            ↓
System shuffles diagram nodes randomly → Selects 20% nodes to knock out
            ↓
Generates AI questions for knocked-out nodes → Displays question panel
            ↓
User sees diagram with blank nodes + question panel
```

### Step 2: Initial Question & Answer | 初始问答

(Same as before - user attempts to answer)

### Step 3: Intelligent Error Analysis (NEW!) | 智能错误分析

**When User Gives Wrong Answer:**

```
User types wrong answer → LangChain Agent activates
                       ↓
╔═══════════════════════════════════════════════════════════╗
║ 🧠 MISCONCEPTION ANALYSIS AGENT                           ║
╠═══════════════════════════════════════════════════════════╣
║ Analyzing error...                                        ║
║                                                           ║
║ Correct Answer: "阳光" (Sunlight)                        ║
║ Student Answer: "氧气" (Oxygen)                          ║
║                                                           ║
║ DIAGNOSIS:                                                ║
║ • Misconception Type: Input-Output Confusion              ║
║ • Root Cause: Doesn't understand process directionality   ║
║ • Common Error: Yes (34% of students make this mistake)   ║
║ • Severity: Medium (fundamental concept gap)              ║
║ • Mental Model: Student knows O2 relates to photosynthesis║
║   but reversed the causal flow                            ║
╚═══════════════════════════════════════════════════════════╝
                       ↓
Agent generates targeted learning material
```

### Step 4: Prerequisite Knowledge Testing (NEW!) | 先验知识测试

**🧠 KEY INNOVATION**: Instead of giving hints about the SAME question, the agent identifies what **prerequisite knowledge** is missing and tests THAT first.

```
Agent diagnosis: "Student answered '氧气' for '阳光'"
                       ↓
Agent reasoning: "Student doesn't understand INPUT vs OUTPUT concept"
                       ↓
╔═══════════════════════════════════════════════════════════╗
║ 🔍 PREREQUISITE KNOWLEDGE GAP DETECTED                    ║
╠═══════════════════════════════════════════════════════════╣
║ I notice you might be confusing inputs and outputs.       ║
║ Let me test if you understand this foundational concept:  ║
║                                                           ║
║ 📚 PREREQUISITE TEST QUESTION:                            ║
║                                                           ║
║ "In the equation: A + B → C + D                          ║
║  Which are the INPUTS (what you start with)?             ║
║                                                           ║
║  Select all that apply:                                   ║
║  [ ] A                                                    ║
║  [ ] B                                                    ║
║  [ ] C                                                    ║
║  [ ] D"                                                   ║
║                                                           ║
║ (Or type your answer: ____________)                       ║
╚═══════════════════════════════════════════════════════════╝
```

**If Prerequisite Test PASSES:**
```
✅ Great! You understand inputs vs outputs!
              ↓
Now let's return to the original question:
"What energy source does photosynthesis need?"

💡 Hint: Knowing that you understand inputs/outputs,
think about which INPUT provides ENERGY (not material).
Photosynthesis:阳光 + 水 + CO₂ → 葡萄糖 + 氧气
                ↑_______________↑    ↑________↑
                   INPUTS            OUTPUTS

Your Answer: [___________________]
```

**If Prerequisite Test FAILS:**
```
❌ Let me explain inputs vs outputs:
              ↓
╔═══════════════════════════════════════════════════════════╗
║ 📖 MINI-LESSON: Inputs vs Outputs                        ║
╠═══════════════════════════════════════════════════════════╣
║ In any process:                                           ║
║                                                           ║
║ 📥 INPUTS = What you START with (before process)         ║
║    Example: Ingredients for cooking                       ║
║                                                           ║
║ 📤 OUTPUTS = What you END with (after process)           ║
║    Example: The cooked food + steam + smell              ║
║                                                           ║
║ 💭 Baking bread:                                          ║
║    Inputs:  Flour + Water + Yeast + Heat                 ║
║    Process: [Baking for 30 minutes]                      ║
║    Outputs: Bread + Steam + Aroma                        ║
║                                                           ║
║ 🔑 Key: Inputs are consumed/used. Outputs are created.   ║
╚═══════════════════════════════════════════════════════════╝
              ↓
Now let's test again with a simpler example:
"When you make tea: Water + Tea leaves + Heat → Hot tea + Used leaves
 Which are the INPUTS?"

Your Answer: [___________________]
              ↓
[If correct] → Return to original photosynthesis question
[If wrong]   → Test even simpler prerequisite (e.g., "before vs after")
```

### Step 5: Return to Original Question | 回到原问题

**After prerequisite knowledge is confirmed:**

```
╔═══════════════════════════════════════════════════════════╗
║ 🔄 BACK TO ORIGINAL QUESTION                              ║
╠═══════════════════════════════════════════════════════════╣
║ Now that you understand inputs vs outputs,                ║
║ let's try the photosynthesis question again:              ║
║                                                           ║
║ "What is the blank node connected to '光合作用'?"         ║
║                                                           ║
║ 💡 Remember:                                              ║
║ • We just learned that inputs are what you START with    ║
║ • This blank node is an INPUT to photosynthesis          ║
║ • Photosynthesis needs: Energy + Water + CO₂             ║
║ • Which input provides the ENERGY?                        ║
║                                                           ║
║ Your Answer: [___________________] [Submit]               ║
╚═══════════════════════════════════════════════════════════╝
```

**Success Path:**
```
User types "阳光" (correct!)
              ↓
✅ Excellent! You've truly understood!
   
   Your learning journey:
   1. ❌ Initially confused inputs/outputs → "氧气" (output)
   2. 📚 Learned the foundational concept (inputs vs outputs)
   3. ✅ Successfully applied it to photosynthesis → "阳光" (input)
   
   This shows you don't just memorize - you UNDERSTAND! 🌟
              ↓
Move to next question
```

**Failure Path (Rare):**
```
User still gets original question wrong
              ↓
Agent identifies NEW prerequisite gap (e.g., "doesn't understand energy concept")
              ↓
Test that prerequisite → Teach if needed → Return to original
              ↓
Maximum 3 prerequisite levels deep before offering skip
```

### Step 6: Question & Answer Cycle | 问答循环 (Updated)

```
Question Panel shows:
┌─────────────────────────────────────────────────┐
│ Question 1 of 5                        [Close]  │
├─────────────────────────────────────────────────┤
│ 🎯 Fill in the blank node:                     │
│                                                  │
│ This node is connected to "光合作用" and        │
│ describes the primary energy source for         │
│ this process. What is it?                       │
│                                                  │
│ 💡 Hint: It comes from the sky                 │
│                                                  │
│ Your Answer: [___________________] [Submit]     │
│                                                  │
│ [Skip Question] [Show Answer] [Next Question]   │
└─────────────────────────────────────────────────┘
```

### Step 3: Answer Validation | 答案验证

**Correct Answer Path:**
```
User types "阳光" → Clicks Submit
              ↓
System validates (exact or semantic match)
              ↓
✅ Correct! Node text appears in diagram
              ↓
Celebration animation → Auto-advance to next question
```

**Wrong Answer Path:**
```
User types "氧气" → Clicks Submit
              ↓
System validates → Detects error
              ↓
❌ Not quite. Let me give you a hint...
              ↓
LLM generates progressive hint:
"💡 Hint Level 2: Plants need this bright thing during the day."
              ↓
User tries again → Cycle repeats (max 3 attempts)
              ↓
After 3 attempts → "Show Answer" button highlighted
```

### Step 4: Completion | 完成

```
All 5 questions answered
              ↓
Summary Screen:
┌─────────────────────────────────────────────────┐
│ 🎉 Learning Session Complete!                   │
├─────────────────────────────────────────────────┤
│ Score: 4/5 (80%)                                │
│                                                  │
│ ✅ Correct: 4 questions                         │
│ ❌ Incorrect: 1 question                        │
│ 💡 Hints used: 3                                │
│                                                  │
│ [Review Mistakes] [New Session] [Exit Learning] │
└─────────────────────────────────────────────────┘
```

---

## 🖼️ UI/UX Design

### Button Placement | 按钮位置

**Location**: Main toolbar, next to "线稿" (Line Mode) button

```
Current Toolbar:
[Add] [Delete] [Auto] [线稿] [Undo] [Redo] [Reset] [Export]

New Toolbar:
[Add] [Delete] [Auto] [线稿] [学习] [Undo] [Redo] [Reset] [Export]
                              ↑
                         NEW BUTTON
```

**Button Specs:**
- **Icon**: 📚 or 🎓 (book/graduation cap)
- **Text**: "学习" (Chinese) / "Learn" (English)
- **Background Color**: Bright yellow (#FFD700 or #FFC107)
- **Border**: Rainbow gradient glow effect
  - Animated circular glow around button border
  - Colors: Red → Orange → Yellow → Green → Blue → Indigo → Violet (rainbow spectrum)
  - Animation: Smooth rotation (2-3 seconds per cycle)
  - Blur radius: 8-12px for soft glow effect
  - Makes button visually distinct and "magical" ✨
- **Tooltip**: "Interactive Learning Mode - Test your knowledge with AI hints"

**Visual Effect:**
```css
/* Conceptual CSS */
.learning-button {
    background: linear-gradient(135deg, #FFD700, #FFC107);
    position: relative;
    border-radius: 6px;
}

.learning-button::before {
    content: '';
    position: absolute;
    inset: -3px;
    border-radius: 8px;
    padding: 3px;
    background: linear-gradient(
        45deg,
        #ff0000, #ff7f00, #ffff00, #00ff00, 
        #0000ff, #4b0082, #9400d3
    );
    -webkit-mask: linear-gradient(#fff 0 0) content-box, 
                   linear-gradient(#fff 0 0);
    mask-composite: exclude;
    animation: rainbow-rotate 3s linear infinite;
    filter: blur(8px);
}

@keyframes rainbow-rotate {
    0% { filter: blur(8px) hue-rotate(0deg); }
    100% { filter: blur(8px) hue-rotate(360deg); }
}
```

**Visual Mockup:**
```
Normal state:                    Hover state:
     ╭──────────╮                   ╭──────────╮
    ╱ 🌈 rainbow  ╲                ╱ 🌈 rainbow  ╲
   │   glow ring   │              │  glow ring   │
   │  ┌──────────┐ │              │ ┌──────────┐ │
   │  │   📚 学习  │ │ (glowing)    │ │  📚 学习  │ │ (glowing++)
   │  │  (yellow) │ │              │ │ (yellow) │ │
   │  └──────────┘ │              │ └──────────┘ │
    ╲   animated  ╱                ╲  animated  ╱
     ╰──────────╯                   ╰──────────╯
```

The rainbow glow creates a **"magical learning portal"** effect that:
- Draws attention to the educational feature
- Signals something special/fun (not just a regular tool)
- Rotates smoothly for a dynamic feel
- Stands out from other monochrome buttons

### Knocked-Out Node Visualization | 被隐藏节点的可视化

**Before Knockout** (Normal node):
```
┌──────────────────┐
│   光合作用过程    │
└──────────────────┘
```

**After Knockout** (Blank node with input):
```
┌──────────────────┐
│ [_____________]  │  ← Input field appears
│     Type here    │
└──────────────────┘
   ↑ Pulsing border (indicates editable)
```

**Visual Indicators:**
- **Pulsing border**: Soft glow animation (purple/orange)
- **Question number badge**: Small badge showing "Q3" in corner
- **Connection lines**: Slightly highlighted to show relationships
- **Related nodes**: Subtle glow to indicate context

### Question Panel Design | 问题面板设计

**Position**: Floating panel on the right side (or modal overlay)

**Components:**
1. **Progress Bar**: "Question 3 of 5" with visual progress
2. **Question Text**: Clear, concise, AI-generated
3. **Context Hint**: Initial hint showing relationships
4. **Input Field**: Large, clear input for answer
5. **Action Buttons**: Submit, Skip, Show Answer
6. **Attempt Counter**: "Attempts: 2/3" (visual dots)
7. **Close Button**: Exit learning mode

**Panel States:**
- **Default**: Question + initial hint
- **Incorrect**: Red border + progressive hint
- **Correct**: Green checkmark + celebration
- **Skipped**: Gray border + "Skipped" label

---

## 🏗️ Technical Architecture

### Component Structure | 组件结构

```
LearningModeManager (new class)
├── Validation Module ⚠️ NEW
│   ├── Node Completeness Checker
│   ├── Placeholder Pattern Detector
│   ├── Button State Manager
│   └── Error Message Generator
├── Question Generation Module
│   ├── Node Selection (20% random)
│   ├── Shuffle Logic
│   └── LLM Question Generator
├── Question Panel UI
│   ├── Panel Renderer
│   ├── Input Handler
│   └── Progress Tracker
├── Answer Validation Module
│   ├── Exact Match Checker
│   ├── Semantic Match Checker (LLM-based)
│   └── Hint Generator (LLM-based)
├── Canvas Integration
│   ├── Node Knockout Renderer
│   ├── Visual Indicators
│   └── Input Field Injection
└── Session Manager
    ├── Score Tracking
    ├── Attempt Counting
    └── Summary Generation
```

### File Structure | 文件结构

```
static/js/
├── learning/
│   ├── learning-mode-manager.js      # Main controller
│   ├── diagram-validator.js          # ⚠️ NEW: Pre-validation logic
│   ├── question-generator.js         # LLM question generation
│   ├── answer-validator.js           # Answer checking logic
│   ├── hint-generator.js             # Progressive hint system
│   ├── learning-panel-ui.js          # Question panel UI
│   └── learning-session.js           # Session state management
├── editor/
│   └── toolbar-manager.js            # Add "Learning" button
└── renderers/
    └── learning-renderer.js          # Knockout node rendering
```

### Validation Logic Example | 验证逻辑示例

```javascript
// diagram-validator.js

class DiagramValidator {
    constructor(diagramSpec, diagramType) {
        this.spec = diagramSpec;
        this.type = diagramType;
        this.placeholderPatterns = [
            // Chinese patterns
            /^分支\s*\d+$/i,
            /^子项\s*\d+\.?\d*$/i,
            /^节点\s*\d*$/i,
            /^属性\s*\d+$/i,
            /^新节点$/i,
            /^主题$/i,
            // English patterns
            /^branch\s*\d+$/i,
            /^child\s*\d+\.?\d*$/i,
            /^node\s*\d*$/i,
            /^attribute\s*\d+$/i,
            /^new node$/i,
            /^topic$/i
        ];
    }
    
    validateForLearningMode() {
        const allNodes = this.extractAllNodes();
        const invalidNodes = [];
        
        for (const node of allNodes) {
            const text = node.text?.trim() || '';
            
            // Check 1: Empty node
            if (text.length === 0) {
                invalidNodes.push({
                    id: node.id,
                    text: text,
                    reason: 'empty',
                    message: 'Empty node'
                });
                continue;
            }
            
            // Check 2: Placeholder pattern
            const isPlaceholder = this.placeholderPatterns.some(
                pattern => pattern.test(text)
            );
            if (isPlaceholder) {
                invalidNodes.push({
                    id: node.id,
                    text: text,
                    reason: 'placeholder',
                    message: 'Placeholder pattern detected'
                });
                continue;
            }
            
            // Check 3: Too short (suspicious)
            if (text.length < 2) {
                invalidNodes.push({
                    id: node.id,
                    text: text,
                    reason: 'too_short',
                    message: 'Text too short (< 2 characters)'
                });
            }
        }
        
        return {
            isValid: invalidNodes.length === 0,
            totalNodes: allNodes.length,
            invalidNodes: invalidNodes,
            validNodes: allNodes.length - invalidNodes.length
        };
    }
    
    extractAllNodes() {
        // Extract all text nodes based on diagram type
        const nodes = [];
        
        switch (this.type) {
            case 'bubble_map':
                nodes.push({id: 'topic', text: this.spec.topic});
                this.spec.attributes?.forEach((attr, i) => {
                    nodes.push({id: `attr_${i}`, text: attr});
                });
                break;
            
            case 'mind_map':
                nodes.push({id: 'topic', text: this.spec.topic});
                this.spec.children?.forEach((branch, i) => {
                    nodes.push({id: `branch_${i}`, text: branch.text});
                    branch.children?.forEach((child, j) => {
                        nodes.push({id: `child_${i}_${j}`, text: child.text});
                    });
                });
                break;
            
            // ... similar for other diagram types
        }
        
        return nodes;
    }
    
    showValidationError(result) {
        const message = this.language === 'zh' 
            ? `无法启动学习模式\n\n您的图表包含 ${result.invalidNodes.length} 个未完成的节点。\n请先填写所有节点的内容。`
            : `Cannot Start Learning Mode\n\nYour diagram contains ${result.invalidNodes.length} incomplete nodes.\nPlease fill in all nodes first.`;
        
        const details = result.invalidNodes
            .slice(0, 5)  // Show max 5
            .map(node => `• ${node.text || '(empty)'} (${node.reason})`)
            .join('\n');
        
        return {
            title: this.language === 'zh' ? '验证失败' : 'Validation Failed',
            message: message,
            details: details,
            actions: [
                {text: this.language === 'zh' ? '编辑图表' : 'Edit Diagram', primary: true},
                {text: this.language === 'zh' ? '取消' : 'Cancel'}
            ]
        };
    }
}

// Usage in LearningModeManager
handleLearningModeClick() {
    const validator = new DiagramValidator(this.currentSpec, this.diagramType);
    const result = validator.validateForLearningMode();
    
    if (!result.isValid) {
        const errorDialog = validator.showValidationError(result);
        this.showNotification(errorDialog.message, 'error');
        this.highlightInvalidNodes(result.invalidNodes);
        return;  // Don't enter learning mode
    }
    
    // Validation passed - proceed to learning mode
    this.enterLearningMode();
}
```

**⚠️ Code Reuse Note:**

The `DiagramValidator` class shares similar logic with existing code in `toolbar-manager.js`:
- `extractExistingNodes()` - already extracts all nodes from diagrams
- Placeholder patterns - already defined for auto-complete filtering

**Recommendation**: 
1. Refactor existing `extractExistingNodes()` into a shared utility
2. Reuse placeholder patterns from `toolbar-manager.js`
3. Avoid code duplication by creating `utils/node-extractor.js`

This ensures consistency between auto-complete filtering and learning mode validation.
```

### Backend API Endpoints | 后端API端点

**New LangChain-powered endpoints:**

```python
# ============================================================================
# ENDPOINT 1: Initialize Learning Session
# ============================================================================
POST /api/learning/start_session

Request:
{
    "diagram_type": "bubble_map",
    "spec": {...},  // Complete diagram specification
    "knocked_out_nodes": ["attribute_3", "attribute_5"],
    "language": "zh"
}

Response:
{
    "success": true,
    "session_id": "learning_session_abc123",
    "questions": [
        {
            "node_id": "attribute_3",
            "question": "这个与'光合作用'相连的空白节点代表什么？",
            "context": {
                "parent": "光合作用",
                "siblings": ["水", "二氧化碳"],
                "diagram_type": "bubble_map"
            },
            "difficulty": "medium"
        }
    ],
    "total_questions": 2
}

# ============================================================================
# ENDPOINT 2: Validate Answer (Triggers LangChain Agent if Wrong)
# ============================================================================
POST /api/learning/validate_answer

Request:
{
    "session_id": "learning_session_abc123",
    "node_id": "attribute_3",
    "user_answer": "氧气",
    "question": "这个与'光合作用'相连的空白节点代表什么？",
    "context": {
        "parent": "光合作用",
        "siblings": ["水", "二氧化碳"]
    },
    "language": "zh"
}

Response (if CORRECT):
{
    "correct": true,
    "confidence": 0.98,
    "message": "完全正确！你理解了光合作用的能量来源！",
    "proceed_to_next": true
}

Response (if WRONG - LangChain Agent Activates):
{
    "correct": false,
    "user_answer": "氧气",
    "correct_answer": "阳光",
    
    // Step 1: Misconception Analysis
    "misconception_analysis": {
        "type": "input_output_confusion",
        "diagnosis": "学生知道氧气与光合作用有关，但混淆了输入和输出",
        "mental_model": "认为氧气是反应物而非生成物",
        "severity": "medium",
        "common_error": true,
        "prevalence": 0.34,
        "root_cause": "不理解过程的方向性"
    },
    
    // Step 2: Learning Material
    "learning_material": {
        "acknowledgment": "你知道氧气和光合作用有关系 - 很好！",
        "contrast": "但是氧气是产物（输出），不是原料（输入）",
        "visual_aid": {
            "type": "flow_diagram",
            "inputs": ["阳光⚡", "水💧", "CO₂"],
            "process": "光合作用🌱",
            "outputs": ["葡萄糖🍬", "氧气🫁"]
        },
        "analogy": {
            "domain": "烘焙",
            "explanation": "就像烘焙：面粉+鸡蛋+热量 → 面包+蒸汽。蒸汽不是原料，是副产品。"
        },
        "key_principle": "氧气是植物制造的，不是植物需要的",
        "memory_trick": "光合作用 = 光（阳光）+ 合成"
    },
    
    // Step 3: Verification Question (Different Angle, Same Answer)
    "verification_question": {
        "question": "光合作用过程中，植物从天空获得什么作为能量来源？",
        "angle": "functional_role",
        "hint": "记住：这是一个输入物，提供能量，不是材料或输出",
        "tests_understanding_of": ["能量来源识别", "输入输出区分"]
    },
    
    "proceed_to_next": false,  // Stay on this node
    "show_learning_material": true,
    "next_action": "display_material_then_verify"
}

# ============================================================================
# ENDPOINT 3: Progressive Hint Generation
# ============================================================================
POST /api/learning/get_hint

Request:
{
    "session_id": "learning_session_abc123",
    "node_id": "attribute_3",
    "attempt_number": 1,
    "previous_answers": ["氧气"],
    "language": "zh"
}

Response:
{
    "hint": "提示 Level 1：光合作用需要能量来源。想想太阳提供什么...",
    "hint_level": 1,
    "remaining_hints": 2,
    "scaffolding_type": "contextual"
}

# ============================================================================
# ENDPOINT 4: Verify Understanding (After Learning Material)
# ============================================================================
POST /api/learning/verify_understanding

Request:
{
    "session_id": "learning_session_abc123",
    "node_id": "attribute_3",
    "verification_answer": "阳光",
    "original_question": "这个与'光合作用'相连的空白节点代表什么？",
    "verification_question": "光合作用过程中，植物从天空获得什么作为能量来源？",
    "misconception_addressed": "input_output_confusion",
    "language": "zh"
}

Response (if VERIFIED - Understanding Achieved):
{
    "correct": true,
    "understanding_verified": true,
    "confidence": 0.95,
    "message": "太棒了！你已经真正理解了这个概念！你正确地从两个不同角度识别了答案。",
    "proceed_to_next": true,
    "mastery_demonstrated": true
}

Response (if STILL WRONG - Escalate):
{
    "correct": false,
    "understanding_verified": false,
    "escalation_level": 2,
    
    // New teaching approach
    "new_learning_material": {
        "strategy": "concrete_examples_with_images",
        "content": "让我们看一些具体例子..."
    },
    
    // Yet another angle for same answer
    "new_verification_question": {
        "question": "太阳能板和植物都需要什么来产生能量？",
        "angle": "analogy_based",
        "cognitive_level": "apply"
    },
    
    "encouragement": "没关系，这是很多学生觉得困难的概念。我们换个方式来理解...",
    "proceed_to_next": false,
    "max_attempts_reached": false
}
```

---

## 🤖 LLM Integration

**🎓 Intelligent Tutoring System (ITS) Architecture:**

This is NOT a simple quiz system. It's an **AI-powered intelligent tutor** that:
- Diagnoses student misconceptions
- Generates adaptive learning materials
- Verifies understanding through multiple angles
- Teaches concepts, not just answers

**🎓 Educational-First Design Philosophy:**

This Learning Mode is designed around **research-backed pedagogical principles**, not just gamification:

1. **Active Recall**: Forcing retrieval strengthens neural pathways (Roediger & Butler, 2011)
2. **Educational Scaffolding**: Progressive hints that guide discovery, not just reveal answers (Vygotsky's ZPD)
3. **🆕 Prerequisite Knowledge Tracing**: Identify and test foundational knowledge gaps before tackling complex concepts
4. **Contextual Learning**: Relationships matter more than isolated facts (Constructivist theory)
5. **Socratic Method**: Questions that prompt thinking, not just answer-checking
6. **Error Analysis**: Understanding WHY wrong answers occur helps correct mental models
7. **Metacognition**: Students learn to think about their own thinking process
8. **🆕 Domain Independence**: Teach abstract concepts first, then apply to specific domains (transfer of learning)
9. **🆕 Dynamic Difficulty**: Agent adapts question complexity based on demonstrated knowledge (no fixed levels)

**Key Difference from Traditional Quizzes:**
- ❌ Traditional: "What is X?" → Wrong → "Try again" → Frustration
- ❌ Hint-Based: "What is X?" → Wrong → "Hint about X" → Student guesses → Still doesn't understand WHY
- ✅ **Learning Mode (Prerequisite-First)**: "What is X?" → Wrong → **AI identifies missing prerequisite → Tests that prerequisite → Teaches if needed → Returns to X with foundational understanding** → True Understanding

---

## 🧠 LangChain Agent Architecture

**Why LangChain?**
- **Agent-based reasoning**: Iteratively analyze student responses
- **Tool calling**: Generate materials, search knowledge, analyze patterns
- **Memory**: Track misconceptions across questions
- **Chains**: Multi-step pedagogical workflows

### Agent Workflow | 智能代理工作流

**🧠 PREREQUISITE-FIRST APPROACH** (Knowledge Tracing)

```
Student gives wrong answer "氧气" to question about "阳光"
                    ↓
╔═══════════════════════════════════════════════════════════╗
║  LANGCHAIN LEARNING AGENT                                 ║
╠═══════════════════════════════════════════════════════════╣
║  Step 1: MISCONCEPTION ANALYSIS                           ║
║  - Analyze: Why did student say "氧气"?                  ║
║  - Diagnosis: "Confused INPUT vs OUTPUT"                  ║
║  - Root cause: "Doesn't understand process directionality"║
╠═══════════════════════════════════════════════════════════╣
║  Step 2: PREREQUISITE IDENTIFICATION 🆕                   ║
║  - Missing knowledge: "input-output distinction"          ║
║  - Prerequisite tree:                                     ║
║    └─ "process_directionality"                            ║
║       └─ "before_after_temporal_concept"                  ║
║  - Decision: Test "input-output distinction" first        ║
╠═══════════════════════════════════════════════════════════╣
║  Step 3: PREREQUISITE TEST GENERATION 🆕                  ║
║  - Generate: Simpler, abstract test question              ║
║  - Content: "A + B → C + D. Which are inputs?"           ║
║  - Cognitive level: Lower than original question          ║
║  - Context: Domain-independent (not photosynthesis yet)   ║
╠═══════════════════════════════════════════════════════════╣
║  Step 4: ADAPTIVE BRANCHING 🆕                            ║
║  - If prerequisite test PASSES:                           ║
║    → Return to original question with targeted hint       ║
║  - If prerequisite test FAILS:                            ║
║    → Teach that prerequisite concept (mini-lesson)        ║
║    → Test with even simpler example (recursive)           ║
║    → Maximum 3 levels deep before offering skip           ║
╚═══════════════════════════════════════════════════════════╝
                    ↓
Student demonstrates prerequisite knowledge
                    ↓
Return to original question ("阳光") with foundational understanding
                    ↓
Student answers correctly → True understanding achieved! ✓
```

**Key Difference from Traditional Approach:**

| Traditional Learning Mode | **NEW: Prerequisite-First Approach** |
|--------------------------|--------------------------------------|
| Wrong answer → Hint about SAME question | Wrong answer → Test PREREQUISITE knowledge |
| "Think about what plants need for photosynthesis..." | "First, do you understand inputs vs outputs in ANY process?" |
| Stay in same domain (photosynthesis) | Abstract to simpler domain (A+B→C+D) |
| Risk: Student guesses correctly without understanding | Ensures: Build foundational knowledge before application |
| Hints get more direct about the answer | Tests get simpler until student demonstrates mastery |

**Pedagogical Advantage:**
✅ **Diagnostic** - Identifies exact knowledge gap  
✅ **Foundational** - Teaches root concepts, not surface facts  
✅ **Transferable** - Student can apply learning to new problems  
✅ **Confidence-building** - Success at simpler level motivates  
✅ **Efficient** - No wasted attempts on questions beyond student's current level
```

### LangChain Tools/Components | 工具组件

```python
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain

class LearningAgent:
    """
    Intelligent tutoring agent that diagnoses misconceptions
    and generates adaptive learning materials.
    """
    
    def __init__(self):
        self.tools = [
            self.misconception_analyzer,
            self.prerequisite_identifier,        # 🆕 NEW TOOL
            self.prerequisite_test_generator,    # 🆕 NEW TOOL
            self.learning_material_generator,
            self.knowledge_base_search
        ]
        
        self.memory = ConversationBufferMemory(
            memory_key="student_progress",
            return_messages=True
        )
        
        self.agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.system_prompt
        )
    
    # Tool 1: Misconception Analysis
    @tool
    def misconception_analyzer(
        self,
        correct_answer: str,
        student_answer: str,
        question_context: dict
    ) -> dict:
        """
        Analyze WHY student gave wrong answer.
        Returns: {
            "misconception_type": "input_output_confusion",
            "root_cause": "Doesn't understand process directionality",
            "severity": "medium",
            "common_error": true
        }
        """
        pass
    
    # Tool 2: Prerequisite Identifier 🆕
    @tool
    def prerequisite_identifier(
        self,
        misconception: dict,
        correct_answer: str,
        student_answer: str,
        context: dict
    ) -> dict:
        """
        Identify what PREREQUISITE knowledge is missing based on the error.
        Returns: {
            "missing_prerequisite": "input_output_distinction",
            "prerequisite_tree": ["process_directionality", "temporal_ordering"],
            "cognitive_level_gap": 2,  # How many levels simpler to test
            "reasoning": "Student confused products with reactants, suggests lack of process understanding"
        }
        """
        pass
    
    # Tool 3: Prerequisite Test Generator 🆕
    @tool
    def prerequisite_test_generator(
        self,
        prerequisite_concept: str,
        original_question: str,
        language: str
    ) -> dict:
        """
        Generate a SIMPLER test question for the prerequisite concept.
        Uses domain-independent examples when possible.
        Returns: {
            "test_question": "In A + B → C + D, which are inputs?",
            "correct_answer": ["A", "B"],
            "question_type": "multiple_choice | text_input",
            "cognitive_level": "remember",  # Lower than original
            "domain": "abstract",  # vs "photosynthesis"
            "hints_if_wrong": [...]
        }
        """
        pass
    
    # Tool 4: Learning Material Generation
    @tool
    def learning_material_generator(
        self,
        prerequisite_concept: str,
        language: str
    ) -> dict:
        """
        Generate mini-lesson for prerequisite concept (NOT the original topic).
        Returns: {
            "material_type": "micro_lesson",
            "concept": "input_output_distinction",
            "content": "...",
            "visual_aid": {...},
            "examples": ["baking", "tea_making"],  # Simple analogies
            "practice_question": "..."
        }
        """
        pass
    
    # Tool 5: Knowledge Base Search
    @tool
    def knowledge_base_search(
        self,
        topic: str,
        misconception: str
    ) -> dict:
        """
        Search for relevant educational materials, common errors, teaching strategies.
        Also includes prerequisite mapping database.
        """
        pass
```

### Complete Agent Workflow Example | 完整代理工作流示例

**Scenario**: Student answers "氧气" for node that should be "阳光"

```python
# ========================================================================
# Step 1: Misconception Analysis
# ========================================================================
analysis = agent.misconception_analyzer(
    correct_answer="阳光",
    student_answer="氧气",
    question_context={
        "parent": "光合作用",
        "siblings": ["水", "二氧化碳"],
        "question": "What energy source does photosynthesis need?"
    }
)

# Returns:
{
    "misconception_type": "input_output_confusion",
    "confidence": 0.92,
    "diagnosis": "Student understands O2 relates to photosynthesis but reversed the causal direction",
    "mental_model": "Thinks oxygen is consumed rather than produced",
    "common_error": True,
    "prevalence": 0.34,  # 34% of students make this error
    "severity": "medium",
    "prerequisite_gaps": ["process_directionality", "energy_vs_material"],
    "teaching_strategy": "test_prerequisite_first"  # 🆕 Changed from "use_flow_diagram"
}

# ========================================================================
# Step 2: Identify Missing Prerequisite 🆕
# ========================================================================
prerequisite = agent.prerequisite_identifier(
    misconception=analysis,
    correct_answer="阳光",
    student_answer="氧气",
    context={
        "parent": "光合作用",
        "siblings": ["水", "二氧化碳"]
    }
)

# Returns:
{
    "missing_prerequisite": "input_output_distinction",
    "prerequisite_tree": [
        "process_directionality",       # Level 1: Understanding process flow
        "temporal_ordering",            # Level 2: Understanding before/after
        "category_distinction"          # Level 3: Understanding types
    ],
    "cognitive_level_gap": 2,  # Test 2 levels simpler
    "reasoning": "Student knows O2 relates to photosynthesis but can't distinguish reactants from products",
    "test_strategy": "abstract_then_concrete"  # Start with domain-independent test
}

# ========================================================================
# Step 3: Generate Prerequisite Test Question 🆕
# ========================================================================
prereq_test = agent.prerequisite_test_generator(
    prerequisite_concept="input_output_distinction",
    original_question="What energy source does photosynthesis need?",
    language="zh"
)

# Returns:
{
    "test_question": "在方程式 A + B → C + D 中，哪些是输入（反应开始时就有的）？",
    "test_question_en": "In the equation A + B → C + D, which are INPUTS (present at the start)?",
    "correct_answer": ["A", "B"],
    "question_type": "multiple_choice",
    "options": ["A", "B", "C", "D"],
    "cognitive_level": "remember",  # Simpler than original "apply" level
    "domain": "abstract",  # NOT photosynthesis domain
    "explanation_if_correct": "Great! You understand inputs are what you START with.",
    "explanation_if_wrong": {
        "answered_C_or_D": "C and D are OUTPUTS - they're created by the process.",
        "general": "Inputs are before the arrow →, outputs are after the arrow →"
    }
}

# ========================================================================
# Step 4: Student Takes Prerequisite Test
# ========================================================================

## Scenario A: Student PASSES prerequisite test
student_prereq_answer = ["A", "B"]  # Correct!

response_pass = {
    "correct": True,
    "message": "✅ Excellent! You understand inputs vs outputs in general.",
    "next_action": "return_to_original_question",
    "enhanced_hint": "Now let's apply this to photosynthesis: 阳光+水+CO₂ → 葡萄糖+O₂. Which is an INPUT that provides energy?"
}

## Scenario B: Student FAILS prerequisite test
student_prereq_answer = ["C", "D"]  # Wrong!

# Agent generates SIMPLER mini-lesson
mini_lesson = agent.learning_material_generator(
    prerequisite_concept="input_output_distinction",
    language="zh"
)

# Returns:
{
    "material_type": "micro_lesson",
    "concept": "input_output_distinction",
    "duration": "1-2 minutes",
    "content": {
        "title": "理解输入和输出",
        "explanation": "在任何过程中：\n输入 = 开始时有的东西\n输出 = 结束时产生的东西",
        "visual_aid": {
            "type": "simple_flow",
            "example": "烘焙面包",
            "inputs_arrow": "面粉 + 水 + 酵母 + 热量",
            "process_box": "[烘焙]",
            "outputs_arrow": "面包 + 蒸汽 + 香味"
        },
        "key_point": "输入被消耗，输出被创造",
        "memory_trick": "输入在箭头左边 ←→ 输出在箭头右边"
    },
    "practice_question": {
        "question": "泡茶：水 + 茶叶 + 热量 → 热茶 + 茶渣。哪些是输入？",
        "answer": ["水", "茶叶", "热量"]
    }
}

# Then test with practice question → If pass → Return to original question

# ========================================================================
# Step 5: Return to Original Question (After Prerequisite Mastery)
# ========================================================================

return_prompt = {
    "message": "现在你理解了输入和输出！让我们回到光合作用问题：",
    "original_question": "What is the blank node connected to '光合作用'?",
    "contextualized_hint": "记住：输入在过程之前。光合作用的输入是：阳光 + 水 + CO₂。哪个提供能量？",
    "student_confidence": "high"  # They demonstrated prerequisite knowledge
}

# Student now answers: "阳光" ✓
final_response = {
    "correct": True,
    "learning_path_summary": {
        "initial_error": "氧气 (confused output for input)",
        "prerequisite_tested": "input_output_distinction",
        "prerequisite_result": "passed after mini-lesson",
        "final_answer": "阳光 ✓",
        "understanding_verified": True
    },
    "message": "太棒了！你不仅记住了答案，还理解了为什么！",
    "metacognitive_reflection": "你先学会了输入输出的概念，然后成功应用到了光合作用。这是真正的理解！"
}
```

### Multi-Angle Question Strategy | 多角度提问策略

**For the SAME node "阳光", generate different questions:**

```python
QUESTION_ANGLES = {
    "structural_relationship": {
        "question": "这个与'光合作用'和'水'相连的节点是什么？",
        "tests": "spatial/relationship memory",
        "cognitive_level": "recognize"
    },
    
    "functional_role": {
        "question": "光合作用的主要能量来源是什么？",
        "tests": "conceptual understanding of function",
        "cognitive_level": "understand"
    },
    
    "process_integration": {
        "question": "植物白天需要什么来将CO₂和H₂O转化为葡萄糖？",
        "tests": "process understanding + causal reasoning",
        "cognitive_level": "apply"
    },
    
    "contrast_discrimination": {
        "question": "在光合作用的输入中，哪个提供能量而不是材料？",
        "tests": "ability to distinguish categories",
        "cognitive_level": "analyze"
    },
    
    "source_direction": {
        "question": "光合作用中，植物从天空获得什么？",
        "tests": "understanding of source and directionality",
        "cognitive_level": "apply"
    }
}

# Agent selects question angles based on:
# 1. What misconception needs to be addressed
# 2. What angle was used before
# 3. Bloom's taxonomy progression
```

### Agent System Prompt | 代理系统提示词

```python
LEARNING_AGENT_SYSTEM_PROMPT = """
You are an expert educational AI tutor specializing in diagnosing student misconceptions 
and generating adaptive learning materials.

Your goal is NOT to just check if answers are correct, but to:
1. Understand WHY students give wrong answers
2. Identify what PREREQUISITE knowledge is missing
3. Test prerequisite knowledge FIRST before re-asking original question
4. Teach missing prerequisites through simple, domain-independent examples
5. Return to original question only after prerequisite mastery is demonstrated

=== YOUR CAPABILITIES ===

Tool 1: misconception_analyzer
- Analyze student's wrong answer in context
- Diagnose the type of error (e.g., input-output confusion, category mistake, partial knowledge)
- Identify ROOT CAUSE, not just surface error
- Estimate severity and commonality

Tool 2: prerequisite_identifier 🆕
- Based on misconception, identify what PREREQUISITE knowledge is missing
- Build prerequisite tree (e.g., "input-output" requires "process directionality")
- Determine cognitive level gap (how many levels simpler to test)
- Decide whether to test prerequisite or give direct hint

Tool 3: prerequisite_test_generator 🆕
- Generate SIMPLER test questions for prerequisite concepts
- Use domain-independent examples (A+B→C+D instead of photosynthesis)
- Cognitive level should be LOWER than original question
- Multiple choice or simple text input

Tool 4: learning_material_generator
- Generate micro-lessons for PREREQUISITE concepts (not original topic yet)
- Use simple, everyday examples (baking, making tea)
- 1-2 minutes maximum
- Include practice question to verify understanding

Tool 5: knowledge_base_search
- Search for common student errors and prerequisite mappings
- Find effective teaching analogies for foundational concepts
- Retrieve prerequisite knowledge hierarchies

=== PEDAGOGICAL PRINCIPLES ===

1. **Growth Mindset**: Treat errors as learning opportunities
2. **Scaffolding**: Provide just enough support, not too much or too little
3. **Multiple Representations**: Use text, visuals, analogies
4. **Deep Processing**: Ask WHY, not just WHAT
5. **Verification**: Test understanding from multiple angles
6. **Encouragement**: Be warm, supportive, never condescending

=== WORKFLOW (Prerequisite-First Approach) ===

When student gives wrong answer:
1. ANALYZE: What misconception does this reveal?
2. IDENTIFY: What PREREQUISITE knowledge is missing?
3. TEST PREREQUISITE: Ask simpler question about prerequisite (domain-independent)
4. BRANCH:
   - If prerequisite test PASSES → Return to original with enhanced hint
   - If prerequisite test FAILS → Teach prerequisite with micro-lesson
5. RE-TEST: Practice question on prerequisite concept
6. RETURN: Back to original question with foundational understanding
7. SUCCEED: Student answers correctly because they understand WHY

=== EXAMPLE REASONING (Prerequisite-First) ===

Student answers "氧气" for "阳光" in photosynthesis:

Reasoning:
- Student knows O2 relates to photosynthesis → Partial knowledge ✓
- Student said O2 when answer is sunlight → INPUT/OUTPUT confusion
- This is a PROCESS DIRECTIONALITY error → Common misconception (34%)
- Root cause: Doesn't understand INPUTS vs OUTPUTS in general

🆕 **Prerequisite-First Decision:**
- DON'T give hint about photosynthesis yet
- DO test if student understands inputs/outputs in ANY process
- Generate abstract test: "A + B → C + D. Which are inputs?"
- If they fail → Teach input/output concept with simple examples (baking, making tea)
- If they pass → Return to photosynthesis with "Now apply this: 阳光+水+CO₂ → 葡萄糖+O₂"

Why This Works Better:
- Student learns the FOUNDATIONAL concept (inputs vs outputs)
- Student can now APPLY this to any domain (not just memorize photosynthesis)
- Student gains CONFIDENCE from succeeding at simpler level
- Student understands WHY, not just WHAT

Remember: Your job is to BUILD FOUNDATIONS, not just give hints.
"""
```

### 1. Question Generation | 问题生成

**Educational Philosophy | 教育理念:**

The initial hints should follow **educational scaffolding principles**:
- **Context-Rich**: Provide relationships and connections to visible nodes
- **Progressive Disclosure**: Start with general clues, get more specific
- **Memory Aids**: Use mnemonics, associations, or memorable characteristics
- **Teaching, Not Telling**: Help users understand WHY, not just WHAT
- **Socratic Questioning**: Guide discovery through leading questions

**LLM Prompt Template (Enhanced):**

```python
QUESTION_GENERATION_PROMPT = """
You are an expert educational tutor helping students learn through active recall.

=== CONTEXT ===
Diagram Type: {diagram_type}
Diagram Topic: {diagram_topic}
Hidden Node (answer): {node_text}

Node Relationships (VISIBLE to student):
- Parent node: {parent_node}
- Sibling nodes: {sibling_nodes}
- Child nodes: {child_nodes}
- Connected nodes: {connected_nodes}

=== YOUR TASK ===
Generate an educational question that helps the student recall "{node_text}" through:

1. **Contextual Clues** - Reference visible nodes they can see
2. **Relationship Hints** - Explain HOW this node connects to others
3. **Conceptual Understanding** - Why this node matters in the diagram
4. **Memory Triggers** - Use characteristics, patterns, or associations

=== EDUCATIONAL PRINCIPLES ===
✓ DO: Give rich context about relationships with visible nodes
✓ DO: Use metaphors, examples, or real-world connections
✓ DO: Provide "thinking frameworks" (e.g., "This is the cause of X")
✓ DO: Use memory techniques (first letter, rhymes, categories)

✗ DON'T: Just describe the node in isolation
✗ DON'T: Give overly vague hints like "It's important"
✗ DON'T: Make it a pure guessing game

=== OUTPUT FORMAT ===
{
    "question": "What is the blank node connected to '{parent_node}'?",
    "initial_hint": "💡 Contextual clue: This node represents [relationship/role]. It connects to {sibling_1} and {sibling_2}, forming [pattern/concept].",
    "educational_rationale": "Brief explanation of why this node matters",
    "difficulty": "easy/medium/hard",
    "memory_aid": "Optional: Mnemonic or association technique"
}

=== EXAMPLES OF GOOD HINTS ===

Example 1 (Bubble Map - Attributes):
Question: "What attribute of '太阳能' is missing?"
Initial Hint: "💡 This node is connected to '太阳能' as one of its key benefits. 
It relates to '清洁' (clean) and '持久' (long-lasting). 
Think about what makes solar energy different from fossil fuels economically."
Memory Aid: "Think: 可 + 更新 = can be renewed"

Example 2 (Mind Map - Branches):
Question: "What is the third main branch of '项目管理'?"
Initial Hint: "💡 This branch appears after '计划' (Planning) and '执行' (Execution). 
It's about checking progress and making sure everything stays on track. 
What do you do to keep projects under control?"
Memory Aid: "P-E-? (Plan-Execute-?)"

Example 3 (Tree Map - Categories):
Question: "What category contains '苹果' and '香蕉'?"
Initial Hint: "💡 Look at what '苹果' (apple) and '香蕉' (banana) have in common. 
They're all siblings under this category in the tree structure. 
This is a broad classification of food items."
Memory Aid: "They all grow on trees or plants"

Language: {language}
Generate everything in {language} only.
Use clear, encouraging, educational tone.
"""
```

**Enhanced Example Output (Chinese):**
```json
{
    "question": "与'光合作用'相连的空白节点是什么？",
    "initial_hint": "💡 上下文提示：这个节点是光合作用的主要能量来源。它与'水'和'二氧化碳'一起，被植物用来制造食物。想想植物在白天最需要什么来进行光合作用？",
    "educational_rationale": "理解能量来源对掌握光合作用过程至关重要",
    "difficulty": "easy",
    "memory_aid": "光（光合作用的'光'）=光源",
    "node_id": "attribute_2",
    "relationships": {
        "parent": "光合作用",
        "siblings": ["水", "二氧化碳"],
        "type": "attribute"
    }
}
```

**Enhanced Example Output (English):**
```json
{
    "question": "What is the blank node connected to 'Photosynthesis'?",
    "initial_hint": "💡 Contextual clue: This node represents the primary energy source for photosynthesis. It works together with 'Water' and 'Carbon Dioxide' - all three are essential inputs. Think about what plants need during the day to make food.",
    "educational_rationale": "Understanding the energy source is key to grasping how photosynthesis works",
    "difficulty": "easy",
    "memory_aid": "Photo = Light (Greek origin)",
    "node_id": "attribute_2",
    "relationships": {
        "parent": "Photosynthesis",
        "siblings": ["Water", "Carbon Dioxide"],
        "type": "attribute"
    }
}
```

### 2. Answer Validation | 答案验证

**Approach: Hybrid (Exact + Semantic)**

```python
def validate_answer(user_answer, correct_answer, language):
    # Step 1: Exact match (case-insensitive)
    if user_answer.lower().strip() == correct_answer.lower().strip():
        return {"is_correct": True, "match_type": "exact", "score": 1.0}
    
    # Step 2: Close match (Levenshtein distance < 2)
    if levenshtein_distance(user_answer, correct_answer) <= 2:
        return {"is_correct": True, "match_type": "close", "score": 0.9}
    
    # Step 3: Semantic match (LLM-based)
    llm_prompt = f"""
    Correct answer: {correct_answer}
    User answer: {user_answer}
    Language: {language}
    
    Are these semantically equivalent? Consider:
    - Synonyms (太阳 = 阳光 = 太阳光)
    - Different expressions of same concept
    - Acceptable variations
    
    Respond: {{"is_correct": true/false, "similarity": 0.0-1.0, "reason": "..."}}
    """
    
    return llm_validate(llm_prompt)
```

**Example Cases:**
- User: "太阳" → Correct: "阳光" → ✅ Semantic match (0.95 similarity)
- User: "月亮" → Correct: "阳光" → ❌ Wrong concept (0.1 similarity)
- User: "氧气" → Correct: "阳光" → ❌ Related but wrong (0.3 similarity)

### 3. Progressive Hint Generation | 渐进式提示生成

**Educational Scaffolding Strategy: 3 Levels of Assistance**

Each hint should **teach progressively**, not just reveal the answer. The goal is to guide thinking, not spoon-feed.

**LLM Prompt Template (Enhanced):**

```python
PROGRESSIVE_HINT_PROMPT = """
You are an expert tutor helping a student who gave an incorrect answer.

=== LEARNING CONTEXT ===
Correct Answer: {correct_answer}
Student's Answer: {user_answer}
Attempt Number: {attempt_number} of 3
Previous Hints Shown: {previous_hints}

Node Relationships (visible to student):
- Parent: {parent_node}
- Siblings: {sibling_nodes}
- Connected: {connected_nodes}

=== HINT LEVEL STRATEGY ===

**Level 1 (First Mistake)** - Redirect Thinking:
- Acknowledge what was GOOD about their answer (if anything)
- Gently redirect their thinking direction
- Focus on RELATIONSHIPS with visible nodes
- Ask leading questions to trigger recall
Example: "Good thinking, but not quite. This node is related to both {sibling_1} and {sibling_2}. What connects all three of these concepts?"

**Level 2 (Second Mistake)** - Narrow the Focus:
- Provide more specific context about role/function
- Use analogies or real-world examples
- Give characteristic hints (but not the word itself)
- Encourage pattern recognition
Example: "Let me help you narrow it down. This is the PRIMARY source that {parent_node} depends on. Think about what's always present during the day..."

**Level 3 (Third Mistake)** - Direct but Educational:
- Give strong clues (first character, word structure, etc.)
- Explain WHY this answer makes sense
- Connect to larger concept
- Prepare for "show answer" moment
Example: "You're almost there! The answer starts with '阳'. It's related to '太阳' (sun) but specifically the light/energy it provides. 阳__"

=== PEDAGOGICAL PRINCIPLES ===
✓ DO: Acknowledge effort ("Good try!", "You're thinking in the right direction")
✓ DO: Explain WHY their answer might seem related
✓ DO: Connect to visible nodes they can see
✓ DO: Use "Socratic questioning" to guide thinking
✓ DO: Build on what they already know

✗ DON'T: Make student feel bad for wrong answer
✗ DON'T: Just say "wrong, try again"
✗ DON'T: Give hints that don't teach the underlying concept
✗ DON'T: Be condescending or overly simplistic

=== ANALYZING STUDENT'S WRONG ANSWER ===
Consider WHY they might have said "{user_answer}":
- Is it related but wrong category?
- Is it a common misconception?
- Is it phonetically similar?
- Is it conceptually adjacent?

Use this analysis to craft a hint that CORRECTS their mental model.

=== OUTPUT FORMAT ===
{
    "hint": "💡 Level {level} hint text...",
    "encouragement": "Positive, encouraging message",
    "teaching_point": "What concept/relationship you're emphasizing",
    "why_not_their_answer": "Brief explanation of why {user_answer} isn't correct"
}

Language: {language}
Tone: Warm, encouraging, educational (like a patient teacher)
"""
```

**Enhanced Example Progression (Chinese - Photosynthesis):**

```
Correct Answer: "阳光" (Sunlight)
Context: Node connected to "光合作用" with siblings "水" and "二氧化碳"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Attempt 1: User types "水" (Water) - wrong
→ Hint 1 (Redirect Thinking):
{
    "hint": "💡 好的思考方向！'水'确实是光合作用的重要组成部分。
    但我们要找的是能量来源，不是原材料。看看'水'和'二氧化碳'旁边，
    还缺少什么来驱动整个光合作用过程？想想植物在白天从天空获得什么？",
    
    "encouragement": "你已经在正确的轨道上了！💪",
    
    "teaching_point": "区分'原材料'（水、二氧化碳）和'能量来源'",
    
    "why_not_their_answer": "'水'是原材料，但光合作用需要能量来转化这些原材料"
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Attempt 2: User types "氧气" (Oxygen) - wrong
→ Hint 2 (Narrow Focus):
{
    "hint": "💡 有趣的猜测！但'氧气'其实是光合作用的产物（输出），
    不是输入。我们要找的是输入能量。想象一下：植物白天需要什么才能工作，
    而晚上没有这个就停止光合作用？这个来自太阳的东西叫什么？",
    
    "encouragement": "你正在深入思考光合作用的过程！很好！🌱",
    
    "teaching_point": "区分光合作用的输入（能量+原料）和输出（产物）",
    
    "why_not_their_answer": "氧气是光合作用产生的，不是光合作用需要的"
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Attempt 3: User types "太阳" (Sun) - very close!
→ Hint 3 (Direct but Educational):
{
    "hint": "💡 非常接近了！'太阳'是正确的概念！但我们需要更准确的词。
    我们要的不是太阳本身，而是太阳发出来的东西。
    想想：'阳____'。这个词特指太阳的光线和能量。
    提示：'光'合作用的'光'就是指这个！",
    
    "encouragement": "你几乎答对了！就差一点点！🌟",
    
    "teaching_point": "区分太阳（物体）和阳光（能量形式）",
    
    "why_not_their_answer": "'太阳'是对的概念，但科学上我们说的是'阳光'或'太阳光'"
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

After 3 attempts → Show Answer with Explanation:
{
    "answer": "阳光",
    "explanation": "💡 答案是'阳光'！
    
    为什么是阳光？
    • 阳光是光合作用的能量来源
    • 植物用阳光的能量，把水和二氧化碳转化为葡萄糖
    • 没有阳光，光合作用就无法进行（这就是为什么植物晚上不进行光合作用）
    
    记忆技巧：'光'合作用 = 光（阳光）+ 合成
    
    关系图：阳光 + 水 + 二氧化碳 → 葡萄糖 + 氧气",
    
    "encouragement": "现在你理解了阳光在光合作用中的关键作用！🌞🌿"
}
```

**Enhanced Example Progression (English - Project Management):**

```
Correct Answer: "Monitoring" (项目监控)
Context: Third branch after "Planning" and "Execution" in Mind Map

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Attempt 1: User types "Closing" - wrong
→ Hint 1:
{
    "hint": "💡 Good thinking! 'Closing' is definitely part of project management, 
    but it comes later. The missing branch happens DURING the project execution phase. 
    After you plan and start executing, what do you need to do continuously to make sure 
    everything is on track? Think: Plan → Execute → _____?",
    
    "encouragement": "You're thinking about the project lifecycle! Keep going! 🎯",
    
    "teaching_point": "Project phases sequence: Plan → Execute → Monitor → Close",
    
    "why_not_their_answer": "'Closing' is the final phase, but we need the middle step"
}

Attempt 2: User types "Testing" - wrong but closer
→ Hint 2:
{
    "hint": "💡 Interesting! 'Testing' is related because it involves checking things. 
    But we need a broader term. This branch is about continuously WATCHING the project's 
    progress, checking metrics, tracking budgets, and making sure you're meeting goals. 
    What's the management term for keeping an eye on everything? Hint: It's what you 
    do with a baby monitor...",
    
    "encouragement": "You're getting warmer! You've got the 'checking' concept! 👍",
    
    "teaching_point": "Monitoring is broader than testing - it's ongoing observation",
    
    "why_not_their_answer": "'Testing' is too specific; we need the overall tracking activity"
}

Attempt 3: User types "Controlling" - so close!
→ Hint 3:
{
    "hint": "💡 You're RIGHT THERE! 'Controlling' is actually a paired term with our answer! 
    In project management, we often say 'M_____ and Controlling' together. 
    The word starts with 'M' and means to observe, track, and watch progress. 
    Think: baby M______.",
    
    "encouragement": "Almost perfect! You understand the concept! 🌟",
    
    "teaching_point": "Monitoring (observe) + Controlling (adjust) = project oversight",
    
    "why_not_their_answer": "'Controlling' is the action after monitoring; we monitor first"
}
```

---

## 📊 Data Structures

### LearningSession Class

```javascript
class LearningSession {
    constructor(diagramSpec, diagramType, language) {
        this.diagramSpec = diagramSpec;
        this.diagramType = diagramType;
        this.language = language;
        
        // Node selection
        this.allNodes = [];           // All nodes in diagram
        this.knockedOutNodes = [];    // 20% nodes to test
        this.remainingNodes = [];     // 80% visible nodes
        
        // Questions
        this.questions = [];          // Generated questions
        this.currentQuestionIndex = 0;
        
        // Session state
        this.sessionId = generateId();
        this.startTime = Date.now();
        this.attempts = {};           // {question_id: attempt_count}
        this.hintsUsed = {};          // {question_id: hints_shown}
        this.answers = {};            // {question_id: user_answer}
        this.scores = {};             // {question_id: is_correct}
        
        // UI state
        this.isPaused = false;
        this.isCompleted = false;
    }
}
```

### Question Object

```javascript
{
    id: "q_1",
    nodeId: "attribute_2",
    nodeText: "阳光",                    // Correct answer (hidden)
    question: "这个节点与"光合作用"相连...",
    initialHint: "💡 它来自天空",
    difficulty: "easy",
    relationships: {
        parent: {id: "topic_center", text: "光合作用"},
        siblings: [{id: "attribute_1", text: "水"}],
        type: "attribute"
    },
    attempts: 0,
    maxAttempts: 3,
    hintsShown: [],
    userAnswer: null,
    isCorrect: null,
    skipped: false,
    timeSpent: 0
}
```

### Session Summary

```javascript
{
    sessionId: "session_abc123",
    diagramType: "bubble_map",
    totalQuestions: 5,
    correctAnswers: 4,
    incorrectAnswers: 1,
    skipped: 0,
    totalHintsUsed: 3,
    totalAttempts: 8,
    averageAttempts: 1.6,
    score: 0.80,                // 80%
    timeSpent: 180,             // 3 minutes
    completedAt: "2025-10-05T12:30:00Z",
    questions: [
        {id: "q_1", correct: true, attempts: 1, hints: 0, time: 30},
        {id: "q_2", correct: true, attempts: 1, hints: 0, time: 25},
        {id: "q_3", correct: false, attempts: 3, hints: 2, time: 60},
        {id: "q_4", correct: true, attempts: 2, hints: 1, time: 40},
        {id: "q_5", correct: true, attempts: 1, hints: 0, time: 25}
    ]
}
```

---

## 🚀 Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2) | 核心基础设施

**Goals:**
- ✅ Create LearningModeManager class
- ✅ Add "Learning" button to toolbar with rainbow glow animation
- ✅ **Implement DiagramValidator class** ⚠️ CRITICAL
  - Node completeness checker
  - Placeholder pattern detection
  - Button enable/disable logic
  - Validation error notifications
- ✅ Implement 20% random node selection
- ✅ Basic node knockout rendering (hide text)
- ✅ Simple input field injection

**Deliverables:**
- Rainbow-glowing "学习" button appears in toolbar
- Button disabled when diagram has placeholders/empty nodes
- Button enabled only when all nodes have meaningful content
- Validation error messages show which nodes are incomplete
- After validation passes: 20% of nodes become blank with input fields
- No questions yet, just visual knockout

**Testing Checklist:**
- [ ] Button disabled on fresh diagram with placeholders
- [ ] Button enabled after all nodes filled
- [ ] Validation catches Chinese placeholders ("分支1", "节点2")
- [ ] Validation catches English placeholders ("Branch 1", "Node 2")
- [ ] Error message shows list of incomplete nodes
- [ ] Clicking disabled button shows helpful tooltip

### Phase 2: LangChain Agent Setup (Week 2-3) | LangChain代理设置

**Goals:**
- ✅ **Install LangChain dependencies** (`langchain`, `langchain-openai`)
- ✅ Create `agents/learning_agent.py` module
- ✅ Implement 4 core agent tools:
  - `misconception_analyzer`
  - `learning_material_generator`
  - `verification_question_generator`
  - `knowledge_base_search`
- ✅ Set up ConversationBufferMemory
- ✅ Create educational system prompt
- ✅ Test agent with mock scenarios

**Deliverables:**
- LangChain agent framework operational
- Agent can analyze student errors
- Agent can generate teaching materials
- Agent tools tested with photosynthesis example

**Testing Checklist:**
- [ ] Agent correctly identifies "input_output_confusion"
- [ ] Learning materials include: acknowledgment, contrast, visual aid, analogy
- [ ] Verification questions ask about same concept from different angle
- [ ] Agent memory persists across multiple questions

### Phase 3: Question Generation & Validation (Week 3-4) | 问题生成与验证

**Goals:**
- ✅ Backend API: `/api/learning/start_session`
- ✅ Backend API: `/api/learning/validate_answer` (with agent integration)
- ✅ LLM prompt template for initial question generation
- ✅ Extract node relationships from diagram spec
- ✅ Integrate agent for wrong answer handling
- ✅ Display correct/incorrect feedback
- ✅ Show learning material modal when answer is wrong
- ✅ Reveal node text when verified understanding achieved

**Deliverables:**
- User types answer → System validates
- Correct answers reveal node text immediately and move to next
- **NEW**: Incorrect answers trigger LangChain agent analysis
- **NEW**: Learning material modal displayed with visual aids, analogies, examples
- **NEW**: Verification question presented (different angle, same answer)
- **NEW**: Understanding verified or escalated to new teaching approach

**Testing Checklist:**
- [ ] Wrong answer triggers agent misconception analysis
- [ ] Learning material includes: acknowledgment, contrast, visual aid, analogy, key principle
- [ ] Verification question tests same concept from different cognitive angle
- [ ] Correct verification = understanding verified, move to next
- [ ] Wrong verification = escalate (new material, new angle, repeat)

### Phase 4: Multi-Angle Verification & Escalation (Week 4-5) | 多角度验证与升级

**Goals:**
- ✅ Backend API: `/api/learning/verify_understanding`
- ✅ **Multi-angle question generation** (5 cognitive perspectives per concept)
- ✅ **Iterative teaching cycle**: Wrong → Analyze → Teach → Verify → Repeat if needed
- ✅ Progressive hint system (3 levels) for original questions
- ✅ Escalation levels (up to 3 teaching attempts)
- ✅ Track misconception patterns across session
- ✅ "Skip" option after max escalations

**Deliverables:**
- Verification questions test understanding from different angles:
  - Structural relationship → Functional role
  - Definition → Application
  - Category → Example
- Failed verification generates NEW learning material with different teaching strategy
- Failed verification generates NEW question angle
- System intelligently escalates teaching approach
- Max 3 escalations before offering skip option

**Testing Checklist:**
- [ ] Question angles are truly different (not just reworded)
- [ ] Escalation Level 1: Flow diagrams + analogies
- [ ] Escalation Level 2: Concrete examples + images
- [ ] Escalation Level 3: Simplified explanation + memory tricks
- [ ] Misconception patterns tracked in session memory
- [ ] Skip option appears after 3 failed escalations

### Phase 5: Learning Material UI & Animations (Week 5-6) | 学习材料界面

**Goals:**
- ✅ **Full-screen learning material modal** with rich content
- ✅ Render flow diagrams (SVG or HTML visualization)
- ✅ Display analogies with visual formatting
- ✅ Interactive buttons ("我明白了", "显示更多例子", "跳过")
- ✅ Progress indicator ("Understanding: 60% verified", "3/5 questions")
- ✅ Celebration animations for verified understanding
- ✅ Encouraging feedback for escalations
- ✅ Mobile responsive design
- ✅ Accessibility (ARIA labels, keyboard navigation)

**Deliverables:**
- Beautiful learning material modal with:
  - Acknowledgment section (warm, encouraging tone)
  - Contrast section (highlight the misconception)
  - Visual aid (flow diagram or illustration)
  - Analogy (relatable real-world example)
  - Key principle (memorable takeaway)
  - Memory trick (mnemonic)
- Smooth transitions between teaching, verification, escalation states
- Visual feedback for all user actions
- Works seamlessly on mobile and desktop

### Phase 6: Session Analytics & Intelligent Reporting (Week 6-7) | 会话分析

**Goals:**
- ✅ Session persistence (localStorage + optional backend)
- ✅ **Misconception analytics dashboard**:
  - Most common error types
  - Concepts requiring most escalations
  - Learning material effectiveness scores
  - Time spent per misconception type
- ✅ Summary screen with insights
- ✅ **Adaptive recommendations** (e.g., "You struggled with process flow concepts - review this topic")
- ✅ Retry option with different 20% selection
- ✅ Export session report (JSON/PDF)

**Deliverables:**
- Complete learning session flow with rich analytics
- Summary shows:
  - Overall score
  - Questions answered correctly on first try
  - Misconceptions identified and addressed
  - Average escalation level
  - Time per question
  - Understanding verification rate
- Intelligent insights: "You had difficulty with input-output relationships. We recommend reviewing cause-effect diagrams."
- Export-friendly session data for teachers
- Retry same diagram with new questions

---

## ⚠️ Potential Challenges

### 0. Diagram Validation | 图表验证 ✅ ADDRESSED

**Challenge**: Users might try to start learning mode with incomplete diagrams (placeholders, empty nodes)

**Solution** (Already Designed):
- Pre-validation before entering learning mode
- Real-time button state management (disabled when invalid)
- Clear error messages listing incomplete nodes
- Reuse existing placeholder detection patterns
- Automatic validation on node edits

**Status**: ✅ Fully designed and specified in document

### 1. Node Selection Strategy | 节点选择策略

**Challenge**: How to select "meaningful" 20% of nodes?

**Options:**
- **Random**: Easy, but might select trivial nodes
- **Strategic**: Select key concept nodes (harder to implement)
- **Balanced**: Mix of easy and hard nodes

**Recommendation**: Start with random, add strategic selection in v2.0

### 2. Semantic Answer Validation | 语义答案验证

**Challenge**: LLM might be too strict or too lenient

**Solutions:**
- Tune similarity threshold (0.7-0.9)
- Allow user to flag incorrect validation
- Fallback to exact match if LLM unavailable
- Cache common synonym mappings

### 3. Question Quality | 问题质量

**Challenge**: LLM-generated questions might be:
- Too obvious (giving away answer)
- Too vague (unhelpful)
- Grammatically awkward

**Solutions:**
- Iterative prompt engineering
- Question quality validation (another LLM call?)
- Manual review of common question templates
- User feedback system ("Report bad question")

### 4. Performance | 性能

**Challenge**: LLM calls for each question/hint add latency

**Solutions:**
- Pre-generate all questions at session start (batch call)
- Cache hints for common wrong answers
- Show loading indicators during LLM calls
- Optimize LLM prompts for faster response

### 5. Diagram Complexity | 图表复杂度

**Challenge**: Some diagrams have 50+ nodes → 10 questions is too many

**Solutions:**
- Cap max questions at 10 (even if 20% > 10 nodes)
- Let user choose difficulty: Easy (5 Q), Medium (10 Q), Hard (15 Q)
- Prioritize "important" nodes (central, highly connected)

### 6. Mobile Support | 移动端支持

**Challenge**: Question panel + diagram on small screens

**Solutions:**
- Full-screen question panel on mobile
- Swipe gesture to switch between diagram and questions
- Simplified UI for mobile devices

---

## 📦 Dependencies & Technology Stack

### New Python Packages | 新增Python包

Add to `requirements.txt`:

```txt
# ============================================================================
# LangChain Framework for Intelligent Tutoring System
# ============================================================================
langchain>=0.1.0              # Core LangChain framework
langchain-openai>=0.0.5       # OpenAI LLM integration for LangChain
langchain-community>=0.0.12   # Community tools and integrations

# Note: LangChain will use the existing Qwen LLM client configuration
# through OpenAI-compatible API interface
```

### Existing Dependencies (No Changes)

```txt
# Already in requirements.txt:
flask>=3.0.0
openai>=1.6.1     # For Qwen API calls
requests>=2.31.0
python-dotenv>=1.0.0
```

### Frontend Dependencies (Already Available)

```javascript
// Already loaded in templates:
- d3.js v7 (for rendering)
- Native browser APIs (Fetch, localStorage, DOM)
// No new frontend dependencies needed!
```

### LangChain Configuration | LangChain配置

**Integration with Existing LLM Client:**

```python
# File: agents/learning_agent.py

from langchain_openai import ChatOpenAI
from llm_clients import get_qwen_turbo_client
import settings

# Configure LangChain to use existing Qwen client
def get_langchain_llm():
    """
    Configure LangChain to use Qwen through OpenAI-compatible interface.
    Reuses existing API configuration from settings.py.
    """
    llm = ChatOpenAI(
        model=settings.QWEN_MODEL,  # e.g., "qwen-turbo-latest"
        openai_api_key=settings.QWEN_API_KEY,
        openai_api_base=settings.QWEN_API_URL,
        temperature=0.7,  # Slightly creative for teaching materials
        max_tokens=1500,  # Enough for detailed explanations
        timeout=30,       # 30s timeout for complex analyses
    )
    return llm

# Agent will use this LLM for all tool calls
```

### File Structure Changes | 文件结构变更

```
MindGraph/
├── agents/
│   ├── learning/                          # NEW DIRECTORY
│   │   ├── __init__.py
│   │   ├── learning_agent.py              # Main LangChain agent
│   │   ├── misconception_analyzer.py      # Tool 1: Analyze errors
│   │   ├── material_generator.py          # Tool 2: Generate teaching materials
│   │   ├── question_generator.py          # Tool 3: Multi-angle questions
│   │   ├── knowledge_base.py              # Tool 4: Common misconceptions DB
│   │   └── prompts.py                     # Educational prompt templates
│   └── ... (existing agent files)
│
├── api_routes.py                          # UPDATE: Add 4 new endpoints
│
├── static/js/editor/
│   ├── learning-mode-manager.js           # NEW: Main learning mode controller
│   ├── learning-material-renderer.js      # NEW: Render visual aids/analogies
│   ├── diagram-validator.js               # NEW: Pre-validation logic
│   └── ... (existing editor files)
│
├── prompts/
│   └── learning_mode.py                   # NEW: LLM prompts for learning mode
│
└── requirements.txt                       # UPDATE: Add LangChain packages
```

### Testing Dependencies (Optional)

```txt
# For testing the LangChain agent:
pytest>=7.4.0
pytest-asyncio>=0.21.0
langchain-test>=0.1.0        # LangChain testing utilities
```

### Installation Commands | 安装命令

```bash
# Install new dependencies
pip install -r requirements.txt

# Verify LangChain installation
python -c "import langchain; print(langchain.__version__)"

# Test Qwen connection through LangChain
python -c "from agents.learning.learning_agent import get_langchain_llm; llm = get_langchain_llm(); print('LLM configured successfully')"
```

### Environment Variables (No Changes Needed)

```bash
# .env file - Already has everything we need:
QWEN_API_KEY=sk-...
QWEN_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-turbo-latest
```

**Note**: LangChain will automatically use these existing environment variables through the OpenAI-compatible interface. No new API keys or configurations needed!

### Dependency Rationale | 依赖说明

**Why LangChain?**
- **Agent Architecture**: Built-in support for tool-calling agents
- **Memory Management**: ConversationBufferMemory for tracking student progress
- **Chain Composition**: Easy to build multi-step pedagogical workflows
- **Debugging**: LangSmith integration for monitoring agent decisions (optional)
- **Flexibility**: Easy to swap LLM providers or add new tools

**Why Not Custom Implementation?**
- LangChain provides battle-tested agent frameworks
- Reduces development time by ~70%
- Active community and regular updates
- Better error handling and retry logic
- Built-in observability tools

---

## 🔮 Future Enhancements

### Version 2.0 Features

1. **Adjustable Difficulty**
   - User selects: 10%, 20%, 30%, 50% knockout
   - Adaptive difficulty based on performance

2. **Multiplayer Mode**
   - Two users compete on same diagram
   - Real-time score comparison
   - Turn-based or simultaneous

3. **Spaced Repetition**
   - Track user's long-term retention
   - Show diagrams again after 1 day, 1 week, 1 month
   - Focus on nodes user struggled with

4. **Custom Question Templates**
   - Teachers create custom question styles
   - Question bank for common topics
   - Community-shared questions

5. **Voice Input**
   - User speaks answer instead of typing
   - Especially useful for mobile

6. **Gamification**
   - Achievements/badges ("Perfect Score!", "No Hints Used")
   - Leaderboards (optional, privacy-conscious)
   - Streak counter ("7 days in a row!")

7. **Export Learning Report**
   - PDF summary of session performance
   - Identify weak areas
   - Recommendations for improvement

8. **AI Tutor Mode**
   - If user struggles, AI explains concept
   - Similar to "MindMate AI Assistant"
   - Integrated learning resources

---

## 📐 Technical Specifications

### Performance Targets | 性能目标

- **Question Generation**: < 3 seconds for 5 questions
- **Answer Validation**: < 500ms per answer
- **Hint Generation**: < 1 second per hint
- **UI Responsiveness**: 60fps animations

### Browser Support | 浏览器支持

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Android)

### Accessibility | 可访问性

- Keyboard navigation support
- Screen reader compatible
- High contrast mode support
- Font size adjustable

### Data Privacy | 数据隐私

- Learning sessions stored client-side (localStorage)
- Optional server-side persistence (with user consent)
- No personally identifiable information (PII) sent to LLM
- User can clear session history

---

## 🎓 Educational Pedagogy

### Learning Science Principles Applied | 应用的学习科学原理

This Learning Mode applies **evidence-based learning science**:

1. **Active Recall** (Retrieval Practice)
   - **Research**: Karpicke & Roediger (2008) - retrieval practice produces better retention than re-reading
   - **Implementation**: Students must actively retrieve node content from memory
   - **Benefit**: Strengthens neural pathways, not just recognition

2. **Educational Scaffolding** (Vygotsky's ZPD)
   - **Research**: Vygotsky's Zone of Proximal Development - learners need guided support
   - **Implementation**: 3-level progressive hints that guide without giving away
   - **Benefit**: Students learn HOW to think, not just WHAT to remember

3. **Contextual Learning** (Constructivism)
   - **Research**: Ausubel's Meaningful Learning Theory - new info connects to existing knowledge
   - **Implementation**: Hints reference visible nodes and relationships
   - **Benefit**: Information embedded in meaningful context, not isolated facts

4. **Error Analysis** (Growth Mindset)
   - **Research**: Dweck's Growth Mindset - mistakes are learning opportunities
   - **Implementation**: Hints analyze WHY wrong answer makes sense, then correct the mental model
   - **Benefit**: Students learn from errors instead of feeling defeated

5. **Immediate Feedback** (Behaviorist Learning)
   - **Research**: Skinner's Reinforcement Theory - immediate feedback reinforces learning
   - **Implementation**: Real-time validation and encouraging messages
   - **Benefit**: Rapid learning cycles, positive reinforcement

6. **Metacognition** (Self-Regulated Learning)
   - **Research**: Flavell's Metacognitive Theory - thinking about thinking improves learning
   - **Implementation**: Hints explain the REASONING process, not just the answer
   - **Benefit**: Students develop problem-solving strategies

7. **Elaborative Interrogation**
   - **Research**: Pressley et al. (1987) - asking "why" questions improves retention
   - **Implementation**: Hints ask "Why might this be the answer?" and "How does this connect?"
   - **Benefit**: Deeper processing leads to better memory

8. **Distributed Practice** (Future Feature)
   - **Research**: Cepeda et al. (2006) - spacing learning sessions improves retention
   - **Implementation**: v2.0 will include spaced repetition for long-term memory
   - **Benefit**: Combat forgetting curve

### What Makes This Different from Other Learning Tools | 与其他学习工具的区别

| Aspect | Traditional Flashcards | Typical Quiz Apps | **MindGraph Learning Mode** |
|--------|------------------------|-------------------|----------------------------|
| **Context** | Isolated facts | Isolated questions | Embedded in visual diagram structure |
| **Hints** | None or generic | "Try again" | Progressive, context-rich, educational |
| **Error Handling** | Mark wrong, move on | Red X, score penalty | Analyze error, teach correct thinking |
| **Relationships** | Not shown | Not emphasized | Central to every hint (siblings, parents, etc.) |
| **Learning Style** | Rote memorization | Testing knowledge | Teaching understanding |
| **Feedback** | Correct/Wrong | % Score | Educational explanation + encouragement |
| **Pedagogy** | Behaviorist | Summative assessment | Formative learning + scaffolding |

### Educational Value Proposition | 教育价值主张

**"From Memorization to Understanding"**

Traditional learning tools focus on **knowing the answer**.  
MindGraph Learning Mode focuses on **understanding the relationships**.

Examples:
- **Traditional**: "What is photosynthesis?" → "Process where plants make food"
- **Learning Mode**: "What energy source drives photosynthesis, working with water and CO₂?" → Teaches the **system**, not just the term

### Target Users | 目标用户

- **K-12 Students**: Learn curriculum topics with context (历史, 科学, 数学)
- **Teachers**: Create interactive practice with built-in scaffolding
- **Professional Learners**: Master business concepts, technical topics with relationships
- **Language Learners**: Vocabulary in meaningful semantic networks
- **Visual Learners**: Benefit from diagram-based spatial memory
- **Anyone preparing for exams**: Active recall beats passive re-reading

---

## 📝 Success Metrics | 成功指标

### User Engagement | 用户参与度

- **Adoption Rate**: % of users who try Learning Mode
- **Completion Rate**: % of sessions completed (not abandoned)
- **Repeat Usage**: Users who use Learning Mode 2+ times

### Learning Effectiveness | 学习效果

- **Score Improvement**: Performance on repeated sessions
- **Hint Dependency**: Do users need fewer hints over time?
- **Time Efficiency**: Faster completion with practice

### Technical Performance | 技术性能

- **LLM Call Success Rate**: > 99%
- **Average Response Time**: < 2 seconds
- **Error Rate**: < 1%

---

## 🌟 Unique Value Proposition

**"From Static Diagrams to Interactive Learning Experiences"**

MindGraph's Learning Mode transforms knowledge visualization into active learning:
- **Not just viewing** → **Active recall**
- **Not just creating** → **Testing understanding**
- **Not just memorizing** → **Understanding relationships**
- **Not just studying** → **Getting AI-powered help**

This positions MindGraph as an **educational platform**, not just a diagram tool.

---

## 📚 Comparison with Existing Tools

| Feature | Quizlet | Anki | Kahoot | **MindGraph Learning Mode** |
|---------|---------|------|--------|----------------------------|
| Visual Learning | ❌ | ❌ | ✅ | ✅ |
| Relationship Context | ❌ | ❌ | ❌ | ✅ |
| AI-Generated Questions | ❌ | ❌ | ❌ | ✅ |
| Progressive Hints | ❌ | ❌ | ❌ | ✅ |
| Diagram Integration | ❌ | ❌ | ❌ | ✅ |
| Self-Paced | ✅ | ✅ | ❌ | ✅ |
| Spaced Repetition | ✅ | ✅ | ❌ | 🔄 (Future) |

---

## 🏁 Next Steps | 下一步

### Before Implementation | 实施前

1. **User Feedback**: Show this design to potential users (students, teachers)
2. **LLM Testing**: Test question generation quality with real diagrams
3. **UI Mockups**: Create detailed mockups in Figma/similar tool
4. **Cost Analysis**: Estimate LLM API costs (questions, validation, hints)

### Implementation Kickoff | 开始实施

1. **Create Git Branch**: `feature/learning-mode`
2. **Set Up Project Structure**: Create files and folders
3. **Start with Phase 1**: Core infrastructure (button + knockout)
4. **Iterative Development**: Weekly demos and feedback

---

## ✅ Approval Checklist | 审批清单

- [ ] Design reviewed and approved
- [ ] UI/UX mockups created
- [ ] LLM prompts tested manually
- [ ] Cost analysis completed
- [ ] Implementation plan agreed upon
- [ ] Git branch created
- [ ] **READY TO START CODING** 🚀

---

**Document Status**: ✅ Complete - Awaiting Approval  
**Author**: MindSpring Team  
**Last Updated**: 2025-10-05

---

*This document serves as the complete design specification for Learning Mode. No coding should begin until this design is reviewed and approved.*

