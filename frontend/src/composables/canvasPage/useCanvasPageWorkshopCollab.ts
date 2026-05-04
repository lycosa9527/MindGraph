/**
 * Workshop / canvas collaboration: WebSocket, remote selection, editing indicators, granular sync.
 */
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useWorkshop } from '@/composables/workshop/useWorkshop'
import { useAuthStore, useDiagramStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import { authFetch } from '@/utils/api'

import { useCanvasPageCollabBus } from './useCanvasPageCollabBus'
import { useCanvasPageCollabDiff } from './useCanvasPageCollabDiff'
import { useCanvasPageCollabIndicators } from './useCanvasPageCollabIndicators'

export function useCanvasPageWorkshopCollab() {
  const route = useRoute()
  const router = useRouter()
  const notify = useNotifications()
  const { t } = useLanguage()
  const diagramStore = useDiagramStore()
  const authStore = useAuthStore()
  const savedDiagramsStore = useSavedDiagramsStore()

  const workshopCode = ref<string | null>(null)
  const workshopVisibility = ref<'organization' | 'network' | null>(null)
  const currentDiagramId = computed(() => savedDiagramsStore.activeDiagramId)

  const applyingRemoteCollabPatch = ref(false)
  let collabDiff: ReturnType<typeof useCanvasPageCollabDiff> | null = null
  let collabIndicators: ReturnType<typeof useCanvasPageCollabIndicators> | null = null

  // Mutable box so the snapshot callback can reach isDiagramOwner and sendUpdate
  // after useWorkshop returns (callbacks are defined before the return value exists).
  const _workshopCtx = {
    isDiagramOwner: null as null | ReturnType<typeof useWorkshop>['isDiagramOwner'],
    sendUpdate: null as null | ReturnType<typeof useWorkshop>['sendUpdate'],
  }

  const {
    sendUpdate,
    sendNodeSelected,
    notifyNodeEditing,
    sendClaimNodeEdit,
    activeEditors,
    remoteSelectionsByUser,
    isDiagramOwner,
    connectionStatus,
    reconnect,
    participantsWithNames,
    diagramOwnerId,
    lastLiveSpecVersion,
    collabSyncVersion,
    roomIdleSecondsRemaining,
    workshopRole,
    sessionDiagramId,
    setOwnerIdOptimistic,
    refreshActiveEditorsRef,
    watchCode: watchWorkshopCode,
    sessionDiagramTitle,
  } = useWorkshop(
    workshopCode,
    currentDiagramId,
    (spec) => {
      const tSpec = (spec.type as DiagramType) || diagramStore.type
      if (!tSpec) {
        return
      }
      applyingRemoteCollabPatch.value = true
      try {
        diagramStore.loadFromSpec(spec, tSpec)
        eventBus.emit('diagram:workshop_snapshot_applied', {})
      } finally {
        nextTick(() => {
          applyingRemoteCollabPatch.value = false
        })
      }
    },
    (nodes, connections, deletedNodeIds, deletedConnectionIds) => {
      collabDiff?.onGranularUpdate(nodes, connections, deletedNodeIds, deletedConnectionIds)
    },
    (nodeId, editor) => {
      if (editor) {
        collabIndicators?.applyNodeEditingIndicator(nodeId, editor)
      } else {
        collabIndicators?.removeNodeEditingIndicator(nodeId)
      }
    },
    (spec, version) => {
      // When the host (diagram owner) is the first to connect, the server seeds the
      // live Redis spec from the DB snapshot which may be stale or empty (if the
      // diagram was never saved). Version 1 means no peer edits have happened yet,
      // so the owner's in-memory diagram is authoritative — push it to the server
      // instead of overwriting local state with the potentially stale seed.
      if (_workshopCtx.isDiagramOwner?.value && version === 1) {
        const currentSpec = diagramStore.getSpecForSave()
        if (currentSpec) {
          _workshopCtx.sendUpdate?.(currentSpec as Record<string, unknown>)
        }
        return
      }
      const tSpec = (spec.type as DiagramType) || diagramStore.type
      if (!tSpec) return
      applyingRemoteCollabPatch.value = true
      try {
        diagramStore.loadFromSpec(spec, tSpec)
        eventBus.emit('diagram:workshop_snapshot_applied', {})
      } finally {
        nextTick(() => {
          applyingRemoteCollabPatch.value = false
        })
      }
    }
  )

  // Populate the mutable box after useWorkshop returns (callbacks fire later).
  _workshopCtx.isDiagramOwner = isDiagramOwner
  _workshopCtx.sendUpdate = sendUpdate

  const collabDiffApi = useCanvasPageCollabDiff({
    workshopCode,
    applyingRemoteCollabPatch,
    getDiagramData: () => diagramStore.data,
    mergeGranularUpdate: (...args) => diagramStore.mergeGranularUpdate(...args),
    clearRedoStack: () => diagramStore.clearRedoStack(),
    updateNode: (id, patch) => diagramStore.updateNode(id, patch),
    sendUpdate,
  })
  collabDiff = collabDiffApi

  const collabIndicatorApi = useCanvasPageCollabIndicators({
    activeEditors,
    remoteSelectionsByUser,
    isDiagramOwner,
    getCurrentUserId: () => Number(authStore.user?.id),
    setCollabForeignLockedNodeIds: (ids) => diagramStore.setCollabForeignLockedNodeIds(ids),
    refreshActiveEditorsRef,
    t,
  })
  collabIndicators = collabIndicatorApi

  const collabBus = useCanvasPageCollabBus({
    workshopCode,
    workshopVisibility,
    sessionDiagramId,
    activeEditors,
    getSelectedNodes: () => diagramStore.selectedNodes,
    route,
    router,
    notify,
    t,
    getCurrentUserId: () => Number(authStore.user?.id),
    setOwnerIdOptimistic,
    setActiveDiagram: (diagramId) => savedDiagramsStore.setActiveDiagram(diagramId),
    sendNodeSelected,
    sendClaimNodeEdit,
    notifyNodeEditing,
    reconnect,
    collabSyncVersion,
  })
  const { applyJoinWorkshopFromQuery, applyWorkshopCodeFromSession } = collabBus

  /** Username shown in banners; resolves host locally if WS still echoes User N. */
  const ownerUsername = computed<string | null>(() => {
    const ownerId = diagramOwnerId.value
    if (ownerId == null) {
      return null
    }
    const synthetic = /^User\s+\d+$/i
    const fromParticipants = participantsWithNames.value.find(
      (p) => p.user_id === ownerId
    )?.username
    const trimmed = fromParticipants?.trim() ?? ''

    const selfId = authStore.user?.id
    const localName =
      selfId !== undefined && Number(selfId) === ownerId && authStore.user?.username?.trim()
        ? authStore.user.username.trim()
        : ''

    if (localName && (!trimmed || synthetic.test(trimmed))) {
      return localName
    }
    return trimmed || localName || null
  })

  watchWorkshopCode()

  watch(
    () => workshopCode.value,
    (code) => {
      diagramStore.setCollabSessionActive(Boolean(code))
      if (!code) {
        diagramStore.setCollabForeignLockedNodeIds([])
      }
    },
    { immediate: true }
  )

  const collabLockedNodeIds = collabIndicatorApi.collabLockedNodeIds

  function resetPreviousDiagramTracking(): void {
    collabBus.resetBusTracking()
    collabDiffApi.resetDiffTracking()
  }

  /**
   * After loading a diagram, silently check if an active workshop session exists
   * for it and auto-reconnect the host's WebSocket without requiring them to click
   * the buddy icon again.  Guests joining via URL are handled by applyJoinWorkshopFromQuery.
   */
  async function checkAndReconnectWorkshop(diagramId: string): Promise<void> {
    if (workshopCode.value) return // already connected
    try {
      const res = await authFetch(`/api/diagrams/${diagramId}/workshop/status`)
      if (!res.ok) return
      const data = (await res.json()) as {
        active?: boolean
        code?: string | null
        workshop_visibility?: string | null
        is_owner?: boolean
      }
      if (!data.active || !data.code || !data.is_owner) return
      // Optimistically set the owner ID so isDiagramOwner is true immediately
      // while the WebSocket handshake is in flight. The authoritative owner_id
      // from the server's `joined` message will overwrite this once it arrives.
      const uid = authStore.user?.id
      if (uid != null) {
        setOwnerIdOptimistic(Number(uid))
      }
      const vis =
        data.workshop_visibility === 'network'
          ? 'network'
          : ('organization' as 'organization' | 'network')
      workshopCode.value = data.code
      workshopVisibility.value = vis
      eventBus.emit('workshop:code-changed', { code: data.code, visibility: vis })
    } catch {
      // Non-fatal: host can still reconnect manually via buddy icon
    }
  }

  const isViewer = computed(() => workshopRole.value === 'viewer')

  return {
    workshopCode,
    workshopVisibility,
    sendUpdate,
    sendNodeSelected,
    notifyNodeEditing,
    activeEditors,
    remoteSelectionsByUser,
    isDiagramOwner,
    workshopRole,
    isViewer,
    connectionStatus,
    reconnect,
    applyingRemoteCollabPatch,
    collabLockedNodeIds,
    applyJoinWorkshopFromQuery,
    applyWorkshopCodeFromSession,
    checkAndReconnectWorkshop,
    resetPreviousDiagramTracking,
    participantsWithNames,
    ownerUsername,
    sessionDiagramTitle,
    lastLiveSpecVersion,
    collabSyncVersion,
    roomIdleSecondsRemaining,
    sessionDiagramId,
  }
}
