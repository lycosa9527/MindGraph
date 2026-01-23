/**
 * Generic Fallback Loader
 * Used for saved diagrams that already have nodes and connections arrays
 */
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

/**
 * Load generic spec (saved diagram format) into diagram nodes and connections
 *
 * @param spec - Generic spec with nodes and connections arrays
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadGenericSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  if (!spec || typeof spec !== 'object') {
    return { nodes, connections }
  }

  if (Array.isArray(spec.nodes)) {
    // Filter out invalid nodes
    const validNodes = (spec.nodes as DiagramNode[]).filter(
      (node) => node && typeof node === 'object' && typeof node.id === 'string'
    )
    nodes.push(...validNodes)
  }
  if (Array.isArray(spec.connections)) {
    // Filter out invalid connections
    const validConnections = (spec.connections as Connection[]).filter(
      (conn) =>
        conn &&
        typeof conn === 'object' &&
        typeof conn.source === 'string' &&
        typeof conn.target === 'string'
    )
    connections.push(...validConnections)
  }

  return { nodes, connections }
}
