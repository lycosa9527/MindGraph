import type { GraphNode } from '@vue-flow/core'

import type { BranchMoveGhostPreview } from '@/composables/editor/useBranchMoveDrag'
import type { DropTarget } from '@/composables/editor/useBranchMoveDrag'
import type { MindGraphNode } from '@/types/vueflow'

import {
  BRANCH_MOVE_NODE_HEIGHT,
  BRANCH_MOVE_NODE_WIDTH,
  TOPIC_NODE_HEIGHT,
  TOPIC_NODE_WIDTH,
} from './conceptMapLinkPreviewGeometry'

const DROP_PREVIEW_SCALE = 1.2

interface NodeWithDimensions {
  dimensions?: { width?: number; height?: number }
  measured?: { width?: number; height?: number }
  style?: { width?: number | string; height?: number | string }
}

function getTargetNodeDimensions(
  node: {
    id?: string
    style?: { width?: number | string; height?: number | string }
  } & NodeWithDimensions
): { width: number; height: number } {
  const defaultW =
    node.id === 'topic' || node.id === 'tree-topic' ? TOPIC_NODE_WIDTH : BRANCH_MOVE_NODE_WIDTH
  const defaultH =
    node.id === 'topic' || node.id === 'tree-topic' ? TOPIC_NODE_HEIGHT : BRANCH_MOVE_NODE_HEIGHT
  const w =
    node.dimensions?.width ??
    node.measured?.width ??
    (typeof node.style?.width === 'number' ? node.style.width : null) ??
    (typeof node.style?.width === 'string' ? parseFloat(node.style.width) || defaultW : defaultW)
  const h =
    node.dimensions?.height ??
    node.measured?.height ??
    (typeof node.style?.height === 'number' ? node.style.height : null) ??
    (typeof node.style?.height === 'string' ? parseFloat(node.style.height) || defaultH : defaultH)
  return { width: Number(w) || defaultW, height: Number(h) || defaultH }
}

/** Border radius for branch-move drop preview — keep in sync with diagram node components. */
export function getDropPreviewBorderRadius(node: MindGraphNode): string {
  const vfType = node.type ?? ''
  const data = node.data
  if (!data) {
    return vfType === 'circle' ? '50%' : '8px'
  }

  const { diagramType, nodeType, originalNode, style } = data
  const styleRadiusPx = style?.borderRadius != null ? `${style.borderRadius}px` : null

  if (vfType === 'concept') {
    return '9999px'
  }

  if (vfType === 'circle') {
    if (diagramType === 'double_bubble_map' && nodeType !== 'topic') {
      return '9999px'
    }
    return '50%'
  }

  const topicUsesPill =
    diagramType === 'tree_map' ||
    diagramType === 'brace_map' ||
    diagramType === 'mindmap' ||
    diagramType === 'mind_map' ||
    diagramType === 'multi_flow_map' ||
    diagramType === 'flow_map'

  if (vfType === 'topic') {
    if (topicUsesPill) {
      return '9999px'
    }
    return `${style?.borderRadius ?? 50}%`
  }

  if (vfType === 'branch') {
    if (diagramType === 'mindmap' || diagramType === 'mind_map' || diagramType === 'tree_map') {
      return '9999px'
    }
    return styleRadiusPx ?? '8px'
  }

  if (vfType === 'flow') {
    if (diagramType === 'flow_map' || diagramType === 'multi_flow_map') {
      return '9999px'
    }
    return styleRadiusPx ?? '6px'
  }

  if (vfType === 'flowSubstep') {
    if (diagramType === 'flow_map') {
      return '9999px'
    }
    return styleRadiusPx ?? '4px'
  }

  if (vfType === 'brace') {
    const isWhole = originalNode?.type === 'topic'
    if (!isWhole) {
      return '9999px'
    }
    return styleRadiusPx ?? '6px'
  }

  if (vfType === 'label') {
    return styleRadiusPx ?? '6px'
  }

  if (vfType === 'bubble') {
    return '50%'
  }

  return styleRadiusPx ?? '8px'
}

/**
 * Returns a CSS class that signals the shape of a drop-target node to the
 * `branch-move-drop-preview` overlay so CSS can apply the correct ant-line style.
 * Mirrors the logic in `getDropPreviewBorderRadius`.
 */
export function getDropTargetShapeClass(node: MindGraphNode): 'is-circle' | 'is-pill' | '' {
  const vfType = node.type ?? ''
  const data = node.data
  if (vfType === 'bubble') return 'is-circle'
  if (vfType === 'circle') {
    if (data?.diagramType === 'double_bubble_map' && data?.nodeType !== 'topic') return 'is-pill'
    return 'is-circle'
  }
  const br = getDropPreviewBorderRadius(node)
  if (br === '9999px') return 'is-pill'
  return ''
}

export function getBranchMoveGhostStyle(state: {
  cursorPos: { x: number; y: number } | null
  ghost: BranchMoveGhostPreview | null
}): Record<string, string> | null {
  if (!state.ghost || !state.cursorPos) return null
  const { width, height } = state.ghost
  return {
    position: 'absolute',
    left: `${state.cursorPos.x - width / 2}px`,
    top: `${state.cursorPos.y - height / 2}px`,
    width: `${width}px`,
    minHeight: `${height}px`,
    pointerEvents: 'none',
  }
}

export function getBranchMoveCircleStyle(state: {
  cursorPos: { x: number; y: number } | null
  nodeStartPos: { x: number; y: number; width: number; height: number } | null
  animationPhase: string
  branchColor: { fill: string; border: string }
}): Record<string, string> {
  if (!state.cursorPos) return { display: 'none' }
  const nodeStart = state.nodeStartPos
  const isShrinking = state.animationPhase === 'shrinking' && nodeStart
  const pos = isShrinking ? nodeStart : null
  const left = isShrinking && pos ? pos.x : state.cursorPos.x - 12
  const top = isShrinking && pos ? pos.y : state.cursorPos.y - 12
  const width = isShrinking && pos ? pos.width : 24
  const height = isShrinking && pos ? pos.height : 24
  const borderRadius = isShrinking ? '9999px' : '50%'
  return {
    position: 'absolute',
    left: left + 'px',
    top: top + 'px',
    width: width + 'px',
    height: height + 'px',
    borderRadius,
    backgroundColor: state.branchColor.fill,
    border: `2px solid ${state.branchColor.border}`,
    boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
    transition:
      state.animationPhase === 'shrinking'
        ? 'left 0.28s ease-out, top 0.28s ease-out, width 0.28s ease-out, height 0.28s ease-out, border-radius 0.28s ease-out'
        : 'none',
  }
}

export function getDropTargetStyle(
  getNodes: () => GraphNode[],
  target: DropTarget
): Record<string, string> {
  const nodes = getNodes()
  const node = nodes.find((n) => n.id === target.nodeId) as
    | (MindGraphNode & NodeWithDimensions)
    | undefined
  if (!node?.position) return { display: 'none' }

  const { width: nodeW, height: nodeH } = getTargetNodeDimensions(node)

  if (target.type === 'before' || target.type === 'after') {
    const y =
      target.type === 'before'
        ? node.position.y - 2
        : node.position.y + nodeH - 2
    return {
      position: 'absolute',
      left: `${node.position.x}px`,
      top: `${y}px`,
      width: `${nodeW}px`,
      height: '4px',
      borderRadius: '2px',
      background: '#2563eb',
      boxShadow: '0 0 0 2px rgb(37 99 235 / 0.25)',
      pointerEvents: 'none',
    }
  }

  const previewW = Math.round(nodeW * DROP_PREVIEW_SCALE)
  const previewH = Math.round(nodeH * DROP_PREVIEW_SCALE)
  const offsetX = (previewW - nodeW) / 2
  const offsetY = (previewH - nodeH) / 2

  const borderRadius = getDropPreviewBorderRadius(node)

  const baseStyle: Record<string, string> = {
    position: 'absolute',
    left: node.position.x - offsetX + 'px',
    top: node.position.y - offsetY + 'px',
    width: previewW + 'px',
    height: previewH + 'px',
    borderRadius,
    pointerEvents: 'none',
  }

  if (target.type === 'child') {
    baseStyle.border = '2px dashed #2563eb'
    baseStyle.background = 'rgb(37 99 235 / 0.08)'
  }

  return baseStyle
}
