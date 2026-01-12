---
name: DebateVerse Implementation
overview: Create DebateVerse (论境), a US-style debate system under AskOnce where 4 AI debaters (2 per side) and 1 AI judge engage in structured debates. Users can participate as debaters, judges, or viewers. The system uses Qwen, Doubao, DeepSeek, and Kimi in turns with context-aware prompts for realistic conversations.
todos: []
---

# DebateVerse (论境) Implementation Plan

## Overview

DebateVerse is a US Parliamentary-style debate system where:

- **4 AI Debaters**: 2 per side (Affirmative and Negative), each with distinct roles (1st debater = establishes framework, 2nd debater = attacks/rebuts)
- **1 AI Judge**: Controls flow, evaluates arguments, and provides final judgment
- **Users**: Can join as debaters, judges, or viewers
- **LLM Rotation**: Qwen, Doubao, DeepSeek, Kimi used in turns for diversity
- **Format**: US Parliamentary style with structured rounds

## Architecture

```
User → DebateVersePage → DebateVerseStore → DebateVerseService → LLMService
                                                      ↓
                                              Database Models
                                                      ↓
                                              Dashscope TTS API
```

## Agent Architecture Decision

### Option 1: 4 Separate Agents (One per Debater)

**Pros**:

- Each debater maintains separate memory/state
- Better isolation between roles
- Can have different personalities/styles per agent

**Cons**:

- More complex to manage (4 agent instances per debate session)
- Higher memory overhead
- More code to maintain
- Overkill - debaters don't need persistent state between turns

### Option 2: 1 Shared Agent + Role-Specific Context (Recommended)

**Pros**:

- Simpler architecture (1 agent instance per debate session)
- Lower memory overhead
- Easier to manage and debug
- Role differentiation through prompts/context, not agent instances
- Follows existing patterns (AskOnce uses 1 service, different prompts)

**Cons**:

- Need to ensure context is properly isolated per role
- Prompt building becomes more critical

### Recommendation: **1 Shared Agent (Enhanced Prompt Builder)**

**Architecture**:

```
DebateSession
  └── 1 Argument Analyzer Agent (LangChain) - Shared for analysis
  └── 1 Context Builder Service - Builds role-specific prompts
  └── LLMService - Calls with role-specific prompts/context
```

**What the Agent Actually Does**:

- **Enhanced Prompt Builder**: Yes, exactly! It's a smart prompt builder that:

                                1. Analyzes debate history (extracts key arguments, identifies flaws)
                                2. Structures information (who said what, when, relationships)
                                3. Builds enriched prompts with attack strategies
                                4. Optimizes context (summarizes old, keeps recent full)

**Key Insight**:

- The "agent" is really just an enhanced prompt builder
- Each debater doesn't need its own agent instance
- Role differentiation comes from prompts, not agent instances
- Similar to AskOnce: 1 service, 3 different models, different prompts

## Performance Challenge: 1-Minute Limit + Information Overload

### Problem

- **1-minute time limit** per side per round
- **Growing debate history** (opening → rebuttal → cross-exam → closing)
- **Agent analysis time** must be fast (< 5-10 seconds ideally)
- **Token limits** - can't send entire debate history to LLM

### Solution: Multi-Layer Optimization Strategy

#### Layer 1: Incremental Analysis (Don't Re-analyze Everything)

```python
# Only analyze NEW messages since last turn
last_analysis_timestamp = get_last_analysis_time(session_id)
new_messages = get_messages_since(session_id, last_analysis_timestamp)

# Incremental update
if new_messages:
    analysis = agent.incremental_analyze(
        previous_analysis=cached_analysis,
        new_messages=new_messages
    )
else:
    analysis = cached_analysis  # Reuse previous
```

#### Layer 2: Structured Extraction (Not Full Text Analysis)

```python
# Extract only key information, not full text
@tool
def extract_key_points(messages: List[Dict]) -> Dict:
    """Extract only essential information:
 - Argument summaries (not full text)
 - Flaw types and locations
 - Unaddressed points
 - Speaker relationships
    """
    return {
        "arguments": [
            {"id": "...", "speaker": "...", "summary": "..."}  # Summary, not full text
        ],
        "flaws": [...],
        "unaddressed": [...]
    }
```

#### Layer 3: Stage-Based Summarization

```python
# Summarize old stages, keep current stage full
def build_context(session_id, current_stage):
    messages = get_all_messages(session_id)
    
    # Full context for current stage
    current_stage_messages = [m for m in messages if m.stage == current_stage]
    
    # Summarized context for previous stages
    previous_stages = summarize_stages(
        messages=[m for m in messages if m.stage != current_stage],
        max_tokens=500  # Limit old context
    )
    
    return {
        "current_stage": current_stage_messages,  # Full
        "previous_summary": previous_stages  # Summarized
    }
```

#### Layer 4: Cached Analysis Results

```python
# Cache analysis results per stage
analysis_cache = {
    "opening": {...},  # Cached after opening stage
    "rebuttal": {...},  # Cached after rebuttal stage
    ...
}

# Only re-analyze if new messages added
if stage_has_new_messages(session_id, stage):
    analysis = agent.analyze(...)
    cache[stage] = analysis
else:
    analysis = cache[stage]  # Use cached
```

#### Layer 5: Parallel Processing

```python
# Run analysis and prompt building in parallel
async def prepare_debater_turn(participant_id, stage):
    # Parallel: analysis + context building
    analysis_task = agent.analyze_async(...)
    context_task = build_context_async(...)
    
    analysis, context = await asyncio.gather(analysis_task, context_task)
    
    # Build prompt (fast, no LLM call)
    prompt = build_prompt(analysis, context)
    
    return prompt
```

#### Layer 6: Token Budget Management

```python
# Allocate token budget intelligently
TOKEN_BUDGET = 8000  # Example

def build_optimized_context(session_id, current_stage):
    budget = {
        "system_prompt": 500,
        "current_stage": 3000,  # Full context
        "previous_summary": 2000,  # Summarized
        "flaw_analysis": 1500,  # Key flaws only
        "attack_strategy": 1000  # Concise strategy
    }
    
    # Build within budget
    context = {}
    for section, max_tokens in budget.items():
        context[section] = build_section(section, max_tokens)
    
    return context
```

### Performance Targets

**Agent Analysis Time**: < 5 seconds (for incremental analysis)

**Prompt Building Time**: < 1 second (mostly string operations)

**Total Prep Time**: < 6 seconds (leaves 54 seconds for LLM response)

**Token Usage**:

- System prompt: ~500 tokens
- Current stage context: ~3000 tokens (full)
- Previous stages summary: ~2000 tokens (summarized)
- Flaw analysis: ~1500 tokens (structured)
- Attack strategy: ~1000 tokens
- **Total**: ~8000 tokens (well within limits)

### Implementation Strategy

**Phase 1 (Prototype)**: Simple approach

- Full context (like AskOnce)
- Basic analysis
- Accept slower performance

**Phase 2 (Production)**: Optimized approach

- Incremental analysis
- Stage summarization
- Cached results
- Token budget management

**Implementation**:

```python
# 1 Shared agent for analysis
argument_analyzer = ArgumentAnalyzerAgent()

# For each debater turn:
analysis = argument_analyzer.analyze(debate_history, my_role)
prompt = build_role_specific_prompt(role, side, stage, analysis)
response = llm_service.chat_stream(messages=prompt, model=assigned_model)
```

**Memory Management**:

- No persistent state needed between turns (all in database)
- Each turn builds fresh context from database
- Agent is stateless - just analyzes and returns structured data

## UX Design: Visual Layout & Prototype

### Visual Layout Design

**Three-Column Stage Layout**:

```
┌─────────────────────────────────────────────────────────┐
│                    Debate Topic Header                    │
├──────────────┬───────────────────┬───────────────────────┤
│              │                   │                       │
│  AFFIRMATIVE │      JUDGE        │     NEGATIVE         │
│     SIDE     │    (Center)       │       SIDE           │
│              │                   │                       │
│  [Figure 1]  │   [Judge Figure]  │    [Figure 3]        │
│  "Qwen"      │   "DeepSeek"      │    "Doubao"          │
│              │                   │                       │
│  [Figure 2]  │                   │    [Figure 4]        │
│  "DeepSeek"  │                   │    "Kimi"            │
│              │                   │                       │
│  Messages    │   Judge Comments  │    Messages          │
│  Stream      │   & Controls      │    Stream            │
│              │                   │                       │
└──────────────┴───────────────────┴───────────────────────┘
```

### Design Principles

1. **Lightweight & Fast**

                                                - SVG-based character figures (no heavy images)
                                                - CSS animations (no JavaScript animation libraries)
                                                - Lazy-load audio (only when speaking)
                                                - Minimal DOM updates during streaming

2. **Fun & Engaging**

                                                - Cute, simple character avatars (SVG circles with expressions)
                                                - Nametags on chest showing model name (Qwen, DeepSeek, etc.)
                                                - Subtle animations when speaking (pulse, bounce)
                                                - Color-coded sides (green for affirmative, red for negative, gray for judge)

3. **Clear Visual Hierarchy**

                                                - Judge prominently in center (larger, elevated position)
                                                - Side-by-side comparison of arguments
                                                - Speech bubbles flowing from figures
                                                - Current speaker highlighted

### Character Design (SVG-based)

**Lightweight SVG Avatars**:

- Simple circular faces with expressions
- Different colors per model (Qwen=blue, DeepSeek=purple, Doubao=pink, Kimi=orange)
- Nametag badge on chest area
- Small size (~60px) to keep lightweight
- CSS-based animations (scale, pulse) when speaking

**Example SVG Structure**:

```svg
<svg class="debater-avatar" data-model="qwen" data-side="affirmative">
  <circle class="avatar-face" fill="#3b82f6"/>
  <circle class="avatar-eye" cx="..." cy="..."/>
  <text class="nametag" x="..." y="...">Qwen</text>
</svg>
```

### Layout Implementation

**CSS Grid Layout** (Lightweight):

```css
.debate-stage {
  display: grid;
  grid-template-columns: 1fr 1.2fr 1fr; /* Left | Center | Right */
  gap: 1rem;
  height: 100vh;
}

.affirmative-side, .negative-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.judge-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: #f3f4f6; /* Gray background per convention */
}
```

### TTS Integration (Dashscope)

**Backend TTS Service**:

- Use Dashscope TTS API (Sambert models)
- Generate audio for each debater message
- Stream audio chunks to frontend
- Cache audio URLs to avoid regeneration

**Frontend Audio Playback**:

- Play audio when debater speaks
- Visual indicator (pulsing avatar) during playback
- Queue audio for sequential playback
- Lightweight Web Audio API (no heavy libraries)

**TTS Flow**:

```
Debater Message → Backend → Dashscope TTS API → Audio URL → Frontend → Play
```

### Message Display

**Speech Bubbles**:

- Appear next to speaking figure
- Stream text content in real-time
- Show thinking content (collapsible)
- Auto-scroll to latest message
- Lightweight CSS-only styling

**Message Flow Animation**:

- Fade-in when message appears
- Slide from figure toward center
- Subtle shadow for depth
- No heavy animation libraries

### Interactive Elements

**User Controls** (if user is debater/judge):

- Input box at bottom (only visible when it's user's turn)
- Judge controls in center (advance round, request judgment)
- Mute/unmute TTS toggle
- Speed control for audio playback

**Viewer Mode**:

- No input controls
- Just watch and listen
- Can toggle TTS on/off
- Can scroll through history

### Responsive Design

**Mobile/Tablet**:

- Stack layout (judge on top, sides below)
- Smaller avatars
- Touch-friendly controls
- Optimized audio streaming

**Desktop**:

- Full three-column layout
- Larger avatars and messages
- Keyboard shortcuts for controls

### Performance Optimizations

1. **Lazy Loading**:

                                                - Load avatars on demand
                                                - Load audio only when needed
                                                - Virtual scrolling for long debates

2. **Efficient Updates**:

                                                - Only update speaking figure
                                                - Batch DOM updates
                                                - Use CSS transforms for animations

3. **Audio Optimization**:

                                                - Compress audio (MP3, ~32kbps)
                                                - Stream audio chunks
                                                - Preload next speaker's audio

4. **Asset Size**:

                                                - SVG avatars (~2KB each)
                                                - No image sprites needed
                                                - Inline critical CSS
                                                - Minimal JavaScript bundle

## Production-Ready Architecture

Building from the ground up using MindGraph's proven, production-tested patterns. No external dependencies on weak implementations - we're creating a robust, scalable system.

### Foundation: MindGraph's Proven Patterns

1. **AskOnce Pattern** (`routers/askonce.py`, `frontend/src/stores/askonce.ts`)

                                                - **Production-tested**: SSE streaming, multi-model coordination, conversation state management
                                                - **Adaptation**: Sequential turn-based flow instead of parallel responses
                                                - **Why**: Battle-tested streaming infrastructure, robust error handling, token tracking

2. **Node Palette Generator** (`agents/node_palette/base_palette_generator.py`)

                                                - **Production-tested**: Round-robin LLM assignment, concurrent streaming with interleaving
                                                - **Adaptation**: Rotate models across debate turns with proper context management
                                                - **Why**: Proven model rotation strategy, handles rate limiting, load balancing

3. **MindMate Conversation Flow** (`frontend/src/components/panels/MindmatePanel.vue`)

                                                - **Production-tested**: Message rendering, streaming UI, conversation history management
                                                - **Adaptation**: Add role-based message styling (debater vs judge vs viewer)
                                                - **Why**: Clean UI patterns, proper state management, professional UX

4. **Voice Agent State Management** (`services/voice_agent.py`)

                                                - **Production-tested**: State machine patterns for managing conversation flow
                                                - **Adaptation**: Use similar state management for debate rounds and speaker order
                                                - **Why**: Robust state transitions, error recovery, session management

5. **Database Models Pattern** (`models/diagrams.py`, `models/pinned_conversations.py`)

                                                - **Production-tested**: SQLAlchemy models with proper relationships and indexing
                                                - **Adaptation**: Debate-specific models with proper foreign keys and constraints
                                                - **Why**: Scalable data structure, efficient queries, data integrity

6. **LLM Service Architecture** (`services/llm_service.py`)

                                                - **Production-tested**: Centralized LLM calls with rate limiting, load balancing, error handling
                                                - **Adaptation**: Use existing infrastructure for all debate LLM calls
                                                - **Why**: Token tracking, quota management, provider abstraction, comprehensive error handling

## Prototype Phase (First)

Before full implementation, create a lightweight prototype to validate UX design:

### Prototype Goals

1. **Visual Layout Validation**

                                                - Three-column stage layout (affirmative | judge | negative)
                                                - SVG character avatars with nametags
                                                - Speech bubble flow from avatars
                                                - Judge area prominence

2. **Interaction Flow**

                                                - Turn-based speaking animation
                                                - TTS audio playback integration
                                                - Message streaming visualization
                                                - User input handling

3. **Performance Testing**

                                                - Lightweight asset loading
                                                - Smooth animations (CSS-only)
                                                - Audio streaming efficiency
                                                - Mobile responsiveness

### Prototype Scope

**Minimal Backend**:

- Mock debate data (hardcoded messages)
- Simple TTS endpoint (Dashscope integration)
- No database (use in-memory state)

**Frontend Prototype**:

- Static layout with SVG avatars
- Mock message streaming
- TTS audio playback
- Basic animations

**Prototype Deliverables**:

- Visual mockup/wireframe
- Interactive prototype (Vue components)
- TTS integration proof-of-concept
- Performance benchmarks

### Prototype Timeline

1. **Day 1**: Visual layout & SVG avatars
2. **Day 2**: Message flow & animations
3. **Day 3**: TTS integration & audio playback
4. **Day 4**: Polish & performance optimization

After prototype validation, proceed with full implementation.

## Implementation Steps

### 1. Backend: Database Models

**File**: `models/debateverse.py`

Create models for:

- `DebateSession`: Stores debate metadata (topic, format, status, created_at, etc.)
- `DebateParticipant`: Links users/AI to sessions with role (affirmative_1, affirmative_2, negative_1, negative_2, judge, viewer)
- `DebateMessage`: Stores all messages in debate (speaker, content, round, timestamp, thinking content)
- `DebateJudgment`: Stores judge's final evaluation and scores

**Key Fields**:

- `DebateSession`: id, topic, format, status (setup/coin_toss/opening/rebuttal/cross_exam/closing/judgment/completed), current_stage, created_by, created_at
- `DebateParticipant`: session_id, user_id (null for AI), role (affirmative_1/affirmative_2/negative_1/negative_2/judge/viewer), model_id (for AI), name, side (affirmative/negative/null for judge)
- `DebateMessage`: session_id, participant_id, content, thinking, stage, round_number, message_type (coin_toss/opening/rebuttal/cross_question/cross_answer/closing/judgment), audio_url, parent_message_id (for cross-exam Q&A pairs)
- `DebateJudgment`: session_id, judge_participant_id, winner_side, scores (JSON), best_debater_id, detailed_analysis, created_at

### 2. Backend: Prompt Builder & Context Management

**File**: `prompts/debateverse.py`

Create centralized prompts following project convention:

- `get_debater_system_prompt(role, side, stage)`: System prompt defining debater's role and style
- `get_judge_system_prompt(stage)`: System prompt for judge's role
- `build_debater_messages(session_id, participant_id, stage)`: Build full message array with context
- `build_judge_messages(session_id, stage)`: Build full message array for judge
- `build_cross_exam_messages(session_id, questioner_id, respondent_id)`: Build Q&A context for cross-examination

**File**: `services/debateverse_context_builder.py` (new)

Context building service for debate messages:

- `build_full_context(session_id, participant_id, stage)`: Build complete context from all previous messages
- `build_stage_context(session_id, stage)`: Build context for specific stage only
- `summarize_previous_stages(session_id, current_stage)`: Summarize old stages to save tokens
- `format_debate_history(messages)`: Format messages for LLM consumption
- `analyze_opponent_arguments(session_id, my_side, stage, incremental=True)`: Use LangChain agent to analyze opponent's arguments (incremental if possible)
- `identify_attack_points(session_id, participant_id, use_cache=True)`: Identify logical flaws and weak points to attack (use cached if available)
- `build_enriched_prompt(session_id, participant_id, stage, token_budget=8000)`: Build prompt with flaw analysis and attack strategies (within token budget)
- `summarize_previous_stages(session_id, current_stage, max_tokens=2000)`: Summarize old stages to save tokens
- `get_incremental_analysis(session_id, last_timestamp)`: Get only new analysis since last turn (performance optimization)

**Context Strategy**:

**Option A: Full Context (Recommended for Prototype)**

- Each LLM call includes ALL previous debate messages
- Simple implementation using `messages` parameter in `llm_service.chat_stream()`
- Similar to AskOnce pattern (`getMessagesForModel()`)
- Pros: Simple, ensures full context, no information loss
- Cons: Token usage grows with debate length

**Option B: Summarized Context (For Production)**

- Recent messages (current stage) included in full
- Previous stages summarized to save tokens
- Pros: Token efficient, scalable for long debates
- Cons: Some context loss, more complex

**Implementation Pattern** (Enhanced with LangChain Analysis):

```python
# Build enriched messages array with argument analysis
async def build_debater_messages(session_id, participant_id, stage):
    messages = []
    
    # Get all previous messages from database
    debate_messages = get_debate_messages(session_id)
    participant = get_participant(participant_id)
    
    # STEP 1: Use LangChain agent to analyze debate history
    from agents.debateverse.argument_analyzer import argument_analyzer_agent
    
    analysis = await argument_analyzer_agent.ainvoke({
        "debate_messages": debate_messages,
        "my_side": participant.side,
        "my_role": participant.role,
        "current_stage": stage
    })
    
    # Extract structured data
    opponent_flaws = analysis["logical_flaws"]
    unaddressed_points = analysis["unaddressed_points"]
    argument_relationships = analysis["argument_chains"]
    
    # STEP 2: Build enriched system prompt with flaw analysis
    system_prompt = get_debater_system_prompt(
        role=participant.role,
        side=participant.side,
        stage=stage,
        opponent_flaws=opponent_flaws,  # Highlight weaknesses to attack
        unaddressed_points=unaddressed_points,  # Points to address
        argument_relationships=argument_relationships  # Context of argument flow
    )
    messages.append({"role": "system", "content": system_prompt})
    
    # STEP 3: Format debate history with clear speaker identification
    for msg in debate_messages:
        speaker_info = f"[{msg.participant_name} ({msg.side}, {msg.role})]"
        timestamp_info = f"[{msg.stage}, Round {msg.round_number}]"
        
        if msg.participant_id == participant_id:
            # My previous messages
            messages.append({
                "role": "assistant",
                "content": f"{speaker_info} {timestamp_info}\n{msg.content}"
            })
        else:
            # Opponent's messages - highlight flaws if detected
            flaw_note = ""
            if msg.id in [f["argument_id"] for f in opponent_flaws]:
                flaw = next(f for f in opponent_flaws if f["argument_id"] == msg.id)
                flaw_note = f"\n[WEAKNESS: {flaw['flaw_type']} - {flaw['description']}]"
            
            messages.append({
                "role": "user",
                "content": f"{speaker_info} {timestamp_info}\n{msg.content}{flaw_note}"
            })
    
    # STEP 4: Add current turn instruction with attack strategy
    attack_strategy = build_attack_strategy(opponent_flaws, unaddressed_points)
    messages.append({
        "role": "user",
        "content": f"{get_stage_instruction(stage)}\n\n[ATTACK STRATEGY]\n{attack_strategy}"
    })
    
    return messages
```

**LangChain Agents for Structured Argument Analysis**:

**Why LangChain Agents Are Needed**:

- **Speaker Identification**: Parse "who said what" from debate history
- **Temporal Context**: Understand "when" arguments were made (sequence matters)
- **Logical Flaw Detection**: Identify contradictions, weak points, logical gaps
- **Argument Relationship Mapping**: Connect arguments to their rebuttals
- **Context-Aware Prompt Building**: Build prompts that highlight opponent's weaknesses

**LangChain Agent Structure**:

```python
# Argument Analysis Agent
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate

@tool
def extract_arguments(debate_messages: List[Dict]) -> Dict:
    """Extract structured arguments from debate messages.
    
    Returns:
        {
            "affirmative": [
                {"speaker": "Affirmative 1", "argument": "...", "round": "opening", "timestamp": ...},
                ...
            ],
            "negative": [...],
            "rebuttals": {
                "affirmative_to_negative": [...],
                "negative_to_affirmative": [...]
            }
        }
    """
    pass

@tool
def identify_logical_flaws(opponent_arguments: List[Dict], my_arguments: List[Dict]) -> List[Dict]:
    """Identify logical flaws, contradictions, and weak points in opponent's arguments.
    
    Returns:
        [
            {
                "flaw_type": "contradiction" | "logical_gap" | "weak_evidence" | "strawman",
                "argument_id": "...",
                "description": "...",
                "attack_strategy": "..."
            },
            ...
        ]
    """
    pass

@tool
def map_argument_relationships(debate_history: Dict) -> Dict:
    """Map relationships between arguments and their rebuttals.
    
    Returns:
        {
            "argument_chains": [
                {"original": "...", "rebutted_by": "...", "counter_rebuttal": "..."}
            ],
            "unaddressed_points": [...],
            "strongest_arguments": [...]
        }
    """
    pass

# Create argument analysis agent
argument_agent = create_react_agent(
    llm,
    tools=[extract_arguments, identify_logical_flaws, map_argument_relationships]
)
```

**Agent Usage Flow**:

1. **Before Each Debater Turn**:
   ```python
   # Analyze debate history
   analysis = argument_agent.invoke({
       "debate_messages": all_previous_messages,
       "my_side": "affirmative",
       "my_role": "affirmative_2",
       "current_stage": "rebuttal"
   })
   
   # Build context-aware prompt with flaws highlighted
   prompt = build_debater_prompt_with_flaws(
       role=role,
       side=side,
       stage=stage,
       opponent_flaws=analysis["logical_flaws"],
       unaddressed_points=analysis["unaddressed_points"],
       argument_relationships=analysis["argument_chains"]
   )
   ```

2. **For Cross-Examination**:
   ```python
   # Identify best questions to ask
   questions = argument_agent.invoke({
       "opponent_arguments": opponent_messages,
       "weak_points": identified_flaws,
       "question_strategy": "expose_contradiction" | "reveal_gap" | "challenge_evidence"
   })
   ```

3. **For Judge Evaluation**:
   ```python
   # Structured evaluation
   evaluation = argument_agent.invoke({
       "debate_history": all_messages,
       "evaluation_criteria": ["logic", "evidence", "rebuttal", "persuasiveness"]
   })
   ```


**Implementation Strategy**:

**Phase 1: Basic Context (Prototype)**:

- Use simple message array (like AskOnce)
- Include speaker names and timestamps in messages
- Let LLM parse context naturally

**Phase 2: Structured Analysis (Production)**:

- Add LangChain argument analysis agent
- Pre-process debate history before each turn
- Build enriched prompts with flaw identification
- Use tools to extract structured argument data

**File Structure**:

- `agents/debateverse/argument_analyzer.py`: LangChain agent for argument analysis
- `agents/debateverse/flaw_detector.py`: Tool for identifying logical flaws
- `services/debateverse_context_builder.py`: Uses agents to build enriched context

**Prompt Structure**:

- Include debate topic, current round, previous arguments, opponent's points
- Define role-specific instructions (1st debater builds framework, 2nd debater attacks)
- Include US Parliamentary format rules and timing

### 3. Backend: TTS Service (Dashscope)

**File**: `services/tts_service.py` (new)

Dashscope TTS integration for voice synthesis:

- `generate_speech(text, model, voice)`: Generate audio from text using Dashscope TTS
- `get_audio_url(text, model, voice)`: Get cached audio URL or generate new
- `stream_audio_chunks(text, model, voice)`: Stream audio chunks for real-time playback

**TTS Configuration**:

- Use Dashscope Sambert models (e.g., `sambert-zhichu-v1` for Chinese)
- Different voices per model/debater for character distinction
- Audio format: MP3, 32kbps (lightweight)
- Cache audio URLs to avoid regeneration

**Integration**:

- Call TTS after each debater message generation
- Return audio URL with message response
- Frontend plays audio when message appears

### 4. Backend: Debate Orchestration Service

**File**: `services/debateverse_service.py`

Core service managing debate flow:

- `create_debate_session(topic, format, user_id, llm_assignments)`: Initialize debate with user-selected LLM assignments
- `advance_stage(session_id, new_stage)`: Transition to next stage (coin_toss → opening → rebuttal → etc.)
- `get_next_speaker(session_id, stage)`: Determine who speaks next based on current stage and round structure
- `generate_debater_response(session_id, participant_id, stage)`: Generate AI debater response using assigned LLM
                                - Builds full context using `debateverse_context_builder`
                                - Uses `llm_service.chat_stream()` with `messages` parameter
                                - Includes all previous debate messages in context
- `generate_cross_exam_question(session_id, questioner_id, respondent_id)`: Generate cross-examination question
                                - Builds Q&A context from previous cross-exam rounds
                                - May use LangChain agent if complex reasoning needed
- `generate_cross_exam_answer(session_id, respondent_id, question_id)`: Generate cross-examination answer
                                - Builds context including the question and previous Q&A pairs
- `generate_tts_audio(session_id, message_id, text)`: Generate TTS audio for message
- `generate_judge_commentary(session_id, stage)`: Generate judge's flow control/evaluation
- `finalize_debate(session_id)`: Trigger final judgment from judge
- `coin_toss(session_id)`: Execute coin toss, determine speaking order

**LLM Assignment Strategy**:

- Rotate models: Qwen → Doubao → DeepSeek → Kimi → (repeat)
- Assign models to debaters based on their role characteristics:
                                - Affirmative 1: Qwen (creative, establishes framework)
                                - Affirmative 2: DeepSeek (logical, attacks)
                                - Negative 1: Doubao (creative, establishes framework)
                                - Negative 2: Kimi (logical, attacks)
                                - Judge: DeepSeek (analytical, neutral)

### 5. Backend: API Router

**File**: `routers/debateverse.py`

Endpoints:

- `POST /api/debateverse/sessions`: Create new debate session (Stage 1: setup)
- `POST /api/debateverse/sessions/{id}/setup`: Complete setup, assign LLMs and roles
- `GET /api/debateverse/sessions/{id}`: Get debate session with messages
- `POST /api/debateverse/sessions/{id}/join`: User joins as debater/judge/viewer
- `POST /api/debateverse/sessions/{id}/coin-toss`: Execute coin toss (Stage 2.1)
- `POST /api/debateverse/sessions/{id}/advance-stage`: Advance to next stage (judge only)
- `POST /api/debateverse/sessions/{id}/messages`: User sends message (if debater)
- `POST /api/debateverse/sessions/{id}/cross-exam`: Submit cross-examination question/answer
- `POST /api/debateverse/sessions/{id}/judge`: Generate judge commentary/judgment
- `POST /api/debateverse/sessions/{id}/finalize`: Trigger final judgment (Stage 3)
- `GET /api/debateverse/sessions/{id}/stream`: SSE stream for real-time updates
- `GET /api/debateverse/sessions`: List user's debate sessions
- `GET /api/debateverse/messages/{id}/audio`: Get TTS audio URL for message
- `POST /api/debateverse/messages/{id}/tts`: Generate TTS audio for message

**SSE Streaming**:

- Stream debater responses and judge commentary in real-time
- Use same pattern as AskOnce (`routers/askonce.py`)
- Stream thinking content for supported models
- Include audio URL in message stream events: `{"type": "message", "audio_url": "..."}`

**TTS Integration**:

- Generate audio asynchronously after message creation
- Return audio URL via SSE event or separate endpoint
- Cache audio URLs in database (DebateMessage.audio_url)
- Support audio regeneration if needed

### 6. Frontend: Store

**File**: `frontend/src/stores/debateverse.ts`

Pinia store managing debate state:

- `sessions`: Array of debate sessions
- `currentSession`: Active session
- `currentStage`: Current stage (setup/coin_toss/opening/rebuttal/cross_exam/closing/judgment/completed)
- `messages`: Messages for current session (with audio URLs)
- `participants`: Participants in current session
- `llmAssignments`: LLM assignments for each role (from Stage 1)
- `userRole`: User's role in current session (debater/judge/viewer)
- `userSide`: User's side if debater (affirmative/negative)
- `userPosition`: User's position if debater (1st/2nd)
- `isStreaming`: Whether debate is in progress
- `currentSpeaker`: Currently speaking participant ID
- `audioQueue`: Queue of audio URLs to play
- `ttsEnabled`: Whether TTS is enabled (user preference)

**Actions**:

- `createSession(topic, format)`: Create new session (Stage 1)
- `completeSetup(llmAssignments, userRole, userSide?, userPosition?)`: Complete Stage 1 setup
- `joinSession(sessionId, role)`: Join existing session
- `coinToss()`: Execute coin toss (Stage 2.1)
- `advanceStage()`: Advance to next stage (if user is judge)
- `sendMessage(content)` (if user is debater, during their turn)
- `sendCrossExamQuestion(question)` (if user is questioner in cross-exam)
- `sendCrossExamAnswer(answer)` (if user is respondent in cross-exam)
- `loadSession(sessionId)`: Load session with all stages
- `playMessageAudio(messageId)`: Play TTS audio for message
- `toggleTTS()`: Enable/disable TTS playback
- `queueAudio(audioUrl)`: Add audio to playback queue

**Persistence**: Load from database via API, cache in store

### 6. Frontend: Components

**Directory**: `frontend/src/components/debateverse/`

**Stage 1 Components** (Setup):

- `DebateSetup.vue`: Main setup screen
- `TopicInput.vue`: Topic input with suggestions
- `RoleSelector.vue`: User role selection (debater/judge/viewer)
- `LLMAssignment.vue`: LLM assignment interface for each role
- `SideSelector.vue`: Side selection (if user is debater)
- `PositionSelector.vue`: Position selection (1st/2nd debater)
- `SetupPreview.vue`: Preview of debate configuration

**Stage 2 Components** (Debate):

- `DebateVerseStage.vue`: Main three-column stage layout (affirmative | judge | negative)
- `DebaterAvatar.vue`: SVG-based cute figure with nametag (lightweight, animated)
- `DebateHeader.vue`: Shows topic, current stage, round progress
- `CoinTossDisplay.vue`: Coin toss animation and result
- `DebateMessages.vue`: Speech bubbles flowing from avatars (per side)
- `DebateMessage.vue`: Individual speech bubble with streaming text and thinking
- `CrossExamPair.vue`: Q&A pair display for cross-examination
- `JudgeArea.vue`: Center area with judge avatar, controls, and commentary
- `DebateInput.vue`: Input for user debater messages (bottom, conditional)
- `CrossExamInput.vue`: Special input for cross-examination Q&A
- `DebateControls.vue`: Judge controls (advance stage, coin toss, request judgment)
- `StageProgress.vue`: Visual progress indicator for debate stages
- `TTSPlayer.vue`: Lightweight audio player for Dashscope TTS

**Stage 3 Components** (Summary):

- `DebateJudgment.vue`: Final judgment display with scores
- `ScoreBreakdown.vue`: Detailed score visualization
- `WinnerAnnouncement.vue`: Winner announcement with celebration
- `DebateStatistics.vue`: Debate stats (messages, speaking time, etc.)
- `ArgumentHighlights.vue`: Key argument highlights
- `ShareExport.vue`: Share/export debate results

**Styling**:

- Swiss Design theme (gray background, clean, minimal)
- SVG-based avatars (no image assets)
- CSS-only animations (no animation libraries)
- Lightweight, optimized for web performance

### 7. Frontend: TTS Audio Player

**File**: `frontend/src/composables/useDebateTTS.ts` (new)

Lightweight TTS audio playback composable:

- `playAudio(url)`: Play audio from URL
- `stopAudio()`: Stop current playback
- `queueAudio(url)`: Queue audio for sequential playback
- `isPlaying`: Reactive state for playback status
- `currentAudioUrl`: Currently playing audio URL

**Implementation**:

- Use Web Audio API (lightweight, no libraries)
- Queue management for sequential playback
- Handle audio errors gracefully
- Support audio speed control

### 8. Frontend: Page

**File**: `frontend/src/pages/DebateVersePage.vue`

Main page component with stage routing:

**Stage 1 (Setup)**:

- `DebateSetup.vue` as main component
- Topic input and suggestions
- Role selection interface
- LLM assignment interface
- Side/position selection (if debater)
- Preview and start button

**Stage 2 (Debate)**:

- Three-column stage layout (`DebateVerseStage.vue`)
- Header with topic, current stage, and controls
- Stage-specific UI:
                                - Coin toss animation (Stage 2.1)
                                - Opening statements (Stage 2.2)
                                - Rebuttal (Stage 2.3)
                                - Cross-examination Q&A (Stage 2.4)
                                - Closing statements (Stage 2.5)
- Three sections: Affirmative side | Judge area | Negative side
- Each side shows 2 debater avatars with speech bubbles
- Judge area in center with controls
- Input area at bottom (if user is debater, during their turn)
- Cross-examination input (if user is in cross-exam)
- TTS controls (mute/unmute, speed)
- Stage progress indicator

**Stage 3 (Summary)**:

- `DebateJudgment.vue` as main component
- Score breakdown visualization
- Winner announcement
- Key argument highlights
- Debate statistics
- Share/export options
- "Start New Debate" button

**Navigation**:

- Sidebar for session history (optional, collapsible)
- Stage indicator showing current stage

### 9. Frontend: Routing & Navigation

**File**: `frontend/src/router/index.ts`

Add route:

```typescript
{
  path: '/debateverse',
  name: 'DebateVerse',
  component: () => import('@/pages/DebateVersePage.vue'),
  meta: { layout: 'main' },
}
```

**File**: `frontend/src/components/sidebar/AppSidebar.vue`

Add navigation item for DebateVerse in the correct position:

- Below AskOnce
- Above "模板资源" (Template Resources)

**Navigation Order**:

1. MindMate
2. MindGraph
3. AskOnce
4. **DebateVerse** (new - 论境)
5. 学校专区 (School Zone) - conditional
6. 模板资源 (Template Resources)
7. 思维课程 (Course)
8. 社区分享 (Community)

**Implementation**:

- Add `debateverse` to `currentMode` computed (check for `/debateverse` path)
- Add menu item in `el-menu` between AskOnce and Template
- Add route handling in `setMode()` function
- Add history component similar to `AskOnceHistory.vue` (optional)

### 10. Database Migration

Create Alembic migration for new tables:

- `debate_sessions`
- `debate_participants`
- `debate_messages`
- `debate_judgments`

### 11. Integration Points

**LLM Service**: Use existing `services/llm_service.py` with `chat_stream()` for SSE

- Use `messages` parameter for multi-turn context (like AskOnce)
- Each debater gets full debate history in `messages` array
- No need for LangChain for simple turn-based responses

**Prompt Building**:

- Use `prompts/debateverse.py` for prompt templates
- Use `services/debateverse_context_builder.py` to build message arrays
- Follow AskOnce pattern: build messages array, pass to `llm_service.chat_stream()`

**Context Management**:

- Full context: All previous messages included (prototype approach)
- Future: Summarize old stages to save tokens (production optimization)
- Database: Store all messages, build context on-demand

**Token Tracking**: Use existing token tracking system (`request_type='debateverse'`)

**Error Handling**: Use existing error handling patterns

**Rate Limiting**: Leverage existing rate limiting infrastructure

**LangChain Agents** (Required for Quality Debates):

- **Argument Analyzer Agent**: Extracts structured arguments, identifies speakers, maps relationships
- **Flaw Detector Tool**: Identifies logical flaws, contradictions, weak points in opponent's arguments
- **Relationship Mapper Tool**: Maps argument chains, rebuttals, unaddressed points
- **Usage**: Pre-process debate history before each turn, enrich prompts with flaw analysis
- **Flow**: Agent analyzes → Identifies flaws → Builds enriched prompt → LLM generates response

**Performance Optimization**:

- **Incremental Analysis**: Only analyze new messages since last turn (not entire history)
- **Cached Results**: Cache analysis per stage, reuse if no new messages
- **Stage Summarization**: Summarize old stages, keep current stage full context
- **Token Budget**: Allocate tokens intelligently (current stage full, previous summarized)
- **Parallel Processing**: Run analysis and context building in parallel
- **Target**: < 6 seconds total prep time (leaves 54s for LLM response in 1-minute limit)

**Why LangChain Agents Are Essential**:

- LLMs need structured understanding of "who said what when"
- Logical flaw detection requires systematic analysis
- Argument relationship mapping helps build coherent rebuttals
- Context-aware prompts lead to better debate quality

## Multi-Stage Debate Flow

### Stage 1: Setup & Role Selection (准备阶段)

**User Actions**:

- Choose user role: Debater, Judge, or Viewer
- Select debate topic (or use suggested topics)
- Assign LLMs to specific roles:
                                - Affirmative 1: [Select LLM: Qwen/Doubao/DeepSeek/Kimi]
                                - Affirmative 2: [Select LLM: Qwen/Doubao/DeepSeek/Kimi]
                                - Negative 1: [Select LLM: Qwen/Doubao/DeepSeek/Kimi]
                                - Negative 2: [Select LLM: Qwen/Doubao/DeepSeek/Kimi]
                                - Judge: [Select LLM: Qwen/Doubao/DeepSeek/Kimi]
- If user is debater: Choose which side (Affirmative/Negative) and position (1st/2nd)

**UI Components**:

- Topic input/suggestion
- Role selection cards
- LLM assignment interface (drag-drop or select)
- Preview of debate setup

**Backend**:

- Create debate session with selected configuration
- Initialize participants with assigned LLMs
- Store user's role choice

### Stage 2: Debate Execution (辩论阶段)

**US Parliamentary Style Debate (公共论坛式) - 2V2 Team Format**

#### 2.1 Coin Toss (掷硬币)

- **Purpose**: Determine speaking order or side selection
- **Implementation**: Random coin toss (or user choice if user is judge)
- **Result**: Sets initial speaking order
- **UI**: Animated coin flip, result display

#### 2.2 Opening Statements (立论发言)

- **Order**: Affirmative 1 → Negative 1
- **Duration**: ~3-5 minutes each (configurable)
- **AI Behavior**:
                                - **Affirmative 1**: Establishes framework, presents core arguments, defines key terms
                                - **Negative 1**: Establishes counter-framework, presents core counter-arguments
- **AI Styles**: Each LLM has distinct style (logical/data-driven/emotional)
- **UI**: Speech bubbles from respective avatars, real-time streaming

#### 2.3 Rebuttal (驳论发言)

- **Order**: Affirmative 2 → Negative 2
- **Duration**: ~3-5 minutes each
- **AI Behavior**:
                                - **Affirmative 2**: Attacks negative's framework, defends affirmative's points
                                - **Negative 2**: Attacks affirmative's framework, defends negative's points
- **AI Capability**: Identify opponent's core arguments, provide targeted counter-arguments
- **UI**: Highlighted attack points, visual connections between arguments

#### 2.4 Cross-Examination (交叉质询)

- **Format**: Multi-round Q&A between sides
- **Order**: 
                                - Round 1: Affirmative 2 questions Negative 1
                                - Round 2: Negative 2 questions Affirmative 1
                                - (Additional rounds if time permits)
- **AI Behavior**:
                                - **Questioner**: Logical questioning to expose contradictions, strengthen own position
                                - **Respondent**: Defensive responses, avoid traps, reinforce own arguments
- **AI Capability**: Multi-turn dialogue, logical reasoning, trap detection
- **UI**: Q&A pairs, visual flow of questions and answers

#### 2.5 Closing Statements (总结陈词)

- **Order**: Affirmative 1 → Negative 1
- **Duration**: ~2-3 minutes each
- **AI Behavior**:
                                - Summarize entire debate
                                - Reinforce own team's strengths
                                - Point out opponent's weaknesses
                                - Elevate arguments to higher level
- **AI Capability**: Synthesize debate thread, persuasive final statement
- **UI**: Summary highlights, key points visualization

**Stage 2 Flow Control**:

- Judge (AI or user) controls round transitions
- Automatic time limits with warnings
- Pause/resume capability
- Round progress indicator

### Stage 3: Summary & Judgment (总结阶段)

**Judge Evaluation**:

- **Scoring Dimensions**:
                                - Logic consistency (逻辑一致性)
                                - Evidence validity (证据效力)
                                - Rebuttal strength (反驳力度)
                                - Persuasiveness & rhetoric (说服力与修辞)
- **Final Verdict**: Winner announcement, best debater selection
- **Detailed Analysis**: Point-by-point evaluation

**UI Components**:

- Score breakdown visualization
- Winner announcement
- Key argument highlights
- Debate statistics (total messages, speaking time, etc.)
- Share/export options

**User Actions**:

- View detailed judgment
- Vote on judgment (if viewer)
- Share debate results
- Start new debate

## Stage Management

**State Machine**:

```
SETUP → COIN_TOSS → OPENING → REBUTTAL → CROSS_EXAM → CLOSING → JUDGMENT → COMPLETE
```

**Stage Transitions**:

- User-controlled (if user is judge)
- AI-controlled (if AI judge)
- Automatic (based on time limits)

## Production-Ready Design Decisions

1. **Context Building**: Each LLM call includes full debate history up to that point (similar to AskOnce's per-model context)

                                                - **Rationale**: Ensures coherent arguments, proper rebuttals, maintains debate thread
                                                - **Implementation**: Build context array from database messages, include role-specific instructions

2. **Model Rotation**: Ensures diverse perspectives and prevents model-specific biases (follow Node Palette round-robin pattern)

                                                - **Rationale**: Different models bring different strengths, prevents echo chamber effect
                                                - **Implementation**: Round-robin assignment with role-based model selection (logical models for framework builders, creative for attackers)

3. **User Participation**: Users can interrupt AI flow by sending messages when it's their turn

                                                - **Rationale**: True interactive debate, not just watching AI talk
                                                - **Implementation**: State machine tracks current speaker, validates user can speak, queues user messages

4. **Real-time Updates**: SSE streaming keeps all viewers synchronized (reuse AskOnce SSE pattern)

                                                - **Rationale**: Professional UX, no polling, instant updates for all participants
                                                - **Implementation**: Battle-tested SSE pattern from AskOnce, stream thinking content for supported models

5. **Database Persistence**: Allows resuming debates, sharing, and analytics

                                                - **Rationale**: Production requirement - debates are valuable content, need persistence
                                                - **Implementation**: Proper SQLAlchemy models with relationships, indexes, soft deletes

6. **Turn Management**: Use state machine pattern (like Voice Agent) to track debate rounds and speaker order

                                                - **Rationale**: Robust flow control, handles edge cases, prevents race conditions
                                                - **Implementation**: State enum (pending/opening/rebuttal/cross/closing/judgment), transition validation

7. **Error Recovery**: Comprehensive error handling at every layer

                                                - **Rationale**: Production systems fail gracefully, users see helpful errors
                                                - **Implementation**: Try-catch blocks, proper error messages, retry logic for transient failures

8. **Token Efficiency**: Optimize context to avoid unnecessary token usage

                                                - **Rationale**: Cost control, faster responses, better user experience
                                                - **Implementation**: Summarize old rounds, include only relevant context, use system prompts efficiently

## Implementation Patterns to Follow

### From AskOnce (`routers/askonce.py`)

```python
# SSE Streaming Pattern
async def stream_from_llm(model_id, messages, ...):
    async for chunk in llm_service.chat_stream(
        messages=messages,
        model=model_id,
        enable_thinking=True,
        yield_structured=True
    ):
        yield f'data: {json.dumps(chunk)}\n\n'
```

**Apply**: Use same SSE pattern for streaming debater responses and judge commentary

### From Node Palette (`agents/node_palette/base_palette_generator.py`)

```python
# Round-robin model assignment
llm_models = ['qwen', 'deepseek', 'doubao']
next_model_index = (current_index + 1) % len(llm_models)
```

**Apply**: Rotate models across debate turns: Affirmative 1 → Qwen, Negative 1 → Doubao, Affirmative 2 → DeepSeek, etc.

### From MindMate (`frontend/src/stores/mindmate.ts`)

```typescript
// Conversation state management
const messages = ref<Message[]>([])
const currentConversationId = ref<string | null>(null)
```

**Apply**: Similar store structure but with debate-specific fields (round, participants, userRole)

### Production Quality Standards

**Code Quality**:

- Follow existing code review patterns (see `docs/ASKONCE_REVIEW.md`)
- Comprehensive error handling at every layer
- Proper logging without emojis (per project convention)
- Clean, professional log messages

**Performance**:

- Leverage existing rate limiting infrastructure
- Use database indexes for efficient queries
- Optimize context building to avoid token waste
- Implement proper caching where appropriate

**User Experience**:

- Swiss Design theme (gray background, clean, minimal)
- Real-time updates via SSE streaming
- Smooth streaming experience (no janky UI)
- Clear role indicators and debate flow visualization

**Scalability**:

- Database-backed persistence (not localStorage)
- Support for concurrent debates
- Efficient message storage and retrieval
- Proper session management

## Files to Create/Modify

**New Files**:

- `models/debateverse.py`
- `prompts/debateverse.py` (Prompt templates)
- `services/debateverse_service.py` (Debate orchestration)
- `services/debateverse_context_builder.py` (Context building from messages)
- `services/tts_service.py` (Dashscope TTS integration)
- `routers/debateverse.py`
- `frontend/src/stores/debateverse.ts`
- `frontend/src/pages/DebateVersePage.vue`
- `frontend/src/components/debateverse/*.vue` (multiple components)
- `frontend/src/composables/useDebateTTS.ts` (TTS audio player)
- `frontend/src/assets/debateverse/` (SVG avatar assets)
- Database migration file

**LangChain Agents**:

- `agents/debateverse/argument_analyzer.py` (LangChain agent for structured argument analysis)
- `agents/debateverse/flaw_detector.py` (Tool for identifying logical flaws and contradictions)
- `agents/debateverse/relationship_mapper.py` (Tool for mapping argument relationships and rebuttals)

**Modified Files**:

- `frontend/src/router/index.ts` (add route)
- `frontend/src/components/sidebar/AppSidebar.vue` (add navigation item between AskOnce and Template)
- `main.py` (register router)
- `config/database.py` (import new models)