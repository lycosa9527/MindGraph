import type { Ref } from 'vue'

import {
  resolveEnterKeyEvent,
  resolveTabKeyEvent,
} from '@/composables/canvasPage/canvasPageEditorShortcutRouting'
import {
  bindCanvasCollabHistoryContext,
  tryCollabGuardedRedo,
  tryCollabGuardedUndo,
} from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import {
  toggleLearningSheetAnswersVisibility,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import { eventBus } from '@/composables/core/useEventBus'
import { useEditorShortcuts, useKeyboard } from '@/composables/core/useKeyboard'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import {
  buildDiagramSaveGuardState,
  flushDiagramSaveWithFeedback,
} from '@/composables/editor/diagramSaveFeedback'
import { useDiagramAutoSave } from '@/composables/editor/useDiagramAutoSave'
import {
  buildMindMapNavRectsFromLayout,
  findMindMapNodeInDirection,
  isMindMapDiagramType,
  mindMapArrowKeyToDirection,
  resolveMindMapNavStartId,
} from '@/composables/mindMap/mindMapArrowNavigation'
import { useAuthStore, useDiagramStore, useLLMResultsStore, usePanelsStore } from '@/stores'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'

type ActiveEditorEntry = { user_id: number }
type DiagramAutoSaveApi = ReturnType<typeof useDiagramAutoSave>

export function useCanvasPageEditorShortcuts(options: {
  workshopCode: Ref<string | null>
  activeEditors: Ref<Map<string, ActiveEditorEntry>>
  relationshipActiveEntry: Ref<unknown>
  diagramAutoSave: DiagramAutoSaveApi
  isCollabGuest: Ref<boolean>
}): { handleSaveKey: () => Promise<void> } {
  const { workshopCode, activeEditors, relationshipActiveEntry, diagramAutoSave, isCollabGuest } =
    options
  const diagramStore = useDiagramStore()
  const authStore = useAuthStore()
  const llmResultsStore = useLLMResultsStore()
  const previewStore = useMindMapSubgraphPreviewStore()
  const notify = useNotifications()
  const { t } = useLanguage()

  bindCanvasCollabHistoryContext(workshopCode, activeEditors)

  const panelsStore = usePanelsStore()
  const useMindMapV2 = useMindMapV2Chrome()
  const { activeTool, closeActiveTool } = useMindMapSideToolbarState()

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
    if (diagramStore.type === 'tree_map' || diagramStore.type === 'multi_flow_map') {
      eventBus.emit('diagram:add_node_requested', {})
      return
    }
    if (
      diagramStore.type === 'mindmap' ||
      diagramStore.type === 'mind_map' ||
      diagramStore.type === 'brace_map' ||
      diagramStore.type === 'flow_map'
    ) {
      eventBus.emit('diagram:add_child_requested', {})
    }
  }

  function handleTabKey(event: KeyboardEvent) {
    if (event.repeat) return
    if (isTypingInInput()) return
    const routed = resolveTabKeyEvent(diagramStore.type)
    if (routed) {
      eventBus.emit(routed, {})
      return
    }
    handleAddBranchKey()
  }

  function handleEnterKey(event: KeyboardEvent) {
    if (event.repeat) return
    if (isTypingInInput()) return
    const routed = resolveEnterKeyEvent(diagramStore.type)
    if (routed) {
      eventBus.emit(routed, {})
      return
    }
    handleAddChildKey()
  }

  function handleSpaceEditKey(event: KeyboardEvent) {
    if (event.repeat) return
    if (isTypingInInput()) return
    if (diagramStore.type === 'concept_map') return
    const selectedId = diagramStore.selectedNodes[0]
    if (!selectedId) return
    eventBus.emit('node:edit_requested', { nodeId: selectedId })
  }

  function handleMindMapArrowKey(key: string) {
    if (isTypingInInput()) return
    if (!useMindMapV2.value) return
    if (!isMindMapDiagramType(diagramStore.type)) return
    const direction = mindMapArrowKeyToDirection(key)
    if (!direction) return

    const rects = buildMindMapNavRectsFromLayout(
      diagramStore.vueFlowNodes,
      (nodeId) => diagramStore.getNodeDimension(nodeId)
    )
    if (rects.length === 0) return

    const startId = resolveMindMapNavStartId(diagramStore.selectedNodes, rects)
    if (!startId) return

    const nextId = findMindMapNodeInDirection(startId, direction, rects)
    if (nextId) {
      diagramStore.selectNodes(nextId)
    }
  }

  function handleUndoKey() {
    if (isTypingInInput()) return
    tryCollabGuardedUndo()
  }

  function handleRedoKey() {
    if (isTypingInInput()) return
    tryCollabGuardedRedo()
  }

  function handleEscapeKey() {
    if (isTypingInInput()) return
    if (useMindMapV2.value && activeTool.value) {
      closeActiveTool()
      return
    }
    if (panelsStore.mindmatePanel.isOpen) {
      panelsStore.closeMindmate()
      return
    }
    if (panelsStore.nodePalettePanel.isOpen) {
      panelsStore.closeNodePalette()
      return
    }
    if (panelsStore.propertyPanel.isOpen) {
      panelsStore.closePropertyPanel()
      return
    }
    diagramStore.clearSelection()
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

  function handleToggleLearningSheetAnswersKey() {
    if (isTypingInInput()) return
    toggleLearningSheetAnswersVisibility()
  }

  async function handleSaveKey() {
    if (!authStore.isAuthenticated) {
      notify.warning(t('editor.saveNeedsLogin'))
      return
    }
    await flushDiagramSaveWithFeedback({
      flush: () => diagramAutoSave.flush(),
      guardState: buildDiagramSaveGuardState({
        llmGenerating: llmResultsStore.isGenerating,
        subgraphGenerating: previewStore.isGenerating,
        collabSessionActive: diagramStore.collabSessionActive,
        isCollabGuest: isCollabGuest.value,
      }),
      t,
      notifySuccess: (message) => notify.success(message),
      notifyWarning: (message) => notify.warning(message),
      onSlotsFull: () => eventBus.emit('canvas:show_slot_full_modal', {} as never),
    })
  }

  function handleCopyKey(): void {
    if (isTypingInInput()) return
    diagramStore.copySelectedNodes()
  }

  function handleCutKey(): void {
    if (isTypingInInput()) return
    diagramStore.cutSelectedNodes()
  }

  function handlePasteKey(): void {
    if (isTypingInInput()) return
    if (!diagramStore.canPaste) return
    const anchor = diagramStore.selectedNodes[0]
    diagramStore.pasteClipboardAt({ anchorNodeId: anchor })
  }

  useEditorShortcuts({
    undo: handleUndoKey,
    redo: handleRedoKey,
    save: handleSaveKey,
    delete: handleDeleteKey,
    escape: handleEscapeKey,
    addNode: handleAddNodeKey,
    clearNodeText: handleClearNodeTextKey,
    copy: handleCopyKey,
    cut: handleCutKey,
    paste: handlePasteKey,
  })

  useKeyboard([
    { key: 'Tab', handler: handleTabKey },
    { key: 'Enter', handler: handleEnterKey },
    { key: ' ', handler: handleSpaceEditKey },
    { key: 'ArrowUp', handler: () => handleMindMapArrowKey('ArrowUp') },
    { key: 'ArrowDown', handler: () => handleMindMapArrowKey('ArrowDown') },
    { key: 'ArrowLeft', handler: () => handleMindMapArrowKey('ArrowLeft') },
    { key: 'ArrowRight', handler: () => handleMindMapArrowKey('ArrowRight') },
    { key: 'h', ctrl: true, shift: true, handler: handleToggleLearningSheetAnswersKey },
  ])

  return { handleSaveKey }
}
