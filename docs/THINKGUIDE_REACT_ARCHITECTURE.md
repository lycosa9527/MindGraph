# ThinkGuide ReAct Architecture

## Overview

ThinkGuide has been refactored to use the **ReAct pattern** (Reasoning + Acting), allowing each diagram type to have unique, diagram-specific behavior while sharing common infrastructure.

**Author:** lycosa9527  
**Made by:** MindSpring Team

---

## Architecture Principles

### 1. **Diagram-Specific Behavior**

Each diagram type has unique ThinkGuide behavior tailored to its educational purpose:

| Diagram Type | ThinkGuide Focus | Educational Goal |
|-------------|-----------------|-----------------|
| **Circle Map** | Socratic refinement of observations | Define topic in context through observation |
| **Bubble Map** | Attribute-focused descriptive thinking | Describe with adjectives and characteristics |
| **Tree Map** | Hierarchical categorization | Classify and group systematically |
| **Mind Map** | Branch organization | Explore connections and relationships |
| **Flow Map** | Sequential reasoning | Analyze processes and cause-effect |

### 2. **ReAct Pattern (Reason → Act → Observe)**

ThinkGuide uses a three-step cycle for all diagram types:

1. **REASON**: Use LLM to understand user intent within diagram context
2. **ACT**: Execute diagram modifications or generate responses
3. **OBSERVE**: Provide feedback and continue the dialogue

---

## File Structure

```
agents/thinking_modes/
├── base_thinking_agent.py           # Abstract base class with ReAct framework
├── circle_map_agent_react.py        # Circle Map specific implementation
├── circle_map_actions.py            # Circle Map action handlers (< 500 lines)
├── factory.py                       # Factory pattern for agent creation
└── circle_map_agent.py              # Legacy agent (kept for reference)

prompts/thinking_modes/
└── circle_map.py                    # Circle Map specific prompts
```

---

## Implementation Details

### BaseThinkingAgent (Abstract Base Class)

**Location:** `agents/thinking_modes/base_thinking_agent.py`

**Responsibilities:**
- Session management
- LLM communication (streaming)
- ReAct workflow orchestration
- Language detection (English/Chinese)

**Abstract Methods (Subclasses MUST implement):**

```python
async def _detect_user_intent(session, message, current_state) -> Dict
    """Detect diagram-specific user intent"""

async def _handle_action(session, intent, message, current_state) -> AsyncGenerator
    """Handle diagram-specific actions"""

def _get_state_prompt(session, state) -> str
    """Get diagram-specific prompt for current state"""

async def _generate_suggested_nodes(session) -> List[Dict]
    """Generate diagram-specific node suggestions"""
```

### CircleMapThinkingAgent

**Location:** `agents/thinking_modes/circle_map_agent_react.py` (< 300 lines)

**Circle Map-Specific Features:**

1. **Intent Detection**: Recognizes Circle Map actions
   - `change_center`: Change the center topic being defined
   - `update_node`: Modify an observation
   - `delete_node`: Remove an observation
   - `update_properties`: Change node styling
   - `add_nodes`: Add new observations
   - `discuss`: Pure discussion, no diagram changes

2. **State Machine**: 7-stage Socratic workflow
   - `CONTEXT_GATHERING`: Understand teaching context
   - `EDUCATIONAL_ANALYSIS`: Analyze observations' relevance
   - `ANALYSIS`: Socratic questioning
   - `REFINEMENT_1`: N → 8 observations
   - `REFINEMENT_2`: 8 → 6 observations
   - `FINAL_REFINEMENT`: 6 → 5 core observations
   - `COMPLETE`: Workflow finished

3. **Node Generation**: Observation-focused suggestions
   - Generated nodes are concrete, observable aspects
   - Appropriate for K12 students
   - Cover different angles of the topic

### CircleMapActionHandler

**Location:** `agents/thinking_modes/circle_map_actions.py`

**Purpose:** Separate action handlers to keep main agent under 500 lines

**Methods:**
- `handle_change_center()`: Update center topic
- `handle_update_node()`: Modify node text
- `handle_delete_node()`: Remove node
- `handle_update_properties()`: Update styling
- `handle_add_nodes()`: Add suggested nodes

---

## ReAct Workflow Example

### User Message: "Change the center to 'Photosynthesis'"

```
1. REASON (Intent Detection)
   ↓
   LLM analyzes: "User wants to change center topic"
   ↓
   Intent: {action: "change_center", target: "Photosynthesis"}

2. ACT (Execute Action)
   ↓
   CircleMapActionHandler.handle_change_center()
   ↓
   - Stream acknowledgment: "I'll update the center topic..."
   - Update diagram data
   - Send diagram_update event to frontend
   - Stream completion: "Successfully updated!"

3. OBSERVE (Continue Dialogue)
   ↓
   Frontend receives updates and re-renders
   ↓
   User sees changes and can continue refining
```

---

## Adding New Diagram Types

To add ThinkGuide support for a new diagram type:

### 1. Create Agent Class

```python
# agents/thinking_modes/bubble_map_agent_react.py

class BubbleMapThinkingAgent(BaseThinkingAgent):
    def __init__(self):
        super().__init__(diagram_type='bubble_map')
    
    async def _detect_user_intent(self, session, message, current_state):
        # Bubble Map specific intent detection
        # Actions: change_subject, add_attribute, etc.
        pass
    
    async def _handle_action(self, session, intent, message, current_state):
        # Bubble Map specific action handling
        pass
    
    def _get_state_prompt(self, session, state):
        # Bubble Map specific prompts
        pass
    
    async def _generate_suggested_nodes(self, session):
        # Generate adjective-based suggestions
        pass
```

### 2. Create Action Handler (if needed)

```python
# agents/thinking_modes/bubble_map_actions.py

class BubbleMapActionHandler:
    async def handle_change_subject(self, session, new_subject):
        # Handle subject change
        pass
    
    async def handle_add_attribute(self, session, attribute):
        # Handle adding descriptive attribute
        pass
```

### 3. Create Prompts

```python
# prompts/thinking_modes/bubble_map.py

CONTEXT_GATHERING_PROMPT_EN = """
Help the teacher describe "{subject}" with vivid adjectives...
"""

# Add prompts for each state
```

### 4. Register in Factory

```python
# agents/thinking_modes/factory.py

from agents.thinking_modes.bubble_map_agent_react import BubbleMapThinkingAgent

class ThinkingAgentFactory:
    _agents = {
        'circle_map': CircleMapThinkingAgent,
        'bubble_map': BubbleMapThinkingAgent,  # Add here
        # ...
    }
```

---

## Benefits of ReAct Architecture

1. **Diagram-Specific Behavior**: Each diagram type has unique ThinkGuide experience
2. **Code Reusability**: Common ReAct infrastructure in base class
3. **Maintainability**: Each agent file < 500 lines
4. **Scalability**: Easy to add new diagram types
5. **Testability**: Each component can be tested independently
6. **LLM-Based Intelligence**: Uses LLM for intent detection, not brittle keyword matching

---

## API Integration

### Router
**Location:** `routers/thinking.py`

**Endpoint:** `POST /thinking_mode/stream`

```python
# Factory pattern - automatically routes to correct agent
agent = ThinkingAgentFactory.get_agent(req.diagram_type)

# ReAct cycle streaming
async for chunk in agent.process_step(
    message=req.message,
    session_id=req.session_id,
    diagram_data=req.diagram_data,
    current_state=req.current_state
):
    yield f"data: {json.dumps(chunk)}\n\n"
```

---

## Testing

### Manual Test

```bash
cd "C:\Users\roywa\Documents\Cursor Projects\MindGraph"
python -c "from agents.thinking_modes.factory import ThinkingAgentFactory; agent = ThinkingAgentFactory.get_agent('circle_map'); print(f'Agent loaded: {agent.__class__.__name__}')"
```

**Expected Output:** `Agent loaded: CircleMapThinkingAgent`

### Import Test

```bash
python -c "import main; import routers.thinking; print('Server modules import successfully')"
```

---

## Future Enhancements

1. **Bubble Map ThinkGuide**: Attribute-focused refinement
2. **Tree Map ThinkGuide**: Hierarchical categorization guidance
3. **Mind Map ThinkGuide**: Branch organization and concept exploration
4. **Flow Map ThinkGuide**: Sequential thinking and cause-effect analysis
5. **Shared Session Store**: Redis/DB for production (currently in-memory)
6. **Multi-Modal Input**: Image analysis for diagram understanding
7. **Adaptive Prompts**: Personalized based on teacher's style

---

## Notes

- **Line Limit**: All agent files kept under 500 lines per user preference [[memory:6419161]]
- **Professional Style**: Clean logs, no emojis [[memory:7691085]]
- **Educational Focus**: Designed for K12 teachers [[memory:7691716]]
- **Author Attribution**: lycosa9527, MindSpring Team [[memory:5011166]]

---

**Last Updated:** 2025-10-11  
**Status:** ✅ Production Ready

