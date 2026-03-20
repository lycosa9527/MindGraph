import {
  computeDefaultArrowheadForConceptMap,
  getConceptMapNodeCenter,
} from '@/composables/diagrams/conceptMapHandles'
import type { Connection } from '@/types'

import type { DiagramContext } from './types'

/**
 * Connection management slice.
 * Handles adding, labelling, and arrowhead toggling on connections.
 */
export function useConnectionManagementSlice(ctx: DiagramContext) {
  function addConnection(sourceId: string, targetId: string, label?: string): string | null {
    if (!ctx.data.value?.nodes || !ctx.data.value.connections) return null

    const sourceExists = ctx.data.value.nodes.some((n) => n.id === sourceId)
    const targetExists = ctx.data.value.nodes.some((n) => n.id === targetId)
    if (!sourceExists || !targetExists) return null

    const duplicate = ctx.data.value.connections.some(
      (c) => c.source === sourceId && c.target === targetId
    )
    if (duplicate) return null

    const connId = `conn-${Date.now()}`
    const conn: Connection = {
      id: connId,
      source: sourceId,
      target: targetId,
      label: label || '',
    }
    if (ctx.type.value === 'concept_map') {
      const sourceNode = ctx.data.value.nodes.find((n) => n.id === sourceId)
      const targetNode = ctx.data.value.nodes.find((n) => n.id === targetId)
      if (sourceNode && targetNode) {
        const sc = getConceptMapNodeCenter(sourceNode)
        const tc = getConceptMapNodeCenter(targetNode)
        conn.arrowheadDirection = computeDefaultArrowheadForConceptMap(sc, tc)
      }
    }
    ctx.data.value.connections.push(conn)
    return connId
  }

  function updateConnectionLabel(connectionId: string, label: string): boolean {
    if (!ctx.data.value?.connections) return false

    const conn = ctx.data.value.connections.find((c) => c.id === connectionId)
    if (!conn) return false

    conn.label = label
    return true
  }

  function updateConnectionArrowheadsForNode(nodeId: string): void {
    if (ctx.type.value !== 'concept_map' || !ctx.data.value?.nodes || !ctx.data.value.connections)
      return

    const nodes = ctx.data.value.nodes
    const connections = ctx.data.value.connections.filter(
      (c) => c.source === nodeId || c.target === nodeId
    )
    for (const conn of connections) {
      if (conn.arrowheadLocked) continue
      const sourceNode = nodes.find((n) => n.id === conn.source)
      const targetNode = nodes.find((n) => n.id === conn.target)
      if (sourceNode && targetNode) {
        const sc = getConceptMapNodeCenter(sourceNode)
        const tc = getConceptMapNodeCenter(targetNode)
        conn.arrowheadDirection = computeDefaultArrowheadForConceptMap(sc, tc)
      }
    }
  }

  function toggleConnectionArrowhead(
    connectionId: string,
    segment: 'sourceSegment' | 'targetSegment'
  ): boolean {
    if (!ctx.data.value?.connections) return false

    const conn = ctx.data.value.connections.find((c) => c.id === connectionId)
    if (!conn) return false

    const current = conn.arrowheadDirection ?? 'none'
    const clickedSource = segment === 'sourceSegment'
    const next: 'none' | 'source' | 'target' | 'both' =
      current === 'none'
        ? clickedSource
          ? 'source'
          : 'target'
        : current === 'source'
          ? 'target'
          : current === 'target'
            ? 'both'
            : 'none'
    conn.arrowheadDirection = next
    conn.arrowheadLocked = true
    ctx.pushHistory('Toggle arrowhead')
    return true
  }

  return {
    addConnection,
    updateConnectionLabel,
    updateConnectionArrowheadsForNode,
    toggleConnectionArrowhead,
  }
}
