# Learning Mode Design Document | 学习模式设计文档

**Feature Name**: Interactive Learning Mode | 交互式学习模式  
**Version**: 1.0  
**Date**: 2025-10-05  
**Status**: Design Phase 🎨

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

### Step 1: Activation | 激活学习模式

```
User creates/opens diagram → Clicks "Learning" button (学习)
                           ↓
System shuffles diagram nodes randomly → Selects 20% nodes to knock out
                           ↓
Generates AI questions for knocked-out nodes → Displays question panel
                           ↓
User sees diagram with blank nodes + question panel
```

### Step 2: Question & Answer Cycle | 问答循环

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

### Backend API Endpoints | 后端API端点

```python
# New endpoints needed:

POST /api/learning/generate_questions
{
    "diagram_type": "bubble_map",
    "spec": {...},
    "knocked_out_nodes": ["node_1", "node_3", "node_7"],
    "language": "zh"
}
→ Returns: List of AI-generated questions with context

POST /api/learning/validate_answer
{
    "question_id": "q1",
    "user_answer": "阳光",
    "correct_answer": "太阳光",
    "node_context": {...},
    "language": "zh"
}
→ Returns: {is_correct: true/false, similarity_score: 0.95}

POST /api/learning/generate_hint
{
    "question_id": "q1",
    "user_answer": "氧气",
    "correct_answer": "阳光",
    "attempt_number": 2,
    "node_context": {...},
    "language": "zh"
}
→ Returns: Progressive hint based on attempt number
```

---

## 🤖 LLM Integration

### 1. Question Generation | 问题生成

**LLM Prompt Template:**

```python
QUESTION_GENERATION_PROMPT = """
You are an educational assistant creating learning questions for a diagram.

Diagram Type: {diagram_type}
Node to Test: {node_text}
Node Relationships:
- Parent: {parent_node}
- Siblings: {sibling_nodes}
- Children: {child_nodes}
- Connected to: {connected_nodes}

Context: This node is part of a {diagram_type} about "{diagram_topic}".

Task: Generate 1 question that helps the user recall "{node_text}" by:
1. Describing its relationship to other nodes
2. Giving contextual clues (but not the answer!)
3. Making it educational and clear

Question format:
{
    "question": "Fill in the blank node: ...",
    "initial_hint": "💡 Hint: ...",
    "difficulty": "easy/medium/hard"
}

Language: {language}
Generate the question in {language} only.
"""
```

**Example Output (Chinese):**
```json
{
    "question": "这个节点与"光合作用"相连，是这个过程的主要能量来源。它是什么？",
    "initial_hint": "💡 提示：它来自天空，是白天最亮的东西",
    "difficulty": "easy",
    "node_id": "attribute_2",
    "relationships": {
        "parent": "光合作用",
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

**Hint Strategy: 3 Levels of Assistance**

```python
HINT_GENERATION_PROMPT = """
User is trying to recall: {correct_answer}
User's wrong answer: {user_answer}
Attempt number: {attempt_number} of 3

Generate a hint at level {attempt_number}:
- Level 1: Subtle hint about relationships ("It's connected to X and Y")
- Level 2: Clearer hint about characteristics ("It's the main source of energy")
- Level 3: Very direct hint ("It starts with '阳' and ends with '光'")

Language: {language}
Be encouraging and educational, not condescending.

Format: {{"hint": "💡 ...", "confidence_boost": "You're getting closer!"}}
"""
```

**Example Progression (Chinese):**

```
Attempt 1: User types "水" (wrong)
→ Hint 1: "💡 这个东西不是液体。想想植物在白天需要什么来进行光合作用？"

Attempt 2: User types "空气" (wrong)
→ Hint 2: "💡 很接近了！但不是空气。它来自天空，是我们能看到的最亮的东西。"

Attempt 3: User types "月亮" (wrong)
→ Hint 3: "💡 几乎对了！但是是白天而不是晚上。它是'太阳'发出的..."

After 3 attempts:
→ Show Answer: "阳光" (with explanation)
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
- ✅ Add "Learning" button to toolbar
- ✅ Implement 20% random node selection
- ✅ Basic node knockout rendering (hide text)
- ✅ Simple input field injection

**Deliverables:**
- User can click "Learning" button
- 20% of nodes become blank with input fields
- No questions yet, just visual knockout

### Phase 2: Question Generation (Week 2-3) | 问题生成

**Goals:**
- ✅ Backend API: `/api/learning/generate_questions`
- ✅ LLM prompt template for question generation
- ✅ Extract node relationships from diagram spec
- ✅ Generate questions based on diagram structure
- ✅ Display questions in simple modal

**Deliverables:**
- LLM generates questions for knocked-out nodes
- Questions include context about relationships
- Questions displayed to user

### Phase 3: Answer Validation (Week 3-4) | 答案验证

**Goals:**
- ✅ Backend API: `/api/learning/validate_answer`
- ✅ Exact match validation
- ✅ Semantic match validation (LLM-based)
- ✅ Display correct/incorrect feedback
- ✅ Reveal node text when correct

**Deliverables:**
- User types answer → System validates
- Correct answers reveal node text
- Incorrect answers show error message

### Phase 4: Hint System (Week 4-5) | 提示系统

**Goals:**
- ✅ Backend API: `/api/learning/generate_hint`
- ✅ Progressive hint generation (3 levels)
- ✅ Attempt counter (max 3 attempts)
- ✅ "Show Answer" button after 3 attempts
- ✅ Hint display in question panel

**Deliverables:**
- Progressive hints based on attempt number
- Encouraging feedback messages
- User can see answer after 3 attempts

### Phase 5: Session Management (Week 5-6) | 会话管理

**Goals:**
- ✅ Session state tracking
- ✅ Score calculation
- ✅ Summary screen after completion
- ✅ "Review Mistakes" feature
- ✅ Session persistence (optional)

**Deliverables:**
- Complete learning session with scoring
- Summary shows performance metrics
- User can review incorrect answers

### Phase 6: Polish & Testing (Week 6-7) | 优化和测试

**Goals:**
- ✅ UI/UX refinements
- ✅ Animations and transitions
- ✅ Bilingual support (EN/ZH)
- ✅ Edge case handling
- ✅ Comprehensive testing

**Deliverables:**
- Production-ready feature
- Full bilingual support
- Comprehensive test coverage

---

## ⚠️ Potential Challenges

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

1. **Active Recall**: Forcing retrieval strengthens memory
2. **Spaced Repetition**: Future feature for long-term retention
3. **Contextual Learning**: Questions include relationships
4. **Progressive Disclosure**: Hints reveal information gradually
5. **Immediate Feedback**: Real-time validation and correction
6. **Gamification**: Scoring and progress tracking increase motivation

### Target Users | 目标用户

- **K-12 Students**: Learn curriculum topics (历史, 科学, 数学)
- **Teachers**: Create interactive practice materials
- **Professional Learners**: Memorize business concepts, technical topics
- **Language Learners**: Vocabulary and concept retention

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

