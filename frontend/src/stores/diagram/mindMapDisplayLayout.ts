import type { Connection, DiagramNode } from '@/types'
import { resolveSessionMindMapCanvasMode } from '@/utils/mindMapCanvasMode'

import { getMindMapCollapsedNodeIds, getMindMapCollapsedPaths } from './mindMapCollapse'
import { type MindMapV2LayoutOptions, recalculateMindMapV2ColumnPositions } from './mindMapLayout'
import { recalculateMindMapLegacyColumnPositions } from './mindMapLayoutLegacy'
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
    if (
      Math.abs(laid.position.x - node.position.x) < 0.5 &&
      Math.abs(laid.position.y - node.position.y) < 0.5
    ) {
      return node
    }
    changed = true
    return { ...node, position: { x: laid.position.x, y: laid.position.y } }
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
export function syncMindMapStoreLayoutPositions(ctx: DiagramContext): void {
  const diagramType = ctx.type.value
  if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return
  if (!ctx.data.value?.nodes) return

  const connections = ctx.data.value.connections ?? []
  const canvasMode = resolveSessionMindMapCanvasMode(ctx.mindMapCanvasMode.value)

  // v2: sole layout owner is mindMapV2LayoutResult — write-back only (no second compute).
  if (canvasMode === 'v2' && ctx.writeBackMindMapV2LayoutFromComputed) {
    ctx.writeBackMindMapV2LayoutFromComputed()
    return
  }

  const collapsedPaths = canvasMode === 'v2' ? getMindMapCollapsedPaths(ctx.data.value) : []
  const collapsedNodeIds =
    canvasMode === 'v2'
      ? getMindMapCollapsedNodeIds(ctx.data.value.nodes, connections, collapsedPaths)
      : new Set<string>()
  const preserveIncomingY = canvasMode === 'v2' && ctx.mindMapPreserveIncomingY.value
  const options: MindMapV2LayoutOptions | undefined = preserveIncomingY
    ? { preserveIncomingY: true }
    : undefined

  // Legacy (always) or v2 fallback before the Vue Flow slice wires write-back.
  const { nodes: laidOut, gaps } = computeMindMapDisplayLayout(
    canvasMode,
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
    connections
  )
}

export function computeMindMapDisplayNodes(
  canvasMode: 'legacy' | 'v2',
  nodes: DiagramNode[],
  connections: Connection[],
  topicWidth: number | null,
  nodeWidths: Record<string, number>,
  nodeHeights: Record<string, number>,
  collapsedNodeIds: ReadonlySet<string> = new Set<string>(),
  diagramStyleId?: string | null,
  options?: MindMapV2LayoutOptions
): DiagramNode[] {
  return computeMindMapDisplayLayout(
    canvasMode,
    nodes,
    connections,
    topicWidth,
    nodeWidths,
    nodeHeights,
    collapsedNodeIds,
    diagramStyleId,
    options
  ).nodes
}
