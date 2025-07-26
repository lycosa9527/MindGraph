# Graph Specs Guide

> **Note:** Playwright is now used for headless browser rendering in the backend (for PNG export), replacing Pyppeteer.

This document describes the JSON schema and validation rules for each supported graph type in the D3.js-based graph generation application.

## Double Bubble Map
```json
{
  "left": "Topic1",
  "right": "Topic2",
  "similarities": ["Feature1", "Feature2"],
  "left_differences": ["Unique1"],
  "right_differences": ["Unique2"]
}
```

## Bubble Map
```json
{
  "topic": "Topic",
  "left": ["Feature1", "Feature2"],
  "right": ["Feature3", "Feature4"]
}
```

## Circle Map
```json
{
  "topic": "Topic",
  "characteristics": ["Feature1", "Feature2"]
}
```

## Tree Map
```json
{
  "topic": "Topic",
  "children": [
    {"name": "Subtopic1", "children": [{"name": "Subtopic1.1"}]}
  ]
}
```

## Concept Map
```json
{
  "topic": "Topic",
  "concepts": [
    {"name": "Concept1", "children": [{"name": "Concept1.1"}]}
  ]
}
```

## Mindmap
```json
{
  "topic": "Topic",
  "children": [
    {"name": "Subtopic1", "children": [{"name": "Subtopic1.1"}]}
  ]
}
```

Each type has a corresponding `validate_<type>(spec)` function in `graph_specs.py`. 