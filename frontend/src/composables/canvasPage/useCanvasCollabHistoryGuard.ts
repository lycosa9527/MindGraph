import type { Ref } from 'vue'

import { notify } from '@/composables/core/notifications'
import { i18n } from '@/i18n'
import { useAuthStore, useDiagramStore } from '@/stores'

import { nodeIdsDiffBetweenDiagrams } from './diagramDiff'

type ActiveEditorEntry = { user_id: number }

type HistoryEntry = { data?: unknown }

/** Pure collab guard — true when undo/redo must be blocked for foreign active editors. */
export function collabHistoryWouldBlock(
  direction: 'undo' | 'redo',
  options: {
    workshopCode: string | null
    activeEditors: Map<string, ActiveEditorEntry>
    currentUserId: number | undefined
    history: HistoryEntry[]
    historyIndex: number
    data: { nodes?: { id: string }[] } | null
  }
): boolean {
  if (!options.workshopCode) {
    return false
  }

  const historyEntry =
    direction === 'undo'
      ? options.history[options.historyIndex - 1]
      : options.history[options.historyIndex + 1]
  const cur = options.data
  if (!historyEntry?.data || !cur) {
    return false
  }

  const changed = nodeIdsDiffBetweenDiagrams(
    cur,
    historyEntry.data as { nodes?: { id: string }[] }
  )
  const selfId = Number(options.currentUserId)
  for (const nid of changed) {
    const ed = options.activeEditors.get(nid)
    if (ed && ed.user_id !== selfId) {
      return true
    }
  }
  return false
}

let workshopCodeRef: Ref<string | null> | null = null
let activeEditorsRef: Ref<Map<string, ActiveEditorEntry>> | null = null

/** Bind workshop collab refs from CanvasPage (shared by keyboard + toolbar undo/redo). */
export function bindCanvasCollabHistoryContext(
  workshopCode: Ref<string | null>,
  activeEditors: Ref<Map<string, ActiveEditorEntry>>
): void {
  workshopCodeRef = workshopCode
  activeEditorsRef = activeEditors
}

function isCollabHistoryBlocked(direction: 'undo' | 'redo'): boolean {
  if (!workshopCodeRef?.value || !activeEditorsRef) {
    return false
  }

  const diagramStore = useDiagramStore()
  const authStore = useAuthStore()

  const blocked = collabHistoryWouldBlock(direction, {
    workshopCode: workshopCodeRef.value,
    activeEditors: activeEditorsRef.value,
    currentUserId:
      authStore.user?.id != null && authStore.user.id !== ''
        ? Number(authStore.user.id)
        : undefined,
    history: diagramStore.history,
    historyIndex: diagramStore.historyIndex,
    data: diagramStore.data,
  })

  if (blocked) {
    notify.warning(
      i18n.global.t(
        direction === 'undo'
          ? 'notification.collabUndoBlocked'
          : 'notification.collabRedoBlocked'
      ) as string
    )
  }
  return blocked
}

/** Undo with workshop collab guard; returns whether undo ran. */
export function tryCollabGuardedUndo(): boolean {
  const diagramStore = useDiagramStore()
  if (!diagramStore.canUndo) {
    return false
  }
  if (isCollabHistoryBlocked('undo')) {
    return false
  }
  diagramStore.undo()
  return true
}

/** Redo with workshop collab guard; returns whether redo ran. */
export function tryCollabGuardedRedo(): boolean {
  const diagramStore = useDiagramStore()
  if (!diagramStore.canRedo) {
    return false
  }
  if (isCollabHistoryBlocked('redo')) {
    return false
  }
  diagramStore.redo()
  return true
}
