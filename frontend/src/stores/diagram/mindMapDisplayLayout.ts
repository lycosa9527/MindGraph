import type { Connection, DiagramNode } from '@/types'

import { recalculateMindMapLegacyColumnPositions } from './mindMapLayoutLegacy'
import { recalculateMindMapV2ColumnPositions } from './mindMapLayout'

export interface MindMapDisplayLayoutResult {
  nodes: DiagramNode[]
  gaps: { left: number; right: number }
}

export function computeMindMapDisplayLayout(
  canvasMode: 'legacy' | 'v2',
  nodes: DiagramNode[],
  connections: Connection[],
  topicWidth: number | null,
  nodeWidths: Record<string, number>,
  nodeHeights: Record<string, number>,
  collapsedNodeIds: ReadonlySet<string> = new Set<string>()
): MindMapDisplayLayoutResult {
  if (canvasMode === 'v2') {
    return recalculateMindMapV2ColumnPositions(
      nodes,
      topicWidth,
      nodeWidths,
      nodeHeights,
      connections,
      collapsedNodeIds
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
  collapsedNodeIds: ReadonlySet<string> = new Set<string>()
): DiagramNode[] {
  return computeMindMapDisplayLayout(
    canvasMode,
    nodes,
    connections,
    topicWidth,
    nodeWidths,
    nodeHeights,
    collapsedNodeIds
  ).nodes
}
