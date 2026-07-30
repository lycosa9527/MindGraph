import type { LoadFromSpecOptions } from '@/stores/diagram/types'
import type { DiagramType } from '@/types'

/**
 * Soft-load options for any hydrate of a mind map that already has stamped
 * nodes + connections (library, snapshot recall, Kitty, import).
 * Does not set preserveMindMapMeasures — that would copy the previous diagram's
 * session width/height maps onto shared ids like `topic` / `branch-r-1-0`.
 * Estimates are seeded in loadFromSpec instead.
 */
export function mindMapLibraryLoadOptions(
  diagramType: DiagramType | string,
  spec: Record<string, unknown>
): LoadFromSpecOptions | undefined {
  const isMindMap = diagramType === 'mindmap' || diagramType === 'mind_map'
  if (!isMindMap) return undefined
  const nodes = spec.nodes
  const connections = spec.connections
  const hasLaidOut =
    Array.isArray(nodes) &&
    nodes.length > 0 &&
    Array.isArray(connections) &&
    connections.length > 0
  if (!hasLaidOut) return undefined
  return {
    preferLaidOutMindMapNodes: true,
  }
}
