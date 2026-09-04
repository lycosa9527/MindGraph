/**
 * Collab connection merge: insert a new edge beside the prior sibling.
 * Mirrors backend ``_connection_insert_index`` / ``_merge_connection_patches``.
 */
export const COLLAB_INSERT_AFTER_TARGET_KEY = 'insert_after_target'

type ConnRow = {
  id?: string
  source?: string
  target?: string
}

const COLLAB_ENDPOINT_KEYS = ['source', 'target', COLLAB_INSERT_AFTER_TARGET_KEY] as const

export function remapCollabConnectionEndpoints(
  patch: Record<string, unknown>,
  remapId: (hint: string) => string
): Record<string, unknown> {
  const next = { ...patch }
  for (const key of COLLAB_ENDPOINT_KEYS) {
    const raw = next[key]
    if (typeof raw === 'string' && raw) {
      next[key] = remapId(raw)
    }
  }
  return next
}

export function stripCollabInsertAfterTarget(
  row: Record<string, unknown>
): Record<string, unknown> {
  if (!(COLLAB_INSERT_AFTER_TARGET_KEY in row)) {
    return row
  }
  const next = { ...row }
  delete next[COLLAB_INSERT_AFTER_TARGET_KEY]
  return next
}

export function collabConnectionInsertIndex(
  conns: readonly ConnRow[],
  patch: Record<string, unknown>
): number {
  const source = typeof patch.source === 'string' ? patch.source : ''
  const afterTarget =
    typeof patch[COLLAB_INSERT_AFTER_TARGET_KEY] === 'string'
      ? (patch[COLLAB_INSERT_AFTER_TARGET_KEY] as string)
      : ''
  if (source && afterTarget) {
    const hit = conns.findIndex((conn) => conn.source === source && conn.target === afterTarget)
    if (hit >= 0) {
      return hit + 1
    }
  }
  if (source) {
    let lastSame = -1
    for (let i = 0; i < conns.length; i += 1) {
      if (conns[i]?.source === source) {
        lastSame = i
      }
    }
    if (lastSame >= 0) {
      return lastSame + 1
    }
  }
  return conns.length
}

export function spliceCollabConnection(
  conns: ConnRow[],
  patch: Record<string, unknown>
): void {
  const clean = stripCollabInsertAfterTarget(patch)
  const connId = typeof clean.id === 'string' ? clean.id : ''
  const source = typeof clean.source === 'string' ? clean.source : ''
  const target = typeof clean.target === 'string' ? clean.target : ''
  if (!connId && !source && !target) {
    return
  }
  const existingIndex = connId
    ? conns.findIndex((conn) => conn.id === connId)
    : source && target
      ? conns.findIndex((conn) => conn.source === source && conn.target === target)
      : -1
  if (existingIndex >= 0) {
    conns[existingIndex] = { ...conns[existingIndex], ...clean }
    return
  }
  conns.splice(collabConnectionInsertIndex(conns, patch), 0, clean)
}