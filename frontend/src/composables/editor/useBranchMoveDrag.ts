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
import {
  getDropPreviewBorderRadius,
  getDropTargetShapeClass,
} from '@/composables/diagramCanvas/diagramCanvasZoomPaneStyles'
import { isLearningSheetCustomPickActive } from '@/composables/mindMap/useLearningSheetCustomMode'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import { mindMapBranchFontSize, resolveMindMapTopicBorderColor } from '@/config/mindMapGeometry'
import { getMindMapThemeForDiagram } from '@/config/mindMapThemes'
import { ANIMATION } from '@/config/uiConfig'
import { useDiagramStore } from '@/stores'
import type { MindGraphNode } from '@/types'
import { readMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'
import { resolveNodeShape } from '@/utils/nodeShapeStyle'

const DEFAULT_NODE_WIDTH = 120
const DEFAULT_NODE_HEIGHT = 50
const LONG_PRESS_MOVE_THRESHOLD_SQ = 15 * 15
/** Start branch drag after this movement (px) — no need to wait for long-press. */
const DRAG_START_THRESHOLD_SQ = 8 * 8

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
  type: 'topic' | 'child' | 'before' | 'after'
  nodeId: string
}

export interface BranchMoveGhostPreview {
  label: string
  width: number
  height: number
  backgroundColor: string
  textColor: string
  borderColor: string
  fontSize: string
  fontWeight: string
  borderRadius: string
  shapeClass: string
  variant: 'standard' | 'underline'
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
  draggedGhost: BranchMoveGhostPreview | null
}

export function useBranchMoveDrag(options?: { allowNodeMove?: () => boolean }) {
  const diagramStore = useDiagramStore()
  const { screenToFlowCoordinate, getNodes, getViewport } = useVueFlow()

  const pendingNodeId = ref<string | null>(null)
  const longPressNodeId = ref<string | null>(null)
  const longPressTimer = ref<ReturnType<typeof setTimeout> | null>(null)
  const cursorPos = ref<{ x: number; y: number } | null>(null)
  const lastMouseDownPos = ref<{ clientX: number; clientY: number } | null>(null)
  const dropTarget = ref<DropTarget | null>(null)
  const capturedBranchColor = ref<{ fill: string; border: string }>(getMindmapBranchColor(0))
  const nodeStartPos = ref<{ x: number; y: number; width: number; height: number } | null>(null)
  const animationPhase = ref<'shrinking' | 'following'>('shrinking')
  const draggedGhost = ref<BranchMoveGhostPreview | null>(null)

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
    draggedGhost: draggedGhost.value,
  }))

  function resolveDiagramType(node?: MindGraphNode): string {
    return (
      node?.data?.diagramType ??
      diagramStore.type ??
      diagramStore.data?.type ??
      ''
    )
  }

  function isMindMapBranchNode(nodeId: string, node?: MindGraphNode): boolean {
    const dt = resolveDiagramType(node)
    if (dt !== 'mindmap' && dt !== 'mind_map') return false
    return nodeId.startsWith('branch-') || node?.type === 'branch'
  }

  function getNodeDimensions(node: MindGraphNode, nodeId?: string): { w: number; h: number } {
    const id = nodeId ?? node.id ?? ''
    const cached = id ? diagramStore.nodeDimensions[id] : undefined
    if (cached?.width && cached?.height) {
      return { w: cached.width, h: cached.height }
    }

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

  function readGhostFromDom(nodeId: string): BranchMoveGhostPreview | null {
    const nodeEl = document.querySelector(
      `.vue-flow__node[data-id="${CSS.escape(nodeId)}"]`
    ) as HTMLElement | null
    const branchEl = nodeEl?.querySelector(
      '.branch-node, .mind-map-node, .mind-map-legacy-node'
    ) as HTMLElement | null
    if (!branchEl) return null

    const zoom = getViewport().zoom || 1
    const rect = branchEl.getBoundingClientRect()
    if (rect.width <= 0 || rect.height <= 0) return null

    const cs = getComputedStyle(branchEl)
    const labelEl = branchEl.querySelector(
      '.inline-edit-display, .mind-map-underline-text .inline-edit-display'
    )
    const label = (labelEl?.textContent ?? '').trim() || '…'
    const isUnderline = branchEl.classList.contains('mind-map-underline-node')

    return {
      label,
      width: Math.max(rect.width / zoom, DEFAULT_NODE_WIDTH),
      height: Math.max(rect.height / zoom, DEFAULT_NODE_HEIGHT),
      backgroundColor: cs.backgroundColor,
      textColor: cs.color,
      borderColor: cs.borderColor,
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      borderRadius: cs.borderRadius,
      shapeClass: isUnderline ? '' : 'is-pill',
      variant: isUnderline ? 'underline' : 'standard',
    }
  }

  function buildDraggedGhost(
    nodeId: string,
    node: MindGraphNode | undefined
  ): BranchMoveGhostPreview | null {
    if (!node) return readGhostFromDom(nodeId)
    if (!isMindMapBranchNode(nodeId, node)) return null

    const storeNode = diagramStore.data?.nodes.find((n) => n.id === nodeId)
    const persistedStyle = (diagramStore.data?._node_styles?.[nodeId] ?? {}) as Record<
      string,
      unknown
    >
    const label = String(node.data?.label ?? storeNode?.text ?? '').trim() || '…'
    const { w, h } = getNodeDimensions(node, nodeId)
    const dataStyle = {
      ...persistedStyle,
      ...(storeNode?.style ?? {}),
      ...(node.data?.style ?? {}),
    } as Record<string, unknown>
    const vueStyle =
      typeof node.style === 'object' && node.style !== null
        ? (node.style as Record<string, unknown>)
        : {}

    const theme = getMindMapThemeForDiagram(diagramStore.data)
    const v2Visuals = readMindMapV2VisualDesignActive()
    const branchIndex = (node.data?.branchIndex as number | undefined) ?? 0
    const branchPalette = getMindmapBranchColor(branchIndex, v2Visuals ? undefined : 'legacy')
    const nodeShape = v2Visuals ? resolveNodeShape(dataStyle as never, true) : 'oval'
    const isUnderline = v2Visuals && nodeShape === 'underline'
    const fontSizePx = dataStyle.fontSize ?? (v2Visuals ? mindMapBranchFontSize(nodeId) : 16)
    const fontSize =
      typeof fontSizePx === 'number' ? `${fontSizePx}px` : String(fontSizePx ?? '16px')

    const ghost: BranchMoveGhostPreview = {
      label,
      width: Math.max(w, DEFAULT_NODE_WIDTH),
      height: Math.max(h, DEFAULT_NODE_HEIGHT),
      backgroundColor: String(
        dataStyle.backgroundColor ??
          vueStyle.backgroundColor ??
          (isUnderline ? 'transparent' : v2Visuals ? theme.backgroundColor : branchPalette.fill)
      ),
      textColor: String(dataStyle.textColor ?? vueStyle.color ?? (v2Visuals ? theme.textColor : '#333333')),
      borderColor: String(
        dataStyle.borderColor ??
          vueStyle.borderColor ??
          (v2Visuals
            ? resolveMindMapTopicBorderColor(null) ?? theme.borderColor
            : branchPalette.border)
      ),
      fontSize,
      fontWeight: String(dataStyle.fontWeight ?? vueStyle.fontWeight ?? 'normal'),
      borderRadius: isUnderline ? '0px' : getDropPreviewBorderRadius(node as MindGraphNode),
      shapeClass: getDropTargetShapeClass(node as MindGraphNode),
      variant: isUnderline ? 'underline' : 'standard',
    }

    return ghost
  }

  function classifyBranchDrop(
    node: MindGraphNode,
    flowX: number,
    flowY: number
  ): DropTarget | null {
    const pos = node.position ?? { x: 0, y: 0 }
    const { w: nodeW, h: nodeH } = getNodeDimensions(node)
    if (flowX < pos.x || flowX > pos.x + nodeW || flowY < pos.y || flowY > pos.y + nodeH) {
      return null
    }
    const relY = flowY - pos.y
    const topZone = nodeH * 0.28
    const bottomZone = nodeH * 0.72
    const nodeId = node.id ?? ''
    if (relY < topZone) return { type: 'before', nodeId }
    if (relY > bottomZone) return { type: 'after', nodeId }
    return { type: 'child', nodeId }
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
    const draggedId = pendingNodeId.value
    let best: DropTarget | null = null
    let bestArea = Infinity
    for (const node of nodes) {
      const nid = node.id ?? ''
      if (nid === topicId || !branchPattern.test(nid)) continue
      if (h.has(nid) || nid === draggedId) continue
      const hit = classifyBranchDrop(node, flowX, flowY)
      if (!hit) continue
      const pos = node.position ?? { x: 0, y: 0 }
      const { w: nodeW, h: nodeH } = getNodeDimensions(node)
      const area = nodeW * nodeH
      if (area < bestArea) {
        bestArea = area
        best = hit
      }
    }
    return best
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
    document.removeEventListener('mousemove', handlePreDragMouseMove, captureOpt)
    document.documentElement.removeEventListener('mouseleave', handleMouseLeave)
    document.removeEventListener('keydown', handleEscape)
  }

  function cleanup(): void {
    clearTimer()
    pendingNodeId.value = null
    longPressNodeId.value = null
    cursorPos.value = null
    dropTarget.value = null
    nodeStartPos.value = null
    animationPhase.value = 'shrinking'
    draggedGhost.value = null
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
      } else if (target.type === 'before' || target.type === 'after') {
        diagramStore.moveTreeMapBranch(nodeId, 'sibling', target.nodeId)
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
      } else if (target.type === 'before') {
        diagramStore.moveMindMapBranch(nodeId, 'before', target.nodeId)
      } else if (target.type === 'after') {
        diagramStore.moveMindMapBranch(nodeId, 'after', target.nodeId)
      } else if (target.type === 'child') {
        diagramStore.moveMindMapBranch(nodeId, 'child', target.nodeId)
      }
    }
  }

  // ---- Desktop: mouse handlers ----

  function attachActiveDragListeners(): void {
    document.removeEventListener('mouseup', handleCancelTimer, captureOpt)
    document.removeEventListener('touchend', handleCancelTimer, captureOpt)
    document.removeEventListener('touchmove', handleCancelTouchMove, captureOpt)
    document.removeEventListener('mousemove', handlePreDragMouseMove, captureOpt)

    document.addEventListener('mouseup', handleDocumentMouseUp, captureOpt)
    document.addEventListener('mousemove', handleDocumentMouseMove, captureOpt)
    if (touchOrigin) {
      document.addEventListener('touchmove', handleDocumentTouchMove, captureOpt)
      document.addEventListener('touchend', handleDocumentTouchEnd, captureOpt)
    }
    document.documentElement.addEventListener('mouseleave', handleMouseLeave)
    document.addEventListener('keydown', handleEscape)
  }

  function beginDragForNode(nodeId: string): void {
    clearTimer()
    activateDragMode(nodeId)
    attachActiveDragListeners()
  }

  function handlePreDragMouseMove(e: MouseEvent): void {
    if (!longPressTimer.value || !longPressNodeId.value || !lastMouseDownPos.value) return
    const dx = e.clientX - lastMouseDownPos.value.clientX
    const dy = e.clientY - lastMouseDownPos.value.clientY
    if (dx * dx + dy * dy < DRAG_START_THRESHOLD_SQ) return
    beginDragForNode(longPressNodeId.value)
    handleDocumentMouseMove(e)
  }

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
      const dt = diagramStore.type ?? ''
      if (usesHierarchicalMove(dt)) {
        handleDropHierarchical(nodeId, target)
      } else {
        diagramStore.moveNodeBySwap(nodeId, target.nodeId)
      }
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
    const idx =
      (node?.data?.branchIndex as number) ??
      (node?.data?.groupIndex as number) ??
      (node?.data?.pairIndex as number) ??
      0
    const diagramType = node?.data?.diagramType as string | undefined
    const isMindMapNode = diagramType === 'mindmap' || diagramType === 'mind_map'
    const paletteMode =
      isMindMapNode && !readMindMapV2VisualDesignActive() ? ('legacy' as const) : undefined
    capturedBranchColor.value = getMindmapBranchColor(idx, paletteMode)
    const pos = node?.position ?? { x: 0, y: 0 }
    const { w, h } = node
      ? getNodeDimensions(node, nodeId)
      : { w: DEFAULT_NODE_WIDTH, h: DEFAULT_NODE_HEIGHT }
    nodeStartPos.value = { x: pos.x, y: pos.y, width: w, height: h }
    draggedGhost.value = buildDraggedGhost(nodeId, node) ?? readGhostFromDom(nodeId)
    pendingNodeId.value = nodeId
    animationPhase.value = draggedGhost.value ? 'following' : 'shrinking'
    const lastPos = lastMouseDownPos.value
    const flowPos =
      lastPos !== null
        ? screenToFlowCoordinate({ x: lastPos.clientX, y: lastPos.clientY })
        : { x: pos.x + w / 2, y: pos.y + h / 2 }
    cursorPos.value = { x: flowPos.x, y: flowPos.y }
    if (!draggedGhost.value) {
      setTimeout(() => {
        animationPhase.value = 'following'
      }, 280)
    }
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
    if (isLearningSheetCustomPickActive()) return false
    if (options?.allowNodeMove && !options.allowNodeMove()) return false
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
    longPressNodeId.value = nodeId
    longPressTimer.value = setTimeout(() => {
      longPressTimer.value = null
      if (longPressNodeId.value) {
        beginDragForNode(longPressNodeId.value)
      }
    }, ANIMATION.LONG_PRESS_MS)

    document.addEventListener('mouseup', handleCancelTimer, captureOpt)
    if (!fromTouch) {
      document.addEventListener('mousemove', handlePreDragMouseMove, captureOpt)
    }
    if (fromTouch) {
      document.addEventListener('touchend', handleCancelTimer, captureOpt)
      document.addEventListener('touchmove', handleCancelTouchMove, captureOpt)
    }
    return false
  }

  function handleCancelTimer(): void {
    if (longPressTimer.value) {
      clearTimer()
      longPressNodeId.value = null
      lastMouseDownPos.value = null
      touchOrigin = false
      document.removeEventListener('mouseup', handleCancelTimer, captureOpt)
      document.removeEventListener('touchend', handleCancelTimer, captureOpt)
      document.removeEventListener('touchmove', handleCancelTouchMove, captureOpt)
      document.removeEventListener('mousemove', handlePreDragMouseMove, captureOpt)
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
