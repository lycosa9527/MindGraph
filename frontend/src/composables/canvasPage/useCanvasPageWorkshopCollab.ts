/**
 * Workshop / canvas collaboration: WebSocket, remote selection, editing indicators, granular sync.
 */
import { computed, nextTick, onScopeDispose, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useWorkshop } from '@/composables/workshop/useWorkshop'
import { useAuthStore, useDiagramStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import type { DiagramNode } from '@/types/diagram'
import { authFetch } from '@/utils/api'

import { calculateDiff } from './diagramDiff'

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

  let previousNodes: Array<Record<string, unknown>> = []
  let previousConnections: Array<Record<string, unknown>> = []
  const applyingRemoteCollabPatch = ref(false)
  /** Pre-send node clones for ``update_partial_filtered`` rollback. */
  const preSendNodeSnapshots = new Map<string, Record<string, unknown>>()

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
      if (nodes || connections || deletedNodeIds?.length || deletedConnectionIds?.length) {
        if (import.meta.env.DEV) {
          console.log('[CollabDebug] onGranularUpdate merging', {
            inNodes: nodes?.length ?? 0,
            inConns: connections?.length ?? 0,
            inDelNodes: deletedNodeIds?.length ?? 0,
            inDelConns: deletedConnectionIds?.length ?? 0,
          })
        }
        applyingRemoteCollabPatch.value = true
        try {
          const ok = diagramStore.mergeGranularUpdate(
            nodes,
            connections,
            deletedNodeIds,
            deletedConnectionIds,
          )
          if (import.meta.env.DEV) {
            console.log('[CollabDebug] mergeGranularUpdate result', ok)
          }
          diagramStore.clearRedoStack()
        } finally {
          // mergeGranularUpdate mutates diagramStore.data.nodes in-place without
          // replacing the data object reference.  The non-deep watcher on
          // diagramStore.data therefore never fires, leaving previousNodes stale.
          // Sync explicitly here so the next runDiffAndSend does not mistake the
          // remote patch for a local edit and echo it back to the server.
          const current = diagramStore.data
          if (current) {
            previousNodes = JSON.parse(JSON.stringify(current.nodes ?? []))
            previousConnections = JSON.parse(JSON.stringify(current.connections ?? []))
          }
          if (diffFlushTimer !== null) {
            clearTimeout(diffFlushTimer)
            diffFlushTimer = null
          }
          diffFirstDirtyAt = 0
          nextTick(() => {
            applyingRemoteCollabPatch.value = false
          })
        }
      }
    },
    (nodeId, editor) => {
      if (editor) {
        applyNodeEditingIndicator(nodeId, editor)
      } else {
        removeNodeEditingIndicator(nodeId)
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

  /** Username shown in banners; resolves host locally if WS still echoes User N. */
  const ownerUsername = computed<string | null>(() => {
    const ownerId = diagramOwnerId.value
    if (ownerId == null) {
      return null
    }
    const synthetic = /^User\s+\d+$/i
    let fromParticipants = participantsWithNames.value.find(
      (p) => p.user_id === ownerId
    )?.username
    let trimmed = fromParticipants?.trim() ?? ''

    const selfId = authStore.user?.id
    const localName =
      selfId !== undefined &&
      Number(selfId) === ownerId &&
      authStore.user?.username?.trim()
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

  watch(
    () => activeEditors.value,
    (editors) => {
      const uid = Number(authStore.user?.id)
      const foreign: string[] = []
      for (const [nid, ed] of editors) {
        if (ed.user_id !== uid) {
          foreign.push(nid)
        }
      }
      diagramStore.setCollabForeignLockedNodeIds(foreign)
    },
    { deep: true, immediate: true }
  )

  const collabLockedNodeIds = computed(() => {
    const uid = Number(authStore.user?.id)
    const out: string[] = []
    for (const [nid, ed] of activeEditors.value) {
      if (ed.user_id !== uid) {
        out.push(nid)
      }
    }
    return out
  })

  let lastRemoteSelectionKey = ''
  watch(
    () => remoteSelectionsByUser.value,
    (next) => {
      nextTick(() => {
        const key = JSON.stringify([...next.entries()])
        if (key === lastRemoteSelectionKey) return
        lastRemoteSelectionKey = key
        document.querySelectorAll('.collab-remote-selected').forEach((el) => {
          el.classList.remove('collab-remote-selected')
          el.removeAttribute('data-collab-remote-user')
        })
        for (const [, sel] of next) {
          const el = document.querySelector(`.vue-flow__node[data-id="${sel.nodeId}"]`) as HTMLElement | null
          if (el) {
            el.classList.add('collab-remote-selected')
            el.setAttribute('data-collab-remote-user', sel.username)
          }
        }
      })
    },
    { deep: true }
  )

  let lastSentSelectionNodeId: string | null = null
  const SELECTION_SEND_DEBOUNCE_MS = 50
  let selectionSendTimer: ReturnType<typeof setTimeout> | null = null

  watch(
    () => [...diagramStore.selectedNodes],
    (ids) => {
      if (!workshopCode.value) {
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
          sendNodeSelected(lastSentSelectionNodeId, false)
        }
        if (primary) {
          sendNodeSelected(primary, true)
        }
        lastSentSelectionNodeId = primary
      }, SELECTION_SEND_DEBOUNCE_MS)
    },
    { deep: true }
  )

  provide('collabCanvas', {
    isNodeLockedByOther: (nodeId: string) => {
      const ed = activeEditors.value.get(nodeId)
      if (!ed) {
        return false
      }
      return ed.user_id !== Number(authStore.user?.id)
    },
    isDiagramOwner,
  })

  function applyNodeEditingIndicator(
    nodeId: string,
    editor: { user_id: number; color: string; emoji: string; username: string }
  ): void {
    // Don't show the indicator on the editor's own screen — they know they're editing.
    if (editor.user_id === Number(authStore.user?.id)) return
    nextTick(() => {
      const nodeElement = document.querySelector(
        `.vue-flow__node[data-id="${nodeId}"]`
      ) as HTMLElement | null
      if (nodeElement) {
        nodeElement.classList.add('workshop-editing')
        nodeElement.style.setProperty('--editor-color', editor.color)
        nodeElement.setAttribute('data-editor-emoji', editor.emoji)
        nodeElement.setAttribute('data-editor-username', editor.username)
        // Store the translated label so CSS attr() can display it without hardcoding "editing".
        nodeElement.setAttribute(
          'data-editor-label',
          t('workshopCanvas.editingNodeLabel', { username: editor.username })
        )
      }
    })
  }

  function removeNodeEditingIndicator(nodeId: string): void {
    nextTick(() => {
      const nodeElement = document.querySelector(
        `.vue-flow__node[data-id="${nodeId}"]`
      ) as HTMLElement | null
      if (nodeElement) {
        nodeElement.classList.remove('workshop-editing')
        nodeElement.style.removeProperty('--editor-color')
        nodeElement.removeAttribute('data-editor-emoji')
        nodeElement.removeAttribute('data-editor-username')
        nodeElement.removeAttribute('data-editor-label')
      }
    })
  }

  const activeEditorSeenAt = new Map<string, number>()
  watch(
    () => activeEditors.value,
    (newEditors, oldEditors) => {
      const now = Date.now()
      if (newEditors) {
        for (const k of newEditors.keys()) {
          activeEditorSeenAt.set(k, now)
        }
      }
      if (oldEditors) {
        for (const [nodeId] of oldEditors) {
          if (!newEditors?.has(nodeId)) {
            removeNodeEditingIndicator(nodeId)
            activeEditorSeenAt.delete(nodeId)
          }
        }
      }

      if (newEditors) {
        for (const [nodeId, editor] of newEditors) {
          if (!oldEditors?.has(nodeId)) {
            applyNodeEditingIndicator(nodeId, editor)
          }
        }
      }
    },
    { deep: true }
  )

  // Stuck ``pendingResync``: reset timer whenever version cursors advance; if
  // still pending after THRESHOLD ms with no such progress, force reconnect.
  const STUCK_VERSION_THRESHOLD_MS = 15_000
  let stuckVersionTimer: ReturnType<typeof setTimeout> | null = null

  watch(
    () => [
      collabSyncVersion.pendingResync.value,
      collabSyncVersion.liveVersion.value,
      collabSyncVersion.lastFrameAt.value,
    ],
    () => {
      if (stuckVersionTimer !== null) {
        clearTimeout(stuckVersionTimer)
        stuckVersionTimer = null
      }
      if (!collabSyncVersion.pendingResync.value) {
        return
      }
      stuckVersionTimer = setTimeout(() => {
        stuckVersionTimer = null
        if (collabSyncVersion.pendingResync.value) {
          if (import.meta.env.DEV) {
            console.warn(
              '[CollabSync] pendingResync stalled — forcing reconnect',
            )
          }
          reconnect()
        }
      }, STUCK_VERSION_THRESHOLD_MS)
    }
  )

  const STALE_EDITOR_PRUNE_MS = 60_000
  const staleEditorInterval = window.setInterval(() => {
    const now = Date.now()
    const uid = Number(authStore.user?.id)
    const editors = activeEditors.value
    let changed = false
    for (const [nid, ed] of editors) {
      const seen = activeEditorSeenAt.get(nid) ?? 0
      if (now - seen > STALE_EDITOR_PRUNE_MS && ed.user_id !== uid) {
        editors.delete(nid)
        activeEditorSeenAt.delete(nid)
        changed = true
      }
    }
    if (changed) {
      activeEditors.value = new Map(editors)
    }
  }, 10_000)
  onScopeDispose(() => {
    window.clearInterval(staleEditorInterval)
    if (stuckVersionTimer !== null) {
      clearTimeout(stuckVersionTimer)
      stuckVersionTimer = null
    }
  })

  eventBus.onWithOwner(
    'workshop:partial-filtered',
    (data) => {
      const raw = (data as { nodeIds?: unknown }).nodeIds
      if (!Array.isArray(raw)) {
        return
      }
      for (const item of raw) {
        if (typeof item !== 'string' || !item) {
          continue
        }
        const snap = preSendNodeSnapshots.get(item)
        if (snap) {
          diagramStore.updateNode(item, snap as Partial<DiagramNode>)
          preSendNodeSnapshots.delete(item)
        }
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'workshop:collab-ack',
    (data) => {
      const raw = (data as { nodeIds?: unknown }).nodeIds
      if (!Array.isArray(raw)) {
        preSendNodeSnapshots.clear()
        return
      }
      for (const item of raw) {
        if (typeof item === 'string' && item) {
          preSendNodeSnapshots.delete(item)
        }
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'workshop:code-changed',
    (data) => {
      if (data.code !== undefined) {
        workshopCode.value = data.code as string | null
      }
      if (data.code === null) {
        workshopVisibility.value = null
      } else if (data.visibility === 'organization' || data.visibility === 'network') {
        workshopVisibility.value = data.visibility
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'diagram:collab_delete_blocked',
    () => {
      notify.warning(t('notification.collabDeleteBlocked'))
    },
    'CanvasPage'
  )

  // When the host successfully starts a new session via OnlineCollabModal,
  // proactively set diagramOwnerId so isDiagramOwner is true immediately
  // (before the WS `joined` message arrives) and isCollabGuest stays false.
  eventBus.onWithOwner(
    'workshop:host-started',
    () => {
      const uid = authStore.user?.id
      if (uid != null) {
        setOwnerIdOptimistic(Number(uid))
      }
    },
    'CanvasPage'
  )

  function applyJoinWorkshopFromQuery(): void {
    const raw = route.query.join_workshop
    if (!raw || typeof raw !== 'string') {
      return
    }
    const trimmed = raw.trim()
    if (!/^[2-9A-HJ-KM-NP-Z]{3}-[2-9A-HJ-KM-NP-Z]{3}$/i.test(trimmed)) {
      return
    }
    workshopCode.value = trimmed
    workshopVisibility.value = null
    eventBus.emit('workshop:code-changed', { code: trimmed })
    const nextQuery = { ...route.query } as Record<string, string | string[] | undefined>
    delete nextQuery.join_workshop
    router.replace({ query: nextQuery })
  }

  /**
   * Restore a workshop session from sessionStorage after a guest page refresh.
   * Sets the active diagram ID so update messages use the correct diagram_id,
   * then sets workshopCode to trigger the WS connect watcher.
   * The WS snapshot message will load the live spec; the DB diagram is skipped.
   */
  function applyWorkshopCodeFromSession(code: string, diagramId: string): void {
    savedDiagramsStore.setActiveDiagram(diagramId)
    workshopCode.value = code
  }

  // Keep sessionStorage in sync with the active workshop session so the guest
  // can reconnect after a page refresh without losing the live spec.
  // Non-immediate so it only fires on value changes, not on the initial null
  // at component mount (which would wipe the keys before CanvasPage.vue reads them).
  watch(
    [() => workshopCode.value, () => sessionDiagramId.value],
    ([code, diagId], [prevCode]) => {
      if (code && diagId) {
        sessionStorage.setItem('mg_workshop_code', code)
        sessionStorage.setItem('mg_workshop_diagram_id', String(diagId))
      } else if (!code && prevCode) {
        // Intentional disconnect or server-forced exit (4010/4011, session_ended):
        // clear the token so the next page load falls through to a normal diagram load.
        sessionStorage.removeItem('mg_workshop_code')
        sessionStorage.removeItem('mg_workshop_diagram_id')
      }
    }
  )

  eventBus.onWithOwner(
    'node_editor:opening',
    (data) => {
      const nodeId = (data as { nodeId: string }).nodeId
      if (!nodeId || !workshopCode.value) {
        return
      }
      const ed = activeEditors.value.get(nodeId)
      if (ed && ed.user_id !== Number(authStore.user?.id)) {
        // Node is locked by another user — the dashed-border indicator on the
        // canvas already makes this clear; no toast needed.
        return
      }
      // Send a claim_node_edit instead of node_editing{editing:true}.
      // The server checks the soft-lock atomically and responds with
      // node_edit_claimed{granted:true/false}.  On grant it also broadcasts
      // node_editing{editing:true} to all participants directly.
      sendClaimNodeEdit(nodeId)
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'node_editor:closed',
    (data) => {
      const nodeId = (data as { nodeId: string }).nodeId
      if (nodeId && workshopCode.value) {
        // Guard flashStructuralLock from overriding the editing:false signal.
        // The save action fires diagram:node_updated synchronously after this
        // handler returns, and the throttle in notifyNodeEditing would buffer
        // the editing:true from flashStructuralLock on top of our editing:false.
        recentlyClosedEditorNodes.add(nodeId)
        setTimeout(
          () => recentlyClosedEditorNodes.delete(nodeId),
          EDITOR_CLOSE_COOLDOWN_MS
        )
        notifyNodeEditing(nodeId, false)
      }
    },
    'CanvasPage'
  )

  const structuralLockReleaseTimers = new Map<string, ReturnType<typeof setTimeout>>()
  const STRUCTURAL_LOCK_HOLD_MS = 400

  // Nodes that just had their text editor closed — suppress flashStructuralLock
  // for these until the cooldown expires (must exceed STRUCTURAL_LOCK_HOLD_MS so
  // the flash triggered by the save's diagram:node_updated never fires).
  const recentlyClosedEditorNodes = new Set<string>()
  const EDITOR_CLOSE_COOLDOWN_MS = STRUCTURAL_LOCK_HOLD_MS + 200

  function clearAllStructuralLockReleaseTimers(): void {
    for (const timer of structuralLockReleaseTimers.values()) {
      clearTimeout(timer)
    }
    structuralLockReleaseTimers.clear()
  }

  function flashStructuralLock(nodeId: string): void {
    if (!nodeId || !workshopCode.value) {
      return
    }
    // Skip the flash if this node's text editor was just closed — the save's
    // diagram:node_updated would otherwise override the editing:false signal
    // already sent via node_editor:closed, causing a spurious re-lock on the
    // server that then clears itself 400ms later (flickering host indicator).
    if (recentlyClosedEditorNodes.has(nodeId)) {
      return
    }
    const existing = structuralLockReleaseTimers.get(nodeId)
    if (existing) {
      clearTimeout(existing)
    } else {
      notifyNodeEditing(nodeId, true)
    }
    const timer = setTimeout(() => {
      structuralLockReleaseTimers.delete(nodeId)
      notifyNodeEditing(nodeId, false)
    }, STRUCTURAL_LOCK_HOLD_MS)
    structuralLockReleaseTimers.set(nodeId, timer)
  }

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
      const selected = diagramStore.selectedNodes
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

  const DIFF_DEBOUNCE_MS = 40
  const DIFF_MAX_WAIT_MS = 200
  let diffFlushTimer: ReturnType<typeof setTimeout> | null = null
  let diffFirstDirtyAt = 0

  function runDiffAndSend(): void {
    diffFlushTimer = null
    diffFirstDirtyAt = 0
    const currentData = diagramStore.data
    if (!currentData || !currentData.nodes || !currentData.connections) {
      if (import.meta.env.DEV) {
        console.log('[CollabDebug] runDiffAndSend short-circuit reason=no-data')
      }
      return
    }
    if (!workshopCode.value) {
      if (import.meta.env.DEV) {
        console.log('[CollabDebug] runDiffAndSend short-circuit reason=no-workshop')
      }
      previousNodes = JSON.parse(JSON.stringify(currentData.nodes))
      previousConnections = JSON.parse(JSON.stringify(currentData.connections || []))
      return
    }
    if (applyingRemoteCollabPatch.value) {
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
        workshopCode: workshopCode.value,
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
      sendUpdate(
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
    () => diagramStore.data,
    (newData) => {
      if (!newData || !newData.nodes || !newData.connections) return

      if (!workshopCode.value) {
        previousNodes = JSON.parse(JSON.stringify(newData.nodes))
        previousConnections = JSON.parse(JSON.stringify(newData.connections || []))
        return
      }

      const nodes = newData.nodes as Array<{ id: string }>
      const connections = (newData.connections || []) as Array<{ id: string }>

      if (applyingRemoteCollabPatch.value) {
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

  function resetPreviousDiagramTracking(): void {
    clearAllStructuralLockReleaseTimers()
    previousNodes = []
    previousConnections = []
    preSendNodeSnapshots.clear()
    if (diffFlushTimer !== null) {
      clearTimeout(diffFlushTimer)
      diffFlushTimer = null
    }
    if (stuckVersionTimer !== null) {
      clearTimeout(stuckVersionTimer)
      stuckVersionTimer = null
    }
    if (selectionSendTimer !== null) {
      clearTimeout(selectionSendTimer)
      selectionSendTimer = null
    }
    diffFirstDirtyAt = 0
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
