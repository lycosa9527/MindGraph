/**
 * Group key for orthogonal mind-map edges that share a tee / bus.
 * Same-side topic→L1 children share one trunk; other parents group by source.
 * Pass `sideOf` so UUID L1s resolve from stamped data / connections.
 */
export function mindMapOrthogonalSiblingGroupKey(
  source: string,
  target: string,
  sideOf?: (targetId: string) => 'left' | 'right' | null
): string {
  if (source === 'topic') {
    const side = sideOf?.(target)
    return side != null ? `topic:${side}` : `topic:${target}`
  }
  return source
}

/**
 * The one edge in a sibling group that paints the shared stem + spine + stubs.
 */
export function mindMapOrthogonalSpineEdgeId<T extends { id?: string }>(
  siblings: readonly T[]
): string | undefined {
  if (siblings.length === 0) return undefined
  const sorted = [...siblings].sort((a, b) => String(a.id ?? '').localeCompare(String(b.id ?? '')))
  return sorted[0]?.id
}

/**
 * Build parent→sibling-edge lists once so each edge does not filter the full edge list.
 */
export function buildMindMapOrthogonalSiblingMap<T extends { source: string; target: string }>(
  edges: readonly T[],
  sideOf?: (targetId: string) => 'left' | 'right' | null
): Map<string, T[]> {
  const map = new Map<string, T[]>()
  for (const edge of edges) {
    const key = mindMapOrthogonalSiblingGroupKey(edge.source, edge.target, sideOf)
    const list = map.get(key)
    if (list) {
      list.push(edge)
    } else {
      map.set(key, [edge])
    }
  }
  return map
}
