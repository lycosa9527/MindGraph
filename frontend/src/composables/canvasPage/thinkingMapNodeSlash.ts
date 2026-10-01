/**
 * Which add or delete a node slash should run on the eight thinking maps.
 * Down deletes. Up adds the child (or the map's only node kind).
 * Left or right adds a sibling of the cut node.
 */
import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import { braceMapRootId, isBraceMapSubpartNode } from '@/stores/diagram/braceMapParentResolve'
import type { Connection, DiagramNode } from '@/types'
import type { NodeSlashAction } from '@/utils/canvasTouchGestures'
import { isFlowMapStepNode, isFlowMapSubstepNode } from '@/utils/flowMapIdentity'
import { isTreeMapCategoryNode, isTreeMapLeafNode } from '@/utils/treeMapIdentity'

/** Handler the slash event bus should call after selecting the cut node. */
export type ThinkingMapSlashCommand =
  'delete' | 'add_node' | 'add_child' | 'add_branch' | 'add_tree_category'

/** Where the cut node sits in that map. */
export type ThinkingMapSlashRole = 'topic' | 'peer' | 'nested' | 'other'

const FLAT_ADD_TYPES = new Set([
  'circle_map',
  'bubble_map',
  'bridge_map',
  'double_bubble_map',
  'multi_flow_map',
])

export function readThinkingMapSlashRole(
  diagramType: string | null | undefined,
  nodeId: string,
  nodes: DiagramNode[],
  connections: Connection[]
): ThinkingMapSlashRole {
  const node = nodes.find((item) => item.id === nodeId)
  if (!node) return 'other'

  if (diagramType === 'tree_map') {
    if (nodeId === 'tree-topic' || nodeId === 'dimension-label' || node.type === 'topic') {
      return 'topic'
    }
    if (isTreeMapCategoryNode(node)) return 'peer'
    if (isTreeMapLeafNode(node)) return 'nested'
    return 'other'
  }

  if (diagramType === 'flow_map') {
    if (isFlowMapSubstepNode(node)) return 'nested'
    if (isFlowMapStepNode(node)) return 'peer'
    return 'topic'
  }

  if (diagramType === 'brace_map') {
    const rootId = braceMapRootId(nodes, connections)
    if (!rootId || nodeId === rootId || nodeId === 'dimension-label' || node.type === 'topic') {
      return 'topic'
    }
    if (isBraceMapSubpartNode(nodeId, connections, rootId)) return 'nested'
    return 'peer'
  }

  return 'other'
}

export function resolveThinkingMapNodeSlash(
  diagramType: string | null | undefined,
  action: NodeSlashAction,
  role: ThinkingMapSlashRole
): ThinkingMapSlashCommand | null {
  if (!isThinkingMapDiagramType(diagramType) || typeof diagramType !== 'string') return null
  if (action === 'delete') return 'delete'
  if (FLAT_ADD_TYPES.has(diagramType)) return 'add_node'

  if (diagramType === 'tree_map') {
    if (action === 'sibling' && role !== 'nested') return 'add_tree_category'
    return 'add_node'
  }

  if (diagramType === 'flow_map') {
    if (action === 'child' && role !== 'topic') return 'add_child'
    return 'add_node'
  }

  if (diagramType === 'brace_map') {
    if (action === 'sibling' && role === 'nested') return 'add_child'
    if (action === 'sibling') return 'add_branch'
    return 'add_node'
  }

  return 'add_node'
}
