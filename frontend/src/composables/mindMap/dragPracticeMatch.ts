/**
 * Drag-practice scoring groups.
 * Sets (siblings, bubble items, one double-bubble column) accept any unused
 * answer from that group. Sequences and paired analogies stay on their own slot.
 */
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'
import { isMindMapTreeConnection } from '@/utils/mindMapLocation'

export type DragPracticeNode = {
  id: string
  parentId?: string
  data?: Record<string, unknown>
}

export type DragPracticeConnection = {
  source: string
  target: string
  edgeType?: string
  sourceHandle?: string
}

const SET_BY_PARENT = new Set([
  'mindmap',
  'mind_map',
  'tree_map',
  'brace_map',
  'bubble_map',
  'circle_map',
])

function structuralParentId(
  nodeId: string,
  nodes: DragPracticeNode[],
  connections: DragPracticeConnection[]
): string | null {
  const node = nodes.find((item) => item.id === nodeId)
  const stamped = node?.parentId?.trim()
  if (stamped) return stamped
  const incoming = connections.filter(
    (edge) => edge.target === nodeId && isMindMapTreeConnection(edge)
  )
  if (incoming.length === 0) return null
  return incoming[0]?.source ?? null
}

/** Group key for blanks that may share answers. Unique key means exact slot. */
export function dragPracticeSlotGroup(
  diagramType: string | null | undefined,
  nodeId: string,
  nodes: DragPracticeNode[],
  connections: DragPracticeConnection[]
): string {
  if (diagramType === 'double_bubble_map') {
    const node = nodes.find((item) => item.id === nodeId)
    const role = node ? readDoubleBubbleRole(node) : null
    if (role) return `role:${role}`
    return `node:${nodeId}`
  }
  if (diagramType && SET_BY_PARENT.has(diagramType)) {
    const parentId = structuralParentId(nodeId, nodes, connections)
    if (parentId) return `parent:${parentId}`
  }
  return `node:${nodeId}`
}
