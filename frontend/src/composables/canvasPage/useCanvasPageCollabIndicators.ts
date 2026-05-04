import { type ComputedRef, computed, nextTick, onScopeDispose, provide, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import type { ActiveEditor, RemoteNodeSelection } from '@/composables/workshop/useWorkshop'

function isCssColorTransparent(value: string): boolean {
  const v = value.trim().toLowerCase()
  if (v === 'transparent') {
    return true
  }
  const match = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+)\s*)?\)$/.exec(v)
  if (match) {
    const alpha = match[4]
    if (alpha !== undefined && parseFloat(alpha) === 0) {
      return true
    }
  }
  return false
}

/** Border / outline of the custom node root, else text or fill color. */
function sampleWorkshopAntColorFromNodeWrapper(wrapper: HTMLElement): string | null {
  const inner = wrapper.querySelector<HTMLElement>(':scope > *')
  if (!inner) {
    return null
  }
  const styles = getComputedStyle(inner)
  const borderWidth = parseFloat(styles.borderTopWidth) || 0
  if (borderWidth > 0) {
    const color = styles.borderTopColor
    if (!isCssColorTransparent(color)) {
      return color
    }
  }
  const outlineWidth = parseFloat(styles.outlineWidth) || 0
  if (outlineWidth > 0) {
    const color = styles.outlineColor
    if (!isCssColorTransparent(color)) {
      return color
    }
  }
  const fromText = styles.color
  if (!isCssColorTransparent(fromText)) {
    return fromText
  }
  const fromBg = styles.backgroundColor
  if (!isCssColorTransparent(fromBg)) {
    return fromBg
  }
  return null
}

const WORKSHOP_REMOTE_EDIT_DOM_MAX_TRIES = 48
const WORKSHOP_REMOTE_EDIT_DOM_RETRY_MS = 50
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

  let lastRemoteSelectionKey = ''
  watch(
    () => options.remoteSelectionsByUser.value,
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
          const el = document.querySelector(
            `.vue-flow__node[data-id="${sel.nodeId}"]`
          ) as HTMLElement | null
          if (el) {
            el.classList.add('collab-remote-selected')
            el.setAttribute('data-collab-remote-user', sel.username)
          }
        }
      })
    },
    { deep: true }
  )

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

  /** Bumps when a new apply starts; stale retry chains for that node exit early. */
  const workshopEditIndicatorApplySeq = new Map<string, number>()

  function applyNodeEditingIndicator(nodeId: string, editor: ActiveEditor): void {
    // Don't show the indicator on the editor's own screen — they know they're editing.
    if (editor.user_id === options.getCurrentUserId()) return

    const seq = (workshopEditIndicatorApplySeq.get(nodeId) ?? 0) + 1
    workshopEditIndicatorApplySeq.set(nodeId, seq)

    const paint = (nodeElement: HTMLElement): void => {
      const antColor = sampleWorkshopAntColorFromNodeWrapper(nodeElement)
      if (antColor) {
        nodeElement.style.setProperty('--workshop-ant-color', antColor)
      }
      nodeElement.classList.add('workshop-editing')
      nodeElement.style.setProperty('--editor-color', editor.color)
      nodeElement.setAttribute('data-editor-emoji', editor.emoji)
      nodeElement.setAttribute('data-editor-username', editor.username)
      nodeElement.setAttribute(
        'data-editor-label',
        options.t('workshopCanvas.editingNodeLabel', { username: editor.username })
      )
    }

    const tryPaint = (attempt: number): void => {
      if (workshopEditIndicatorApplySeq.get(nodeId) !== seq) {
        return
      }
      const nodeElement = document.querySelector(
        `.vue-flow__node[data-id="${nodeId}"]`
      ) as HTMLElement | null
      if (nodeElement) {
        const current = options.activeEditors.value.get(nodeId)
        if (!current || current.user_id !== editor.user_id) {
          return
        }
        paint(nodeElement)
        return
      }
      if (attempt + 1 >= WORKSHOP_REMOTE_EDIT_DOM_MAX_TRIES) {
        return
      }
      window.setTimeout(() => tryPaint(attempt + 1), WORKSHOP_REMOTE_EDIT_DOM_RETRY_MS)
    }

    nextTick(() => tryPaint(0))
  }

  function removeNodeEditingIndicator(nodeId: string): void {
    workshopEditIndicatorApplySeq.delete(nodeId)
    nextTick(() => {
      const nodeElement = document.querySelector(
        `.vue-flow__node[data-id="${nodeId}"]`
      ) as HTMLElement | null
      if (nodeElement) {
        nodeElement.classList.remove('workshop-editing')
        nodeElement.style.removeProperty('--workshop-ant-color')
        nodeElement.style.removeProperty('--editor-color')
        nodeElement.removeAttribute('data-editor-emoji')
        nodeElement.removeAttribute('data-editor-username')
        nodeElement.removeAttribute('data-editor-label')
      }
    })
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

  eventBus.onWithOwner(
    'diagram:workshop_snapshot_applied',
    () => {
      const selfId = options.getCurrentUserId()
      nextTick(() => {
        for (const [nodeId, editor] of options.activeEditors.value) {
          if (editor.user_id !== selfId) {
            applyNodeEditingIndicator(nodeId, editor)
          }
        }
      })
    },
    'CanvasPage'
  )

  return {
    collabLockedNodeIds,
    applyNodeEditingIndicator,
    removeNodeEditingIndicator,
  }
}
