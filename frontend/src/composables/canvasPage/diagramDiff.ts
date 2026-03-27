/** Diff helpers for workshop collab undo/redo guards. */

export function calculateDiff<T extends { id: string }>(oldArray: T[], newArray: T[]): T[] {
  const oldMap = new Map(oldArray.map((item) => [item.id, item]))
  const changed: T[] = []

  for (const newItem of newArray) {
    const oldItem = oldMap.get(newItem.id)
    if (!oldItem || JSON.stringify(oldItem) !== JSON.stringify(newItem)) {
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
    if (!o || JSON.stringify(n) !== JSON.stringify(o)) {
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
