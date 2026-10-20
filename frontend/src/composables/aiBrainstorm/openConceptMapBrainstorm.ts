/**
 * Concept-map AI generate: open the concept palette.
 * A selected concept opens its own tab. The topic opens the concept list.
 */
import { isCollabGuestAiBlocked } from '@/composables/collab/useCollabGuestAiGate'
import { notify } from '@/composables/core/notifications'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore, usePanelsStore } from '@/stores'

export function openConceptMapBrainstorm(options?: { toggle?: boolean }): void {
  const diagramStore = useDiagramStore()
  const panelsStore = usePanelsStore()
  const nodes = diagramStore.data?.nodes ?? []
  if (!nodes.length) {
    notify.warningKey('canvas.toolbar.createDiagramFirst')
    return
  }
  if (isCollabGuestAiBlocked(diagramStore.collabSessionActive, diagramStore.collabIsDiagramOwner)) {
    notify.warningKey('canvas.toolbar.collabAiBlocked')
    return
  }
  if (options?.toggle && panelsStore.diagramBrainstormPanel.isOpen) {
    panelsStore.closeDiagramBrainstorm()
    return
  }

  const openOptions: Record<string, unknown> = { useConceptListHeader: true }
  if (diagramStore.selectedNodes.length === 1) {
    const nodeId = diagramStore.selectedNodes[0]
    const node = nodes.find((item) => item.id === nodeId)
    const topicNode = nodes.find(
      (item) => item.type === 'topic' || item.type === 'center' || item.id === 'topic'
    )
    if (node && node.id !== topicNode?.id && node.text?.trim()) {
      openOptions.conceptMapNodeId = node.id
      openOptions.conceptMapNodeText = node.text.trim()
    }
  }
  eventBus.emit('panel:open_requested', {
    panel: 'diagramBrainstorm',
    source: 'concept-map-ribbon',
    options: openOptions,
  })
}
