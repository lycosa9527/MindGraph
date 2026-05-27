import type { Connection, DiagramNode } from '@/types'

export function braceMapRootId(
  nodes: DiagramNode[],
  connections: Connection[]
): string | undefined {
  const targetIds = new Set(connections.map((c) => c.target))
  return (
    nodes.find((n) => n.type === 'topic')?.id ??
    nodes.find((n) => n.id !== undefined && !targetIds.has(n.id))?.id
  )
}

/**
 * Subparts must attach under their part group (depth-1 child of root), not under another subpart.
 */
export function resolveBraceMapSubpartAttachParentId(
  parentId: string,
  connections: Connection[],
  rootId: string
): string {
  if (parentId === rootId || parentId === 'topic') {
    return parentId
  }

  const parentConn = connections.find((c) => c.target === parentId)
  const immediateParent = parentConn?.source
  if (!immediateParent || immediateParent === rootId) {
    return parentId
  }

  let currentId = parentId
  for (;;) {
    const conn = connections.find((c) => c.target === currentId)
    const source = conn?.source
    if (!source || source === rootId) {
      return currentId
    }
    currentId = source
  }
}

export function isBraceMapPartAddTarget(
  parentId: string,
  parentNode: DiagramNode,
  rootId: string | undefined
): boolean {
  if (!rootId) {
    return parentId === 'topic' || parentNode.type === 'topic'
  }
  return parentId === rootId || parentId === 'topic' || parentNode.type === 'topic'
}

/** True when the node is a sub-part (parent is a part, not the whole/topic). */
export function isBraceMapSubpartNode(
  nodeId: string,
  connections: Connection[],
  rootId: string
): boolean {
  if (nodeId === rootId || nodeId === 'topic' || nodeId === 'dimension-label') {
    return false
  }
  const parentConn = connections.find((c) => c.target === nodeId)
  const parent = parentConn?.source
  return !!parent && parent !== rootId
}
