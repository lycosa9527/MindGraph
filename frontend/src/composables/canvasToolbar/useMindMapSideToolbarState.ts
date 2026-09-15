import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { getAiBrainstorm } from '@/composables/aiBrainstorm/useAiBrainstorm'
import { useCollabGuestAiGate } from '@/composables/collab/useCollabGuestAiGate'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useMindMapAudienceGenerate } from '@/composables/mindMap/audience/useMindMapAudienceGenerate'
import { getAiBrainstormDiagramKey } from '@/composables/nodePalette/sessionKeys'
import { useDiagramStore, usePanelsStore, useSavedDiagramsStore } from '@/stores'

export type MindMapSideToolId =
  | 'outline'
  | 'waterfall'
  | 'learning_sheet'
  | 'one_sentence'
  | 'document_summary'

/** Active side tool panel; null = no overlay panel. */
const activeTool = ref<MindMapSideToolId | null>(null)

export function useMindMapSideToolbarState() {
  const route = useRoute()
  const diagramStore = useDiagramStore()
  const panelsStore = usePanelsStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const notify = useNotifications()
  const { t } = useLanguage()
  const { handleMindMapAiGenerate } = useMindMapAudienceGenerate()
  const { aiBlockedByCollab, guardCollabGuestAi } = useCollabGuestAiGate()

  function guardCollabGuestFeature(): boolean {
    if (!aiBlockedByCollab.value) {
      return true
    }
    notify.warning(t('canvas.toolbar.collabGuestFeatureBlocked'))
    return false
  }

  function requireDiagram(): boolean {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return false
    }
    return true
  }

  function openTool(toolId: MindMapSideToolId): void {
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
    const previous = activeTool.value
    if (previous === 'waterfall' && toolId !== 'waterfall' && panelsStore.aiBrainstormPanel.isOpen) {
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
