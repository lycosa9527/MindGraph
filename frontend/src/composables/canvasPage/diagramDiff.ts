/** Diff helpers for workshop collab undo/redo guards. */

/**
 * Recursive deep equality with key-order independence (unlike JSON.stringify).
 * Handles primitives, plain objects (own enumerable keys only), arrays, and Date.
 */
export function workshopDeepEqual(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) {
    return true
  }
  if (typeof a !== typeof b || a === null || b === null) {
    return false
  }
  if (typeof a !== 'object' || typeof b !== 'object') {
    return false
  }
  if (a instanceof Date && b instanceof Date) {
    return a.getTime() === b.getTime()
  }
  if (Array.isArray(a)) {
    return Array.isArray(b) && a.length === b.length && a.every((item, i) => workshopDeepEqual(item, b[i]))
  }
  if (Array.isArray(b)) {
    return false
  }
  const ao = a as Record<string, unknown>
  const bo = b as Record<string, unknown>
  const keysA = Object.keys(ao)
  const keysB = Object.keys(bo)
  if (keysA.length !== keysB.length) {
    return false
  }
  for (const k of keysA) {
    if (!Object.prototype.hasOwnProperty.call(bo, k)) {
      return false
    }
    if (!workshopDeepEqual(ao[k], bo[k])) {
      return false
    }
  }
  return true
}

export function calculateDiff<T extends { id: string }>(oldArray: T[], newArray: T[]): T[] {
  const oldMap = new Map(oldArray.map((item) => [item.id, item]))
  const changed: T[] = []

  for (const newItem of newArray) {
    const oldItem = oldMap.get(newItem.id)
    if (!oldItem || !workshopDeepEqual(oldItem, newItem)) {
      changed.push(newItem)
    }
  }

  return changed
}

export function nodeIdsDiffBetweenDiagrams(
  a: { nodes?: { id: string }[] } | null,
  b: { nodes?: { id: string }[] } | null
): Set<string> {
  const ids = new Set<string>()
  const nodesA = a?.nodes ?? []
  const nodesB = b?.nodes ?? []
  const mapB = new Map(nodesB.map((n) => [n.id, n]))
  for (const n of nodesA) {
    const o = mapB.get(n.id)
    if (!o || !workshopDeepEqual(n, o)) {
      ids.add(n.id)
    }
  }
  for (const n of nodesB) {
    if (!nodesA.find((x) => x.id === n.id)) {
      ids.add(n.id)
    }
  }
  return ids
}
