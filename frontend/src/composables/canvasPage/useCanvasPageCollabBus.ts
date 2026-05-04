import { type Ref, onScopeDispose, watch } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

import { eventBus } from '@/composables/core/useEventBus'
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import type { CollabSyncVersion } from '@/composables/workshop/useCollabSyncVersion'
import type { ActiveEditor } from '@/composables/workshop/useWorkshop'

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
}

const SELECTION_SEND_DEBOUNCE_MS = 50
const STUCK_VERSION_THRESHOLD_MS = 15_000
const STRUCTURAL_LOCK_HOLD_MS = 400
const EDITOR_CLOSE_COOLDOWN_MS = STRUCTURAL_LOCK_HOLD_MS + 200

export function useCanvasPageCollabBus(options: UseCanvasPageCollabBusOptions) {
  let lastSentSelectionNodeId: string | null = null
  let selectionSendTimer: ReturnType<typeof setTimeout> | null = null
  let stuckVersionTimer: ReturnType<typeof setTimeout> | null = null
  const structuralLockReleaseTimers = new Map<string, ReturnType<typeof setTimeout>>()
  const recentlyClosedEditorNodes = new Set<string>()

  watch(
    () => [...options.getSelectedNodes()],
    (ids) => {
      if (!options.workshopCode.value) {
        return
      }
      if (selectionSendTimer !== null) {
        clearTimeout(selectionSendTimer)
        selectionSendTimer = null
      }
      selectionSendTimer = setTimeout(() => {
        selectionSendTimer = null
        const primary = ids.length > 0 ? ids[0] : null
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
      }, SELECTION_SEND_DEBOUNCE_MS)
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

  function clearAllStructuralLockReleaseTimers(): void {
    for (const timer of structuralLockReleaseTimers.values()) {
      clearTimeout(timer)
    }
    structuralLockReleaseTimers.clear()
  }

  function flashStructuralLock(nodeId: string): void {
    if (!nodeId || !options.workshopCode.value) {
      return
    }
    // Skip if the node's editor was just closed; otherwise the save event can
    // briefly re-lock the node after an explicit editing:false signal.
    if (recentlyClosedEditorNodes.has(nodeId)) {
      return
    }
    const existing = structuralLockReleaseTimers.get(nodeId)
    if (existing) {
      clearTimeout(existing)
    } else {
      options.notifyNodeEditing(nodeId, true)
    }
    const timer = setTimeout(() => {
      structuralLockReleaseTimers.delete(nodeId)
      options.notifyNodeEditing(nodeId, false)
    }, STRUCTURAL_LOCK_HOLD_MS)
    structuralLockReleaseTimers.set(nodeId, timer)
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
        sessionStorage.setItem('mg_workshop_code', code)
        sessionStorage.setItem('mg_workshop_diagram_id', String(diagId))
      } else if (!code && prevCode) {
        sessionStorage.removeItem('mg_workshop_code')
        sessionStorage.removeItem('mg_workshop_diagram_id')
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
      options.sendClaimNodeEdit(nodeId)
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'node_editor:closed',
    (data) => {
      const nodeId = (data as { nodeId: string }).nodeId
      if (nodeId && options.workshopCode.value) {
        recentlyClosedEditorNodes.add(nodeId)
        setTimeout(() => recentlyClosedEditorNodes.delete(nodeId), EDITOR_CLOSE_COOLDOWN_MS)
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
        flashStructuralLock(nodeId)
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
        flashStructuralLock(nodeId)
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
        flashStructuralLock(nodeId)
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
            flashStructuralLock(nodeId)
          }
        }
      }
    },
    'CanvasPage'
  )

  function resetBusTracking(): void {
    clearAllStructuralLockReleaseTimers()
    if (stuckVersionTimer !== null) {
      clearTimeout(stuckVersionTimer)
      stuckVersionTimer = null
    }
    if (selectionSendTimer !== null) {
      clearTimeout(selectionSendTimer)
      selectionSendTimer = null
    }
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
