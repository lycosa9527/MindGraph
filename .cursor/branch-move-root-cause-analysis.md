# Branch Move "Nothing Happens" - Root Cause Analysis

## Summary

When clicking and holding on a mind map branch node, the branch move feature does not trigger. This analysis traces the event flow and identifies the root cause.

---

## 1. Diagram Settings (Mind Map)

**Location**: `frontend/src/stores/diagram.ts` lines 310-326

```typescript
if (diagramType === 'mindmap' || diagramType === 'mind_map') {
  // ...
  vueFlowNode.draggable = false  // Per-node override
}
```

**Vue Flow props** (`DiagramCanvas.vue` line 1219):
- `:nodes-draggable="!props.handToolActive"` — Global: true when hand tool off
- Per-node `draggable: false` overrides this for mind map nodes

**Conclusion**: Mind map nodes are correctly non-draggable. This is NOT blocking our custom handler.

---

## 2. Event Flow: Mousedown on Branch Node

**Component hierarchy**:
```
DiagramCanvas (provide branchMove)
  └── VueFlow
        └── NodeRenderer
              └── .vue-flow__node (Vue Flow wrapper)
                    └── BranchNode (our component)
                          └── div.branch-node @mousedown
                                └── InlineEditableText @mousedown
                                      └── span (display text)
```

**Event order when user clicks on text**:
1. **Target**: span (display text) or InlineEditableText div
2. **Bubble phase**: span → InlineEditableText div → BranchNode div → vue-flow__node → ...

**InlineEditableText** (`InlineEditableText.vue` lines 351-355, 387-388):
- Has `@mousedown="handleMouseDown"` on root div
- `handleMouseDown`: only calls `event.stopPropagation()` when `localIsEditing` (editing mode)
- When NOT editing: event bubbles to BranchNode — OK

**Root cause candidate**: Vue Flow's `.vue-flow__node` wrapper likely attaches mousedown handlers for:
- Selection (`elements-selectable`)
- Drag initiation (when draggable)

When `nodes-draggable` is true globally, Vue Flow may attach handlers to the node wrapper. Even with per-node `draggable: false`, the wrapper may still capture mousedown for selection or other logic. If Vue Flow uses **capture phase** or **pointer capture**, it can run before our bubble-phase handler and potentially consume the event.

---

## 3. Provide/Inject

- DiagramCanvas provides `branchMove`
- BranchNode injects it
- Nodes are descendants of DiagramCanvas (no Teleport for nodes)
- **Conclusion**: Provide/inject should work. CurvedEdge uses same pattern for CONCEPT_MAP_GENERATING_KEY.

---

## 4. Root Cause

**Most likely**: Vue Flow's node wrapper handles mousedown (for selection or drag) and runs before or instead of our handler. Our `@mousedown` on BranchNode runs in the **bubble phase**. If Vue Flow uses capture or consumes the event, we never receive it.

**Fix**: Use `@mousedown.capture` on BranchNode so our handler runs in the **capture phase** before Vue Flow's handlers. We can then start our 2s timer without stopping propagation (so selection still works on quick click).

---

## 5. Additional Safeguard: nodes-draggable for Mind Map

The user said "this drag should really be limited to the nodes we are holding". Currently:
- `nodes-draggable` is global (all diagram types)
- Mind map overrides per-node to `draggable: false`

**Recommendation**: For mind map, consider passing `nodes-draggable="false"` when diagram type is mindmap, so Vue Flow does not attach any drag-related handlers. Our long-press handles branch move entirely.

---

## 6. Recommended Fixes

1. **Use `@mousedown.capture`** on BranchNode — run in capture phase before Vue Flow
2. **Optionally**: When `diagramStore.type` is mindmap, pass `:nodes-draggable="false"` to VueFlow (redundant with per-node but ensures no global handlers)
3. **Verify**: Add temporary `console.log` in `handleBranchMovePointerDown` to confirm it fires

---

# Curve Length Asymmetry After Branch Move - Root Cause Analysis

## Summary

After moving a branch (e.g. from right to left), left and right curve extents become asymmetric (e.g. left: 457.4, right: 442.6 instead of 450, 450). The `extentDiff` in logs is ~14.83.

## Root Cause

**The scale formulas in `normalizeMindMapHorizontalSymmetry` use `node.position.x` (the left edge of the node) but extent is measured from center to node center.**

- **Extent** = distance from canvas center to the node's center: `centerX - (position.x + NODE_WIDTH/2)` for left
- **Current formula** scales `(centerX - position.x)` for left = extent + NODE_WIDTH/2
- **Effect**: Left nodes get over-scaled by NODE_WIDTH/2 × (scale - 1) ≈ 7.4px; right nodes get under-scaled by the same amount
- **Result**: Left extent ≈ 457.4, right extent ≈ 442.6 (extentDiff ≈ 14.8)

## Fix

Scale based on node **center**, not left edge:

```typescript
// For left:
const center = node.position.x + DEFAULT_NODE_WIDTH / 2
const distFromCenter = centerX - center
const newCenter = centerX - distFromCenter * scale
node.position.x = newCenter - DEFAULT_NODE_WIDTH / 2

// For right:
const center = node.position.x + DEFAULT_NODE_WIDTH / 2
const distFromCenter = center - centerX
const newCenter = centerX + distFromCenter * scale
node.position.x = newCenter - DEFAULT_NODE_WIDTH / 2
```

Apply this pattern to all 4 scale operations in `normalizeMindMapHorizontalSymmetry`: scale-up block, leftExpanded, rightExpanded, and both shrink blocks.

---

## Left Curves Appear Shorter Than Right (Unresolved)

**Symptom**: Even with equal extents (extentDiff ≈ 0), left curves look shorter than right.

**Diagnostic logs added** (enable CurvedEdge via `window.__DEBUG_CURVE_LENGTH__ = true`):
1. **Frontend - [CurveDebug] layout before normalize**: leftExtentRaw, rightExtentRaw, leftMinCenterX, rightMaxCenterX
2. **Frontend - [CurveDebug] normalize before/after**: leftExtent, rightExtent, extentDiff
3. **Frontend - [CurveDebug] topic-to-branch** (when `window.__DEBUG_CURVE_LENGTH__`): sourceX, targetX, horizontalSpan, side per topic→branch edge
4. **Frontend - [CurveDebug] branch-to-child** (when `window.__DEBUG_CURVE_LENGTH__`): sourceX, targetX, horizontalSpan, side per branch→child edge
5. **Frontend - [CurveDebug] branch-to-child spans** (always): leftMin/Max/Avg, rightMin/Max/Avg, leftCount, rightCount
6. **Backend - [CurveDebug]**: left_branches_x, right_branches_x (logger.debug)

**Root cause (branch-to-child)**: Layout produces asymmetric spans (left 224.72 vs right 240). Fix: `normalizeBranchToChildSpans` scales the shorter side's children relative to their parents to match. Extent normalize was changed to expand the smaller side (instead of shrinking the larger) so it doesn't undo the branch-to-child fix.
