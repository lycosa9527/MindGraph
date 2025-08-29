# Centralized Prompt Registry

This directory contains a unified, organized system for all diagram prompts in the MindGraph project.

## 🚀 Latest Updates (v2.5.3)

### Smart LLM Classification System
- ✅ **Advanced Intent Understanding**: Distinguishes between diagram type to create vs topic content
- ✅ **Edge Case Handling**: Correctly processes complex prompts like "生成关于概念图的思维导图" → `mind_map`
- ✅ **Centralized Classification**: All LLM classification prompts moved to `main_agent.py`
- ✅ **Enhanced Examples**: Specific patterns for better semantic understanding

## 🎯 Problem Solved

**Before**: Prompts were scattered across multiple files:
- Some in `agent.py` (bubble_map, double_bubble_map, circle_map)
- Some in `deepseek_agent.py` (bridge_map, flow_map, etc.)
- Inconsistent architecture and maintenance nightmare
- Hardcoded keyword-based classification

**After**: All prompts centralized in one organized system:
- Single source of truth for all prompts
- Consistent architecture and easy maintenance
- All diagram types supported in main agent workflow
- **Smart LLM-based classification** with semantic understanding

## 📁 Structure

```
prompts/
├── __init__.py              # Main registry and interface
├── main_agent.py           # Main agent prompts (LLM classification, concept generation)
├── thinking_maps.py         # All 7 Thinking Maps® prompts  
├── concept_maps.py          # Concept map prompts
├── mind_maps.py            # Mind map prompts with clockwise positioning
└── README.md               # This documentation
```

## 🧠 Smart Classification Examples

The LLM classification system in `main_agent.py` handles complex user intent:

| User Input | Detected Type | Explanation |
|------------|---------------|-------------|
| `"生成一个关于概念图的思维导图"` | `mind_map` | User wants to CREATE a mind map ABOUT concept maps |
| `"生成一个关于思维导图的概念图"` | `concept_map` | User wants to CREATE a concept map ABOUT mind maps |
| `"create a bubble map about double bubble maps"` | `bubble_map` | User wants to CREATE a bubble map ABOUT double bubbles |
| `"compare cats and dogs"` | `double_bubble_map` | Comparison intent automatically detected |

## 🚀 Usage

### Basic Usage

```python
from prompts import get_prompt, get_available_diagram_types

# Get a prompt for bridge map generation in English
bridge_prompt = get_prompt("bridge_map", "en", "generation")

# Get available diagram types
diagram_types = get_available_diagram_types()
print(diagram_types)
# ['bubble_map', 'bridge_map', 'circle_map', 'concept_map', ...]
```

### In Agent Workflow

The main `agent.py` now uses the centralized registry:

```python
def generate_graph_spec(user_prompt: str, graph_type: str, language: str = 'zh') -> dict:
    from prompts import get_prompt
    
    # Get the appropriate prompt template
    prompt_text = get_prompt(graph_type, language, 'generation')
    
    if not prompt_text:
        return {"error": f"No prompt template found for {graph_type}"}
    
    # Use the prompt with LLM...
```

## 📊 Supported Diagram Types

### Thinking Maps® (8 types)
1. **Circle Map** - Define topics in context
2. **Bubble Map** - Describe attributes and characteristics  
3. **Double Bubble Map** - Compare and contrast two topics
4. **Tree Map** - Categorize and classify information
5. **Brace Map** - Show whole/part relationships
6. **Flow Map** - Sequence events and processes
7. **Multi-Flow Map** - Analyze cause and effect relationships
8. **Bridge Map** - Show analogies and similarities

### Concept Maps
- **Concept Map** - Show relationships between concepts

### Mind Maps
- **Mind Map** - Organize ideas around a central topic
- **Radial Mind Map** - Create a radial mind map structure



## 🔧 API Reference

### `get_prompt(diagram_type, language, prompt_type)`

Get a prompt template for a specific diagram type.

**Parameters:**
- `diagram_type` (str): Type of diagram (e.g., 'bridge_map', 'bubble_map')
- `language` (str): Language code ('en' or 'zh')
- `prompt_type` (str): Type of prompt ('generation', 'classification', 'extraction')

**Returns:**
- `str`: The prompt template

### `get_available_diagram_types()`

Get list of all available diagram types.

**Returns:**
- `list`: List of diagram type names

### `get_prompt_metadata(diagram_type)`

Get metadata about a diagram type's prompts.

**Returns:**
- `dict`: Metadata including supported languages and prompt types

## 🧪 Testing

Run the test script to verify the system works:

```bash
python test_prompts.py
```

This will test:
- Prompt registry functionality
- Bridge map prompt availability (previously missing)
- Agent integration
- Error handling

## 🔄 Migration Benefits

### For Developers
- **Single Location**: All prompts in one organized place
- **Consistent Patterns**: Same structure for all diagram types
- **Easy Maintenance**: Add new prompts without touching agent code
- **Type Safety**: Clear interface with proper error handling

### For Users
- **Complete Support**: All diagram types now work in main agent
- **Consistent Quality**: All prompts follow same educational standards
- **Better Error Messages**: Clear feedback when prompts aren't available

### For System
- **Modular Architecture**: Clean separation of concerns
- **Extensible Design**: Easy to add new diagram types
- **Validation Integration**: Works with existing validation system
- **Multi-language Support**: Consistent EN/ZH support for all types

## 🎉 Bridge Map Fix

The **bridge map** was previously missing from the main agent workflow. Now it's fully supported:

```python
# This now works!
result = generate_graph_spec("Create analogies between animals and vehicles", "bridge_map", "en")
```

The bridge map prompt generates proper JSON with:
- `relating_factor`: The common relationship
- `analogies`: Array of analogy pairs with left_pair and right_pair

## 🔮 Future Enhancements

- **Prompt Versioning**: Track prompt versions and changes
- **A/B Testing**: Compare different prompt variations
- **Prompt Analytics**: Monitor prompt effectiveness
- **Dynamic Prompts**: Context-aware prompt generation
- **Prompt Templates**: Reusable prompt components

## 📝 Contributing

When adding new diagram types:

1. Add prompts to appropriate file in `prompts/`
2. Add to the registry in the file's `*_PROMPTS` dictionary
3. Add validation in `graph_specs.py`
4. Add renderer in `d3-renderers.js`
5. Update documentation
6. Run tests to verify

This centralized system makes the codebase much more maintainable and ensures all diagram types are properly supported! 