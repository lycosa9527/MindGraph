import {
  computeDefaultArrowheadForConceptMap,
  getConceptMapNodeCenter,
} from '@/composables/diagrams/conceptMapHandles'
import { useConceptMapRelationshipStore } from '@/stores/conceptMapRelationship'
import type { Connection } from '@/types'
import { normalizeTopicRootLabelIfNeeded } from '@/utils/conceptMapTopicRootEdge'

import { collabForeignLockBlocksAnyId, emitCollabDeleteBlocked } from './collabHelpers'
import type { DiagramContext } from './types'

/**
 * Connection management slice.
 * Handles adding, labelling, and arrowhead toggling on connections.
 */
type AddConnectionExtra = Partial<
  Pick<Connection, 'linkedFromConnectionId' | 'arrowheadDirection' | 'arrowheadLocked'>
>

export function useConnectionManagementSlice(ctx: DiagramContext) {
  function addConnection(
    sourceId: string,
    targetId: string,
    label?: string,
    extra?: AddConnectionExtra
  ): string | null {
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
      ...extra,
    }
    if (ctx.type.value === 'concept_map' && !conn.arrowheadLocked) {
      const sourceNode = ctx.data.value.nodes.find((n) => n.id === sourceId)
      const targetNode = ctx.data.value.nodes.find((n) => n.id === targetId)
      if (sourceNode && targetNode) {
        const sc = getConceptMapNodeCenter(sourceNode)
        const tc = getConceptMapNodeCenter(targetNode)
        conn.arrowheadDirection = computeDefaultArrowheadForConceptMap(sc, tc)
      }
    }
    ctx.data.value.connections.push(conn)
    normalizeTopicRootLabelIfNeeded(conn, ctx.data.value.nodes)
    return connId
  }

  function updateConnectionLabel(connectionId: string, label: string): boolean {
    if (!ctx.data.value?.connections) return false

    const conn = ctx.data.value.connections.find((c) => c.id === connectionId)
    if (!conn) return false

    conn.label = label
    normalizeTopicRootLabelIfNeeded(conn, ctx.data.value.nodes)
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

  function removeConnection(connectionId: string): boolean {
    if (!ctx.data.value?.connections || ctx.type.value !== 'concept_map') {
      return false
    }

    const conns = ctx.data.value.connections
    const exists = conns.some((c) => c.id === connectionId)
    if (!exists) {
      return false
    }

    const toRemove = new Set<string>([connectionId])
    let growing = true
    while (growing) {
      growing = false
      for (const c of conns) {
        if (toRemove.has(c.id)) {
          continue
        }
        const parentId = c.linkedFromConnectionId
        if (parentId && toRemove.has(parentId)) {
          toRemove.add(c.id)
          growing = true
        }
      }
    }

    const endpointNodeIds = new Set<string>()
    for (const c of conns) {
      if (toRemove.has(c.id)) {
        endpointNodeIds.add(c.source)
        endpointNodeIds.add(c.target)
      }
    }

    if (collabForeignLockBlocksAnyId(ctx, endpointNodeIds)) {
      emitCollabDeleteBlocked()
      return false
    }

    const relStore = useConceptMapRelationshipStore()
    for (const id of toRemove) {
      relStore.clearConnection(id)
    }

    ctx.data.value.connections = conns.filter((c) => !toRemove.has(c.id))

    if (ctx.selectedConnectionId.value && toRemove.has(ctx.selectedConnectionId.value)) {
      ctx.selectedConnectionId.value = null
    }

    ctx.pushHistory('Delete relationship')
    return true
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
    removeConnection,
    updateConnectionArrowheadsForNode,
    toggleConnectionArrowhead,
  }
}
