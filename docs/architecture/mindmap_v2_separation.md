# Mind map canvas — classic vs v2 separation

Classic mind map canvas remains the **default** (`mindMapCanvasMode: legacy`). V2 chrome
(side toolbar, **Document Summary** (文档总结), orthogonal edges, subtree layout) is **opt-in** when
`FEATURE_MINDMAP_V2_CANVAS=True` and the user selects the new canvas in Language settings.

## Central gate

- `useMindMapV2Chrome()` — UI chrome only
- `readMindMapV2VisualDesignActive()` — layout, geometry, themes, stroke sync in stores/spec loader
- `effectiveMindMapCanvasMode(mode, flag)` — runtime mode with flag forcing legacy when off

## Layout split (baseline c2611060e for classic)

| Mode | Initial loader | Reactive recalc |
|------|----------------|-----------------|
| Legacy | [`mindMapLegacyLayout.ts`](../../frontend/src/stores/specLoader/mindMapLegacyLayout.ts) — column X per depth, top-down Y | [`mindMapLayoutLegacy.ts`](../../frontend/src/stores/diagram/mindMapLayoutLegacy.ts) |
| V2 | [`mindMapV2Layout.ts`](../../frontend/src/stores/specLoader/mindMapV2Layout.ts) — subtree-relative X, symmetric root stacking | [`mindMapLayout.ts`](../../frontend/src/stores/diagram/mindMapLayout.ts) |

Size estimates: [`mindMapMeasurements.ts`](../../frontend/src/stores/specLoader/mindMapMeasurements.ts) branches on mode. Legacy uses [`mindMapLegacyGeometry.ts`](../../frontend/src/config/mindMapLegacyGeometry.ts); v2 uses `MIND_MAP_GEOMETRY`.

## Color split

| Mode | Branches | Topic | Connections |
|------|----------|-------|-------------|
| Legacy | 20 Material hues — `getMindmapBranchColor(i, 'legacy')` / `LEGACY_MINDMAP_BRANCH_COLORS` | Blue pill via `LEGACY_MINDMAP_THEME` (render ignores persisted v2 theme colors) | Per-branch palette, curved edges; topic handles indexed per side, **evenly spaced on the pill** (`classicMindMapTopicHandles.ts`); **Add branch** redistributes clockwise and seeds two children |
| V2 | Unified `mindMapThemes` presets | Theme accent | Unified topic border, orthogonal edges |

Other diagram types (tree map, flow map, …) keep the shared 12 Radix hues in `MINDMAP_BRANCH_COLORS`.

## V2-only surfaces

- **Visual design**: unified connection stroke, `mindMapThemes`, node shapes, `MIND_MAP_GEOMETRY`
- Components: `MindMapSideToolbar`, `MindMapDocumentSummaryPanel` (Document Summary portal; replaces unmounted `FileCenterPanel`), `MindMapDirectionalAddOverlay`, subgraph/collapse overlays
- Store ops (gated): `toggleMindMapCollapse`, `performMindMapDirectionalAdd`, subgraph preview restore/apply

## Shared paths (both modes)

- Tree mutations: `addMindMapBranch`, `moveMindMapBranch`, spec round-trip via `nodesAndConnectionsToMindMapSpec`
- `useAutoComplete`, `generateGraphStream`, backend agents
- Inline recommendations on classic thinking-map toolbars (skipped for v2 in toolbar apps)

## Persisted data (dual buckets)

`_mindmap_canvas.legacy` and `_mindmap_canvas.v2` store independent path-keyed node styles.
Legacy bucket strips `nodeShape`, `backgroundColor`, and `borderColor` (classic render uses palette/theme defaults).
On legacy load, `_mindmap_theme` is cleared.

Mode switch: `reconcileMindMapCanvasModeSwitch` — snapshot outgoing mode, reload spec, restore target bucket, sync strokes.

## Runtime gates checklist

| Behavior | Gate |
|----------|------|
| Side toolbar + Document Summary | `useMindMapV2Chrome` + `FEATURE_KNOWLEDGE_SPACE` |
| Initial layout loader | `readMindMapV2VisualDesignActive` → legacy vs v2 layout file |
| Connection stroke colors | Legacy: `syncLegacyMindMapConnectionStrokeColors`. V2: `syncMindMapConnectionStrokeColors` |
| Orthogonal edges | `getEdgeTypeForDiagram(..., mode)` |
| Column vs subtree recalc | `vueFlowIntegration` + `effectiveMindMapCanvasMode` |
| Node shapes, theme presets | v2 only |
| Collapse / directional add / subgraph | v2 only (`mindMapOps`) |

## Maintainer grep (regression check)

```bash
rg "readMindMapV2VisualDesignActive|useMindMapV2Chrome|MIND_MAP_GEOMETRY|getMindMapThemeForDiagram" \
  frontend/src/stores/specLoader/mindMap.ts \
  frontend/src/stores/diagram/nodeManagement.ts
```

Classic paths in those files should gate v2 imports/calls. Tests: `frontend/tests/mindMapSeparation.spec.ts`, `mindMapColorPalettes.spec.ts`.
