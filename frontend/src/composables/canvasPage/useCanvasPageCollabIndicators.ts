import { type ComputedRef, computed, onScopeDispose, provide, watch } from 'vue'

import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import type { ActiveEditor, RemoteNodeSelection } from '@/composables/workshop/useWorkshop'
import { lockRingColorForUser } from '@/shared/collabPalette'
import { useCanvasNodeIndicatorsStore } from '@/stores/canvasNodeIndicators'

const STALE_EDITOR_PRUNE_MS = 60_000

interface UseCanvasPageCollabIndicatorsOptions {
  activeEditors: ComputedRef<Map<string, ActiveEditor>>
  remoteSelectionsByUser: ComputedRef<Map<number, RemoteNodeSelection>>
  isDiagramOwner: ComputedRef<boolean>
  getCurrentUserId: () => number
  setCollabForeignLockedNodeIds: (ids: string[]) => void
  refreshActiveEditorsRef: () => void
  t: UseLanguageTranslate
}

export function useCanvasPageCollabIndicators(options: UseCanvasPageCollabIndicatorsOptions) {
  const indicatorStore = useCanvasNodeIndicatorsStore()

  watch(
    () => options.activeEditors.value,
    (editors) => {
      const uid = options.getCurrentUserId()
      const foreign: string[] = []
      for (const [nid, ed] of editors) {
        if (ed.user_id !== uid) {
          foreign.push(nid)
        }
      }
      options.setCollabForeignLockedNodeIds(foreign)
    },
    { deep: true, immediate: true }
  )

  const collabLockedNodeIds = computed(() => {
    const uid = options.getCurrentUserId()
    const out: string[] = []
    for (const [nid, ed] of options.activeEditors.value) {
      if (ed.user_id !== uid) {
        out.push(nid)
      }
    }
    return out
  })

  // Remote selection: update indicator store — nodes computed applies class reactively.
  watch(
    () => options.remoteSelectionsByUser.value,
    (next) => {
      const entries: Array<{ nodeId: string; color: string }> = []
      for (const [userId, sel] of next) {
        entries.push({
          nodeId: sel.nodeId,
          color: lockRingColorForUser(userId, sel.color),
        })
      }
      indicatorStore.setCollabSelected(entries)
    },
    { deep: true }
  )

  function applyNodeEditingIndicator(nodeId: string, editor: ActiveEditor): void {
    if (editor.user_id === options.getCurrentUserId()) return

    const userColor = lockRingColorForUser(editor.user_id, editor.color)
    indicatorStore.setWorkshopEditing(nodeId, {
      antColor: userColor,
      editorColor: userColor,
      emoji: editor.emoji,
      label: options.t('workshopCanvas.editingNodeLabel', { username: editor.username }),
    })
  }

  function removeNodeEditingIndicator(nodeId: string): void {
    indicatorStore.clearWorkshopEditing(nodeId)
  }

  const activeEditorSeenAt = new Map<string, number>()
  watch(
    () => options.activeEditors.value,
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
        const selfId = options.getCurrentUserId()
        for (const [nodeId, editor] of newEditors) {
          if (editor.user_id !== selfId) {
            applyNodeEditingIndicator(nodeId, editor)
          }
        }
      }
    },
    { deep: true }
  )

  const staleEditorInterval = window.setInterval(() => {
    const now = Date.now()
    const uid = options.getCurrentUserId()
    const editors = options.activeEditors.value
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
      options.refreshActiveEditorsRef()
    }
  }, 10_000)

  onScopeDispose(() => {
    window.clearInterval(staleEditorInterval)
  })

  provide('collabCanvas', {
    isNodeLockedByOther: (nodeId: string) => {
      const ed = options.activeEditors.value.get(nodeId)
      if (!ed) {
        return false
      }
      return ed.user_id !== options.getCurrentUserId()
    },
    isDiagramOwner: options.isDiagramOwner,
  })

  return {
    collabLockedNodeIds,
    applyNodeEditingIndicator,
    removeNodeEditingIndicator,
  }
}
