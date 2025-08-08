# Enhanced Brace Map - 5-Column Layout

## Overview

The enhanced brace map now features a clear **5-column layout** that provides optimal visual hierarchy and relationship mapping between whole/part relationships.

## Layout Structure

### Column Layout (Left to Right)

1. **Topic Column** - Main subject/concept
2. **Big Brace Column** - Main brace connecting topic to all parts
3. **Parts Column** - Main components/parts
4. **Small Brace Column** - Individual braces for each part's subparts
5. **Subparts Column** - Detailed components/subparts

### Visual Hierarchy

```
Topic | Big Brace | Parts | Small Brace | Subparts
  A         {        B        {            C
            {        D        {            E
            {        F        {            G
```

## Technical Implementation

### D3.js Renderer Enhancements

- **Simplified 5-column layout** with clear column separation
- **Two types of braces** with different widths and styles:
  - Big brace: 20px width (connects topic to all parts)
  - Small braces: 15px width (connect each part to its subparts)
- **Fixed column positioning** for consistent layout
- **Optimized spacing** for readability

### Layout Structure

The new implementation uses a clean 5-column approach:
- Column 1: Topic (left-aligned)
- Column 2: Big brace (connects topic to all parts)
- Column 3: Parts (main categories)
- Column 4: Small braces (connect each part to its subparts)
- Column 5: Subparts (detailed components)

## Configuration

### Brace Spacing Configuration

```python
BRACE_SPACING_CONFIG = {
    'main_brace_from_topic': 20,
    'main_brace_to_secondary_brace': 20,
    'secondary_brace_to_parts': 20,
    'part_brace_from_part': 15,
    'tertiary_brace_to_subparts': 15,
    'topic_left_offset': 200,
    'minimum_brace_height': 20,
    'minimum_spacing': 10,
    'secondary_brace_width': 10,
    'tertiary_brace_width': 8
}
```

### Theme Configuration

The enhanced brace map supports the same theme configuration as before, with additional styling for the new brace types.

## Usage Examples

### Basic Example

```json
{
  "topic": "Computer System",
  "parts": [
    {
      "name": "Hardware",
      "subparts": [
        {"name": "CPU"},
        {"name": "RAM"},
        {"name": "Storage"}
      ]
    },
    {
      "name": "Software",
      "subparts": [
        {"name": "OS"},
        {"name": "Applications"},
        {"name": "Drivers"}
      ]
    }
  ]
}
```

### Complex Example

```json
{
  "topic": "Ecosystem",
  "parts": [
    {
      "name": "Biotic Factors",
      "subparts": [
        {"name": "Plants"},
        {"name": "Animals"},
        {"name": "Microorganisms"},
        {"name": "Fungi"}
      ]
    },
    {
      "name": "Abiotic Factors", 
      "subparts": [
        {"name": "Climate"},
        {"name": "Soil"},
        {"name": "Water"},
        {"name": "Sunlight"}
      ]
    },
    {
      "name": "Interactions",
      "subparts": [
        {"name": "Food Chains"},
        {"name": "Symbiosis"},
        {"name": "Competition"}
      ]
    }
  ]
}
```

## Benefits

### Visual Clarity
- **Clearer hierarchy** with distinct brace types
- **Better separation** between different relationship levels
- **Improved readability** for complex structures

### Enhanced Relationships
- **Individual part connections** via secondary braces
- **Detailed subpart relationships** via tertiary braces
- **Comprehensive whole/part mapping**

### Scalability
- **Adaptive spacing** for varying content densities
- **Dynamic positioning** for optimal layout
- **Collision prevention** for complex diagrams

## Migration from 3-Column Layout

The enhanced brace map is **backward compatible** with existing 3-column brace map specifications. The system automatically:

1. **Detects legacy specifications** and applies enhanced layout
2. **Maintains existing functionality** while adding new features
3. **Preserves user preferences** and context

## Future Enhancements

- **Customizable brace styles** (dashed, dotted, etc.)
- **Interactive brace highlighting** on hover
- **Animated brace drawing** for dynamic presentations
- **Export capabilities** for various formats

## Technical Notes

### Performance Optimizations
- **Efficient collision detection** algorithms
- **Optimized rendering** for large datasets
- **Memory-efficient** layout calculations

### Browser Compatibility
- **Modern browsers** (Chrome, Firefox, Safari, Edge)
- **Responsive design** for different screen sizes
- **Accessibility features** for screen readers

## Testing

Use the provided test script to verify the enhanced brace map functionality:

```bash
python test_enhanced_brace_map.py
```

This will generate a test specification and demonstrate the 5-column layout structure.
