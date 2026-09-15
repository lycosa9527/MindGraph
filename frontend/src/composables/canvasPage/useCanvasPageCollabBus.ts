import { type Ref, nextTick, onScopeDispose, watch } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

import { eventBus } from '@/composables/core/useEventBus'
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import {
  consumeRecentlyClosedFlash,
  shouldFlashStructuralLock,
} from '@/composables/workshop/applyCollabEditorPresence'
import type { CollabSyncVersion } from '@/composables/workshop/useCollabSyncVersion'
import type { ActiveEditor } from '@/composables/workshop/useWorkshop'
import {
  clearWorkshopSessionStorage,
  persistWorkshopSession,
  queryWithSessionDiagramId,
} from '@/utils/workshopSessionStorage'

interface CanvasPageCollabNotify {
  warning: (message: string) => void
}

interface UseCanvasPageCollabBusOptions {
  workshopCode: Ref<string | null>
  workshopVisibility: Ref<'organization' | 'network' | null>
  sessionDiagramId: Ref<string | null>
  activeEditors: { readonly value: Map<string, ActiveEditor> }
  getSelectedNodes: () => string[]
  route: RouteLocationNormalizedLoaded
  router: Router
  notify: CanvasPageCollabNotify
  t: UseLanguageTranslate
  getCurrentUserId: () => number
  setOwnerIdOptimistic: (userId: number) => void
  setActiveDiagram: (diagramId: string) => void
  sendNodeSelected: (nodeId: string | null, selected: boolean) => void
  sendClaimNodeEdit: (nodeId: string) => void
  notifyNodeEditing: (nodeId: string, editing: boolean) => void
  reconnect: () => void
  collabSyncVersion: CollabSyncVersion
  /** Skip local presence flash while a remote WS patch is being applied. */
  applyingRemoteCollabPatch?: Ref<boolean>
}

const STUCK_VERSION_THRESHOLD_MS = 15_000

export function useCanvasPageCollabBus(options: UseCanvasPageCollabBusOptions) {
  let lastSentSelectionNodeId: string | null = null
  let selectionSendScheduled = false
  let stuckVersionTimer: ReturnType<typeof setTimeout> | null = null
  const structuralHeldNodes = new Set<string>()
  const draggingNodeIds = new Set<string>()
  const recentlyClosedEditorNodes = new Set<string>()
  const openTextEditorNodes = new Set<string>()

  watch(
    () => [...options.getSelectedNodes()],
    () => {
      if (!options.workshopCode.value) {
        return
      }
      if (selectionSendScheduled) {
        return
      }
      selectionSendScheduled = true
      void nextTick(() => {
        selectionSendScheduled = false
        const current = options.getSelectedNodes()
        const primary = current.length > 0 ? current[0] : null
        if (primary === lastSentSelectionNodeId) {
          return
        }
        if (lastSentSelectionNodeId && lastSentSelectionNodeId !== primary) {
          options.sendNodeSelected(lastSentSelectionNodeId, false)
        }
        if (primary) {
          options.sendNodeSelected(primary, true)
        }
        lastSentSelectionNodeId = primary
      })
    },
    { deep: true }
  )

  watch(
    () => [
      options.collabSyncVersion.pendingResync.value,
      options.collabSyncVersion.liveVersion.value,
      options.collabSyncVersion.lastFrameAt.value,
    ],
    () => {
      if (stuckVersionTimer !== null) {
        clearTimeout(stuckVersionTimer)
        stuckVersionTimer = null
      }
      if (!options.collabSyncVersion.pendingResync.value) {
        return
      }
      stuckVersionTimer = setTimeout(() => {
        stuckVersionTimer = null
        if (options.collabSyncVersion.pendingResync.value) {
          if (import.meta.env.DEV) {
            console.warn('[CollabSync] pendingResync stalled — forcing reconnect')
          }
          options.reconnect()
        }
      }, STUCK_VERSION_THRESHOLD_MS)
    }
  )

  function refreshOpenTextLocks(): void {
    for (const nodeId of openTextEditorNodes) {
      options.sendClaimNodeEdit(nodeId)
    }
  }

  function beginStructuralLock(nodeId: string): void {
    if (options.applyingRemoteCollabPatch?.value) {
      return
    }
    if (consumeRecentlyClosedFlash(recentlyClosedEditorNodes, nodeId)) {
      return
    }
    const holder = options.activeEditors.value.get(nodeId)
    if (
      !shouldFlashStructuralLock({
        workshopActive: Boolean(options.workshopCode.value),
        nodeId,
        recentlyClosed: false,
        textEditorOpen: openTextEditorNodes.has(nodeId),
        holderUserId: holder?.user_id ?? null,
        currentUserId: options.getCurrentUserId(),
      })
    ) {
      return
    }
    if (structuralHeldNodes.has(nodeId)) {
      return
    }
    structuralHeldNodes.add(nodeId)
    options.notifyNodeEditing(nodeId, true)
  }

  function endStructuralLock(nodeId: string): void {
    if (!structuralHeldNodes.has(nodeId)) {
      return
    }
    if (openTextEditorNodes.has(nodeId) || draggingNodeIds.has(nodeId)) {
      return
    }
    structuralHeldNodes.delete(nodeId)
    options.notifyNodeEditing(nodeId, false)
  }

  function applyJoinWorkshopFromQuery(): void {
    const raw = options.route.query.join_workshop
    if (!raw || typeof raw !== 'string') {
      return
    }
    const trimmed = raw.trim()
    if (!/^[2-9A-HJ-KM-NP-Z]{3}-[2-9A-HJ-KM-NP-Z]{3}$/i.test(trimmed)) {
      return
    }
    options.workshopCode.value = trimmed
    options.workshopVisibility.value = null
    eventBus.emit('workshop:code-changed', { code: trimmed })
    const nextQuery = { ...options.route.query } as Record<string, string | string[] | undefined>
    delete nextQuery.join_workshop
    options.router.replace({ query: nextQuery })
  }

  function applyWorkshopCodeFromSession(code: string, diagramId: string): void {
    options.setActiveDiagram(diagramId)
    options.workshopCode.value = code
  }

  watch(
    [() => options.workshopCode.value, () => options.sessionDiagramId.value],
    ([code, diagId], [prevCode]) => {
      if (code && diagId) {
        const diagramId = String(diagId)
        persistWorkshopSession(code, diagramId)
        options.setActiveDiagram(diagramId)
        const nextQuery = queryWithSessionDiagramId(
          options.route.query as Record<string, unknown>,
          diagramId
        )
        if (nextQuery) {
          void options.router.replace({
            query: nextQuery as Record<string, string | string[] | undefined>,
          })
        }
      } else if (!code && prevCode) {
        clearWorkshopSessionStorage()
      }
    }
  )

  eventBus.onWithOwner(
    'workshop:code-changed',
    (data) => {
      if (data.code !== undefined) {
        options.workshopCode.value = data.code as string | null
      }
      if (data.code === null) {
        options.workshopVisibility.value = null
      } else if (data.visibility === 'organization' || data.visibility === 'network') {
        options.workshopVisibility.value = data.visibility
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'diagram:collab_delete_blocked',
    () => {
      options.notify.warning(options.t('notification.collabDeleteBlocked'))
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'diagram:collab_lock_blocked',
    () => {
      options.notify.warning(options.t('collab.nodeLocked'))
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'workshop:host-started',
    () => {
      const uid = options.getCurrentUserId()
      if (Number.isFinite(uid)) {
        options.setOwnerIdOptimistic(uid)
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'node_editor:opening',
    (data) => {
      const nodeId = (data as { nodeId: string }).nodeId
      if (!nodeId || !options.workshopCode.value) {
        return
      }
      const ed = options.activeEditors.value.get(nodeId)
      if (ed && ed.user_id !== options.getCurrentUserId()) {
        return
      }
      openTextEditorNodes.add(nodeId)
      options.sendClaimNodeEdit(nodeId)
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'node_editor:closed',
    (data) => {
      const nodeId = (data as { nodeId: string }).nodeId
      if (nodeId && options.workshopCode.value) {
        openTextEditorNodes.delete(nodeId)
        recentlyClosedEditorNodes.add(nodeId)
        structuralHeldNodes.delete(nodeId)
        options.notifyNodeEditing(nodeId, false)
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'diagram:node_added',
    (data) => {
      const payload = data as { node?: { id?: string } } | undefined
      const nodeId = payload?.node?.id
      if (typeof nodeId === 'string' && nodeId) {
        beginStructuralLock(nodeId)
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'diagram:node_updated',
    (data) => {
      const payload = data as { nodeId?: string } | undefined
      const nodeId = payload?.nodeId
      if (typeof nodeId === 'string' && nodeId) {
        beginStructuralLock(nodeId)
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'diagram:position_changed',
    (data) => {
      const payload = data as { nodeId?: string } | undefined
      const nodeId = payload?.nodeId
      if (typeof nodeId === 'string' && nodeId) {
        beginStructuralLock(nodeId)
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'diagram:branch_moved',
    () => {
      const selected = options.getSelectedNodes()
      if (Array.isArray(selected)) {
        for (const nodeId of selected) {
          if (typeof nodeId === 'string' && nodeId) {
            beginStructuralLock(nodeId)
          }
        }
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'interaction:drag_started',
    (data) => {
      const nodeId = (data as { nodeId?: string }).nodeId
      if (typeof nodeId === 'string' && nodeId) {
        draggingNodeIds.add(nodeId)
        beginStructuralLock(nodeId)
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'interaction:drag_ended',
    (data) => {
      const nodeId = (data as { nodeId?: string }).nodeId
      if (typeof nodeId === 'string' && nodeId) {
        draggingNodeIds.delete(nodeId)
        endStructuralLock(nodeId)
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'workshop:collab-ack',
    (data) => {
      const raw = (data as { nodeIds?: unknown }).nodeIds
      if (Array.isArray(raw)) {
        for (const item of raw) {
          if (typeof item === 'string' && item) {
            endStructuralLock(item)
          }
        }
      }
      refreshOpenTextLocks()
    },
    'CanvasPage'
  )

  function resetBusTracking(): void {
    for (const nodeId of structuralHeldNodes) {
      options.notifyNodeEditing(nodeId, false)
    }
    structuralHeldNodes.clear()
    draggingNodeIds.clear()
    recentlyClosedEditorNodes.clear()
    openTextEditorNodes.clear()
    if (stuckVersionTimer !== null) {
      clearTimeout(stuckVersionTimer)
      stuckVersionTimer = null
    }
    selectionSendScheduled = false
  }

  onScopeDispose(() => {
    resetBusTracking()
  })

  return {
    applyJoinWorkshopFromQuery,
    applyWorkshopCodeFromSession,
    resetBusTracking,
  }
}
