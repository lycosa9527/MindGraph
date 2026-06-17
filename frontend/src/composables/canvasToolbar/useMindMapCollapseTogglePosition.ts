import { nextTick, onUnmounted, ref, watch, type Ref } from 'vue'

import { DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
import { DEFAULT_MINDMAP_RANK_SEPARATION } from '@/composables/diagrams/layoutConfig'
import { MINDMAP_UNDERLINE_STROKE_WIDTH } from '@/config/mindMapGeometry'
import { mindMapConnectionAnchorY } from '@/config/mindMapGeometry'
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import { getMindMapVisibleCollapsedNodeIds } from '@/stores/diagram/mindMapCollapse'
import { resolveNodeShape } from '@/utils/nodeShapeStyle'

/** Match `.mind-map-collapse-overlay__btn--collapse` */
const COLLAPSE_HANDLE_HALF = 9
/** Match `.mind-map-collapse-overlay__btn--expand` pill half-width */
const EXPAND_PILL_HALF = 14
const OUTWARD_GAP = 6

export type CollapseOverlayHandle = {
  nodeId: string
  mode: 'collapse' | 'expand'
  left: number
  top: number
  count?: number
  /** Screen coords — parent node connection anchor (stub line start). */
  lineStart: { left: number; top: number }
  strokeColor: string
}

function readViewport(container: HTMLElement): { x: number; y: number; zoom: number } {
  const pane = container.querySelector('.vue-flow__transformationpane') as HTMLElement | null
  if (!pane) return { x: 0, y: 0, zoom: 1 }
  const transform = getComputedStyle(pane).transform
  if (!transform || transform === 'none') return { x: 0, y: 0, zoom: 1 }
  const matrix = new DOMMatrixReadOnly(transform)
  return { x: matrix.e, y: matrix.f, zoom: matrix.a || 1 }
}

function flowToScreen(
  container: HTMLElement,
  flowX: number,
  flowY: number
): { left: number; top: number } {
  const vp = readViewport(container)
  const rect = container.getBoundingClientRect()
  return {
    left: rect.left + flowX * vp.zoom + vp.x,
    top: rect.top + flowY * vp.zoom + vp.y,
  }
}

function nodeFlowSize(
  nodeId: string,
  node: DiagramNode,
  widths: Record<string, number>,
  heights: Record<string, number>
): { w: number; h: number } {
  return {
    w: widths[nodeId] ?? (node.data?.estimatedWidth as number | undefined) ?? DEFAULT_NODE_WIDTH,
    h: heights[nodeId] ?? (node.data?.estimatedHeight as number | undefined) ?? 34,
  }
}

function resolveNodeMergedStyle(
  node: DiagramNode,
  nodeStyles?: Record<string, NodeStyle>
): NodeStyle | undefined {
  return { ...nodeStyles?.[node.id], ...node.style }
}

function nearestChildId(
  parentId: string,
  connections: Connection[],
  nodes: DiagramNode[],
  widths: Record<string, number>,
  heights: Record<string, number>,
  isLeftBranch: boolean
): string | null {
  const childIds = connections.filter((c) => c.source === parentId).map((c) => c.target)
  let bestId: string | null = null
  let bestEdge = isLeftBranch ? -Infinity : Infinity

  for (const id of childIds) {
    const node = nodes.find((n) => n.id === id)
    if (!node?.position) continue
    const { w } = nodeFlowSize(id, node, widths, heights)
    const edge = isLeftBranch ? node.position.x + w : node.position.x
    if (isLeftBranch) {
      if (edge > bestEdge) {
        bestEdge = edge
        bestId = id
      }
    } else if (edge < bestEdge) {
      bestEdge = edge
      bestId = id
    }
  }
  return bestId
}

function resolveToggleFlowPoint(
  parentId: string,
  nodes: DiagramNode[],
  connections: Connection[],
  widths: Record<string, number>,
  heights: Record<string, number>,
  nodeStyles?: Record<string, NodeStyle>
): { toggleX: number; anchorY: number; parentOutX: number } | null {
  const parent = nodes.find((n) => n.id === parentId)
  if (!parent?.position) return null

  const isLeftBranch = parentId.startsWith('branch-l-')
  const parentStyle = resolveNodeMergedStyle(parent, nodeStyles)
  const parentShape = resolveNodeShape(parentStyle, true)
  const { w: pw, h: ph } = nodeFlowSize(parentId, parent, widths, heights)
  const anchorY = mindMapConnectionAnchorY(parent.position.y, ph, parentShape)
  const parentOutX = isLeftBranch ? parent.position.x : parent.position.x + pw

  const childId = nearestChildId(
    parentId,
    connections,
    nodes,
    widths,
    heights,
    isLeftBranch
  )

  let toggleX: number
  if (childId) {
    const child = nodes.find((n) => n.id === childId)
    if (!child?.position) return null
    const { w: cw } = nodeFlowSize(childId, child, widths, heights)
    const childInX = isLeftBranch ? child.position.x + cw : child.position.x
    toggleX = (parentOutX + childInX) / 2
  } else {
    toggleX = isLeftBranch
      ? parentOutX - DEFAULT_MINDMAP_RANK_SEPARATION / 2
      : parentOutX + DEFAULT_MINDMAP_RANK_SEPARATION / 2
  }

  return { toggleX, anchorY, parentOutX }
}

function domAnchorY(container: HTMLElement, nodeId: string, rect: DOMRect): number {
  const nodeEl = container.querySelector(`.vue-flow__node[data-id="${nodeId}"]`)
  const isUnderline = nodeEl?.querySelector('.mind-map-underline-node') != null
  const lineEl = isUnderline ? nodeEl?.querySelector('.mind-map-underline-line') : null
  const lineRect = lineEl?.getBoundingClientRect()
  if (lineRect) return lineRect.top + lineRect.height / 2
  if (isUnderline) return rect.bottom - MINDMAP_UNDERLINE_STROKE_WIDTH / 2
  return rect.top + rect.height / 2
}

function resolveToggleHandle(
  container: HTMLElement,
  nodeId: string,
  nodes: DiagramNode[],
  connections: Connection[],
  widths: Record<string, number>,
  heights: Record<string, number>,
  nodeStyles: Record<string, NodeStyle> | undefined,
  strokeColor: string,
  mode: 'collapse' | 'expand',
  count?: number
): CollapseOverlayHandle | null {
  const flow = resolveToggleFlowPoint(nodeId, nodes, connections, widths, heights, nodeStyles)
  if (!flow) return null

  const isLeftBranch = nodeId.startsWith('branch-l-')
  const handleHalf = mode === 'expand' ? EXPAND_PILL_HALF : COLLAPSE_HANDLE_HALF
  const parentRect = container
    .querySelector(`.vue-flow__node[data-id="${nodeId}"]`)
    ?.getBoundingClientRect()

  let anchorTop: number
  let lineStartLeft: number
  let toggleLeft: number

  if (parentRect) {
    anchorTop = domAnchorY(container, nodeId, parentRect)
    lineStartLeft = isLeftBranch ? parentRect.left : parentRect.right

    const childId = nearestChildId(
      nodeId,
      connections,
      nodes,
      widths,
      heights,
      isLeftBranch
    )
    const childRect = childId
      ? container
          .querySelector(`.vue-flow__node[data-id="${childId}"]`)
          ?.getBoundingClientRect()
      : undefined

    if (childRect) {
      const parentEdge = isLeftBranch ? parentRect.left : parentRect.right
      const childEdge = isLeftBranch ? childRect.right : childRect.left
      toggleLeft = (parentEdge + childEdge) / 2
    } else {
      const vp = readViewport(container)
      const halfStub = (DEFAULT_MINDMAP_RANK_SEPARATION * vp.zoom) / 2
      toggleLeft = isLeftBranch
        ? parentRect.left - halfStub
        : parentRect.right + halfStub
    }

    if (isLeftBranch) {
      toggleLeft = Math.min(toggleLeft, parentRect.left - handleHalf - OUTWARD_GAP)
    } else {
      toggleLeft = Math.max(toggleLeft, parentRect.right + handleHalf + OUTWARD_GAP)
    }
  } else {
    const parentScreen = flowToScreen(container, flow.parentOutX, flow.anchorY)
    anchorTop = parentScreen.top
    lineStartLeft = parentScreen.left
    toggleLeft = flowToScreen(container, flow.toggleX, flow.anchorY).left
  }

  return {
    nodeId,
    mode,
    left: toggleLeft,
    top: anchorTop,
    count,
    lineStart: { left: lineStartLeft, top: anchorTop },
    strokeColor,
  }
}

export function useMindMapCollapseOverlayPositions(options: {
  containerRef: Ref<HTMLElement | null>
  selectedNodeId: Ref<string | null>
  collapsedPaths: Ref<string[]>
  nodes: Ref<DiagramNode[] | undefined>
  connections: Ref<Connection[] | undefined>
  nodeWidths: Ref<Record<string, number>>
  nodeHeights: Ref<Record<string, number>>
  nodeStyles: Ref<Record<string, NodeStyle> | undefined>
  strokeColor: Ref<string>
  enabled: Ref<boolean>
  editingNodeId: Ref<string | null>
  getDescendantCount: (nodeId: string) => number
  getDescendantIds: (rootId: string) => Set<string>
}) {
  const handles = ref<CollapseOverlayHandle[]>([])
  const visible = ref(false)

  let rafId = 0

  function measure(): void {
    const container = options.containerRef.value
    const connections = options.connections.value
    const nodes = options.nodes.value
    if (!options.enabled.value || !container || !connections?.length || !nodes?.length) {
      handles.value = []
      visible.value = false
      return
    }

    const widths = options.nodeWidths.value
    const heights = options.nodeHeights.value
    const styles = options.nodeStyles.value
    const stroke = options.strokeColor.value
    const next: CollapseOverlayHandle[] = []
    const collapsedNodeIds = getMindMapVisibleCollapsedNodeIds(
      nodes,
      connections,
      options.collapsedPaths.value,
      options.getDescendantIds
    )
    const selectedId = options.selectedNodeId.value
    const editingId = options.editingNodeId.value

    for (const nodeId of collapsedNodeIds) {
      if (editingId === nodeId) continue
      const count = options.getDescendantCount(nodeId)
      if (count <= 0) continue
      const handle = resolveToggleHandle(
        container,
        nodeId,
        nodes,
        connections,
        widths,
        heights,
        styles,
        stroke,
        'expand',
        count
      )
      if (handle) next.push(handle)
    }

    if (
      selectedId &&
      selectedId !== 'topic' &&
      editingId !== selectedId &&
      !collapsedNodeIds.has(selectedId) &&
      connections.some((c) => c.source === selectedId)
    ) {
      const handle = resolveToggleHandle(
        container,
        selectedId,
        nodes,
        connections,
        widths,
        heights,
        styles,
        stroke,
        'collapse'
      )
      if (handle) next.push(handle)
    }

    handles.value = next
    visible.value = next.length > 0
  }

  function scheduleMeasure(): void {
    cancelAnimationFrame(rafId)
    rafId = requestAnimationFrame(() => {
      void nextTick(measure)
    })
  }

  watch(
    () =>
      [
        options.selectedNodeId.value,
        options.enabled.value,
        options.collapsedPaths.value.join('|'),
        options.nodes.value?.length,
        options.editingNodeId.value,
        options.strokeColor.value,
      ] as const,
    scheduleMeasure,
    { immediate: true }
  )

  onUnmounted(() => {
    cancelAnimationFrame(rafId)
  })

  return {
    handles,
    visible,
    scheduleMeasure,
  }
}
