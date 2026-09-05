/**
 * V3 ribbon commands — reuses existing stores, node actions, and event-bus paths.
 */
import { computed, reactive } from 'vue'

import { useCanvasReset } from '@/composables/canvasPage/useCanvasReset'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar/useCanvasToolbarApps'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useNodeActions } from '@/composables/editor/useNodeActions'
import { useLearningSheetCustomMode } from '@/composables/mindMap/useLearningSheetCustomMode'
import { CANVAS_MINDMAP_EXPORT_MENU_ITEMS } from '@/config/canvasExportMenu'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useCanvasExportStore } from '@/stores'

import { useV3ChromeActions } from './useV3ChromeActions'

export function useV3RibbonActions() {
  const chrome = useV3ChromeActions()
  const { t } = useLanguage()
  const notify = useNotifications()
  const diagramStore = useDiagramSession()
  const { resetToDefaultTemplate } = useCanvasReset()
  const { handleAddChild, handleAddSibling, handleAddBranch, handleDeleteNode } = useNodeActions({
    registerEventBusListeners: false,
  })
  const { handleMoreAppItem, moreApps, handleAIGenerate } = useCanvasToolbarApps()
  const sideToolbar = useMindMapSideToolbarState()
  const learningSheet = useLearningSheetCustomMode()
  const canvasExportStore = useCanvasExportStore()

  const canPaste = computed(() => diagramStore.canPaste)
  const structureMode = computed(() => {
    void diagramStore.data?.nodes?.length
    void diagramStore.data?.connections?.length
    return diagramStore.getMindMapStructureMode()
  })

  function requireSelection(): boolean {
    if (diagramStore.selectedNodes.length === 0) {
      notify.warning(t('canvas.toolbar.selectNodesFirst'))
      return false
    }
    return true
  }

  function handleAddChildClick(): void {
    const selectedId = diagramStore.selectedNodes[0]
    if (!selectedId || selectedId === 'topic') {
      handleAddBranch()
      return
    }
    handleAddChild()
  }

  function copySelected(): void {
    if (!requireSelection()) return
    diagramStore.copySelectedNodes()
  }

  function cutSelected(): void {
    if (!requireSelection()) return
    diagramStore.cutSelectedNodes()
  }

  function pasteAtSelection(): void {
    if (!diagramStore.canPaste) return
    const anchor = diagramStore.selectedNodes[0]
    diagramStore.pasteClipboardAt({ anchorNodeId: anchor })
  }

  function requestSave(): void {
    eventBus.emit('canvas:save_requested', {})
  }

  function exportFormat(format: string): void {
    eventBus.emit('toolbar:export_requested', {
      format,
      options: { ...canvasExportStore.mergedExportOptions },
    })
  }

  function requestWorksheetText(): void {
    eventBus.emit('toolbar:worksheet_text_requested', {})
  }

  function requestSnapshot(): void {
    eventBus.emit('snapshot:requested', {})
  }

  function recallSnapshot(versionNumber: number): void {
    eventBus.emit('snapshot:recall_requested', { versionNumber })
  }

  function deleteSnapshot(versionNumber: number): void {
    eventBus.emit('snapshot:delete_requested', { versionNumber })
  }

  async function resetTemplate(): Promise<void> {
    await resetToDefaultTemplate()
  }

  function setStructure(mode: 'balanced' | 'right'): void {
    if (diagramStore.setMindMapStructureMode(mode)) {
      notify.success(t('canvas.toolbar.mindMapStructureApplied'))
    }
  }

  function zoomIn(): void {
    eventBus.emit('view:zoom_in_requested', {})
  }

  function zoomOut(): void {
    eventBus.emit('view:zoom_out_requested', {})
  }

  function zoomSet(percent: number): void {
    const zoom = Math.max(0.1, Math.min(4, percent / 100))
    eventBus.emit('view:zoom_set_requested', { zoom })
  }

  function fitToScreen(): void {
    eventBus.emit('view:fit_to_canvas_requested', { animate: true, userInitiated: true })
  }

  function toggleHand(active?: boolean): void {
    eventBus.emit('view:hand_tool_toggle_requested', { active })
  }

  function startPresentation(): void {
    eventBus.emit('presentation:start_requested', {})
  }

  function openCollab(mode: 'organization' | 'network' | 'stop'): void {
    eventBus.emit('collab:open_requested', { mode })
  }

  function openSideTool(tool: Parameters<typeof sideToolbar.openTool>[0]): void {
    sideToolbar.openTool(tool)
  }

  function requestAiSubgraph(): void {
    const nodeId = diagramStore.selectedNodes[0]
    if (!nodeId) {
      notify.warning(t('canvas.toolbar.selectNodesFirst'))
      return
    }
    eventBus.emit('mindmap:ai_subgraph_requested', { nodeId })
  }

  function requestExplainNode(): void {
    const nodeId = diagramStore.selectedNodes[0]
    if (!nodeId) {
      notify.warning(t('canvas.toolbar.selectNodesFirst'))
      return
    }
    eventBus.emit('mindmap:explain_node_requested', { nodeId })
  }

  function runTranslate(): void {
    const app = moreApps.value.find((item) => item.appKey === 'translate_diagram')
    if (app) {
      handleMoreAppItem(app)
    }
  }

  function toggleVirtualKeyboard(): void {
    const app = moreApps.value.find((item) => item.appKey === 'virtual_keyboard')
    if (app) {
      handleMoreAppItem(app)
    }
  }

  function resetNodeStyles(): void {
    const nodeId = diagramStore.selectedNodes[0]
    if (!nodeId) {
      notify.warning(t('canvas.toolbar.selectNodesFirst'))
      return
    }
    diagramStore.clearNodeStyle(nodeId)
  }

  return reactive({
    ...chrome,
    handleAIGenerate,
    handleAddChildClick,
    handleAddSibling,
    handleDeleteNode,
    canPaste,
    copySelected,
    cutSelected,
    pasteAtSelection,
    requestSave,
    exportFormat,
    exportMenuItems: CANVAS_MINDMAP_EXPORT_MENU_ITEMS,
    requestWorksheetText,
    requestSnapshot,
    recallSnapshot,
    deleteSnapshot,
    resetTemplate,
    structureMode,
    setStructure,
    zoomIn,
    zoomOut,
    zoomSet,
    fitToScreen,
    toggleHand,
    startPresentation,
    openCollab,
    openSideTool,
    requestAiSubgraph,
    requestExplainNode,
    runTranslate,
    toggleVirtualKeyboard,
    resetNodeStyles,
    learningSheet,
  })
}
