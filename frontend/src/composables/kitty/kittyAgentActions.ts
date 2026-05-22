import { eventBus } from '@/composables/core/useEventBus'

export function executeKittyAgentAction(action: string, params: Record<string, unknown>): void {
  eventBus.emit('voice:action_executed', { action, params })

  switch (action) {
    case 'open_mindmate':
    case 'open_thinkguide':
      eventBus.emit('panel:open_requested', { panel: 'mindmate', source: 'kitty_agent' })
      break

    case 'close_mindmate':
    case 'close_thinkguide':
      eventBus.emit('panel:close_requested', { panel: 'mindmate', source: 'kitty_agent' })
      break

    case 'open_node_palette':
      eventBus.emit('panel:open_requested', { panel: 'nodePalette', source: 'kitty_agent' })
      break

    case 'close_node_palette':
      eventBus.emit('panel:close_requested', { panel: 'nodePalette', source: 'kitty_agent' })
      break

    case 'close_all_panels':
      eventBus.emit('panel:close_all_requested', { source: 'kitty_agent' })
      break

    case 'auto_complete':
      eventBus.emit('diagram:auto_complete_requested', { source: 'kitty_agent' })
      break

    case 'start_inline_recommendations':
      eventBus.emit('kitty:inline_recommendations_requested', {
        nodeId: params.node_id as string | undefined,
        nodeIndex: typeof params.node_index === 'number' ? params.node_index : undefined,
      })
      break

    case 'add_node_with_recommendations':
      eventBus.emit('kitty:add_node_with_recommendations_requested', {
        text: typeof params.text === 'string' ? params.text : undefined,
      })
      break

    case 'select_node':
      if (params.node_id || params.node_index !== undefined) {
        eventBus.emit('selection:select_requested', {
          nodeId: params.node_id as string,
          nodeIndex: params.node_index as number,
        })
      }
      break

    case 'explain_node':
      if (params.node_id && params.node_label) {
        eventBus.emit('panel:open_requested', { panel: 'mindmate' })
        eventBus.emit('selection:highlight_requested', { nodeId: params.node_id as string })
        setTimeout(() => {
          const prompt =
            (params.prompt as string) ||
            `Explain the concept of "${params.node_label}" in simple terms.`
          eventBus.emit('mindmate:send_message', { message: prompt })
        }, 500)
      }
      break

    case 'ask_mindmate':
    case 'ask_thinkguide': {
      const messageRaw = params.message ?? params.prompt
      const message = typeof messageRaw === 'string' ? messageRaw.trim() : ''
      if (!message) break
      eventBus.emit('panel:open_requested', { panel: 'mindmate', source: 'kitty_agent' })
      setTimeout(() => {
        eventBus.emit('mindmate:send_message', { message })
      }, 400)
      break
    }
  }
}

export function applyKittyDiagramUpdate(action: string, updates: Record<string, unknown>): void {
  switch (action) {
    case 'update_center':
      eventBus.emit('diagram:update_center', { ...updates, source: 'kitty_agent' })
      break

    case 'update_node':
    case 'update_nodes': {
      const nodeUpdates = Array.isArray(updates) ? updates : [updates]
      eventBus.emit('diagram:update_nodes', { nodes: nodeUpdates, source: 'kitty_agent' })
      break
    }

    case 'add_node':
    case 'add_nodes': {
      const nodesToAdd = Array.isArray(updates) ? updates : [updates]
      eventBus.emit('diagram:add_nodes', { nodes: nodesToAdd, source: 'kitty_agent' })
      break
    }

    case 'delete_node':
    case 'remove_nodes': {
      const nodeIds = Array.isArray(updates) ? updates : [updates]
      eventBus.emit('diagram:remove_nodes', { nodeIds, source: 'kitty_agent' })
      break
    }

    default:
      eventBus.emit('diagram:update_requested', { action, updates, source: 'kitty_agent' })
  }
}
