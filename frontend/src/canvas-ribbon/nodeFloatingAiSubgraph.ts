/**
 * Whether the selected node shows 智能生成子图 on the floating toolbar.
 * Diagram types follow the AI tab. Mind maps still hide the center topic.
 */
import {
  diagramRibbonCapabilities,
  isMindMapDiagramType,
} from '@/canvas-ribbon/diagramRibbonCapabilities'
import { isMindMapSubgraphExpandable } from '@/utils/mindMapSubgraphContext'

export function showsNodeFloatingAiSubgraph(
  type: string | null | undefined,
  mindMapV2: boolean,
  nodeId: string | null | undefined
): boolean {
  if (!diagramRibbonCapabilities(type, mindMapV2).subgraph) return false
  if (isMindMapDiagramType(type)) return isMindMapSubgraphExpandable(nodeId)
  return nodeId != null
}
