/**
 * Outbound collab patches shaped by ``node_editing`` presence (not timers).
 * Layout-only echoes of a locked node must not look like a text conflict.
 */

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === 'object' && !Array.isArray(value)
}

export function asReadonlyIdSet(value: unknown): ReadonlySet<string> {
  return value instanceof Set ? value : new Set<string>()
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** Same allowlist as ``layout_patch_for_locked_node`` on the server. */
export function layoutPatchForLockedNode(
  node: Record<string, unknown>
): Record<string, unknown> | null {
  const id = typeof node.id === 'string' ? node.id : ''
  if (!id) {
    return null
  }
  const out: Record<string, unknown> = { id }
  const position = node.position
  if (isPlainObject(position)) {
    const posX = finiteNumber(position.x)
    const posY = finiteNumber(position.y)
    if (posX != null && posY != null) {
      out.position = { x: posX, y: posY }
    }
  }
  const width = finiteNumber(node.width)
  if (width != null) {
    out.width = width
  }
  const height = finiteNumber(node.height)
  if (height != null) {
    out.height = height
  }
  return Object.keys(out).length > 1 ? out : null
}

/**
 * Peers reflow while someone else holds a text lock (often seconds later).
 * Keep position/size; drop text so the server never sees a content conflict.
 */
export function applyForeignLockToOutboundNodes(
  nodes: Array<Record<string, unknown>>,
  foreignLockedIds: ReadonlySet<string>
): Array<Record<string, unknown>> {
  if (foreignLockedIds.size === 0) {
    return nodes
  }
  const out: Array<Record<string, unknown>> = []
  for (const node of nodes) {
    const id = typeof node.id === 'string' ? node.id : ''
    if (!id || !foreignLockedIds.has(id)) {
      out.push(node)
      continue
    }
    const layout = layoutPatchForLockedNode(node)
    if (layout) {
      out.push(layout)
    }
  }
  return out
}

export function applyForeignLockToOutboundConnections(
  connections: Array<Record<string, unknown>>,
  foreignLockedIds: ReadonlySet<string>
): Array<Record<string, unknown>> {
  if (foreignLockedIds.size === 0) {
    return connections
  }
  return connections.filter((conn) => {
    const target = conn.target
    return typeof target !== 'string' || !foreignLockedIds.has(target)
  })
}
