import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useNotifications } from '@/composables/core/useNotifications'
import { useLanguage } from '@/composables/core/useLanguage'
import { getNodePaletteDiagramKey } from '@/composables/nodePalette/sessionKeys'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar/useCanvasToolbarApps'
import { useDiagramStore, usePanelsStore, useSavedDiagramsStore } from '@/stores'

export type MindMapSideToolId =
  | 'outline'
  | 'waterfall'
  | 'learning_sheet'
  | 'one_sentence'
  | 'document_summary'

/** Active side tool panel; null = sidebar visible, no panel. */
const activeTool = ref<MindMapSideToolId | null>(null)

/** Left toolbar expand/collapse — survives panel open/close (toolbar unmounts via v-if). */
const sidebarExpanded = ref(false)

export function useMindMapSideToolbarState() {
  const route = useRoute()
  const diagramStore = useDiagramStore()
  const panelsStore = usePanelsStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const notify = useNotifications()
  const { t } = useLanguage()
  const { handleAIGenerate } = useCanvasToolbarApps()

  const sidebarVisible = computed(() => activeTool.value === null)
  const outlinePanelOpen = computed(() => activeTool.value === 'outline')
  const aiPanelOpen = computed(() => activeTool.value === 'one_sentence')

  function requireDiagram(): boolean {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return false
    }
    return true
  }

  function openTool(toolId: MindMapSideToolId): void {
    if (!requireDiagram()) return
    activeTool.value = toolId

    if (toolId === 'waterfall') {
      const diagramKey = getNodePaletteDiagramKey(
        'mindmap',
        savedDiagramsStore.activeDiagramId,
        route.query.diagramId as string | undefined
      )
      panelsStore.openNodePalette({ mindMapWaterfallMode: true, diagramKey })
    }
  }

  function closeActiveTool(): void {
    const closing = activeTool.value
    activeTool.value = null
    sidebarExpanded.value = true
    if (closing === 'waterfall' && panelsStore.nodePalettePanel.isOpen) {
      panelsStore.closeNodePalette()
    }
  }

  function runOneSentenceGenerate(generationInstructions?: string): void {
    if (diagramStore.collabSessionActive) {
      notify.warning(t('canvas.toolbar.collabLiveAiDisabled'))
      return
    }
    void handleAIGenerate({ generationInstructions })
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
    sidebarVisible,
    sidebarExpanded,
    outlinePanelOpen,
    aiPanelOpen,
    openTool,
    closeActiveTool,
    handleToolSelect,
    runOneSentenceGenerate,
  }
}

/** Close waterfall when its external panel closes. */
export function bindMindMapExternalPanelClose(
  isNodePaletteOpen: () => boolean,
  onClose: () => void
): () => void {
  return watch(isNodePaletteOpen, (paletteOpen) => {
    if (!paletteOpen && activeTool.value === 'waterfall') {
      onClose()
    }
  })
}

/** Reset side-toolbar UI when the canvas returns to the default template. */
export function resetMindMapSideToolbarState(): void {
  activeTool.value = null
  sidebarExpanded.value = false
}
