import type { Connection } from '@/types'

/**
 * Incident connections for a concept map node (any edge touching the node).
 */
export function getConceptMapIncidentConnections(
  nodeId: string,
  connections: Connection[] | null | undefined
): Connection[] {
  if (!nodeId || !connections?.length) return []
  return connections.filter((c) => c.source === nodeId || c.target === nodeId)
}

/**
 * Deterministic primary edge for Tab recommendations (relationship label mode).
 * Sort by connection id so frontend apply/highlight/backend context stay aligned.
 */
export function getConceptMapPrimaryIncidentConnection(
  nodeId: string,
  connections: Connection[] | null | undefined
): Connection | null {
  const incident = getConceptMapIncidentConnections(nodeId, connections)
  if (incident.length === 0) return null
  return [...incident].sort((a, b) => a.id.localeCompare(b.id))[0] ?? null
}

/** Tab inline rec uses relationship-label stage when the node has ≥1 incident edge. */
export function conceptMapUsesRelationshipInlineRec(
  nodeId: string,
  connections: Connection[] | null | undefined
): boolean {
  return getConceptMapPrimaryIncidentConnection(nodeId, connections) !== null
}
