/**
 * Mobile canvas top toolbar actions (save, nodes, AI, palette, zoom).
 */
import { ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import {
  buildDiagramSaveGuardState,
  flushDiagramSaveWithFeedback,
  type DiagramSaveGuardState,
} from '@/composables/editor/diagramSaveFeedback'
import type { useDiagramAutoSave } from '@/composables/editor/useDiagramAutoSave'
import type { useAuthStore } from '@/stores/auth'
import type { useDiagramStore } from '@/stores/diagram'
import type { useLLMResultsStore } from '@/stores/llmResults'
import type { usePanelsStore } from '@/stores/panels'

export interface UseMobileCanvasToolbarOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  authStore: ReturnType<typeof useAuthStore>
  llmResultsStore: ReturnType<typeof useLLMResultsStore>
  panelsStore: ReturnType<typeof usePanelsStore>
  diagramAutoSave: ReturnType<typeof useDiagramAutoSave>
  saveGuardState?: () => DiagramSaveGuardState
  isConceptMap: { value: boolean }
  isAIGenerating: { value: boolean }
  handleAIGenerate: (options?: {
    generationInstructions?: string
    topicOverride?: string
  }) => void | Promise<void>
  handleConceptGeneration: () => void
  translate: (key: string, fallback?: string) => string
  notifySuccess: (message: string) => void
  notifyWarning: (message: string) => void
}

export function useMobileCanvasToolbar(options: UseMobileCanvasToolbarOptions) {
  const {
    diagramStore,
    authStore,
    llmResultsStore,
    panelsStore,
    diagramAutoSave,
    saveGuardState,
    isConceptMap,
    isAIGenerating,
    handleAIGenerate,
    handleConceptGeneration,
    translate,
    notifySuccess,
    notifyWarning,
  } = options

  const isSaving = ref(false)
  const showNodePalette = ref(false)
  const showModelDrawer = ref(false)

  async function handleSave(): Promise<void> {
    if (isSaving.value) return
    if (!authStore.isAuthenticated) {
      notifyWarning(translate('notification.signInToUse'))
      return
    }
    isSaving.value = true
    try {
      await flushDiagramSaveWithFeedback({
        flush: () => diagramAutoSave.flush(),
        guardState: saveGuardState?.() ??
          buildDiagramSaveGuardState({
            llmGenerating: llmResultsStore.isGenerating,
            subgraphGenerating: false,
            collabSessionActive: diagramStore.collabSessionActive,
            isCollabGuest: false,
          }),
        t: translate,
        notifySuccess: (message) => notifySuccess(message),
        notifyWarning: (message) => notifyWarning(message),
        onSlotsFull: () => notifyWarning(translate('notification.slotsFull', '图示槽位已满')),
      })
    } finally {
      isSaving.value = false
    }
  }

  function handleAddNode(): void {
    if (diagramStore.type === 'concept_map') return
    eventBus.emit('diagram:add_node_requested', {})
  }

  function handleDeleteSelected(): void {
    eventBus.emit('diagram:delete_selected_requested', {})
  }

  function handleToolbarAI(): void {
    if (!authStore.isAuthenticated) {
      notifyWarning(translate('notification.signInToUse'))
      return
    }
    if (isConceptMap.value) {
      handleConceptGeneration()
      return
    }
    if (isAIGenerating.value) return
    void handleAIGenerate()
  }

  function toggleConceptMapAiToolbar(): void {
    if (llmResultsStore.selectedModel) {
      llmResultsStore.setSelectedModel(null)
    } else {
      llmResultsStore.setSelectedModel('qwen')
    }
  }

  function toggleNodePalette(): void {
    if (panelsStore.nodePalettePanel.isOpen) {
      panelsStore.closeNodePalette()
      showNodePalette.value = false
    } else {
      panelsStore.openNodePalette()
      showNodePalette.value = true
    }
  }

  function handleFitToScreen(): void {
    eventBus.emit('view:fit_to_window_requested', { animate: true, userInitiated: true })
  }

  function handleZoomReset(): void {
    eventBus.emit('view:zoom_reset_requested', {})
  }

  return {
    isSaving,
    showNodePalette,
    showModelDrawer,
    handleSave,
    handleAddNode,
    handleDeleteSelected,
    handleToolbarAI,
    toggleConceptMapAiToolbar,
    toggleNodePalette,
    handleFitToScreen,
    handleZoomReset,
  }
}
