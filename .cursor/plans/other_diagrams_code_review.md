# Other Diagrams - Code Review for Similar Issues

This document reviews flow map, tree map, brace map, bridge map, concept map, and multi-flow map for the same or similar issues fixed in circle/bubble/double-bubble maps.

## Reference: The 7 Issues Fixed (Circle/Bubble/Double-Bubble)

| # | Issue | Root Cause |
|---|-------|------------|
| 1 | Theme word node multi-line display | Need wrap support for long text |
| 2 | Circle map zoom too much, graph incomplete after adding text | No refit after text edit |
| 3 | Bubble map shifts bottom-right after edit | Content-dependent center |
| 4 | Theme bubble not centered when lengthening | Same as #3 + text-adaptive sizing |
| 5 | Long English text exceeds bubble | Fixed max-width, need text-adaptive |
| 6 | Mixed character types cause unwanted wrapping | Need explicit noWrap |
| 7 | Double bubble bubbles inconsistent after edit | Fixed radii, need reload on edit |

---

## 1. Flow Map

**Components**: FlowNode, FlowSubstepNode  
**Spec loader**: flowMap.ts

### Layout
- Uses `DEFAULT_CENTER_X`, `DEFAULT_CENTER_Y` – fixed center
- No content-dependent center shift

### Text handling
- **FlowNode**: `max-width="200px"`, `truncate` – long text gets ellipsis
- **FlowSubstepNode**: `max-width="94px"`, `truncate` – very tight

### Issues found

| Issue | Severity | Details |
|-------|----------|---------|
| **#5-like: Text overflow** | Medium | FlowSubstepNode 94px is very small. Long English (e.g. "Implementation") truncates. FlowNode 200px is better but still fixed. |
| **#6-like: Mixed char wrapping** | Low | Uses `truncate` (single-line ellipsis), not wrap. No explicit `noWrap` – relies on `shouldPreventWrap` (Chinese < 5 chars). Mixed chars may behave inconsistently. |
| **#2-like: No refit after edit** | Low | Flow map layout grows downward/rightward when steps/substeps are added. Editing text doesn't change layout (fixed node dimensions). Refit only needed when structure changes, not text. |

### Recommendations
1. Consider increasing FlowSubstepNode max-width (e.g. 120px) or making it text-adaptive.
2. Add `noWrap` for flow map nodes if single-line is desired (they use truncate, so effectively single-line).
3. No refit needed for flow map text edits (layout is structure-based, not text-based).

---

## 2. Tree Map

**Components**: TopicNode, BranchNode  
**Spec loader**: treeMap.ts (Dagre layout)

### Layout
- Uses Dagre with fixed `NODE_WIDTH`, `NODE_HEIGHT` (120, 50)
- `DEFAULT_CENTER_X` for centering
- Positions computed once at load – no recalculation on text change

### Text handling
- **TopicNode**: `max-width="300px"`, no truncate – text can wrap
- **BranchNode**: `max-width="150px"`, no truncate – text can wrap
- Tree map BranchNode has `min-width: 120px`

### Issues found

| Issue | Severity | Details |
|-------|----------|---------|
| **#2-like: No refit after edit** | Medium | When user edits a node and text wraps to multiple lines, node height can grow. Dagre layout uses fixed dimensions – nodes may overlap or diagram may extend off-view. No refit triggered. |
| **#5-like: Text overflow** | Low | 150px for BranchNode is reasonable. Very long text wraps; with fixed height (50px) from Dagre, text could overflow vertically. |
| **#6-like: Mixed char wrapping** | Low | No `noWrap` – mixed Chinese+English may wrap unexpectedly. Tree map nodes typically benefit from wrap for long labels. |

### Recommendations
1. Add refit after text_updated for tree_map (similar to circle_map).
2. Consider whether tree map needs layout recalculation when text changes (Dagre uses fixed dims – may need recalc if nodes can grow).
3. Add `TREE_MAP_FIT_DELAY` to uiConfig if refit is added.

---

## 3. Brace Map

**Components**: BraceNode  
**Spec loader**: braceMap.ts (Dagre layout)

### Layout
- Uses Dagre with fixed `nodeWidth`, `nodeHeight` (120, 40)
- Horizontal layout (whole → parts → subparts)

### Text handling
- **BraceNode**: `max-width="140px"`, no truncate – text can wrap

### Issues found

| Issue | Severity | Details |
|-------|----------|---------|
| **#2-like: No refit after edit** | Medium | Same as tree map. When text wraps and node grows, layout doesn't update. Diagram may extend off-view. |
| **#5-like: Text overflow** | Low | 140px with wrap. Brace nodes can have short labels (part names). Subparts may need more space. |
| **#6-like: Mixed char wrapping** | Low | No `noWrap`. Part names could be mixed – wrap behavior may be inconsistent. |

### Recommendations
1. Add refit after text_updated for brace_map.
2. Add `BRACE_MAP_FIT_DELAY` to uiConfig.
3. Consider layout recalculation if brace nodes can grow (Dagre uses fixed dims).

---

## 4. Bridge Map

**Components**: BranchNode, LabelNode  
**Spec loader**: bridgeMap.ts

### Layout
- Uses `DEFAULT_CENTER_Y`, `startX = DEFAULT_PADDING + estimatedLabelWidth + gap`
- Label position affects layout – `estimatedLabelWidth = 100` is a guess
- LabelNode has `recalculatePosition()` on text change – good

### Text handling
- **BranchNode**: `max-width="150px"`, no truncate
- **LabelNode**: `max-width="180px"` (dimension), `max-width="200px"` (placeholder) – has `recalculatePosition` on text_updated

### Issues found

| Issue | Severity | Details |
|-------|----------|---------|
| **#3-like: Layout shift** | Low | Bridge map uses `estimatedLabelWidth` for initial layout. LabelNode recalculates its position on edit, but the pair nodes don't shift – gap is maintained. Layout is mostly stable. |
| **#2-like: No refit after edit** | Low | When dimension label or pair text changes, LabelNode recalculates. Diagram bounds may change. Refit could help. |
| **#6-like: Mixed char wrapping** | Low | No `noWrap` on BranchNode. Bridge pairs are typically short (e.g. "猫 : cat"). |

### Recommendations
1. Consider adding refit for bridge_map when LabelNode triggers recalculatePosition (optional).
2. Bridge map is relatively stable – lower priority.

---

## 5. Concept Map

**Components**: ConceptNode  
**Spec loader**: conceptMap.ts

### Layout
- Free-form – user positions nodes by dragging
- No automatic layout centering

### Text handling
- **ConceptNode**: `max-width="300px"` (topic), `150px` (concept), no truncate

### Issues found

| Issue | Severity | Details |
|-------|----------|---------|
| **#2-like: No refit** | N/A | Concept map is free-form. Refit on text edit could be disorienting (user might have positioned nodes deliberately). |
| **#5-like: Text overflow** | Low | 150px for concepts is reasonable. Very long concept names could wrap. |
| **#6-like: Mixed char wrapping** | Low | No `noWrap`. Concept labels often mixed – wrap may be acceptable. |

### Recommendations
1. No refit for concept_map – intentional (free-form layout).
2. Concept map already has special handling (regenerateForNodeIfNeeded for edge labels).
3. Consider `noWrap` for concept nodes if single-line is preferred – likely not critical.

---

## 6. Multi-Flow Map

**Components**: TopicNode, FlowNode  
**Spec loader**: multiFlowMap.ts

### Layout
- Uses `DEFAULT_CENTER_X`, `DEFAULT_CENTER_Y` – fixed center
- Text-adaptive: `topicNodeWidth`, `nodeWidths` for visual balance
- `recalculateMultiFlowMapLayout` uses stored widths

### Text handling
- **TopicNode**: `max-width="300px"`, has `@width-change` – stores width for layout
- **FlowNode**: `max-width="200px"`, `truncate`, has `@width-change` – stores width for balance

### Issues found

| Issue | Severity | Details |
|-------|----------|---------|
| **#2-like: No refit after edit** | Medium | When topic or cause/effect text changes, `multi_flow_map:node_width_changed` fires. Layout recalculates. But no `fitDiagram` is triggered – diagram may extend off-view if new layout is larger. |
| **#5-like: Text overflow** | Low | FlowNode uses truncate. TopicNode and FlowNode store width – layout adapts. Good. |
| **#6-like: Mixed char wrapping** | Low | Uses truncate (single-line). |

### Recommendations
1. Add refit after text_updated for multi_flow_map when layout recalculates.
2. Add `MULTI_FLOW_MAP_FIT_DELAY` to uiConfig.
3. Trigger refit when `multi_flow_map:topic_width_changed` or `multi_flow_map:node_width_changed` causes significant layout change (or always refit on text_updated for multi_flow_map).

---

## Summary Table

| Diagram | Refit needed? | Layout shift risk? | Text overflow risk? | Mixed-char wrap? |
|---------|---------------|--------------------|---------------------|------------------|
| Flow map | No (structure-based) | No (fixed center) | Medium (substep 94px) | Low |
| Tree map | Yes | Low (Dagre fixed) | Low | Low |
| Brace map | Yes | Low (Dagre fixed) | Low | Low |
| Bridge map | Optional | Low (LabelNode recalc) | Low | Low |
| Concept map | No (free-form) | N/A | Low | Low |
| Multi-flow map | Yes | No (fixed center) | Low | Low |

---

## Recommended Implementation Order

1. **Multi-flow map refit** – Layout recalculates on text change; refit ensures diagram stays visible.
2. **Tree map refit** – Node text wrap can grow nodes; refit helps.
3. **Brace map refit** – Same as tree map.
4. **FlowSubstepNode max-width** – Consider increasing from 94px to 120px for long English.
5. **Bridge map refit** (optional) – Lower priority.

---

## Implementation Notes

### For refit (tree_map, brace_map, multi_flow_map)

In DiagramCanvas.vue `node:text_updated` handler, add:

```typescript
if (diagramStore.type === 'tree_map') {
  setTimeout(() => fitDiagram(true), ANIMATION.TREE_MAP_FIT_DELAY)
}
if (diagramStore.type === 'brace_map') {
  setTimeout(() => fitDiagram(true), ANIMATION.BRACE_MAP_FIT_DELAY)
}
if (diagramStore.type === 'multi_flow_map') {
  setTimeout(() => fitDiagram(true), ANIMATION.MULTI_FLOW_MAP_FIT_DELAY)
}
```

In uiConfig.ts, add:

```typescript
TREE_MAP_FIT_DELAY: 180,
BRACE_MAP_FIT_DELAY: 180,
MULTI_FLOW_MAP_FIT_DELAY: 180,
```

### For FlowSubstepNode

Consider changing `max-width="94px"` to `max-width="120px"` or making it dynamic based on content (like FlowNode's width-change pattern).
