import { type Ref, nextTick, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import type { DiagramNode } from '@/types/diagram'

import { calculateDiff } from './diagramDiff'

interface CanvasDiagramData {
  nodes?: unknown[]
  connections?: unknown[]
}

interface UseCanvasPageCollabDiffOptions {
  workshopCode: Ref<string | null>
  applyingRemoteCollabPatch: Ref<boolean>
  getDiagramData: () => CanvasDiagramData | null | undefined
  mergeGranularUpdate: (
    nodes?: Array<Record<string, unknown>>,
    connections?: Array<Record<string, unknown>>,
    deletedNodeIds?: string[],
    deletedConnectionIds?: string[]
  ) => boolean
  clearRedoStack: () => void
  updateNode: (id: string, patch: Partial<DiagramNode>) => void
  sendUpdate: (
    spec?: Record<string, unknown>,
    nodes?: Array<Record<string, unknown>>,
    connections?: Array<Record<string, unknown>>,
    deletedNodeIds?: string[],
    deletedConnectionIds?: string[]
  ) => string | null
}

const DIFF_DEBOUNCE_MS = 40
const DIFF_MAX_WAIT_MS = 200

export function useCanvasPageCollabDiff(options: UseCanvasPageCollabDiffOptions) {
  let previousNodes: Array<Record<string, unknown>> = []
  let previousConnections: Array<Record<string, unknown>> = []
  let diffFlushTimer: ReturnType<typeof setTimeout> | null = null
  let diffFirstDirtyAt = 0

  /** Pre-send node clones for ``update_partial_filtered`` rollback. */
  const preSendNodeSnapshots = new Map<string, Record<string, unknown>>()

  function clearPendingDiffTimer(): void {
    if (diffFlushTimer !== null) {
      clearTimeout(diffFlushTimer)
      diffFlushTimer = null
    }
    diffFirstDirtyAt = 0
  }

  function syncPreviousFromCurrent(): void {
    const current = options.getDiagramData()
    if (current) {
      previousNodes = JSON.parse(JSON.stringify(current.nodes ?? []))
      previousConnections = JSON.parse(JSON.stringify(current.connections ?? []))
    }
  }

  function onGranularUpdate(
    nodes?: Array<Record<string, unknown>>,
    connections?: Array<Record<string, unknown>>,
    deletedNodeIds?: string[],
    deletedConnectionIds?: string[]
  ): void {
    if (!nodes && !connections && !deletedNodeIds?.length && !deletedConnectionIds?.length) {
      return
    }
    if (import.meta.env.DEV) {
      console.log('[CollabDebug] onGranularUpdate merging', {
        inNodes: nodes?.length ?? 0,
        inConns: connections?.length ?? 0,
        inDelNodes: deletedNodeIds?.length ?? 0,
        inDelConns: deletedConnectionIds?.length ?? 0,
      })
    }
    options.applyingRemoteCollabPatch.value = true
    try {
      const ok = options.mergeGranularUpdate(
        nodes,
        connections,
        deletedNodeIds,
        deletedConnectionIds
      )
      if (import.meta.env.DEV) {
        console.log('[CollabDebug] mergeGranularUpdate result', ok)
      }
      options.clearRedoStack()
    } finally {
      // mergeGranularUpdate mutates diagramStore.data.nodes in-place without
      // replacing the data object reference. Keep local diff cursors in sync.
      syncPreviousFromCurrent()
      clearPendingDiffTimer()
      nextTick(() => {
        options.applyingRemoteCollabPatch.value = false
      })
    }
  }

  function runDiffAndSend(): void {
    diffFlushTimer = null
    diffFirstDirtyAt = 0
    const currentData = options.getDiagramData()
    if (!currentData || !currentData.nodes || !currentData.connections) {
      if (import.meta.env.DEV) {
        console.log('[CollabDebug] runDiffAndSend short-circuit reason=no-data')
      }
      return
    }
    if (!options.workshopCode.value) {
      if (import.meta.env.DEV) {
        console.log('[CollabDebug] runDiffAndSend short-circuit reason=no-workshop')
      }
      previousNodes = JSON.parse(JSON.stringify(currentData.nodes))
      previousConnections = JSON.parse(JSON.stringify(currentData.connections || []))
      return
    }
    if (options.applyingRemoteCollabPatch.value) {
      if (import.meta.env.DEV) {
        console.log('[CollabDebug] runDiffAndSend short-circuit reason=applying-remote-patch')
      }
      void nextTick(() => {
        scheduleDiffFlush()
      })
      return
    }

    if (import.meta.env.DEV) {
      console.log('[CollabDebug] runDiffAndSend entry', {
        workshopCode: options.workshopCode.value,
        nodes: currentData.nodes.length,
        conns: (currentData.connections || []).length,
      })
    }

    const currentNodes = currentData.nodes as Array<{ id: string }>
    const currentConnections = (currentData.connections || []) as Array<{ id: string }>
    const changedNodes = calculateDiff(previousNodes as Array<{ id: string }>, currentNodes)
    const changedConnections = calculateDiff(
      previousConnections as Array<{ id: string }>,
      currentConnections
    )

    const currentNodeIds = new Set(currentNodes.map((n) => n.id))
    const deletedNodeIds = (previousNodes as Array<{ id: string }>)
      .filter((n) => n.id && !currentNodeIds.has(n.id))
      .map((n) => n.id)

    const currentConnectionIds = new Set(currentConnections.map((c) => c.id))
    const deletedConnectionIds = (previousConnections as Array<{ id: string }>)
      .filter((c) => c.id && !currentConnectionIds.has(c.id))
      .map((c) => c.id)

    if (import.meta.env.DEV) {
      console.log('[CollabDebug] runDiffAndSend diff', {
        changedNodes: changedNodes.length,
        changedConns: changedConnections.length,
        deletedNodes: deletedNodeIds.length,
        deletedConns: deletedConnectionIds.length,
        sampleNodeId: (changedNodes[0] as Record<string, unknown> | undefined)?.id,
        sampleDeletedId: deletedNodeIds[0],
      })
    }

    if (
      changedNodes.length > 0 ||
      changedConnections.length > 0 ||
      deletedNodeIds.length > 0 ||
      deletedConnectionIds.length > 0
    ) {
      if (import.meta.env.DEV) {
        console.log('[CollabDebug] runDiffAndSend calling-sendUpdate')
      }
      for (const n of changedNodes) {
        const rid = (n as { id?: string }).id
        if (typeof rid === 'string' && rid) {
          preSendNodeSnapshots.set(rid, JSON.parse(JSON.stringify(n)) as Record<string, unknown>)
        }
      }
      options.sendUpdate(
        undefined,
        changedNodes.length > 0 ? changedNodes : undefined,
        changedConnections.length > 0 ? changedConnections : undefined,
        deletedNodeIds,
        deletedConnectionIds
      )
    } else if (import.meta.env.DEV) {
      console.log('[CollabDebug] runDiffAndSend nothing-to-send')
    }

    previousNodes = JSON.parse(JSON.stringify(currentNodes))
    previousConnections = JSON.parse(JSON.stringify(currentConnections))
  }

  function scheduleDiffFlush(): void {
    const now = Date.now()
    if (diffFirstDirtyAt === 0) {
      diffFirstDirtyAt = now
    }
    if (diffFlushTimer !== null) {
      clearTimeout(diffFlushTimer)
    }
    const elapsed = now - diffFirstDirtyAt
    if (elapsed >= DIFF_MAX_WAIT_MS) {
      runDiffAndSend()
      return
    }
    const wait = Math.min(DIFF_DEBOUNCE_MS, DIFF_MAX_WAIT_MS - elapsed)
    diffFlushTimer = setTimeout(runDiffAndSend, wait)
  }

  watch(
    () => options.getDiagramData(),
    (newData) => {
      if (!newData || !newData.nodes || !newData.connections) return

      if (!options.workshopCode.value) {
        previousNodes = JSON.parse(JSON.stringify(newData.nodes))
        previousConnections = JSON.parse(JSON.stringify(newData.connections || []))
        return
      }

      const nodes = newData.nodes as Array<{ id: string }>
      const connections = (newData.connections || []) as Array<{ id: string }>

      if (options.applyingRemoteCollabPatch.value) {
        previousNodes = JSON.parse(JSON.stringify(nodes))
        previousConnections = JSON.parse(JSON.stringify(connections))
        void nextTick(() => {
          scheduleDiffFlush()
        })
        return
      }

      scheduleDiffFlush()
    },
    { deep: true }
  )

  function restoreFilteredNodes(rawNodeIds: unknown): void {
    if (!Array.isArray(rawNodeIds)) {
      return
    }
    for (const item of rawNodeIds) {
      if (typeof item !== 'string' || !item) {
        continue
      }
      const snap = preSendNodeSnapshots.get(item)
      if (snap) {
        options.updateNode(item, snap as Partial<DiagramNode>)
        preSendNodeSnapshots.delete(item)
      }
    }
  }

  function acknowledgeNodes(rawNodeIds: unknown): void {
    if (!Array.isArray(rawNodeIds)) {
      preSendNodeSnapshots.clear()
      return
    }
    for (const item of rawNodeIds) {
      if (typeof item === 'string' && item) {
        preSendNodeSnapshots.delete(item)
      }
    }
  }

  function resetDiffTracking(): void {
    previousNodes = []
    previousConnections = []
    preSendNodeSnapshots.clear()
    clearPendingDiffTimer()
  }

  eventBus.onWithOwner(
    'workshop:partial-filtered',
    (data) => {
      restoreFilteredNodes((data as { nodeIds?: unknown }).nodeIds)
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'workshop:collab-ack',
    (data) => {
      acknowledgeNodes((data as { nodeIds?: unknown }).nodeIds)
    },
    'CanvasPage'
  )

  return {
    onGranularUpdate,
    resetDiffTracking,
  }
}
