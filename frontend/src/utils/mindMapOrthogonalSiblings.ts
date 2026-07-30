import { mindMapBranchSide } from '@/utils/mindMapEdgeEndpoints'

/**
 * Group key for orthogonal mind-map edges that share a tee / bus.
 * Topic children are split by left/right side; other parents group by source id.
 */
export function mindMapOrthogonalSiblingGroupKey(source: string, target: string): string {
  if (source === 'topic') {
    const side = mindMapBranchSide(target)
    return side != null ? `topic:${side}` : `topic:${target}`
  }
  return source
}

/**
 * Build parent→sibling-edge lists once so each edge does not filter the full edge list.
 */
export function buildMindMapOrthogonalSiblingMap<T extends { source: string; target: string }>(
  edges: readonly T[]
): Map<string, T[]> {
  const map = new Map<string, T[]>()
  for (const edge of edges) {
    const key = mindMapOrthogonalSiblingGroupKey(edge.source, edge.target)
    const list = map.get(key)
    if (list) {
      list.push(edge)
    } else {
      map.set(key, [edge])
    }
  }
  return map
}
