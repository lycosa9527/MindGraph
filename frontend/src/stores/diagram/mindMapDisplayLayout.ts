import type { Connection, DiagramData, DiagramNode } from '@/types'
import { voidMindMapAssociationsAcrossSides } from '@/utils/mindMapAssociationLine'
import { resolveSessionMindMapCanvasMode } from '@/utils/mindMapCanvasMode'
import { collapseDuplicateMindMapNodes } from '@/utils/mindMapIdentityMigrate'
import { filterTreeMindMapNodes } from '@/utils/mindMapSummary'
import { nodeIdsWithImage } from '@/utils/nodeImageFrame'

import { getMindMapCollapsedNodeIds, getMindMapCollapsedPaths } from './mindMapCollapse'
import { type MindMapV2LayoutOptions, recalculateMindMapV2ColumnPositions } from './mindMapLayout'
import { recalculateMindMapLegacyColumnPositions } from './mindMapLayoutLegacy'
import { mergeLaidOutTreeWithSummaries } from './mindMapSummaryLayout'
import { nodesWithMindMapWrapBoxes } from './mindMapTextEditSize'
import type { DiagramContext } from './types'

export interface MindMapDisplayLayoutResult {
  nodes: DiagramNode[]
  gaps: { left: number; right: number }
}

/**
 * Copy laid-out positions into store nodes when they differ.
 * Returns the same array reference when nothing moved (avoids churn).
 */
export function mergeMindMapLayoutPositions(
  storeNodes: DiagramNode[],
  laidOut: DiagramNode[]
): DiagramNode[] {
  const byId = new Map(laidOut.map((node) => [node.id, node]))
  let changed = false
  const next = storeNodes.map((node) => {
    const laid = byId.get(node.id)
    if (!laid?.position || !node.position) return node
    const laidWidth = laid.data?.estimatedWidth
    const laidHeight = laid.data?.estimatedHeight
    const positionMoved =
      Math.abs(laid.position.x - node.position.x) >= 0.5 ||
      Math.abs(laid.position.y - node.position.y) >= 0.5
    const widthMoved = typeof laidWidth === 'number' && laidWidth !== node.data?.estimatedWidth
    const heightMoved = typeof laidHeight === 'number' && laidHeight !== node.data?.estimatedHeight
    if (!positionMoved && !widthMoved && !heightMoved) return node
    changed = true
    return {
      ...node,
      position: { x: laid.position.x, y: laid.position.y },
      data: {
        ...node.data,
        ...(typeof laidWidth === 'number' ? { estimatedWidth: laidWidth } : {}),
        ...(typeof laidHeight === 'number' ? { estimatedHeight: laidHeight } : {}),
      },
    }
  })
  return changed ? next : storeNodes
}

/**
 * Write display-layout positions back into Pinia so the next in-place insert
 * seeds from the same X/Y the canvas shows (single position SoT).
 *
 * v2: write-back only from {@link DiagramContext.writeBackMindMapV2LayoutFromComputed}
 * (sole layout owner). Legacy: compute here as before.
 */
function collapseStoredMindMapDuplicates(ctx: DiagramContext): void {
  const data = ctx.data.value
  if (!data?.nodes?.length) return
  const collapsed = collapseDuplicateMindMapNodes(
    data.nodes,
    data.connections ?? [],
    data._node_styles
  )
  if (collapsed.nodes === data.nodes && collapsed.connections === data.connections) return
  data.nodes = collapsed.nodes
  data.connections = collapsed.connections
  if (collapsed.nodeStyles) {
    data._node_styles = collapsed.nodeStyles
  }
}

export function syncMindMapStoreLayoutPositions(ctx: DiagramContext): void {
  const diagramType = ctx.type.value
  if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return
  if (!ctx.data.value?.nodes) return
  collapseStoredMindMapDuplicates(ctx)

  const connections = ctx.data.value.connections ?? []
  const canvasMode = resolveSessionMindMapCanvasMode(ctx.mindMapCanvasMode.value)

  const v2Family = canvasMode === 'v2'

  // v2: sole layout owner is mindMapV2LayoutResult — write-back only (no second compute).
  if (v2Family && ctx.writeBackMindMapV2LayoutFromComputed) {
    ctx.writeBackMindMapV2LayoutFromComputed()
    dropCrossSideMindMapAssociations(ctx)
    return
  }

  const collapsedPaths = v2Family ? getMindMapCollapsedPaths(ctx.data.value) : []
  const collapsedNodeIds = v2Family
    ? getMindMapCollapsedNodeIds(ctx.data.value.nodes, connections, collapsedPaths)
    : new Set<string>()
  const preserveIncomingY = v2Family && ctx.mindMapPreserveIncomingY.value
  const options: MindMapV2LayoutOptions = {
    ...(preserveIncomingY ? { preserveIncomingY: true } : {}),
    imageNodeIds: nodeIdsWithImage(ctx.data.value.nodes, ctx.data.value, connections),
  }

  // Legacy (always) or v2 fallback before the Vue Flow slice wires write-back.
  const { nodes: laidOut, gaps } = computeMindMapDisplayLayout(
    v2Family ? 'v2' : 'legacy',
    ctx.data.value.nodes,
    connections,
    ctx.mindMapTopicActualWidth.value,
    ctx.mindMapNodeWidths.value,
    ctx.mindMapNodeHeights.value,
    collapsedNodeIds,
    ctx.data.value._mindmap_diagram_style as string | undefined,
    options
  )
  ctx.mindMapTopicBranchGaps.value = gaps
  const merged = mergeMindMapLayoutPositions(ctx.data.value.nodes, laidOut)
  if (merged !== ctx.data.value.nodes) {
    ctx.data.value.nodes = merged
  }
  dropCrossSideMindMapAssociations(ctx)
}

function dropCrossSideMindMapAssociations(ctx: DiagramContext): void {
  const data = ctx.data.value
  if (!data?.connections?.length || !data.nodes) return
  const next = voidMindMapAssociationsAcrossSides(data.connections, data.nodes)
  if (next === data.connections) return
  data.connections = next
  const selected = ctx.selectedConnectionId.value
  if (selected && !next.some((conn) => conn.id === selected)) {
    ctx.selectedConnectionId.value = null
  }
}

/**
 * v2 column layout from the wrap box the label paints.
 * Saved `estimatedWidth` can still be a collapsed or one-line number. Stamp
 * first so rank X uses the same measurement as the node, including on file open
 * before Vue Flow has measured anything.
 */
export function layoutMindMapV2WithWrapBoxes(
  nodes: DiagramNode[],
  data: DiagramData,
  topicWidth: number | null,
  nodeWidths: Record<string, number>,
  nodeHeights: Record<string, number>,
  options?: { preserveIncomingY?: boolean; reuseStoredWrapBox?: boolean }
): MindMapDisplayLayoutResult {
  const connections = data.connections ?? []
  const treeNodes = nodesWithMindMapWrapBoxes(filterTreeMindMapNodes(nodes), data, {
    reuseStored: options?.reuseStoredWrapBox === true,
  })
  const collapsedPaths = getMindMapCollapsedPaths(data)
  const collapsedNodeIds = getMindMapCollapsedNodeIds(treeNodes, connections, collapsedPaths)
  const imageNodeIds = nodeIdsWithImage(treeNodes, data, connections)
  const diagramStyleId =
    typeof data._mindmap_diagram_style === 'string' ? data._mindmap_diagram_style : undefined
  const laidOut = computeMindMapDisplayLayout(
    'v2',
    treeNodes,
    connections,
    topicWidth,
    nodeWidths,
    nodeHeights,
    collapsedNodeIds,
    diagramStyleId,
    {
      ...(options?.preserveIncomingY ? { preserveIncomingY: true } : {}),
      imageNodeIds,
    }
  )
  return {
    nodes: mergeLaidOutTreeWithSummaries(
      laidOut.nodes,
      nodes,
      connections,
      data,
      nodeWidths,
      nodeHeights
    ),
    gaps: laidOut.gaps,
  }
}

function seedWrapMeasureMaps(
  nodes: DiagramNode[],
  widths: Record<string, number>,
  heights: Record<string, number>
): void {
  for (const node of nodes) {
    if (!node.id || node.type === 'boundary') continue
    const width = node.data?.estimatedWidth
    const height = node.data?.estimatedHeight
    if (typeof width === 'number' && width > 0) widths[node.id] = width
    if (typeof height === 'number' && height > 0) heights[node.id] = height
  }
}

/**
 * Replace saved rank positions with the wrap layout before the canvas paints.
 * The measure batch holds store positions, so the file's columns would stay
 * on screen until a full page remount.
 */
export function restackLoadedMindMapV2Nodes(
  nodes: DiagramNode[],
  spec: DiagramData,
  connections: Connection[],
  options: {
    preserveMeasures: boolean
    widths: Record<string, number>
    heights: Record<string, number>
    topicWidth: number | null
  }
): {
  nodes: DiagramNode[]
  widths: Record<string, number>
  heights: Record<string, number>
  topicWidth: number | null
  gaps: { left: number; right: number }
} {
  const layoutData: DiagramData = {
    ...spec,
    nodes,
    connections,
  }
  const laidOut = layoutMindMapV2WithWrapBoxes(
    nodes,
    layoutData,
    options.preserveMeasures ? options.topicWidth : null,
    options.preserveMeasures ? { ...options.widths } : {},
    options.preserveMeasures ? { ...options.heights } : {}
  )
  if (options.preserveMeasures) {
    return {
      nodes: laidOut.nodes,
      widths: options.widths,
      heights: options.heights,
      topicWidth: options.topicWidth,
      gaps: laidOut.gaps,
    }
  }
  const widths: Record<string, number> = {}
  const heights: Record<string, number> = {}
  seedWrapMeasureMaps(laidOut.nodes, widths, heights)
  return {
    nodes: laidOut.nodes,
    widths,
    heights,
    topicWidth: widths.topic ?? null,
    gaps: laidOut.gaps,
  }
}

export function computeMindMapDisplayLayout(
  canvasMode: 'legacy' | 'v2',
  nodes: DiagramNode[],
  connections: Connection[],
  topicWidth: number | null,
  nodeWidths: Record<string, number>,
  nodeHeights: Record<string, number>,
  collapsedNodeIds: ReadonlySet<string> = new Set<string>(),
  diagramStyleId?: string | null,
  options?: MindMapV2LayoutOptions
): MindMapDisplayLayoutResult {
  if (canvasMode === 'v2') {
    return recalculateMindMapV2ColumnPositions(
      nodes,
      topicWidth,
      nodeWidths,
      nodeHeights,
      connections,
      collapsedNodeIds,
      diagramStyleId,
      options
    )
  }
  return recalculateMindMapLegacyColumnPositions(
    nodes,
    topicWidth,
    nodeWidths,
    nodeHeights,
    connections,
    options?.imageNodeIds
  )
}
