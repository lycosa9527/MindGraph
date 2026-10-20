/**
 * Thinking-map "AI subgraph": open the type's AI brainstorm on the selection.
 */
import { getDiagramBrainstormKey } from '@/composables/aiBrainstorm/sessionKeys'
import { thinkingMapBrainstormFocus } from '@/composables/aiBrainstorm/thinkingMapBrainstormFocus'
import { getDiagramBrainstorm } from '@/composables/aiBrainstorm/useDiagramBrainstorm'
import { isCollabGuestAiBlocked } from '@/composables/collab/useCollabGuestAiGate'
import { notify } from '@/composables/core/notifications'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore, usePanelsStore, useSavedDiagramsStore } from '@/stores'
import { useLearningAssignmentCanvasStore } from '@/stores/learningAssignmentCanvas'

function paletteOpenOptions(
  focus: ReturnType<typeof thinkingMapBrainstormFocus>
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
  const focus = thinkingMapBrainstormFocus({
    diagramType: diagramStore.type,
    nodes,
    connections: diagramStore.data?.connections,
    nodeId,
    dimension,
  })

  if (panelsStore.diagramBrainstormPanel.isOpen) {
    const palette = getDiagramBrainstorm()
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
  const diagramKey = getDiagramBrainstormKey(
    diagramType,
    savedDiagramsStore.activeDiagramId,
    routeDiagramId
  )
  panelsStore.clearDiagramBrainstormSession(diagramKey)
  panelsStore.setDiagramBrainstormSuggestions([])
  eventBus.emit('panel:open_requested', {
    panel: 'diagramBrainstorm',
    source: 'thinking-map-ai-expand',
    options: paletteOpenOptions(focus),
  })
}
