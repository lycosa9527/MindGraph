# Mind map canvas — classic vs v2 separation

Classic mind map canvas remains the **default** (`mindMapCanvasMode: legacy`). V2 chrome
(side toolbar, File Center, orthogonal edges, column layout v2) is **opt-in** via Language
settings.

## Central gate

`useMindMapV2Chrome()` — `isMindMapDiagramType(type) && ui.mindMapCanvasMode === 'v2'`

## V2-only surfaces (safe to evolve independently)

- Components: `canvas/MindMapSideToolbar.vue`, `MindMapSidePanel.vue`, `FileCenterPanel.vue`,
  `MindMapOneSentencePanel.vue`, `MindMapWaterfallPanel.vue`, `diagram/MindMap*` overlays
- Composables: `composables/mindMap/*`, `composables/fileCenter/*`,
  `useMindMapRagBranchExpand`, `useMindMapSubgraphSuggest` (UI gated in `DiagramCanvas`)
- Store branches: `recalculateMindMapV2ColumnPositions`, `mindmapOrthogonal` edges when mode is v2

## Shared paths (both modes)

- `useAutoComplete`, `generateGraphStream`, backend `workflow.py` / `generate_pipeline.py`
- Inline recommendations on classic thinking-map toolbars (skipped for v2 mind maps in toolbar apps)
- Classic layout: `recalculateMindMapLegacyColumnPositions`, curved edges when mode is legacy

## Runtime gates checklist

| Behavior | Gate |
|----------|------|
| Side toolbar + File Center | `useMindMapV2Chrome` |
| RAG auto branch expand | v2 + `FEATURE_KNOWLEDGE_SPACE` + saved diagram |
| Orthogonal edges | `getEdgeTypeForDiagram(..., mindMapCanvasMode)` |
| Column layout | `vueFlowIntegration` branches on canvas mode |
