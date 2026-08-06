# Mind map canvas — classic vs v2 separation

New (v2) mind map canvas is the **default** (`mindMapCanvasMode: v2`) when
`FEATURE_MINDMAP_V2_CANVAS=True` (on by default). A one-time browser migration
(`mindgraph_mindmap_canvas_v2_default_migrated`) moves sticky Classic preferences
onto New; Classic remains opt-in via Language settings. V2 chrome includes side
toolbar, **Document Summary** (文档总结), orthogonal edges, and subtree layout.
Set `FEATURE_MINDMAP_V2_CANVAS=False` to force classic-only at runtime (does not
overwrite the saved New-canvas preference).

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

Baseline for Material fills/borders/default text: commit `7c7df0d3` (pre–v2 layout port).

| Mode | Branches | Topic | Connections |
|------|----------|-------|-------------|
| Legacy | 20 Material hues — default `getMindmapBranchColor(i)` / `LEGACY_MINDMAP_BRANCH_COLORS` (alias of `MINDMAP_BRANCH_COLORS`) | Blue pill via `LEGACY_MINDMAP_THEME` (`#1976d2` / `#ffffff`); classic apply paths never seed v2 theme `textColor` | Per-branch palette, curved edges; topic handles indexed per side, **evenly spaced on the pill** (`classicMindMapTopicHandles.ts`); **Add branch** redistributes clockwise and seeds two children |
| V2 | Unified `mindMapThemes` presets for node paint; Radix-12 only via `getMindmapBranchColor(i, 'v2')` when a branch-index caller still needs it | Theme accent | Unified topic border, orthogonal edges |

Other diagram types (tree map, flow map, bubble, double-bubble, …) use the same Material-20 default as classic mind map.

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

| Bucket | Contents |
|--------|----------|
| `legacy` | `node_styles_by_path` only (sanitized) |
| `v2` | `node_styles_by_path`, `theme`, `diagram_style`, `collapsed_paths` |

Legacy sanitize strips `nodeShape`, `backgroundColor`, `borderColor`, `fontFamily`, and `borderWidth` (classic render uses Material palette + `LEGACY_MINDMAP_THEME`). Keeps user text formatting (`textColor`, font size/weight/style).
On legacy load/switch, live `_mindmap_theme` and `_mindmap_diagram_style` are cleared; returning to v2 restores them from the v2 bucket. Classic apply never calls `buildMindMapStyleForNewBranchNode`.

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
