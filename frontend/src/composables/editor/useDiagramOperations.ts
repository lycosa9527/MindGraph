/**
 * useDiagramOperations - Bridges voice-agent diagram events onto the diagram store.
 *
 * Mutations go through the same store primitives as the editor (see diagramVoiceMutations).
 */
import { onUnmounted } from 'vue'

import { useDiagramStore } from '@/stores/diagram'

import { eventBus } from '../core/useEventBus'
import {
  applyVoiceDiagramAddNodes,
  applyVoiceDiagramRemoveNodes,
  applyVoiceDiagramUpdateCenter,
  applyVoiceDiagramUpdateNodes,
} from './diagramVoiceMutations'

export interface UseDiagramOperationsOptions {
  ownerId?: string
  /** When true, skip automatic destroy on component unmount (app-level singleton). */
  persistent?: boolean
}

export function useDiagramOperations(options: UseDiagramOperationsOptions = {}) {
  const { ownerId = `DiagramOps_${Date.now()}`, persistent = false } = options

  const unsubAddNodes = eventBus.onWithOwner(
    'diagram:add_nodes',
    (data) => {
      const store = useDiagramStore()
      if (!store.data?.nodes) return

      const nodes = data.nodes as unknown[]
      if (!Array.isArray(nodes)) return

      applyVoiceDiagramAddNodes(store, nodes)
    },
    ownerId
  )

  const unsubUpdateNodes = eventBus.onWithOwner(
    'diagram:update_nodes',
    (data) => {
      const store = useDiagramStore()
      if (!store.data?.nodes) return

      const nodes = data.nodes as unknown[]
      if (!Array.isArray(nodes)) return

      applyVoiceDiagramUpdateNodes(store, nodes)
    },
    ownerId
  )

  const unsubRemoveNodes = eventBus.onWithOwner(
    'diagram:remove_nodes',
    (data) => {
      const store = useDiagramStore()
      if (!store.data?.nodes) return

      const nodeIds = data.nodeIds as unknown[]
      if (!Array.isArray(nodeIds)) return

      applyVoiceDiagramRemoveNodes(store, nodeIds)
    },
    ownerId
  )

  const unsubUpdateCenter = eventBus.onWithOwner(
    'diagram:update_center',
    (data) => {
      const store = useDiagramStore()
      if (!store.data?.nodes) return

      const payload =
        typeof data === 'object' && data !== null ? (data as Record<string, unknown>) : {}
      applyVoiceDiagramUpdateCenter(store, payload)
    },
    ownerId
  )

  function destroy(): void {
    unsubAddNodes()
    unsubUpdateNodes()
    unsubRemoveNodes()
    unsubUpdateCenter()
    eventBus.removeAllListenersForOwner(ownerId)
  }

  if (!persistent) {
    onUnmounted(() => {
      destroy()
    })
  }

  return { destroy }
}

let _globalOps: ReturnType<typeof useDiagramOperations> | null = null

export function getDiagramOperations(): ReturnType<typeof useDiagramOperations> {
  if (!_globalOps) {
    _globalOps = useDiagramOperations({ ownerId: 'GlobalDiagramOps', persistent: true })
  }
  return _globalOps
}
