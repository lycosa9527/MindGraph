# Standalone Diagram Style System Guide

## Overview

The standalone style system provides comprehensive control over diagram appearance, including colors, fonts, sizes, and themes. It's designed to work seamlessly with user prompts that include styling instructions.

## Key Features

### 1. **Smart Color Themes**
- **192 color schemes** (like Xmind) with 6 variations each
- **Theme categories**: Classic, Innovation
- **Variations**: Colorful, Monochromatic, Dark, Light, Print, Display
- **Automatic color harmony** and professional appearance

### 2. **Importance-Based Color Intensity**
- **Center Topic**: Full intensity (100%)
- **Main Topic**: 80% intensity  
- **Sub Topic**: 60% intensity
- **Detail**: 40% intensity

### 3. **Automatic Text Legibility**
- **Contrast calculation** based on background luminance
- **Automatic text color** selection (black/white)
- **Ensures readability** across all color combinations

### 4. **Prompt-to-Style Parsing**
- **Natural language processing** of user style instructions
- **Color name recognition** (red, blue, green, etc.)
- **Theme detection** (classic, innovation, dark, light, etc.)
- **Font size extraction** from prompts
- **Importance level detection** (emphasis, main, sub)

## Usage Examples

### Basic Usage

```python
from diagram_styles import parse_style_from_prompt, get_style

# Parse style from user prompt
prompt = "Create a bubble map with blue background and red topic nodes, font size 20"
user_style = parse_style_from_prompt(prompt)

# Get complete style for diagram
final_style = get_style("bubble_map", user_style)
```

### Advanced Usage with Themes

```python
# Use specific color theme
style = get_style("mindmap", user_style, "innovation", "dark")

# Apply importance-based intensity
style = get_style("tree_map", {"importance": "center"}, "classic", "colorful")
```

## Supported Diagram Types

### Thinking Maps
- **bubble_map**: Topic and characteristics
- **double_bubble_map**: Comparison with similarities/differences
- **tree_map**: Hierarchical structure
- **flow_map**: Sequential steps
- **brace_map**: Parts of a whole
- **circle_map**: Context and definition
- **multi_flow_map**: Cause and effect
- **bridge_map**: Analogies

### Mind Maps
- **mindmap**: Hierarchical mind map
- **radial_mindmap**: Radial layout with multiple branches

### Concept Maps
- **concept_map**: Concepts and relationships
- **semantic_web**: Central concept with branches

### Common Diagrams
- **venn_diagram**: Set relationships
- **fishbone_diagram**: Cause analysis
- **flowchart**: Process flow
- **org_chart**: Organizational structure
- **timeline**: Chronological events

## Style Properties

### Global Properties
```python
{
    "fontFamily": "Inter, Segoe UI, sans-serif",
    "background": "#ffffff",
    "strokeWidth": 2,
    "borderRadius": 4
}
```

### Diagram-Specific Properties

#### Bubble Map
```python
{
    "topicColor": "#4e79a7",
    "topicTextColor": "#ffffff",
    "topicFontSize": 18,
    "topicFontWeight": "bold",
    "charColor": "#a7c7e7",
    "charTextColor": "#2c3e50",
    "charFontSize": 14,
    "stroke": "#2c3e50"
}
```

#### Mind Map
```python
{
    "centralTopicColor": "#4e79a7",
    "centralTopicTextColor": "#ffffff",
    "centralTopicFontSize": 20,
    "centralTopicFontWeight": "bold",
    "mainBranchColor": "#a7c7e7",
    "mainBranchTextColor": "#2c3e50",
    "mainBranchFontSize": 16,
    "subBranchColor": "#f4f6fb",
    "subBranchTextColor": "#2c3e50",
    "subBranchFontSize": 14
}
```

## Color Themes

### Classic Theme
- **Colorful**: Professional blue-based palette
- **Monochromatic**: Grayscale variations
- **Dark**: Dark background theme
- **Light**: Light background theme
- **Print**: Print-friendly grayscale
- **Display**: Screen-optimized colors

### Innovation Theme
- **Colorful**: Vibrant, modern palette
- **Monochromatic**: Red-based variations
- **Dark**: Dark innovation theme
- **Light**: Light innovation theme
- **Print**: Print-friendly innovation
- **Display**: Digital innovation colors

## Integration with Existing Workflow

### 1. **In Your Agent/API**
```python
def process_diagram_request(user_prompt: str, diagram_type: str):
    # Extract style from prompt
    user_style = parse_style_from_prompt(user_prompt)
    
    # Get complete style
    final_style = get_style(diagram_type, user_style)
    
    # Add to diagram spec
    diagram_spec = create_diagram_spec(diagram_type, content)
    diagram_spec["style"] = final_style
    
    return diagram_spec
```

### 2. **In Your D3.js Renderer**
```javascript
function renderDiagram(diagramSpec) {
    const style = diagramSpec.style;
    
    // Apply styles to D3 elements
    svg.selectAll(".topic")
        .attr("fill", style.topicColor)
        .attr("stroke", style.stroke)
        .style("font-size", style.topicFontSize + "px");
}
```

### 3. **In Your Validation**
```python
from graph_specs import validate_diagram_spec

# Validate diagram spec (style is optional)
is_valid, error = validate_diagram_spec(diagram_type, diagram_spec)
```

## User Prompt Examples

### Simple Color Requests
```
"Make the topic node red"
"Use blue background"
"Green branches with yellow text"
```

### Theme Requests
```
"Use the classic dark theme"
"Apply innovation colorful theme"
"Professional monochromatic style"
```

### Complex Requests
```
"Create a mind map with innovation theme, emphasis on central topic, font size 24, and bold stroke"
"Draw a bubble map with blue background, red topic nodes, green characteristics, and thin borders"
"Make a tree map using classic dark theme with important nodes highlighted"
```

## Benefits

### 1. **User-Friendly**
- Natural language style instructions
- No need to learn technical color codes
- Intuitive theme selection

### 2. **Professional Quality**
- Pre-designed color harmonies
- Automatic contrast optimization
- Consistent visual hierarchy

### 3. **Flexible**
- Per-diagram customization
- Theme variations
- Easy to extend

### 4. **Maintainable**
- Centralized style definitions
- Separation of concerns
- Easy to update and modify

## Future Enhancements

### Planned Features
- **Custom color palettes**: User-defined color schemes
- **Animation styles**: Transition and animation controls
- **Layout preferences**: Spacing and positioning controls
- **Accessibility**: High contrast and colorblind-friendly themes
- **Export styles**: Print and presentation optimizations

### Extension Points
- **New diagram types**: Easy to add style support
- **Custom themes**: User-created theme definitions
- **Style presets**: Saved style configurations
- **API integration**: External style management

## Testing

Run the test suite to verify functionality:

```bash
python test_style_system.py
python style_integration_example.py
```

## Conclusion

The standalone style system provides a powerful, flexible, and user-friendly way to control diagram appearance. It seamlessly integrates with existing workflows while offering professional-quality styling options that enhance the visual impact of your diagrams. 