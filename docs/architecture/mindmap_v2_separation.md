# Mind map canvas — classic vs v2 separation

New (v2) mind map canvas is the **default** (`mindMapCanvasMode: v2`) when
`FEATURE_MINDMAP_V2_CANVAS=True` (on by default). V2 chrome includes side toolbar,
**Document Summary** (文档总结), orthogonal edges, and subtree layout. Classic canvas
(`legacy`) remains available via Language settings; set `FEATURE_MINDMAP_V2_CANVAS=False`
to force classic-only.

## Canvas component split (lazy-loaded shells)

Mind maps mount through **`DiagramCanvasHost`** → **`MindMapCanvasRouter`**, which
lazy-loads exactly one shell:

| Shell | Chunk | Edge registry | Overlays |
|-------|-------|---------------|----------|
| `MindMapLegacyCanvas` | classic | `diagramCanvasEdgeTypesLegacy` (curved only) | none |
| `MindMapV2Canvas` | v2 | `diagramCanvasEdgeTypesMindMapV2` (+ orthogonal) | `MindMapV2CanvasOverlays` |

Each shell passes `mindMapVariant` into `DiagramCanvas` and **`provide`s
`MIND_MAP_CANVAS_VARIANT_KEY`** so `TopicNode` / `BranchNode` use
`useMindMapCanvasVisuals()` instead of re-resolving from the store on first paint.

Non–mind-map types still mount `DiagramCanvas` directly (showcase, export-render, etc.).

Mode switch in Language settings remounts the active shell (`:key` on router).

### Node component split (lazy-loaded)

`TopicNode` and `BranchNode` remain the Vue Flow registry entry points but are thin routers:

| Router | Legacy chunk | V2 chunk | Other types |
|--------|--------------|----------|-------------|
| `TopicNode.vue` | `mindMap/MindMapLegacyTopicNode.vue` | `mindMap/MindMapV2TopicNode.vue` | `TopicNodeDiagram.vue` |
| `BranchNode.vue` | `mindMap/MindMapLegacyBranchNode.vue` | `mindMap/MindMapV2BranchNode.vue` | `BranchNodeDiagram.vue` |

Variant files hardcode styling (no runtime legacy/v2 branches). `useMindMapCanvasVisuals()` reads
`MIND_MAP_CANVAS_VARIANT_KEY` from the canvas shell for the router decision only.

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

### V2 layout ownership (production)

| Concern | Owner |
|---------|--------|
| Sole layout compute | `mindMapV2LayoutResult` in [`vueFlowIntegration.ts`](../../frontend/src/stores/diagram/vueFlowIntegration.ts) → `computeMindMapDisplayLayout('v2')` → `recalculateMindMapV2ColumnPositions` |
| Canvas nodes | `vueFlowNodes` maps `mindMapV2LayoutNodes` (no second layout engine) |
| Pinia write-back | `scheduleMindMapRecalc` → `writeBackMindMapV2LayoutFromComputed` (merge positions into `data.nodes`) |
| Topic width SoT | `mindMapTopicActualWidth` via `resolveMindMapTopicLayoutWidth` (layout + topic→L1 edges) |

**`mindMapPreserveIncomingY` (sticky L1 Enter):**

- **Set** on v2 L1 in-place sibling commit so first paint keeps insert Y (settle only: fan center, overlap push, side pack).
- **Kept** across measure / text edit-end / L1 height delta (full restack on measure caused delayed L1 shift).
- **Cleared** on collapse/expand, diagram style shape switch, and full reload (`commitMindMapReload` / `loadSpec` / store reset) so those ops can run `correctYPositions`.

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
