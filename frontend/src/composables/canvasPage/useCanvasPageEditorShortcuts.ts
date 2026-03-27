import type { Ref } from 'vue'

import { nodeIdsDiffBetweenDiagrams } from '@/composables/canvasPage/diagramDiff'
import { eventBus } from '@/composables/core/useEventBus'
import { useEditorShortcuts } from '@/composables/core/useKeyboard'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramAutoSave } from '@/composables/editor/useDiagramAutoSave'
import { useAuthStore, useDiagramStore } from '@/stores'

type ActiveEditorEntry = { user_id: number }
type DiagramAutoSaveApi = ReturnType<typeof useDiagramAutoSave>

export function useCanvasPageEditorShortcuts(options: {
  workshopCode: Ref<string | null>
  activeEditors: Ref<Map<string, ActiveEditorEntry>>
  relationshipActiveEntry: Ref<unknown>
  diagramAutoSave: DiagramAutoSaveApi
}): { handleSaveKey: () => Promise<void> } {
  const { workshopCode, activeEditors, relationshipActiveEntry, diagramAutoSave } = options
  const diagramStore = useDiagramStore()
  const authStore = useAuthStore()
  const notify = useNotifications()
  const { t } = useLanguage()

  function isTypingInInput(): boolean {
    const active = document.activeElement as HTMLElement
    return (
      active?.tagName === 'INPUT' || active?.tagName === 'TEXTAREA' || !!active?.isContentEditable
    )
  }

  function handleDeleteKey() {
    if (isTypingInInput()) return
    eventBus.emit('diagram:delete_selected_requested', {})
  }

  function handleAddNodeKey() {
    if (isTypingInInput()) return
    if (diagramStore.type === 'concept_map') return
    eventBus.emit('diagram:add_node_requested', {})
  }

  function handleAddBranchKey() {
    if (isTypingInInput()) return
    if (diagramStore.type === 'concept_map') return
    if (
      diagramStore.type === 'mindmap' ||
      diagramStore.type === 'mind_map' ||
      diagramStore.type === 'brace_map' ||
      diagramStore.type === 'flow_map'
    ) {
      eventBus.emit('diagram:add_branch_requested', {})
    } else {
      eventBus.emit('diagram:add_node_requested', {})
    }
  }

  function handleAddChildKey() {
    if (isTypingInInput()) return
    if (diagramStore.type === 'concept_map') return
    if (
      diagramStore.type === 'mindmap' ||
      diagramStore.type === 'mind_map' ||
      diagramStore.type === 'brace_map' ||
      diagramStore.type === 'flow_map'
    ) {
      eventBus.emit('diagram:add_child_requested', {})
    }
  }

  function handleUndoKey() {
    if (isTypingInInput()) return
    if (!diagramStore.canUndo) {
      return
    }
    if (workshopCode.value) {
      const prevEntry = diagramStore.history[diagramStore.historyIndex - 1]
      const cur = diagramStore.data
      if (prevEntry?.data && cur) {
        const changed = nodeIdsDiffBetweenDiagrams(
          cur,
          prevEntry.data as { nodes?: { id: string }[] }
        )
        for (const nid of changed) {
          const ed = activeEditors.value.get(nid)
          if (ed && ed.user_id !== Number(authStore.user?.id)) {
            notify.warning(t('notification.collabUndoBlocked'))
            return
          }
        }
      }
    }
    diagramStore.undo()
  }

  function handleRedoKey() {
    if (isTypingInInput()) return
    if (!diagramStore.canRedo) {
      return
    }
    if (workshopCode.value) {
      const nextEntry = diagramStore.history[diagramStore.historyIndex + 1]
      const cur = diagramStore.data
      if (nextEntry?.data && cur) {
        const changed = nodeIdsDiffBetweenDiagrams(
          cur,
          nextEntry.data as { nodes?: { id: string }[] }
        )
        for (const nid of changed) {
          const ed = activeEditors.value.get(nid)
          if (ed && ed.user_id !== Number(authStore.user?.id)) {
            notify.warning(t('notification.collabRedoBlocked'))
            return
          }
        }
      }
    }
    diagramStore.redo()
  }

  function handleClearNodeTextKey() {
    if (isTypingInInput()) return
    if (relationshipActiveEntry.value) return
    const selected = [...diagramStore.selectedNodes]
    if (selected.length === 0) {
      notify.warning(t('notification.selectNodeToClear'))
      return
    }
    const protectedIds = [
      'topic',
      'event',
      'flow-topic',
      'left-topic',
      'right-topic',
      'dimension-label',
      'outer-boundary',
    ]
    let clearedCount = 0
    const isLearningSheet = diagramStore.isLearningSheet

    for (const nodeId of selected) {
      if (protectedIds.includes(nodeId)) continue
      const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
      if (node && node.type !== 'topic' && node.type !== 'center' && node.type !== 'boundary') {
        if (isLearningSheet) {
          if (diagramStore.emptyNodeForLearningSheet(nodeId)) {
            clearedCount++
          }
        } else {
          if (diagramStore.emptyNode(nodeId)) {
            clearedCount++
          }
        }
      }
    }

    if (clearedCount > 0) {
      diagramStore.pushHistory(
        isLearningSheet
          ? t('notification.historyEmptyLearning')
          : t('notification.historyClearNodes')
      )
      notify.success(
        isLearningSheet
          ? t('notification.canvasClearNodesLearning', { count: clearedCount })
          : t('notification.canvasClearNodes', { count: clearedCount })
      )
      if (isLearningSheet) {
        diagramAutoSave.performSave()
      }
    } else {
      notify.warning(t('notification.cannotClearTopicOrCenter'))
    }
  }

  async function handleSaveKey() {
    if (!authStore.isAuthenticated) {
      notify.warning(t('editor.saveNeedsLogin'))
      return
    }
    const result = await diagramAutoSave.flush()
    if (result.saved) {
      notify.success(t('editor.savedSuccess'))
    } else if (result.reason === 'skipped_slots_full') {
      eventBus.emit('canvas:show_slot_full_modal', {} as never)
    }
  }

  useEditorShortcuts({
    undo: handleUndoKey,
    redo: handleRedoKey,
    save: handleSaveKey,
    delete: handleDeleteKey,
    addNode: handleAddNodeKey,
    addBranch: handleAddBranchKey,
    addChild: handleAddChildKey,
    clearNodeText: handleClearNodeTextKey,
  })

  return { handleSaveKey }
}
