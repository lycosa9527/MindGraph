/**
 * Workshop / canvas collaboration: WebSocket, remote selection, editing indicators, granular sync.
 */
import { computed, nextTick, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useWorkshop } from '@/composables/workshop/useWorkshop'
import { useAuthStore, useDiagramStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'

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
  const currentDiagramId = computed(() => savedDiagramsStore.activeDiagramId)

  let previousNodes: Array<Record<string, unknown>> = []
  let previousConnections: Array<Record<string, unknown>> = []
  const applyingRemoteCollabPatch = ref(false)

  const {
    sendUpdate,
    sendNodeSelected,
    notifyNodeEditing,
    activeEditors,
    remoteSelectionsByUser,
    isDiagramOwner,
    watchCode: watchWorkshopCode,
  } = useWorkshop(
    workshopCode,
    currentDiagramId,
    undefined,
    (nodes, connections) => {
      if (nodes || connections) {
        applyingRemoteCollabPatch.value = true
        try {
          diagramStore.mergeGranularUpdate(nodes, connections)
          diagramStore.clearRedoStack()
        } finally {
          nextTick(() => {
            applyingRemoteCollabPatch.value = false
          })
        }
      }
    },
    (nodeId, editor) => {
      if (editor) {
        console.log(`[Workshop] User ${editor.username} ${editor.emoji} editing node ${nodeId}`)
        applyNodeEditingIndicator(nodeId, editor)
      } else {
        console.log(`[Workshop] Node ${nodeId} editing stopped`)
        removeNodeEditingIndicator(nodeId)
      }
    },
    (spec, _version) => {
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
          const el = document.querySelector(`#${CSS.escape(sel.nodeId)}`) as HTMLElement | null
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
  watch(
    () => [...diagramStore.selectedNodes],
    (ids) => {
      if (!workshopCode.value) {
        return
      }
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
    editor: { color: string; emoji: string; username: string }
  ): void {
    nextTick(() => {
      const nodeElement = document.querySelector(`#${CSS.escape(nodeId)}`) as HTMLElement
      if (nodeElement) {
        nodeElement.classList.add('workshop-editing')
        nodeElement.style.setProperty('--editor-color', editor.color)
        nodeElement.setAttribute('data-editor-emoji', editor.emoji)
        nodeElement.setAttribute('data-editor-username', editor.username)
      }
    })
  }

  function removeNodeEditingIndicator(nodeId: string): void {
    nextTick(() => {
      const nodeElement = document.querySelector(`#${CSS.escape(nodeId)}`) as HTMLElement
      if (nodeElement) {
        nodeElement.classList.remove('workshop-editing')
        nodeElement.style.removeProperty('--editor-color')
        nodeElement.removeAttribute('data-editor-emoji')
        nodeElement.removeAttribute('data-editor-username')
      }
    })
  }

  watch(
    () => activeEditors.value,
    (newEditors, oldEditors) => {
      if (oldEditors) {
        for (const [nodeId] of oldEditors) {
          if (!newEditors.has(nodeId)) {
            removeNodeEditingIndicator(nodeId)
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

  eventBus.onWithOwner(
    'workshop:code-changed',
    (data) => {
      if (data.code !== undefined) {
        workshopCode.value = data.code as string | null
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

  function applyJoinWorkshopFromQuery(): void {
    const raw = route.query.join_workshop
    if (!raw || typeof raw !== 'string') {
      return
    }
    const trimmed = raw.trim()
    if (!/^\d{3}-\d{3}$/.test(trimmed)) {
      return
    }
    workshopCode.value = trimmed
    eventBus.emit('workshop:code-changed', { code: trimmed })
    const nextQuery = { ...route.query } as Record<string, string | string[] | undefined>
    delete nextQuery.join_workshop
    router.replace({ query: nextQuery })
  }

  eventBus.onWithOwner(
    'node_editor:opening',
    (data) => {
      const nodeId = (data as { nodeId: string }).nodeId
      if (!nodeId || !workshopCode.value) {
        return
      }
      const ed = activeEditors.value.get(nodeId)
      if (ed && ed.user_id !== Number(authStore.user?.id)) {
        notify.warning(t('notification.canvasSomeoneEditingNode'))
        return
      }
      notifyNodeEditing(nodeId, true)
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'node_editor:closed',
    (data) => {
      const nodeId = (data as { nodeId: string }).nodeId
      if (nodeId && workshopCode.value) {
        notifyNodeEditing(nodeId, false)
      }
    },
    'CanvasPage'
  )

  watch(
    () => diagramStore.data,
    (newData) => {
      if (!newData) return

      if (workshopCode.value && newData.nodes && newData.connections) {
        if (applyingRemoteCollabPatch.value) {
          previousNodes = JSON.parse(JSON.stringify(newData.nodes))
          previousConnections = JSON.parse(JSON.stringify(newData.connections || []))
          return
        }
        const changedNodes = calculateDiff(
          previousNodes as Array<{ id: string }>,
          newData.nodes as Array<{ id: string }>
        )
        const changedConnections = calculateDiff(
          previousConnections as Array<{ id: string }>,
          (newData.connections || []) as Array<{ id: string }>
        )

        if (changedNodes.length > 0 || changedConnections.length > 0) {
          sendUpdate(undefined, changedNodes, changedConnections)
        }

        previousNodes = JSON.parse(JSON.stringify(newData.nodes))
        previousConnections = JSON.parse(JSON.stringify(newData.connections || []))
      } else if (newData.nodes && newData.connections) {
        previousNodes = JSON.parse(JSON.stringify(newData.nodes))
        previousConnections = JSON.parse(JSON.stringify(newData.connections || []))
      }
    },
    { deep: true }
  )

  function resetPreviousDiagramTracking(): void {
    previousNodes = []
    previousConnections = []
  }

  return {
    workshopCode,
    sendUpdate,
    sendNodeSelected,
    notifyNodeEditing,
    activeEditors,
    remoteSelectionsByUser,
    isDiagramOwner,
    applyingRemoteCollabPatch,
    collabLockedNodeIds,
    applyJoinWorkshopFromQuery,
    resetPreviousDiagramTracking,
  }
}
