# Root Cause Analysis: Mind Map Layout Wrong After Branch Move

## Symptom
After dragging a child node to another branch, the left side curves become very short. Switching to another AI model and back makes the layout correct again.

## Key Insight
When switching models, we **load a different diagram** (the original model's result). The "correct" layout = original diagram. The move produces wrong layout. Switching reverts the move and shows the original.

## Code Path Comparison

### Move path (wrong layout)
1. `moveMindMapBranch` → `nodesAndConnectionsToMindMapSpec` → modify spec
2. `loadMindMapSpec({ topic, leftBranches, rightBranches, preserveLeftRight: true })`
3. Layout runs, normalize runs (once)
4. **Mutate** `data.value.nodes = result.nodes` (same data.value object)

### Switch model path (correct layout)
1. `loadFromSpec(spec, diagramType)` with LLM spec
2. `loadSpecForDiagramType` → `loadMindMapSpec`
3. Layout runs, normalize runs (once inside loadMindMapSpec)
4. **Second normalize** in loadFromSpec
5. **Replace** `data.value = { ... }` (new object)
6. Emit `diagram:loaded`

## Hypotheses

### 1. Data mutation vs replacement
Move mutates `data.value.nodes`; switch replaces entire `data.value`. Vue Flow may not fully refresh when the parent object reference stays the same.

### 2. Missing diagram:loaded
Move does not emit `diagram:loaded`. Various listeners (clearNodePaletteState, useInlineRecommendationsCoordinator, useNodePalette) may affect rendering.

### 3. Normalize not the root cause
Expand/shrink fixes in normalize did not work. The issue may be earlier (layout) or in how Vue Flow receives updates.

### 4. Vue Flow internal state
Vue Flow may cache node positions/dimensions. Full object replacement could invalidate cache; mutation might not.

## Fix applied
1. **Replace `data.value` entirely** (like loadFromSpec) instead of mutating `data.value.nodes`
2. **Emit `diagram:loaded`** so listeners (clearNodePaletteState, etc.) run and Vue Flow gets a full refresh signal

This mirrors the switch-model path so the move path should behave the same.
