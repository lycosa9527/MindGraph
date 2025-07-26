# Thinking Maps Guide

Based on the official Thinking Maps® methodology developed by David Hyerle, this guide explains the 8 fundamental thinking maps and their proper data structures for use with D3.js rendering.

## Overview

Thinking Maps® are consistent visual patterns linked directly to eight specific thought processes. They help visualize abstract thoughts to reach higher levels of critical and creative thinking. Each map corresponds to a fundamental cognitive skill.

## The 8 Thinking Maps

### 1. Circle Map - For Defining in Context
**Cognitive Process**: Defining in context

**Purpose**: Used for brainstorming and defining a topic in context. The central circle contains the main topic, and the outer circle contains context information.

**Data Structure**:
```json
{
  "topic": "Main topic or concept",
  "context": [
    "Context item 1",
    "Context item 2",
    "Context item 3"
  ]
}
```

**Example**:
```json
{
  "topic": "Photosynthesis",
  "context": [
    "Plants use sunlight",
    "Converts CO2 to oxygen",
    "Process in chloroplasts",
    "Essential for life on Earth"
  ]
}
```

### 2. Bubble Map - For Describing Attributes
**Cognitive Process**: Describing attributes

**Purpose**: Used to describe a topic using adjectives and descriptive phrases. The central bubble contains the topic, and surrounding bubbles contain descriptive attributes.

**Data Structure**:
```json
{
  "topic": "Main topic or object",
  "attributes": [
    "Attribute 1",
    "Attribute 2",
    "Attribute 3"
  ]
}
```

**Example**:
```json
{
  "topic": "Ocean",
  "attributes": [
    "Deep",
    "Salty",
    "Blue",
    "Vast",
    "Mysterious",
    "Home to marine life"
  ]
}
```

### 3. Double Bubble Map - For Comparing and Contrasting
**Cognitive Process**: Comparing and contrasting

**Purpose**: Used to compare and contrast two topics. Similarities are placed in bubbles between the two main topics, while differences are placed in bubbles connected to each individual topic.

**Data Structure**:
```json
{
  "left": "First topic",
  "right": "Second topic",
  "similarities": [
    "Similarity 1",
    "Similarity 2",
    "Similarity 3"
  ],
  "left_differences": [
    "Difference unique to left topic 1",
    "Difference unique to left topic 2"
  ],
  "right_differences": [
    "Difference unique to right topic 1",
    "Difference unique to right topic 2"
  ]
}
```

**Example**:
```json
{
  "left": "Dogs",
  "right": "Cats",
  "similarities": [
    "Mammals",
    "Domestic pets",
    "Have four legs",
    "Carnivores"
  ],
  "left_differences": [
    "Bark",
    "Pack animals",
    "Need regular walks"
  ],
  "right_differences": [
    "Meow",
    "Independent",
    "Use litter box"
  ]
}
```

### 4. Tree Map - For Categorizing
**Cognitive Process**: Classifying

**Purpose**: Used for classifying and categorizing information. The main category is at the top, with subcategories below, and specific examples under each subcategory.

**Data Structure**:
```json
{
  "topic": "Main category",
  "children": [
    {
      "id": "subcategory1",
      "label": "Subcategory 1",
      "children": [
        {
          "id": "example1",
          "label": "Example 1"
        },
        {
          "id": "example2",
          "label": "Example 2"
        }
      ]
    },
    {
      "id": "subcategory2",
      "label": "Subcategory 2",
      "children": [
        {
          "id": "example3",
          "label": "Example 3"
        }
      ]
    }
  ]
}
```

**Example**:
```json
{
  "topic": "Animals",
  "children": [
    {
      "id": "mammals",
      "label": "Mammals",
      "children": [
        {"id": "dog", "label": "Dog"},
        {"id": "cat", "label": "Cat"},
        {"id": "elephant", "label": "Elephant"}
      ]
    },
    {
      "id": "birds",
      "label": "Birds",
      "children": [
        {"id": "eagle", "label": "Eagle"},
        {"id": "sparrow", "label": "Sparrow"}
      ]
    }
  ]
}
```

### 5. Brace Map - For Whole/Part Relationships
**Cognitive Process**: Part-whole spatial reasoning

**Purpose**: Used to analyze physical objects by breaking them down into parts and subparts. The whole object is on the left, with parts and subparts branching to the right.

**Data Structure**:
```json
{
  "main_topic": "Whole object or concept",
  "parts": [
    "Part 1",
    "Part 2",
    "Part 3"
  ]
}
```

**Example**:
```json
{
  "main_topic": "Computer",
  "parts": [
    "Monitor",
    "Keyboard",
    "Mouse",
    "CPU",
    "Speakers"
  ]
}
```

### 6. Flow Map - For Sequencing
**Cognitive Process**: Sequencing

**Purpose**: Used for sequencing and ordering information. Shows the stages and substages of an event or process in chronological order.

**Data Structure**:
```json
{
  "title": "Process or event name",
  "steps": [
    "Step 1",
    "Step 2",
    "Step 3",
    "Step 4"
  ]
}
```

**Example**:
```json
{
  "title": "Water Cycle",
  "steps": [
    "Evaporation",
    "Condensation",
    "Precipitation",
    "Collection"
  ]
}
```

### 7. Multi-Flow Map - For Cause and Effect
**Cognitive Process**: Cause and effect reasoning

**Purpose**: Used to show cause and effect relationships. The central event is in the middle, with causes on the left and effects on the right.

**Data Structure**:
```json
{
  "event": "Central event or situation",
  "causes": [
    "Cause 1",
    "Cause 2",
    "Cause 3"
  ],
  "effects": [
    "Effect 1",
    "Effect 2",
    "Effect 3"
  ]
}
```

**Example**:
```json
{
  "event": "Global Warming",
  "causes": [
    "Burning fossil fuels",
    "Deforestation",
    "Industrial emissions",
    "Vehicle emissions"
  ],
  "effects": [
    "Rising temperatures",
    "Melting ice caps",
    "Sea level rise",
    "Extreme weather events"
  ]
}
```

### 8. Bridge Map - For Analogies
**Cognitive Process**: Reasoning by analogy

**Purpose**: Used to show analogies and similarities between relationships. The relating factor is fixed as "as" (standard bridge map format), with pairs of related items in the format a:b, c:d, e:f, etc.

**Data Structure**:
```json
{
  "relating_factor": "relationship word or phrase",
  "analogies": [
    {
      "left": "First item in analogy pair",
      "right": "Second item in analogy pair",
      "id": 0
    }
  ]
}
```

**Example**:
```json
{
  "relating_factor": "as",
  "analogies": [
    {
      "left": "手",
      "right": "手套",
      "id": 0
    },
    {
      "left": "脚",
      "right": "袜子",
      "id": 1
    },
    {
      "left": "头",
      "right": "帽子",
      "id": 2
    }
  ]
}
```



## Implementation Notes

### Validation
Each thinking map type has a corresponding validation function in `graph_specs.py` that ensures:
- Required fields are present
- Data types are correct
- Content limits are reasonable
- Nested structures are valid

### Rendering
The D3.js renderer should interpret each map type according to its visual pattern:
- **Circle Map**: Concentric circles
- **Bubble Map**: Central bubble with surrounding attribute bubbles
- **Double Bubble Map**: Two main bubbles with connecting similarity bubbles
- **Tree Map**: Hierarchical tree structure
- **Brace Map**: Left-to-right part breakdown
- **Flow Map**: Sequential flow from left to right
- **Multi-Flow Map**: Central event with causes (left) and effects (right)
- **Bridge Map**: Bridge structure with pairs on either side

### Educational Benefits
Thinking Maps help students:
- Develop critical thinking skills
- Organize information visually
- Make connections between concepts
- Improve comprehension and retention
- Build cognitive processing skills

## References

- [Mindomo Blog - What is a thinking map?](https://www.mindomo.com/blog/thinking-map/)
- [Pedagogy of Confidence - Thinking Maps®](https://pedagogyofconfidence.net/thinking-maps/)
- Thinking Maps® methodology developed by David Hyerle 