import type { Ref } from 'vue'
import { ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import type { DiagramNode, MindGraphNode } from '@/types'

/** Narrow store surface for this composable (avoids Pinia `Store` deep instantiation). */
export interface DiagramCanvasContextMenuStore {
  clearSelection: () => void
  type: string | null
  addNode: (node: DiagramNode) => void
  pushHistory: (label: string) => void
  pasteNodesAt: (pos: { x: number; y: number }) => void
}

export function useDiagramCanvasContextMenu(options: {
  vueFlowWrapper: Ref<HTMLElement | null>
  getNodes: () => Array<{ id: string }>
  screenToFlowCoordinate: (pos: { x: number; y: number }) => { x: number; y: number }
  presentationRailOpen: Ref<boolean>
  emitPaneClick: () => void
  diagramStore: DiagramCanvasContextMenuStore
  t: (key: string) => string
}) {
  const {
    vueFlowWrapper,
    getNodes,
    screenToFlowCoordinate,
    presentationRailOpen,
    emitPaneClick,
    diagramStore,
    t,
  } = options

  const contextMenuVisible = ref(false)
  const contextMenuX = ref(0)
  const contextMenuY = ref(0)
  const contextMenuNode = ref<MindGraphNode | null>(null)
  const contextMenuTarget = ref<'node' | 'pane'>('pane')

  const lastPaneClickTime = ref(0)
  const lastPaneClickPosition = ref<{ x: number; y: number } | null>(null)
  const DOUBLE_CLICK_THRESHOLD_MS = 300
  const DOUBLE_CLICK_POSITION_THRESHOLD = 10

  function handlePaneClick(event?: MouseEvent) {
    const now = Date.now()
    const isDoubleClick =
      diagramStore.type === 'concept_map' &&
      event &&
      now - lastPaneClickTime.value < DOUBLE_CLICK_THRESHOLD_MS &&
      lastPaneClickPosition.value &&
      Math.abs(event.clientX - lastPaneClickPosition.value.x) < DOUBLE_CLICK_POSITION_THRESHOLD &&
      Math.abs(event.clientY - lastPaneClickPosition.value.y) < DOUBLE_CLICK_POSITION_THRESHOLD

    if (isDoubleClick && event) {
      const flowPos = screenToFlowCoordinate({
        x: event.clientX,
        y: event.clientY,
      })
      diagramStore.addNode({
        id: '',
        text: t('diagram.defaultNewConcept'),
        type: 'branch',
        position: { x: flowPos.x - 50, y: flowPos.y - 18 },
      })
      diagramStore.pushHistory('Add concept')
      lastPaneClickTime.value = 0
      lastPaneClickPosition.value = null
    } else {
      if (event) {
        lastPaneClickTime.value = now
        lastPaneClickPosition.value = {
          x: event.clientX,
          y: event.clientY,
        }
      }
      /* Selection clear, relationship + inline rec dismiss: useInlineRecommendationsCoordinator */
      eventBus.emit('canvas:pane_clicked', {})
    }
    emitPaneClick()
  }

  function handlePaneContextMenu(event: MouseEvent) {
    event.preventDefault()
    contextMenuX.value = event.clientX
    contextMenuY.value = event.clientY
    contextMenuNode.value = null
    contextMenuTarget.value = 'pane'
    contextMenuVisible.value = true
  }

  function handleNodeContextMenu(event: MouseEvent, node: MindGraphNode) {
    event.preventDefault()
    contextMenuX.value = event.clientX
    contextMenuY.value = event.clientY
    contextMenuNode.value = node
    contextMenuTarget.value = 'node'
    contextMenuVisible.value = true
  }

  function isEventPathInsideVueFlowWrapper(event: MouseEvent): boolean {
    const wrap = vueFlowWrapper.value
    if (!wrap) {
      return false
    }
    return event.composedPath().includes(wrap)
  }

  function findVueFlowNodeFromComposedPath(event: MouseEvent): Element | null {
    for (const n of event.composedPath()) {
      if (n instanceof Element && n.classList.contains('vue-flow__node')) {
        return n
      }
    }
    return null
  }

  function applyContextMenuFromEvent(mouseEvent: MouseEvent): void {
    if (!isEventPathInsideVueFlowWrapper(mouseEvent)) {
      return
    }

    const nodeElement = findVueFlowNodeFromComposedPath(mouseEvent)
    if (nodeElement) {
      const nodeId = nodeElement.getAttribute('data-id')
      if (nodeId) {
        const node = getNodes().find((n) => n.id === nodeId)
        if (node) {
          handleNodeContextMenu(mouseEvent, node as unknown as MindGraphNode)
          return
        }
      }
    }

    handlePaneContextMenu(mouseEvent)
  }

  function handleContextMenuEvent(event: Event): void {
    event.preventDefault()
    if (presentationRailOpen.value) {
      return
    }
    applyContextMenuFromEvent(event as MouseEvent)
  }

  function closeContextMenu() {
    contextMenuVisible.value = false
    contextMenuNode.value = null
  }

  function handleContextMenuPaste(position: { x: number; y: number }) {
    const flowPos = screenToFlowCoordinate({ x: position.x, y: position.y })
    diagramStore.pasteNodesAt(flowPos)
  }

  function handleContextMenuAddConcept(position: { x: number; y: number }) {
    const flowPos = screenToFlowCoordinate({ x: position.x, y: position.y })
    diagramStore.addNode({
      id: '',
      text: t('diagram.defaultNewConcept'),
      type: 'branch',
      position: { x: flowPos.x - 50, y: flowPos.y - 18 },
    })
    diagramStore.pushHistory('Add concept')
  }

  return {
    contextMenuVisible,
    contextMenuX,
    contextMenuY,
    contextMenuNode,
    contextMenuTarget,
    lastPaneClickTime,
    lastPaneClickPosition,
    handlePaneClick,
    handlePaneContextMenu,
    handleNodeContextMenu,
    handleContextMenuEvent,
    closeContextMenu,
    handleContextMenuPaste,
    handleContextMenuAddConcept,
  }
}
