/**
 * Snapshot mind-map diagram store state for vector SVG export.
 */
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import type { Connection, DiagramData, DiagramNode, NodeStyle } from '@/types'
import type { MindMapCanvasMode } from '@/stores/ui'
import {
  getMindMapCollapseHiddenIds,
  getMindMapCollapsedPaths,
} from '@/stores/diagram/mindMapCollapse'
import type { MindMapVectorNodeDraw } from '@/utils/diagramMindMapVectorNodes'

export type MindMapVectorSnapshot = {
  canvasMode: MindMapCanvasMode
  diagramStyleId: string | null
  outlineWireframe: boolean
  topicActualWidth: number | null
  nodes: MindMapVectorNodeDraw[]
  connections: Connection[]
}

export type MindMapVectorStoreLike = {
  type: string | null
  data: DiagramData | null
  mindMapNodeWidths: Record<string, number>
  mindMapNodeHeights: Record<string, number>
  nodeDimensions: Record<string, { width: number; height: number }>
  mindMapTopicActualWidth: number | null
  getDescendantIds?: (rootId: string) => Set<string>
}

function descendantIdsFromChildIds(nodes: DiagramNode[], rootId: string): Set<string> {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const result = new Set<string>()
  const stack = [rootId]
  while (stack.length > 0) {
    const id = stack.pop()
    if (!id || result.has(id)) continue
    result.add(id)
    const node = byId.get(id)
    for (const childId of node?.childIds ?? []) {
      stack.push(childId)
    }
  }
  return result
}

function resolveNodeSize(
  node: DiagramNode,
  widths: Record<string, number>,
  heights: Record<string, number>,
  dimensions: Record<string, { width: number; height: number }>
): { width: number; height: number } {
  const dim = dimensions[node.id]
  const styleW = node.style?.width
  const styleH = node.style?.height
  return {
    width:
      widths[node.id] ??
      dim?.width ??
      (typeof styleW === 'number' ? styleW : undefined) ??
      MIND_MAP_GEOMETRY.minWidth,
    height:
      heights[node.id] ??
      dim?.height ??
      (typeof styleH === 'number' ? styleH : undefined) ??
      MIND_MAP_GEOMETRY.minHeight,
  }
}

function mergeStyle(
  node: DiagramNode,
  preserved: Record<string, NodeStyle> | undefined
): NodeStyle {
  return { ...preserved?.[node.id], ...node.style }
}

export function isMindMapVectorExportType(type: string | null | undefined): boolean {
  return type === 'mindmap' || type === 'mind_map'
}

export function buildMindMapVectorSnapshot(options: {
  store: MindMapVectorStoreLike
  canvasMode: MindMapCanvasMode
  outlineWireframe: boolean
}): MindMapVectorSnapshot | null {
  const { store, canvasMode, outlineWireframe } = options
  if (!isMindMapVectorExportType(store.type) || !store.data) {
    return null
  }

  const data = store.data
  const preserved = data._node_styles
  const diagramStyleId = (data._mindmap_diagram_style as string | undefined) ?? null
  const connections = data.connections ?? []
  const nodes = data.nodes ?? []

  const collapsedPaths = canvasMode === 'v2' ? getMindMapCollapsedPaths(data) : []
  const getDescendants =
    store.getDescendantIds ??
    ((rootId: string) => descendantIdsFromChildIds(nodes, rootId))
  const hiddenIds = getMindMapCollapseHiddenIds(
    nodes,
    connections,
    collapsedPaths,
    getDescendants
  )

  const drawNodes: MindMapVectorNodeDraw[] = []
  for (const node of nodes) {
    if (hiddenIds.has(node.id)) continue
    if (!node.position) continue
    const style = mergeStyle(node, preserved)
    // Ensure shape from diagram style is visible to drawers when not overridden
    if (!style.nodeShape) {
      style.nodeShape = resolveMindMapNodeShape(
        { id: node.id, type: node.type, style },
        diagramStyleId
      )
    }
    const size = resolveNodeSize(
      node,
      store.mindMapNodeWidths,
      store.mindMapNodeHeights,
      store.nodeDimensions
    )
    drawNodes.push({
      id: node.id,
      text: node.text ?? '',
      type: node.type,
      x: node.position.x,
      y: node.position.y,
      width: size.width,
      height: size.height,
      style,
    })
  }

  const visibleIds = new Set(drawNodes.map((n) => n.id))
  const visibleConnections = connections.filter(
    (c) => visibleIds.has(c.source) && visibleIds.has(c.target)
  )

  return {
    canvasMode,
    diagramStyleId,
    outlineWireframe: outlineWireframe && canvasMode === 'v2',
    topicActualWidth: store.mindMapTopicActualWidth,
    nodes: drawNodes,
    connections: visibleConnections,
  }
}
