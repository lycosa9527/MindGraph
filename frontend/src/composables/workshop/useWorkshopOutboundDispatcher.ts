import type { Ref } from 'vue'

interface UseWorkshopOutboundDispatcherOptions {
  ws: Ref<WebSocket | null>
  diagramId: Ref<string | null>
  pendingResync: Readonly<Ref<boolean>>
  queueSize: Readonly<Ref<number>>
  getSessionDiagramId: () => string | null
  canSendRealtimeControl: () => boolean
  clearRoomIdleCountdownUi: () => void
  enqueueUpdatePayload: (payload: Record<string, unknown> & { type: string }) => string
}

function buildUpdatePayload(
  options: UseWorkshopOutboundDispatcherOptions,
  spec?: Record<string, unknown>,
  nodes?: Array<Record<string, unknown>>,
  connections?: Array<Record<string, unknown>>,
  deletedNodeIds?: string[],
  deletedConnectionIds?: string[]
): Record<string, unknown> | null {
  const hasGranular =
    nodes !== undefined ||
    connections !== undefined ||
    (deletedNodeIds && deletedNodeIds.length > 0) ||
    (deletedConnectionIds && deletedConnectionIds.length > 0)

  if (!hasGranular && !spec) {
    return null
  }

  const updateMessage: Record<string, unknown> = {
    type: 'update',
    diagram_id: options.getSessionDiagramId() ?? options.diagramId.value,
    timestamp: new Date().toISOString(),
  }

  if (hasGranular) {
    if (nodes !== undefined) {
      updateMessage.nodes = nodes
    }
    if (connections !== undefined) {
      updateMessage.connections = connections
    }
    if (deletedNodeIds && deletedNodeIds.length > 0) {
      updateMessage.deleted_node_ids = deletedNodeIds
    }
    if (deletedConnectionIds && deletedConnectionIds.length > 0) {
      updateMessage.deleted_connection_ids = deletedConnectionIds
    }
  } else if (spec) {
    updateMessage.spec = spec
  }

  return updateMessage
}

export function useWorkshopOutboundDispatcher(options: UseWorkshopOutboundDispatcherOptions) {
  const nodeEditingThrottleMap = new Map<
    string,
    { timer: ReturnType<typeof setTimeout> | null; lastEditing: boolean }
  >()
  const NODE_EDITING_THROTTLE_MS = 100

  function sendUpdate(
    spec?: Record<string, unknown>,
    nodes?: Array<Record<string, unknown>>,
    connections?: Array<Record<string, unknown>>,
    deletedNodeIds?: string[],
    deletedConnectionIds?: string[]
  ): string | null {
    const payload = buildUpdatePayload(
      options,
      spec,
      nodes,
      connections,
      deletedNodeIds,
      deletedConnectionIds
    )
    if (!payload) {
      if (import.meta.env.DEV) {
        console.warn(
          '[WorkshopWS] sendUpdate called without spec, nodes, connections, or deletions'
        )
      }
      return null
    }

    options.clearRoomIdleCountdownUi()

    if (import.meta.env.DEV) {
      console.log('[CollabSync] sendUpdate enqueue', {
        wsReady: options.ws.value?.readyState,
        pendingResync: options.pendingResync.value,
        hasGranular:
          nodes !== undefined ||
          connections !== undefined ||
          (deletedNodeIds?.length ?? 0) > 0 ||
          (deletedConnectionIds?.length ?? 0) > 0,
        nodes: nodes?.length ?? 0,
        conns: connections?.length ?? 0,
        delNodes: deletedNodeIds?.length ?? 0,
        delConns: deletedConnectionIds?.length ?? 0,
        queueDepth: options.queueSize.value,
      })
    }

    return options.enqueueUpdatePayload(payload as Record<string, unknown> & { type: string })
  }

  function sendNodeSelected(nodeId: string | null, selected: boolean): void {
    if (!options.canSendRealtimeControl()) {
      return
    }
    if (!nodeId) {
      return
    }
    try {
      if (!options.ws.value) {
        return
      }
      options.ws.value.send(
        JSON.stringify({
          type: 'node_selected',
          node_id: nodeId,
          selected,
        })
      )
    } catch (error) {
      console.error('[WorkshopWS] Failed to send node_selected:', error)
    }
  }

  function sendNodeEditingRaw(nodeId: string, editing: boolean): void {
    if (!options.canSendRealtimeControl()) {
      return
    }
    try {
      if (!options.ws.value) {
        return
      }
      options.ws.value.send(JSON.stringify({ type: 'node_editing', node_id: nodeId, editing }))
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error('[WorkshopWS] Failed to send node_editing:', error)
      }
    }
  }

  function notifyNodeEditing(nodeId: string, editing: boolean): void {
    if (!options.canSendRealtimeControl()) {
      return
    }
    let state = nodeEditingThrottleMap.get(nodeId)
    if (!state) {
      state = { timer: null, lastEditing: editing }
      nodeEditingThrottleMap.set(nodeId, state)
    }
    state.lastEditing = editing
    if (state.timer === null) {
      sendNodeEditingRaw(nodeId, editing)
      state.timer = setTimeout(() => {
        const s = nodeEditingThrottleMap.get(nodeId)
        if (s) {
          s.timer = null
          sendNodeEditingRaw(nodeId, s.lastEditing)
        }
      }, NODE_EDITING_THROTTLE_MS)
    }
  }

  function sendClaimNodeEdit(nodeId: string): void {
    if (!options.canSendRealtimeControl()) {
      return
    }
    try {
      if (!options.ws.value) {
        return
      }
      options.ws.value.send(JSON.stringify({ type: 'claim_node_edit', node_id: nodeId }))
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error('[WorkshopWS] Failed to send claim_node_edit:', error)
      }
    }
  }

  function clearNodeEditingThrottles(): void {
    nodeEditingThrottleMap.forEach((state) => {
      if (state.timer !== null) {
        clearTimeout(state.timer)
        state.timer = null
      }
    })
    nodeEditingThrottleMap.clear()
  }

  return {
    sendUpdate,
    sendNodeSelected,
    notifyNodeEditing,
    sendClaimNodeEdit,
    clearNodeEditingThrottles,
  }
}
