# Diagram chrome — legacy spec (pre rainbow alignment)

Snapshot of thinking-map and floating-toolbar appearance **before** thinking maps were aligned to mind map v2 rainbow chrome. Mind map v2 itself was already the reference and is not fully restated here.

Use this when reverting that alignment. The mechanical revert is `git` history. This file is the value catalog those commits replaced.

Concept maps were left on this spec on purpose (their nodes and edge fallbacks were not retargeted).

## Shared palette

Thinking maps and classic mind maps used Material-20 in [`frontend/src/config/mindMapLegacyColors.ts`](../../frontend/src/config/mindMapLegacyColors.ts), exposed as `getMindmapBranchColor` / `MINDMAP_BRANCH_COLORS`.

| Index | Fill | Border |
|------:|------|--------|
| 0 | `#e3f2fd` | `#0d47a1` |
| 1 | `#e8f5e9` | `#1b5e20` |
| 2 | `#fff3e0` | `#e65100` |
| 3 | `#fce4ec` | `#880e4f` |
| 4 | `#f3e5f5` | `#4a148c` |
| 5 | `#e0f7fa` | `#006064` |
| 6 | `#fff8e1` | `#f57f17` |
| 7 | `#efebe9` | `#3e2723` |
| 8 | `#e8eaf6` | `#283593` |
| 9 | `#f1f8e9` | `#33691e` |
| 10 | `#fbe9e7` | `#bf360c` |
| 11 | `#f5f5f5` | `#212121` |
| 12 | `#e0f2f1` | `#004d40` |
| 13 | `#fffde7` | `#f9a825` |
| 14 | `#ede7f6` | `#4527a0` |
| 15 | `#e1f5fe` | `#01579b` |
| 16 | `#f8bbd0` | `#6a1b9a` |
| 17 | `#dcedc8` | `#1b5e20` |
| 18 | `#cfd8dc` | `#37474f` |
| 19 | `#ffccbc` | `#bf360c` |

Rainbow on a thinking map meant “restore this palette”, not the six mind-map families. `thinkingMapDisplayedNodeColors` returned `null` for theme `rainbow`. `resolveThinkingMapConnectorStroke('rainbow', paletteBorder, fallback)` returned `paletteBorder`.

Connectors were full opacity. There was no shared `strokeOpacity: 0.7`.

## Theme defaults (`useTheme.ts` `DEFAULT_THEMES`)

Canvas background for every type: `#f5f5f5`.

| Type | Topic fill / text / stroke / width | Group fill / text / stroke / width | Fonts |
|------|--------------------------------------|-------------------------------------|-------|
| circle_map | `#1976d2` / `#ffffff` / `#000000` / 3 | context `#e3f2fd` / `#333333` / `#1976d2` / 2 | topic 20, context 14. Boundary stroke `#000000` width 2 (component fallback `#666666`) |
| bubble_map | `#1976d2` / `#ffffff` / `#000000` / 2 | attribute `#e3f2fd` / `#333333` / `#000000` / 2 | topic 20, attribute 14 |
| double_bubble_map | central `#1976d2` / `#ffffff` / `#000000` / 3; side topics stroke width 2 | attribute `#e3f2fd` / `#333333` / `#000000` / 2. Similarities had **no** palette stamp | central 18, topic 16, attribute 12 |
| tree_map | root `#1976d2` / `#ffffff` / `#000000` / 3 | branch `#e3f2fd` / `#333333` / `#1976d2` / 1.5; leaf `#ffffff` / `#333333` / `#c8d6e5` / 1 | root 20, branch 16, leaf 14 |
| brace_map | `#1976d2` / `#ffffff` / `#000000` / 3 | part and subpart `#e3f2fd` / `#333333` / `#1976d2` / 2. Brace color `#666666`. Dimension label `#1976d2` | topic 18, part 16, subpart 12 |
| flow_map | stroke `#000000` width 3 | step `#ffffff` / `#303133` / `#409eff` / 2 | step 13 |
| multi_flow_map | stroke `#000000` width 3 | step `#ffffff` / `#303133` / `#409eff` / 2 | step 13 |
| bridge_map | first pair `#1976d2` / `#ffffff` / `#0d47a1` / 2 | line `#666666`, analogy text `#333333` | analogy 14, dimension label `#1976d2` |

`getNodeStyle` hard fallbacks (used when a theme field is missing): topic `#1976d2` / `#0d47a1` / width 3 / 18px; branch `#e3f2fd` / `#4e79a7` / 2 / 16px; attribute stroke `#000000`; subpart width 1 and font 12; root font 20; step `#409eff` / 13px; context stroke `#1976d2`.

V2 mind-map fallback theme (only when a node has no style): topic `#3b82f6` / `#ffffff` / `#2563eb` / 1.5. Vector export default rounded radius was **10** (`diagramMindMapVectorNodes.ts`). V2 node fallbacks included `#1976d2`, `#0d47a1`, `#e3f2fd`, `#4e79a7`.

## Loader metrics

| Map | Fonts | Padding used for measure |
|-----|-------|--------------------------|
| circle / bubble | `TOPIC_FONT_SIZE` 18, `CONTEXT_FONT_SIZE` 14. `textMeasurement.ts` `TOPIC_DEFAULT_FONT_SIZE` **20**, `CONTEXT_DEFAULT_FONT_SIZE` 14 | text-measured radii |
| double bubble | similarities uncolored; diffs stamped with Material pair | capsule height `min(diameter * 0.56, 65)`, width `diameter * 1.22` |
| tree | branch and leaf measured at **16**. Topic 18. Padding X **32** (16 per side), Y **8**. Topic padding X **24**, Y **16** | `treeMap.ts`, `treeMapTopicLayout.ts` |
| brace | topic 18, part 16, subpart **12**. Topic pad X `48 + 6` (px-6 plus 3px border). Pill pad X `40 + 4`. Height pad Y 32 (topic) / 16 (pills) | `braceMap.ts` |
| flow | topic 18, step **13**, substep **12**. Topic pad X **48**, step pad X **40** | `flowMap.ts` |
| multi-flow | topic 18 (`MULTI_FLOW_TOPIC_FONT_SIZE`), cause/effect **13**, pad X **40**. Topic pad X **48** (`MULTI_FLOW_TOPIC_PADDING_X`) | `multiFlowMap.ts`, `layoutConfig.ts` |

Node CSS that matched those pads: topic `px-6` (24px), tree/brace branch `px-4 py-2` (16 / 8), flow `px-5 py-3` (20 / 12). Flow min height **48px**. Rounded rectangles **8px** (`nodeShapeBorderRadius(..., false)` and several `\|\| 8` / `\|\| 6` fallbacks). `paintNodeShape` always called `applyNodeShapeToStyle` with `isMindMap: false`.

## Edges and overlays

| Painter | Fallback stroke | Width |
|---------|-----------------|-------|
| RadialEdge | `#888888` | 2 |
| CurvedEdge | `#94a3b8` (relationship `#666666`) | 2 |
| StraightEdge | `#3b82f6` | 2 |
| StepEdge | `#bbb` | 2 |
| TreeEdge | `#ccc` | 2 |
| HorizontalStepEdge | `#888` | **1.5** |
| BraceEdge | `#64748b` | 2 |
| Brace overlay | Material border via `getMindmapBranchColor` | 2, full opacity. Alternative chips `#1976d2` |
| Bridge overlay | line `#666`, separator and chips `#1976d2`, “as” label `#606266` at **12px** | line 2, full opacity |
| Circle boundary | `#666666` | 2, full opacity |
| LabelNode | `#1976d2` | 14px |

## Floating toolbar

`FLOATING_TOOLBAR_COLORS` (also used by the ribbon node-style cluster, summary bar, association bar, and training text color):

`#ffffff`, `#f8fafc`, `#e2e8f0`, `#94a3b8`, `#475569`, `#1e293b`, `#dbeafe`, `#93c5fd`, `#3b82f6`, `#1d4ed8`, `#dcfce7`, `#86efac`, `#22c55e`, `#166534`, `#fef3c7`, `#fcd34d`, `#f59e0b`, `#b45309`, `#fce7f3`, `#f9a8d4`, `#ec4899`, `#9d174d`, `#ede9fe`, `#a78bfa`.

Font sizes: `12, 13, 14, 15, 16, 18, 20, 24, 28, 32`.

Toolbar readback initial refs: font 14, text `#000000`, border `#000000`, fill `#ffffff`, shape `rounded`. It copied only style fields that were already stored. Border-color pick synced connectors for a mind-map **topic** only. Rounded from the toolbar was 4.5px on mind maps and 8px on thinking maps.

## What a revert must put back

1. `thinkingMapDisplayedNodeColors` returns `null` on rainbow; `restoreThinkingMapDefaultNodeColors` writes Material `fill` / `border`.
2. `resolveThinkingMapConnectorStroke` returns the stored palette border on rainbow.
3. `DEFAULT_THEMES` rows in the table above, loader font and padding constants, and the CSS pads (`px-6`, `px-4 py-2`, `px-5 py-3`).
4. Edge fallbacks and widths in the edge table, at opacity 1. Brace/bridge/boundary/label hex values.
5. `nodeShapeBorderRadius` / `paintNodeShape`: non-mind-map rounded = `8px`.
6. `FLOATING_TOOLBAR_COLORS` list above, including the training field if it was split onto its own constant.
7. V2 mind-map topic fallback `#3b82f6` / `#2563eb` and vector radius `10`, if those were changed in the same work.
