import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import { openConceptMapBrainstorm } from '@/composables/aiBrainstorm/openConceptMapBrainstorm'
import {
  getAiBrainstormDiagramKey,
  getDiagramBrainstormKey,
} from '@/composables/aiBrainstorm/sessionKeys'
import { getAiBrainstorm } from '@/composables/aiBrainstorm/useAiBrainstorm'
import { useCollabGuestAiGate } from '@/composables/collab/useCollabGuestAiGate'
import { eventBus } from '@/composables/core/useEventBus'
import { useNotifications } from '@/composables/core/useNotifications'
import { useLearningAiGate } from '@/composables/learningSpace/useLearningAiGate'
import { useMindMapAudienceGenerate } from '@/composables/mindMap/audience/useMindMapAudienceGenerate'
import { resetLearningSheetCustomModeUi } from '@/composables/mindMap/useLearningSheetCustomMode'
import { useDiagramStore, usePanelsStore, useSavedDiagramsStore } from '@/stores'
import { useLearningAssignmentCanvasStore } from '@/stores/learningAssignmentCanvas'

export type MindMapSideToolId =
  'outline' | 'waterfall' | 'learning_sheet' | 'one_sentence' | 'document_summary'

/** Active side tool panel; null = no overlay panel. */
const activeTool = ref<MindMapSideToolId | null>(null)

/**
 * 对话式修改 is the one-sentence sheet.
 * On thinking maps and concept maps, AI头脑风暴 is the diagram brainstorm panel,
 * which does not share `activeTool`, so opening either one must close the other.
 */
let oneSentenceYieldsToPalette = false

function bindOneSentenceYieldsToDiagramBrainstorm(): void {
  if (oneSentenceYieldsToPalette) return
  oneSentenceYieldsToPalette = true
  const panelsStore = usePanelsStore()
  watch(
    () => panelsStore.diagramBrainstormPanel.isOpen,
    (open) => {
      if (open && activeTool.value === 'one_sentence') {
        activeTool.value = null
      }
    },
    { flush: 'sync' }
  )
}

/** Close 挖空支架图 chrome when a student enters homework. Call once from the canvas page. */
export function watchHomeworkLearningSheet(): void {
  const lsCanvas = useLearningAssignmentCanvasStore()
  watch(
    () => lsCanvas.showLearningSheet,
    (shown) => {
      if (shown) return
      if (activeTool.value === 'learning_sheet') {
        activeTool.value = null
      }
      resetLearningSheetCustomModeUi()
    }
  )
}

export function isCoveringMindMapSideTool(tool: MindMapSideToolId | null): boolean {
  return (
    tool === 'waterfall' ||
    tool === 'learning_sheet' ||
    tool === 'one_sentence' ||
    tool === 'document_summary'
  )
}

export function coveringMindMapSideToolOpen(): boolean {
  return isCoveringMindMapSideTool(activeTool.value)
}

export function useMindMapSideToolbarState() {
  bindOneSentenceYieldsToDiagramBrainstorm()
  const route = useRoute()
  const diagramStore = useDiagramStore()
  const panelsStore = usePanelsStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const notify = useNotifications()
  const { handleMindMapAiGenerate } = useMindMapAudienceGenerate()
  const { aiBlockedByCollab, guardCollabGuestAi } = useCollabGuestAiGate()
  const lsCanvas = useLearningAssignmentCanvasStore()
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

  function closeDiagramBrainstormForOneSentence(): void {
    if (!panelsStore.diagramBrainstormPanel.isOpen) return
    const diagramType =
      diagramStore.type === 'mind_map' ? 'mindmap' : (diagramStore.type ?? 'unknown')
    const diagramKey = getDiagramBrainstormKey(
      diagramType,
      savedDiagramsStore.activeDiagramId,
      route.query.diagramId as string | undefined
    )
    panelsStore.saveDiagramBrainstormSession(diagramKey)
    panelsStore.closeDiagramBrainstorm()
  }

  function openThinkingMapDiagramBrainstorm(): void {
    if (!requireDiagram()) return
    if (!guardCollabGuestAi()) return
    if (!requireCapability('ai_brainstorm')) return
    if (panelsStore.diagramBrainstormPanel.isOpen) {
      panelsStore.closeDiagramBrainstorm()
      return
    }
    eventBus.emit('panel:open_requested', {
      panel: 'diagramBrainstorm',
      source: 'thinking-map-ribbon',
    })
  }

  function openTool(toolId: MindMapSideToolId): void {
    if (toolId === 'learning_sheet' && !lsCanvas.showLearningSheet) return
    if (toolId === 'waterfall' && diagramStore.type === 'concept_map') {
      openConceptMapBrainstorm({ toggle: true })
      return
    }
    if (toolId === 'waterfall' && isThinkingMapDiagramType(diagramStore.type)) {
      openThinkingMapDiagramBrainstorm()
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
    if (toolId === 'one_sentence') {
      closeDiagramBrainstormForOneSentence()
    }
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
