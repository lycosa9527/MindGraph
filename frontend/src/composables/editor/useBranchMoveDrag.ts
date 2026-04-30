/**
 * useBranchMoveDrag - Long-press drag-and-drop for moving/swapping nodes
 * across all thinking map types.
 *
 * Desktop flow:
 *   mousedown 1.5 s → enter drag mode → hide node (+ paired/child nodes) →
 *   circle follows cursor → show drop preview → mouseup to confirm or cancel
 *
 * Mobile flow (tap-to-confirm):
 *   touchstart 1.5 s → enter drag mode → circle follows finger →
 *   lift finger (no target) → stays active → next tap on another node confirms
 *
 * Mindmap & tree_map use moveMindMapBranch / moveTreeMapBranch (hierarchical).
 * All other diagram types use moveNodeBySwap (position swap).
 * Bridge map and double bubble map diff nodes move as pairs.
 */
import { computed, onUnmounted, ref } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { DEFAULT_CENTER_X } from '@/composables/diagrams/layoutConfig'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import { ANIMATION } from '@/config/uiConfig'
import { useDiagramStore } from '@/stores'
import type { MindGraphNode } from '@/types'

const DEFAULT_NODE_WIDTH = 120
const DEFAULT_NODE_HEIGHT = 50
const LONG_PRESS_MOVE_THRESHOLD_SQ = 15 * 15

/** Top-level branches are depth 1 (branch-r-1-X or branch-l-1-X). */
function isTopLevelBranch(nodeId: string): boolean {
  return /^branch-(r|l)-1-\d+$/.test(nodeId)
}

/** Tree map: categories (tree-cat-X) are top-level. */
function isTopLevelTreeMapNode(nodeId: string): boolean {
  return /^tree-cat-\d+$/.test(nodeId)
}

/**
 * Classify a node into a swap group. Nodes in the same group can be swapped.
 * Returns null if the node is not draggable (e.g. topic nodes).
 */
function getSwapGroup(diagramType: string, nodeId: string): string | null {
  switch (diagramType) {
    case 'mindmap':
    case 'mind_map':
      return nodeId.startsWith('branch-') ? 'branch' : null
    case 'tree_map':
      if (nodeId.startsWith('tree-cat-') || nodeId.startsWith('tree-leaf-')) return 'tree-node'
      return null
    case 'bubble_map':
      return nodeId.startsWith('bubble-') ? 'bubble' : null
    case 'circle_map':
      return nodeId.startsWith('context-') ? 'context' : null
    case 'double_bubble_map':
      if (nodeId.startsWith('similarity-')) return 'similarity'
      if (nodeId.startsWith('left-diff-') || nodeId.startsWith('right-diff-')) return 'diff'
      return null
    case 'flow_map':
      if (nodeId.startsWith('flow-step-') || nodeId.startsWith('flow-substep-')) return 'flow-node'
      return null
    case 'multi_flow_map':
      if (nodeId.startsWith('cause-')) return 'cause'
      if (nodeId.startsWith('effect-')) return 'effect'
      return null
    case 'brace_map':
      if (nodeId.startsWith('label-') || nodeId.startsWith('dimension-')) return null
      return 'brace'
    case 'bridge_map':
      return nodeId.startsWith('pair-') ? 'pair' : null
    default:
      return null
  }
}

/** Whether the diagram type uses hierarchical move (vs simple swap). */
function usesHierarchicalMove(diagramType: string): boolean {
  return diagramType === 'mindmap' || diagramType === 'mind_map' || diagramType === 'tree_map'
}

/** Get the topic node ID for hierarchical-move diagram types. */
function getTopicId(diagramType: string): string {
  if (diagramType === 'tree_map') return 'tree-topic'
  return 'topic'
}

export interface DropTarget {
  type: 'topic' | 'child'
  nodeId: string
  index?: number
}

export interface BranchMoveState {
  active: boolean
  draggedNodeId: string | null
  cursorPos: { x: number; y: number } | null
  dropTarget: DropTarget | null
  hiddenIds: Set<string>
  branchColor: { fill: string; border: string }
  nodeStartPos: { x: number; y: number; width: number; height: number } | null
  animationPhase: 'shrinking' | 'following'
}

export function useBranchMoveDrag() {
  const diagramStore = useDiagramStore()
  const { screenToFlowCoordinate, getNodes } = useVueFlow()

  const pendingNodeId = ref<string | null>(null)
  const longPressTimer = ref<ReturnType<typeof setTimeout> | null>(null)
  const cursorPos = ref<{ x: number; y: number } | null>(null)
  const lastMouseDownPos = ref<{ clientX: number; clientY: number } | null>(null)
  const dropTarget = ref<DropTarget | null>(null)
  const capturedBranchColor = ref<{ fill: string; border: string }>(getMindmapBranchColor(0))
  const nodeStartPos = ref<{ x: number; y: number; width: number; height: number } | null>(null)
  const animationPhase = ref<'shrinking' | 'following'>('shrinking')

  let touchOrigin = false
  let awaitingTapConfirm = false

  const active = computed(() => pendingNodeId.value !== null)

  const hiddenIds = computed(() => {
    const id = pendingNodeId.value
    if (!id) return new Set<string>()
    return diagramStore.getNodeGroupIds(id)
  })

  const branchColor = computed(() => capturedBranchColor.value)

  const state = computed<BranchMoveState>(() => ({
    active: active.value,
    draggedNodeId: pendingNodeId.value,
    cursorPos: cursorPos.value,
    dropTarget: dropTarget.value,
    hiddenIds: hiddenIds.value,
    branchColor: branchColor.value,
    nodeStartPos: nodeStartPos.value,
    animationPhase: animationPhase.value,
  }))

  function getNodeDimensions(node: MindGraphNode): { w: number; h: number } {
    const graphNode = node as MindGraphNode & { dimensions?: { width: number; height: number } }
    const dims = graphNode.dimensions
    if (dims?.width && dims?.height) return { w: dims.width, h: dims.height }
    const style =
      typeof node.style === 'object' && node.style !== null
        ? (node.style as Record<string, unknown>)
        : undefined
    const styleW = style?.width as number | undefined
    const styleH = style?.height as number | undefined
    const dataSize = node.data?.style?.size as number | undefined
    if (dataSize) return { w: dataSize, h: dataSize }
    return { w: styleW ?? DEFAULT_NODE_WIDTH, h: styleH ?? DEFAULT_NODE_HEIGHT }
  }

  function hitTestHierarchical(
    nodes: MindGraphNode[],
    flowX: number,
    flowY: number
  ): DropTarget | null {
    const dt = diagramStore.type ?? ''
    const isTreeMap = dt === 'tree_map'
    const topicId = getTopicId(dt)
    const topic = nodes.find((n) => n.id === topicId)
    if (topic?.position) {
      const { w, h } = getNodeDimensions(topic)
      if (
        flowX >= topic.position.x &&
        flowX <= topic.position.x + w &&
        flowY >= topic.position.y &&
        flowY <= topic.position.y + h
      ) {
        return { type: 'topic', nodeId: topicId }
      }
    }
    const branchPattern = isTreeMap ? /^tree-(cat|leaf)-/ : /^branch-/
    const h = hiddenIds.value
    for (const node of nodes) {
      if (node.id === topicId || !branchPattern.test(node.id ?? '')) continue
      if (h.has(node.id ?? '')) continue
      const pos = node.position ?? { x: 0, y: 0 }
      const { w: nodeW, h: nodeH } = getNodeDimensions(node)
      if (flowX >= pos.x && flowX <= pos.x + nodeW && flowY >= pos.y && flowY <= pos.y + nodeH) {
        return { type: 'child', nodeId: node.id ?? '' }
      }
    }
    return null
  }

  function hitTestSwap(nodes: MindGraphNode[], flowX: number, flowY: number): DropTarget | null {
    const dt = diagramStore.type ?? ''
    const draggedId = pendingNodeId.value
    if (!draggedId) return null
    const dragGroup = getSwapGroup(dt, draggedId)
    if (!dragGroup) return null
    const h = hiddenIds.value
    for (const node of nodes) {
      const nid = node.id ?? ''
      if (h.has(nid)) continue
      if (getSwapGroup(dt, nid) !== dragGroup) continue
      if (dt === 'brace_map' && node.data?.originalNode?.type === 'topic') continue
      const pos = node.position ?? { x: 0, y: 0 }
      const { w, h: nodeH } = getNodeDimensions(node)
      if (flowX >= pos.x && flowX <= pos.x + w && flowY >= pos.y && flowY <= pos.y + nodeH) {
        return { type: 'child', nodeId: nid }
      }
    }
    return null
  }

  function hitTest(flowX: number, flowY: number): DropTarget | null {
    const nodes = getNodes.value as MindGraphNode[]
    const dt = diagramStore.type ?? ''
    if (usesHierarchicalMove(dt)) {
      return hitTestHierarchical(nodes, flowX, flowY)
    }
    return hitTestSwap(nodes, flowX, flowY)
  }

  function clearTimer(): void {
    if (longPressTimer.value) {
      clearTimeout(longPressTimer.value)
      longPressTimer.value = null
    }
  }

  const captureOpt = { capture: true }

  function removeAllListeners(): void {
    document.removeEventListener('mouseup', handleDocumentMouseUp, captureOpt)
    document.removeEventListener('mousemove', handleDocumentMouseMove, captureOpt)
    document.removeEventListener('touchmove', handleDocumentTouchMove, captureOpt)
    document.removeEventListener('touchend', handleDocumentTouchEnd, captureOpt)
    document.removeEventListener('mouseup', handleCancelTimer, captureOpt)
    document.removeEventListener('touchend', handleCancelTimer, captureOpt)
    document.removeEventListener('touchmove', handleCancelTouchMove, captureOpt)
    document.documentElement.removeEventListener('mouseleave', handleMouseLeave)
    document.removeEventListener('keydown', handleEscape)
  }

  function cleanup(): void {
    clearTimer()
    pendingNodeId.value = null
    cursorPos.value = null
    dropTarget.value = null
    nodeStartPos.value = null
    animationPhase.value = 'shrinking'
    lastMouseDownPos.value = null
    touchOrigin = false
    awaitingTapConfirm = false
    removeAllListeners()
  }

  function executeDrop(draggedId: string, targetNodeId: string): void {
    const dt = diagramStore.type ?? ''
    if (usesHierarchicalMove(dt)) {
      handleDropHierarchical(draggedId, { type: 'child', nodeId: targetNodeId })
    } else {
      diagramStore.moveNodeBySwap(draggedId, targetNodeId)
    }
  }

  function handleDropHierarchical(nodeId: string, target: DropTarget): void {
    const dt = diagramStore.type ?? ''
    const isTreeMap = dt === 'tree_map'
    if (isTreeMap) {
      if (target.type === 'topic') {
        diagramStore.moveTreeMapBranch(nodeId, 'topic', target.nodeId)
      } else if (isTopLevelTreeMapNode(nodeId)) {
        diagramStore.moveTreeMapBranch(nodeId, 'sibling', target.nodeId)
      } else if (isTopLevelTreeMapNode(target.nodeId)) {
        diagramStore.moveTreeMapBranch(nodeId, 'child', target.nodeId)
      } else {
        diagramStore.moveTreeMapBranch(nodeId, 'sibling', target.nodeId)
      }
    } else {
      if (target.type === 'topic') {
        const flowX = cursorPos.value?.x ?? DEFAULT_CENTER_X + 1
        diagramStore.moveMindMapBranch(nodeId, 'topic', undefined, undefined, flowX)
      } else if (isTopLevelBranch(nodeId)) {
        diagramStore.moveMindMapBranch(nodeId, 'sibling', target.nodeId)
      } else {
        diagramStore.moveMindMapBranch(nodeId, 'child', target.nodeId)
      }
    }
  }

  // ---- Desktop: mouse handlers ----

  function handleDocumentMouseUp(): void {
    const target = dropTarget.value
    const nodeId = pendingNodeId.value
    if (!nodeId) return

    if (target && target.nodeId !== nodeId) {
      const dt = diagramStore.type ?? ''
      if (usesHierarchicalMove(dt)) {
        handleDropHierarchical(nodeId, target)
      } else {
        diagramStore.moveNodeBySwap(nodeId, target.nodeId)
      }
    }
    cleanup()
  }

  function handleDocumentMouseMove(e: MouseEvent): void {
    const flow = screenToFlowCoordinate({ x: e.clientX, y: e.clientY })
    cursorPos.value = { x: flow.x, y: flow.y }
    dropTarget.value = hitTest(flow.x, flow.y)
  }

  function handleMouseLeave(): void {
    cleanup()
  }

  function handleEscape(e: KeyboardEvent): void {
    if (e.key === 'Escape') cleanup()
  }

  // ---- Mobile: touch handlers ----

  function handleDocumentTouchMove(e: TouchEvent): void {
    if (e.touches.length !== 1) return
    const touch = e.touches[0]
    const flow = screenToFlowCoordinate({ x: touch.clientX, y: touch.clientY })
    cursorPos.value = { x: flow.x, y: flow.y }
    dropTarget.value = hitTest(flow.x, flow.y)
  }

  function handleDocumentTouchEnd(): void {
    const target = dropTarget.value
    const nodeId = pendingNodeId.value
    if (!nodeId) return

    if (target && target.nodeId !== nodeId) {
      executeDrop(nodeId, target.nodeId)
      cleanup()
      return
    }

    awaitingTapConfirm = true
    removeAllListeners()
    document.addEventListener('keydown', handleEscape)
  }

  function handleCancelTouchMove(e: TouchEvent): void {
    if (!longPressTimer.value || !lastMouseDownPos.value) return
    if (e.touches.length !== 1) return
    const touch = e.touches[0]
    const dx = touch.clientX - lastMouseDownPos.value.clientX
    const dy = touch.clientY - lastMouseDownPos.value.clientY
    if (dx * dx + dy * dy > LONG_PRESS_MOVE_THRESHOLD_SQ) {
      handleCancelTimer()
    }
  }

  // ---- Activation (shared by mouse & touch) ----

  function activateDragMode(nodeId: string): void {
    const vfNodes = getNodes.value as MindGraphNode[]
    const node = vfNodes.find((n) => n.id === nodeId)
    pendingNodeId.value = nodeId
    const idx =
      (node?.data?.branchIndex as number) ??
      (node?.data?.groupIndex as number) ??
      (node?.data?.pairIndex as number) ??
      0
    capturedBranchColor.value = getMindmapBranchColor(idx)
    const pos = node?.position ?? { x: 0, y: 0 }
    const { w, h } = node
      ? getNodeDimensions(node)
      : { w: DEFAULT_NODE_WIDTH, h: DEFAULT_NODE_HEIGHT }
    nodeStartPos.value = { x: pos.x, y: pos.y, width: w, height: h }
    animationPhase.value = 'shrinking'
    const lastPos = lastMouseDownPos.value
    const flowPos =
      lastPos !== null
        ? screenToFlowCoordinate({ x: lastPos.clientX, y: lastPos.clientY })
        : { x: pos.x + w / 2, y: pos.y + h / 2 }
    cursorPos.value = { x: flowPos.x, y: flowPos.y }
    setTimeout(() => {
      animationPhase.value = 'following'
    }, 280)
  }

  /**
   * Called by node components on mousedown/touchstart.
   * Returns true if the event was consumed (tap-to-confirm or cancel).
   */
  function onBranchMovePointerDown(
    nodeId: string,
    isEditing: boolean,
    clientX?: number,
    clientY?: number,
    fromTouch?: boolean
  ): boolean {
    const dt = diagramStore.type
    if (!dt) return false
    if (isEditing) return false

    if (active.value && pendingNodeId.value) {
      const draggedId = pendingNodeId.value
      if (nodeId !== draggedId && getSwapGroup(dt, nodeId)) {
        executeDrop(draggedId, nodeId)
      }
      cleanup()
      return true
    }

    if (!getSwapGroup(dt, nodeId)) return false
    if (dt === 'brace_map') {
      const node = diagramStore.data?.nodes.find((n) => n.id === nodeId)
      if (node?.type === 'topic') return false
    }

    clearTimer()
    touchOrigin = !!fromTouch
    if (clientX !== undefined && clientY !== undefined) {
      lastMouseDownPos.value = { clientX, clientY }
    }
    longPressTimer.value = setTimeout(() => {
      longPressTimer.value = null
      activateDragMode(nodeId)

      document.removeEventListener('mouseup', handleCancelTimer, captureOpt)
      document.removeEventListener('touchend', handleCancelTimer, captureOpt)
      document.removeEventListener('touchmove', handleCancelTouchMove, captureOpt)

      document.addEventListener('mouseup', handleDocumentMouseUp, captureOpt)
      document.addEventListener('mousemove', handleDocumentMouseMove, captureOpt)
      if (touchOrigin) {
        document.addEventListener('touchmove', handleDocumentTouchMove, captureOpt)
        document.addEventListener('touchend', handleDocumentTouchEnd, captureOpt)
      }
      document.documentElement.addEventListener('mouseleave', handleMouseLeave)
      document.addEventListener('keydown', handleEscape)
    }, ANIMATION.LONG_PRESS_MS)

    document.addEventListener('mouseup', handleCancelTimer, captureOpt)
    if (fromTouch) {
      document.addEventListener('touchend', handleCancelTimer, captureOpt)
      document.addEventListener('touchmove', handleCancelTouchMove, captureOpt)
    }
    return false
  }

  function handleCancelTimer(): void {
    if (longPressTimer.value) {
      clearTimer()
      pendingNodeId.value = null
      lastMouseDownPos.value = null
      touchOrigin = false
      document.removeEventListener('mouseup', handleCancelTimer, captureOpt)
      document.removeEventListener('touchend', handleCancelTimer, captureOpt)
      document.removeEventListener('touchmove', handleCancelTouchMove, captureOpt)
    }
  }

  function onBranchMovePointerUp(): void {
    if (longPressTimer.value) {
      document.removeEventListener('mouseup', handleCancelTimer, captureOpt)
    }
  }

  function cancelDrag(): void {
    if (active.value) {
      cleanup()
    }
  }

  onUnmounted(cleanup)

  return {
    state,
    onBranchMovePointerDown,
    onBranchMovePointerUp,
    cancelDrag,
    awaitingTapConfirm: computed(() => awaitingTapConfirm),
  }
}
