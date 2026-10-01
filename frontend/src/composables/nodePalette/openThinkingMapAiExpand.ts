/**
 * Thinking-map "AI subgraph": open the type's node palette on the selection.
 */
import { isCollabGuestAiBlocked } from '@/composables/collab/useCollabGuestAiGate'
import { notify } from '@/composables/core/notifications'
import { eventBus } from '@/composables/core/useEventBus'
import { getNodePaletteDiagramKey } from '@/composables/nodePalette/sessionKeys'
import { thinkingMapPaletteFocus } from '@/composables/nodePalette/thinkingMapPaletteFocus'
import { getNodePalette } from '@/composables/nodePalette/useNodePalette'
import { useDiagramStore, usePanelsStore, useSavedDiagramsStore } from '@/stores'
import { useLearningAssignmentCanvasStore } from '@/stores/learningAssignmentCanvas'

function paletteOpenOptions(
  focus: ReturnType<typeof thinkingMapPaletteFocus>
): Record<string, unknown> {
  if (!focus) return {}
  if (focus.kind === 'mode') return { mode: focus.mode }
  return {
    stage: focus.stage,
    stage_data: focus.stageData,
    mode: focus.name,
  }
}

export function openThinkingMapAiExpand(nodeId: string): void {
  const diagramStore = useDiagramStore()
  const panelsStore = usePanelsStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const nodes = diagramStore.data?.nodes ?? []
  if (!nodes.length) {
    notify.warningKey('canvas.toolbar.createDiagramFirst')
    return
  }
  if (isCollabGuestAiBlocked(diagramStore.collabSessionActive, diagramStore.collabIsDiagramOwner)) {
    notify.warningKey('canvas.toolbar.collabAiBlocked')
    return
  }
  const learning = useLearningAssignmentCanvasStore()
  if (!learning.can('ai_brainstorm')) {
    if (learning.isActive) {
      notify.warningKey('learningSpace.aiCapabilityBlocked')
    }
    return
  }

  const dimension = (diagramStore.data as { dimension?: string } | null)?.dimension ?? null
  const focus = thinkingMapPaletteFocus({
    diagramType: diagramStore.type,
    nodes,
    connections: diagramStore.data?.connections,
    nodeId,
    dimension,
  })

  if (panelsStore.nodePalettePanel.isOpen) {
    const palette = getNodePalette()
    if (focus?.kind === 'mode') {
      void palette.switchTab(focus.mode)
    } else if (focus?.kind === 'parent') {
      void palette.switchStageTab(focus.id, focus.name)
    }
    return
  }

  const diagramType =
    diagramStore.type === 'mind_map' ? 'mindmap' : (diagramStore.type ?? 'unknown')
  const routeDiagramId = new URLSearchParams(window.location.search).get('diagramId') ?? undefined
  const diagramKey = getNodePaletteDiagramKey(
    diagramType,
    savedDiagramsStore.activeDiagramId,
    routeDiagramId
  )
  panelsStore.clearNodePaletteSession(diagramKey)
  panelsStore.setNodePaletteSuggestions([])
  eventBus.emit('panel:open_requested', {
    panel: 'nodePalette',
    source: 'thinking-map-ai-expand',
    options: paletteOpenOptions(focus),
  })
}
