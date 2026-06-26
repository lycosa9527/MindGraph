# Mind map canvas — classic vs v2 separation

Classic mind map canvas remains the **default** (`mindMapCanvasMode: legacy`). V2 chrome
(side toolbar, File Center, orthogonal edges, column layout v2) is **opt-in** when
`FEATURE_MINDMAP_V2_CANVAS=True` and the user selects the new canvas in Language settings.

## Central gate

`useMindMapV2Chrome()` — `isMindMapDiagramType(type) && effectiveMindMapCanvasMode(mode, flag) === 'v2'`

## V2-only surfaces (safe to evolve independently)

- **Visual design**: unified connection stroke (topic border color), `mindMapThemes` presets,
  node shapes (rectangle / oval / underline), `MIND_MAP_GEOMETRY` typography and padding
- Components: `canvas/MindMapSideToolbar.vue`, `MindMapSidePanel.vue`, `FileCenterPanel.vue`,
  `MindMapOneSentencePanel.vue`, `MindMapWaterfallPanel.vue`, `diagram/MindMap*` overlays
- Composables: `composables/mindMap/*`, `composables/fileCenter/*`,
  `useMindMapRagBranchExpand`, `useMindMapSubgraphSuggest` (UI gated in `DiagramCanvas`)
- Store branches: `recalculateMindMapV2ColumnPositions`, `mindmapOrthogonal` edges when mode is v2

## Shared paths (both modes)

- `useAutoComplete`, `generateGraphStream`, backend `workflow.py` / `generate_pipeline.py`
- Inline recommendations on classic thinking-map toolbars (skipped for v2 mind maps in toolbar apps)
- Classic layout: `recalculateMindMapLegacyColumnPositions`, curved edges when mode is legacy
- Classic visuals: pill-shaped nodes, per-branch palette colors (`getMindmapBranchColor`), indexed topic handles

## Persisted data (dual buckets)

`_mindmap_canvas.legacy` and `_mindmap_canvas.v2` store independent path-keyed node styles.
Mode switch runs `reconcileMindMapCanvasModeSwitch`: snapshot outgoing mode, reload spec for
handles/layout, restore target bucket, sync connection colors. Saved via `getSpecForSave`.

On load, `hydrateMindMapCanvasStylesOnLoad` applies the bucket for the active UI mode after
`loadFromSpec` assigns diagram data (fixes stale `_node_styles` when mode differs from save time).

## Runtime gates checklist

| Behavior | Gate |
|----------|------|
| Side toolbar + File Center | `useMindMapV2Chrome` |
| Connection stroke colors | Legacy: per-branch palette via `syncLegacyMindMapConnectionStrokeColors` / `resolveLegacyMindMapConnectionStrokeColor`. V2: unified topic border via `syncMindMapConnectionStrokeColors`. Mode switch: `diagramStore.resyncMindMapConnectionStrokeColors()` |
| RAG auto branch expand | v2 + `FEATURE_KNOWLEDGE_SPACE` + saved diagram |
| Orthogonal edges | `getEdgeTypeForDiagram(..., mindMapCanvasMode)` |
| Column layout | `vueFlowIntegration` branches on canvas mode |
| Node shapes, theme presets | `readMindMapV2VisualDesignActive` / `useMindMapV2Chrome` |
| Connection stroke colors | Legacy: per-branch palette. V2: unified topic border. Resync on mode change via `resyncMindMapConnectionStrokeColorsForActiveMode` |
