import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import { getAiBrainstorm } from '@/composables/aiBrainstorm/useAiBrainstorm'
import { useCollabGuestAiGate } from '@/composables/collab/useCollabGuestAiGate'
import { eventBus } from '@/composables/core/useEventBus'
import { useNotifications } from '@/composables/core/useNotifications'
import { useLearningAiGate } from '@/composables/learningSpace/useLearningAiGate'
import { useMindMapAudienceGenerate } from '@/composables/mindMap/audience/useMindMapAudienceGenerate'
import { openConceptMapNodePalette } from '@/composables/nodePalette/openConceptMapNodePalette'
import { getAiBrainstormDiagramKey } from '@/composables/nodePalette/sessionKeys'
import { useDiagramStore, usePanelsStore, useSavedDiagramsStore } from '@/stores'

export type MindMapSideToolId =
  'outline' | 'waterfall' | 'learning_sheet' | 'one_sentence' | 'document_summary'

/** Active side tool panel; null = no overlay panel. */
const activeTool = ref<MindMapSideToolId | null>(null)

export function useMindMapSideToolbarState() {
  const route = useRoute()
  const diagramStore = useDiagramStore()
  const panelsStore = usePanelsStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const notify = useNotifications()
  const { handleMindMapAiGenerate } = useMindMapAudienceGenerate()
  const { aiBlockedByCollab, guardCollabGuestAi } = useCollabGuestAiGate()
  const { requireCapability } = useLearningAiGate()

  function guardCollabGuestFeature(): boolean {
    if (!aiBlockedByCollab.value) {
      return true
    }
    notify.warningKey('canvas.toolbar.collabGuestFeatureBlocked')
    return false
  }

  function requireDiagram(): boolean {
    if (!diagramStore.data?.nodes?.length) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return false
    }
    return true
  }

  function openThinkingMapNodePalette(): void {
    if (!requireDiagram()) return
    if (!guardCollabGuestAi()) return
    if (!requireCapability('ai_brainstorm')) return
    if (panelsStore.nodePalettePanel.isOpen) {
      panelsStore.closeNodePalette()
      return
    }
    eventBus.emit('panel:open_requested', {
      panel: 'nodePalette',
      source: 'thinking-map-ribbon',
    })
  }

  function openTool(toolId: MindMapSideToolId): void {
    if (toolId === 'waterfall' && diagramStore.type === 'concept_map') {
      openConceptMapNodePalette({ toggle: true })
      return
    }
    if (toolId === 'waterfall' && isThinkingMapDiagramType(diagramStore.type)) {
      openThinkingMapNodePalette()
      return
    }
    if (!requireDiagram()) return
    if (toolId === 'learning_sheet' && !guardCollabGuestFeature()) {
      return
    }
    if (
      (toolId === 'waterfall' || toolId === 'one_sentence' || toolId === 'document_summary') &&
      !guardCollabGuestAi()
    ) {
      return
    }
    if (toolId === 'waterfall' && !requireCapability('ai_brainstorm')) return
    if (toolId === 'document_summary' && !requireCapability('file_generate')) return
    const previous = activeTool.value
    if (
      previous === 'waterfall' &&
      toolId !== 'waterfall' &&
      panelsStore.aiBrainstormPanel.isOpen
    ) {
      getAiBrainstorm().dismiss()
    }
    activeTool.value = toolId

    if (toolId === 'waterfall') {
      const diagramKey = getAiBrainstormDiagramKey(
        savedDiagramsStore.activeDiagramId,
        route.query.diagramId as string | undefined
      )
      panelsStore.openAiBrainstorm({ diagramKey })
    }
  }

  function closeActiveTool(): void {
    const closing = activeTool.value
    activeTool.value = null
    if (closing === 'waterfall' && panelsStore.aiBrainstormPanel.isOpen) {
      getAiBrainstorm().dismiss()
    }
  }

  function runOneSentenceGenerate(generationInstructions?: string): void {
    if (!guardCollabGuestAi()) {
      return
    }
    void handleMindMapAiGenerate({ generationInstructions })
  }

  function handleToolSelect(toolId: MindMapSideToolId): void {
    if (toolId === 'learning_sheet') {
      if (!requireDiagram()) return
      if (activeTool.value === 'learning_sheet') {
        closeActiveTool()
        return
      }
      openTool('learning_sheet')
      return
    }

    if (toolId === 'one_sentence') {
      if (!requireDiagram()) return
      if (activeTool.value === 'one_sentence') {
        closeActiveTool()
        return
      }
      openTool('one_sentence')
      return
    }

    if (toolId === 'document_summary') {
      if (!requireDiagram()) return
      if (activeTool.value === 'document_summary') {
        closeActiveTool()
        return
      }
      openTool('document_summary')
      return
    }

    if (activeTool.value === toolId) {
      closeActiveTool()
      return
    }

    openTool(toolId)
  }

  eventBus.removeAllListenersForOwner('mindMapSideToolbarOutline')
  eventBus.onWithOwner(
    'mindmap:outline_toggle_requested',
    () => {
      handleToolSelect('outline')
    },
    'mindMapSideToolbarOutline'
  )

  return {
    activeTool,
    openTool,
    closeActiveTool,
    handleToolSelect,
    runOneSentenceGenerate,
  }
}

/** Close waterfall when its external panel closes. */
export function bindMindMapExternalPanelClose(
  isAiBrainstormOpen: () => boolean,
  onClose: () => void
): () => void {
  return watch(isAiBrainstormOpen, (open) => {
    if (!open && activeTool.value === 'waterfall') {
      onClose()
    }
  })
}

/** Reset side-toolbar UI when the canvas returns to the default template. */
export function resetMindMapSideToolbarState(): void {
  activeTool.value = null
}
