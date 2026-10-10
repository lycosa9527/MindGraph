/**
 * Shared actions for New-canvas ribbon and status bar. Does not change the V2 diagram.
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  tryCollabGuardedRedo,
  tryCollabGuardedUndo,
} from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import { useCanvasDiagramTranslate } from '@/composables/canvasToolbar/useCanvasDiagramTranslate'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar/useCanvasToolbarApps'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useAutoComplete } from '@/composables/editor/useAutoComplete'
import { useDiagramImport } from '@/composables/editor/useDiagramImport'
import { useNodeActions } from '@/composables/editor/useNodeActions'
import { useOrgCustomLlm } from '@/composables/llm/useOrgCustomLlm'
import { useLearningSheetCustomMode } from '@/composables/mindMap/useLearningSheetCustomMode'
import { CANVAS_LLM_MENU, canvasLlmLogo } from '@/config/canvasLlmMenu'
import { useLLMResultsStore, usePanelsStore, useUIStore } from '@/stores'
import { navigateBackFromCanvas } from '@/utils/canvasBackNavigation'

export function useMindMapRibbonChromeActions() {
  const router = useRouter()
  const route = useRoute()
  const notify = useNotifications()
  const diagramStore = useDiagramSession()
  const uiStore = useUIStore()
  const panelsStore = usePanelsStore()
  const llmResultsStore = useLLMResultsStore()
  const { handleAddNode, handleDeleteNode } = useNodeActions({
    registerEventBusListeners: false,
  })
  const { handleAIGenerate } = useCanvasToolbarApps()
  const { leaveTranslatePreview } = useCanvasDiagramTranslate()
  const { triggerImportInPlace } = useDiagramImport()
  const { switchToModel } = useAutoComplete()
  const { t } = useLanguage()
  const { customLlmEnabled, displayNameForModel } = useOrgCustomLlm()
  const learningSheet = useLearningSheetCustomMode()

  const nodeCount = computed(() => diagramStore.data?.nodes?.length ?? 0)
  const canUndo = computed(() => diagramStore.canUndo)
  const canRedo = computed(() => diagramStore.canRedo)
  const selectedId = computed(() => diagramStore.selectedNodes[0] ?? null)
  const selectedNode = computed(() => diagramStore.selectedNodeData[0] ?? null)
  const hasSelection = computed(() => diagramStore.selectedNodes.length > 0)
  const llmMenu = computed(() => {
    if (customLlmEnabled.value) {
      return [
        {
          id: 'qwen',
          label: displayNameForModel('qwen'),
          model: '',
          logo: canvasLlmLogo('qwen'),
        },
      ]
    }
    return CANVAS_LLM_MENU.map((item) => ({
      id: item.id,
      label: String(t(item.labelKey)),
      model: String(t(item.modelKey)),
      logo: item.logo,
    }))
  })
  const selectedLlm = computed(() => {
    const current = llmResultsStore.canvasModelChoice
    if (current && llmMenu.value.some((item) => item.id === current)) {
      return current
    }
    return customLlmEnabled.value ? 'qwen' : 'express'
  })
  const selectedLlmRow = computed(
    () => llmMenu.value.find((item) => item.id === selectedLlm.value) ?? llmMenu.value[0]
  )
  const lineModeOn = computed(() => uiStore.wireframeMode)
  const isLearningSheet = computed(() => diagramStore.isLearningSheet)
  const isMindmateOpen = computed(() => panelsStore.mindmatePanel.isOpen)
  const isNodePaletteOpen = computed(() => panelsStore.nodePalettePanel.isOpen)

  function goBack(): void {
    if (route.path.startsWith('/training')) return
    navigateBackFromCanvas(router, route.path)
  }

  function emptySelected(): void {
    const nodeId = selectedId.value
    if (!nodeId) {
      notify.warningKey('canvas.toolbar.selectNodesFirst')
      return
    }
    diagramStore.emptyNode(nodeId)
  }

  function toggleLineMode(): void {
    uiStore.toggleWireframe()
  }

  function toggleLearning(): void {
    if (!diagramStore.data?.nodes?.length) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return
    }
    if (diagramStore.isLearningSheet) {
      learningSheet.exitLearningSheet()
      return
    }
    if (diagramStore.hasPreservedLearningSheet()) {
      diagramStore.applyLearningSheetView()
      return
    }
    diagramStore.setLearningSheetMode(true)
  }

  function openNodePalette(): void {
    eventBus.emit('panel:open_requested', { panel: 'nodePalette', source: 'mind-map-ribbon' })
  }

  function toggleMindmate(): void {
    if (panelsStore.mindmatePanel.isOpen) {
      panelsStore.closeMindmate()
      return
    }
    panelsStore.openMindmate()
  }

  function fitView(): void {
    eventBus.emit('view:fit_diagram_requested', {})
  }

  function selectLlm(model: string): void {
    void leaveTranslatePreview().then(async () => {
      const switched = await switchToModel(model)
      if (!switched) {
        llmResultsStore.setSelectedModel(model)
      }
    })
  }

  return {
    llmMenu,
    selectedLlmRow,
    nodeCount,
    canUndo,
    canRedo,
    selectedId,
    selectedNode,
    hasSelection,
    selectedLlm,
    lineModeOn,
    isLearningSheet,
    isMindmateOpen,
    isNodePaletteOpen,
    goBack,
    handleAddNode,
    handleDeleteNode,
    emptySelected,
    handleAIGenerate,
    toggleLineMode,
    toggleLearning,
    openNodePalette,
    toggleMindmate,
    undo: tryCollabGuardedUndo,
    redo: tryCollabGuardedRedo,
    exportPng: () => {
      eventBus.emit('toolbar:export_requested', { format: 'png' })
    },
    saveMg: () => {
      eventBus.emit('toolbar:export_requested', { format: 'mg' })
    },
    importMg: triggerImportInPlace,
    fitView,
    selectLlm,
  }
}
