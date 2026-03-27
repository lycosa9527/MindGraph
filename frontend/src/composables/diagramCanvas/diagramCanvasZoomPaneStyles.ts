import type { GraphNode } from '@vue-flow/core'

import type { DropTarget } from '@/composables/editor/useBranchMoveDrag'

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
    | ({ position?: { x: number; y: number } } & NodeWithDimensions)
    | undefined
  if (!node?.position) return { display: 'none' }

  const { width: nodeW, height: nodeH } = getTargetNodeDimensions(node)
  const previewW = Math.round(nodeW * DROP_PREVIEW_SCALE)
  const previewH = Math.round(nodeH * DROP_PREVIEW_SCALE)
  const offsetX = (previewW - nodeW) / 2
  const offsetY = (previewH - nodeH) / 2

  return {
    position: 'absolute',
    left: node.position.x - offsetX + 'px',
    top: node.position.y - offsetY + 'px',
    width: previewW + 'px',
    height: previewH + 'px',
    border: '2px dashed #3b82f6',
    borderRadius: '9999px',
    backgroundColor: 'rgba(59, 130, 246, 0.1)',
    pointerEvents: 'none',
  }
}
