---
name: Refactor diagram.ts store
overview: Split the 3406-line `diagram.ts` Pinia store into ~15 focused modules using a "slice" pattern, while preserving the single `useDiagramStore` public API that 35+ consumer files depend on.
todos:
  - id: phase1-types
    content: Extract types.ts, constants.ts, events.ts into stores/diagram/ -- foundation modules with no behavior change
    status: pending
  - id: phase2-cross-cutting
    content: "Extract cross-cutting slices: history, selection, customPositions, nodeStyles, copyPaste, titleManagement, learningSheet"
    status: pending
  - id: phase3-diagram-ops
    content: "Extract diagram-type operation modules: mindMapOps, flowMapOps, treeMapOps, braceMapOps, bubbleMapOps, doubleBubbleMapOps"
    status: pending
  - id: phase4-heavy
    content: "Extract remaining heavy modules: nodeManagement, connectionManagement, vueFlowIntegration, specIO, nodeSwapOps, multiFlowLayout"
    status: pending
  - id: phase5-cleanup
    content: Slim diagram.ts to ~400-500 lines, fix ContextMenu.vue direct mutation, verify all 35+ consumers
    status: pending
isProject: false
---

# Refactor `diagram.ts` into Modular Slices

## Problem

`[frontend/src/stores/diagram.ts](frontend/src/stores/diagram.ts)` is 3406 lines -- 4x the 600-800 line max. It contains **18 logical domains** (mind map ops, tree map ops, flow map ops, history, selection, styles, etc.) all in a single Composition API Pinia store.

## Constraints

- **35+ consumer files** import `useDiagramStore` -- the public API must not change
- The store uses Pinia's Composition API (`defineStore('diagram', () => {...})`)
- Some slices have cross-dependencies (e.g., `removeNode` calls `buildFlowMapSpecFromNodes` and `loadFromSpec`; `addBraceMapPart` calls `addNode`, `addConnection`, `pushHistory`)
- The existing `specLoader/` subdirectory already demonstrates a per-diagram-type module pattern

## Strategy: Context-Based Slice Pattern

Each module exports a factory function that receives a shared context object containing core state and cross-cutting operations. The main `diagram.ts` creates the context, calls each slice, and returns a flat API.

```typescript
// Pattern for each slice module
export function useMindMapOps(ctx: DiagramContext) {
  function addMindMapBranch(...) { /* uses ctx.data, ctx.pushHistory, ctx.emitEvent */ }
  function addMindMapChild(...) { ... }
  return { addMindMapBranch, addMindMapChild, ... }
}
```

```typescript
// Main diagram.ts wiring
export const useDiagramStore = defineStore('diagram', () => {
  // Core state (refs)
  const data = ref<DiagramData>(...)
  // ...

  // Build context (two-phase: create then fill cross-deps)
  const ctx: DiagramContext = { data, type, ... } as DiagramContext

  // Initialize slices
  const historySlice = useHistorySlice(ctx)
  ctx.pushHistory = historySlice.pushHistory  // fill cross-dep

  const mindMapSlice = useMindMapOps(ctx)
  // ... etc

  return { ...historySlice, ...mindMapSlice, ... }
})
```

## New File Structure

```
stores/
  diagram.ts                 (~400-500 lines) -- core state + wiring
  diagram/
    types.ts                 (~50 lines)  -- DiagramContext, DiagramEvent, DiagramEventType
    constants.ts             (~60 lines)  -- VALID_DIAGRAM_TYPES, MAX_HISTORY_SIZE, PLACEHOLDER_TEXTS
    events.ts                (~80 lines)  -- emitEvent, subscribeToDiagramEvents, getEdgeTypeForDiagram, getMindMapCurveExtents
    history.ts               (~70 lines)  -- pushHistory, undo, redo, clearHistory, canUndo, canRedo
    selection.ts             (~50 lines)  -- selectNodes, clearSelection, addToSelection, removeFromSelection, hasSelection, selectedNodeData
    nodeManagement.ts        (~250 lines) -- addNode, updateNode, removeNode, emptyNode
    connectionManagement.ts  (~80 lines)  -- addConnection, updateConnectionLabel, updateConnectionArrowheadsForNode, toggleConnectionArrowhead
    learningSheet.ts         (~120 lines) -- isLearningSheet, hiddenAnswers, emptyNodeForLearningSheet, setLearningSheetMode, restoreFromLearningSheetMode, applyLearningSheetView, hasPreservedLearningSheet
    copyPaste.ts             (~40 lines)  -- copySelectedNodes, pasteNodesAt, canPaste
    customPositions.ts       (~60 lines)  -- saveCustomPosition, hasCustomPosition, getCustomPosition, clearCustomPosition, resetToAutoLayout
    nodeStyles.ts            (~100 lines) -- saveNodeStyle, getNodeStyle, clearNodeStyle, clearAllNodeStyles, applyStylePreset
    titleManagement.ts       (~70 lines)  -- getTopicNodeText, effectiveTitle, setTitle, initTitle, resetTitle, shouldAutoUpdateTitle
    vueFlowIntegration.ts    (~200 lines) -- vueFlowNodes, vueFlowEdges, updateNodePosition, updateNodesFromVueFlow, syncFromVueFlow, circleMapLayoutNodes
    specIO.ts                (~300 lines) -- loadFromSpec, loadDefaultTemplate, getSpecForSave, mergeGranularUpdate, getDoubleBubbleSpecFromData, buildFlowMapSpecFromNodes, buildTreeMapSpecFromNodes
    mindMapOps.ts            (~300 lines) -- addMindMapBranch, addMindMapChild, removeMindMapNodes, getMindMapDescendantIds, moveMindMapBranch
    flowMapOps.ts            (~150 lines) -- toggleFlowMapOrientation, addFlowMapStep, addFlowMapSubstep
    treeMapOps.ts            (~250 lines) -- removeTreeMapNodes, getTreeMapDescendantIds, moveTreeMapBranch, addTreeMapCategory, addTreeMapChild
    braceMapOps.ts           (~120 lines) -- addBraceMapPart, removeBraceMapNodes
    bubbleMapOps.ts          (~50 lines)  -- removeBubbleMapNodes
    doubleBubbleMapOps.ts    (~80 lines)  -- addDoubleBubbleMapNode, removeDoubleBubbleMapNodes
    nodeSwapOps.ts           (~500 lines) -- getNodeGroupIds, moveNodeBySwap, swapBubbleMapNodes, swapCircleMapNodes, swapDoubleBubbleMapNodes, swapFlowMapNodes, moveFlowMapNode, swapMultiFlowMapNodes, swapBraceMapNodes, moveBraceMapNode, swapBridgeMapPairs
    multiFlowLayout.ts       (~30 lines)  -- setTopicNodeWidth, setNodeWidth
    index.ts                 (~20 lines)  -- barrel re-export of DiagramContext type
```

## Execution Phases

### Phase 1: Foundation (low risk, no behavior change)

Extract types, constants, and the event system into `diagram/types.ts`, `diagram/constants.ts`, and `diagram/events.ts`. Update imports in `diagram.ts`. Verify nothing breaks.

### Phase 2: Cross-cutting concerns (medium risk)

Extract history, selection, custom positions, node styles, copy/paste, title, and learning sheet slices. These have minimal cross-dependencies and are self-contained. Wire them through `DiagramContext`.

### Phase 3: Diagram-type-specific operations (medium risk)

Extract per-diagram-type operation modules: mindMapOps, treeMapOps, flowMapOps, braceMapOps, bubbleMapOps, doubleBubbleMapOps. These depend on `pushHistory`, `emitEvent`, `loadFromSpec`, etc., which are available via context.

### Phase 4: Remaining heavy modules (higher risk)

Extract nodeManagement (has complex `removeNode` with diagram-type branching), connectionManagement, vueFlowIntegration, specIO, and nodeSwapOps. These have the most cross-dependencies and need careful wiring.

### Phase 5: Final cleanup

- Slim `diagram.ts` to ~400-500 lines (state definitions + context wiring + return)
- Update `[stores/index.ts](frontend/src/stores/index.ts)` if needed (currently re-exports from `./diagram`)
- Fix the direct mutation in `ContextMenu.vue` (`data.connections.push(...)`) -- replace with a store action
- Verify all 35+ consumer files still work

## Key Risk: Cross-Slice Dependencies

The trickiest part is that some operations call others across domains. The main cases:

- `removeNode` dispatches to `buildFlowMapSpecFromNodes`, `loadFromSpec`, `removeBubbleMapNodes`, etc. based on diagram type
- `addBraceMapPart` calls `addNode`, `addConnection`, `pushHistory`
- `moveMindMapBranch` calls `loadMindMapSpec`, `getMindMapCurveExtents`, `useInlineRecommendationsStore`
- `loadFromSpec` calls `recalculateBubbleMapLayout`, `normalizeMindMapHorizontalSymmetry`, `setDiagramType`

The `DiagramContext` pattern handles this by making these functions available on the context object. The main `diagram.ts` fills in the context after creating all slices (two-phase initialization).

## What Does NOT Change

- `useDiagramStore` name and return type (all 35+ consumers unaffected)
- `subscribeToDiagramEvents` export
- `DiagramEventType` / `DiagramEvent` type exports
- All store state, actions, and getters remain accessible at the same paths
- `stores/index.ts` barrel re-exports remain identical

