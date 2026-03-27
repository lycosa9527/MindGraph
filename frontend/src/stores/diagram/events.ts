import { DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
import { eventBus } from '@/composables/core/useEventBus'
import type { DiagramNode, DiagramType, MindGraphEdgeType } from '@/types'

import type { DiagramEvent, DiagramEventType, EventCallback, MindMapCurveExtents } from './types'

const eventSubscribers = new Map<DiagramEventType | '*', Set<EventCallback>>()

export function emitEvent(type: DiagramEventType, payload?: unknown): void {
  const event: DiagramEvent = { type, payload, timestamp: Date.now() }

  eventSubscribers.get(type)?.forEach((cb) => cb(event))
  eventSubscribers.get('*')?.forEach((cb) => cb(event))

  switch (type) {
    case 'diagram:node_added':
      eventBus.emit('diagram:node_added', { node: payload, category: undefined })
      break
    case 'diagram:node_updated':
      eventBus.emit('diagram:node_updated', payload as { nodeId: string; updates: unknown })
      break
    case 'diagram:nodes_deleted':
      eventBus.emit('diagram:nodes_deleted', payload as { nodeIds: string[] })
      break
    case 'diagram:selection_changed':
      eventBus.emit('state:selection_changed', payload as { selectedNodes: string[] })
      eventBus.emit('interaction:selection_changed', payload as { selectedNodes: string[] })
      break
    case 'diagram:position_changed':
      eventBus.emit(
        'diagram:position_saved',
        payload as { nodeId: string; position: { x: number; y: number } }
      )
      break
    case 'diagram:operation_completed':
      eventBus.emit(
        'diagram:operation_completed',
        payload as { operation: string; details?: unknown }
      )
      break
    case 'diagram:layout_reset':
      eventBus.emit('diagram:positions_cleared', {})
      break
  }
}

export function subscribeToDiagramEvents(
  eventType: DiagramEventType | '*',
  callback: EventCallback
): () => void {
  let subscribers = eventSubscribers.get(eventType)
  if (!subscribers) {
    subscribers = new Set()
    eventSubscribers.set(eventType, subscribers)
  }
  subscribers.add(callback)

  return () => {
    eventSubscribers.get(eventType)?.delete(callback)
  }
}

export function getEdgeTypeForDiagram(diagramType: DiagramType | null): MindGraphEdgeType {
  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    return 'curved'
  }
  if (!diagramType) return 'curved'

  const edgeTypeMap: Partial<Record<DiagramType, MindGraphEdgeType>> = {
    bubble_map: 'radial',
    double_bubble_map: 'curved',
    tree_map: 'step',
    flow_map: 'straight',
    multi_flow_map: 'straight',
    brace_map: 'brace',
    bridge_map: 'bridge',
  }

  return edgeTypeMap[diagramType] || 'curved'
}

export function getMindMapCurveExtents(nodes: DiagramNode[], centerX: number): MindMapCurveExtents {
  const leftNodes = nodes.filter((n) => n.type === 'branch' && n.id.startsWith('branch-l-'))
  const rightNodes = nodes.filter((n) => n.type === 'branch' && n.id.startsWith('branch-r-'))
  const getCenterX = (n: DiagramNode) =>
    (n.position?.x ?? 0) + ((n.data?.estimatedWidth as number) || DEFAULT_NODE_WIDTH) / 2
  const left = leftNodes.length > 0 ? centerX - Math.min(...leftNodes.map(getCenterX)) : 0
  const right = rightNodes.length > 0 ? Math.max(...rightNodes.map(getCenterX)) - centerX : 0
  return { left, right }
}
