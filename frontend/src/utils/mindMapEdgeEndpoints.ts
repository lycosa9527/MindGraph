import {
  MIND_MAP_GEOMETRY,
  MINDMAP_UNDERLINE_STROKE_WIDTH,
  mindMapConnectionAnchorY,
} from '@/config/mindMapGeometry'
import type { MindGraphNodeData, NodeStyle } from '@/types'
import { resolveNodeShape } from '@/utils/nodeShapeStyle'

export function mindMapBranchSide(nodeId: string | undefined): 'left' | 'right' | null {
  if (!nodeId) return null
  if (nodeId.startsWith('branch-l-')) return 'left'
  if (nodeId.startsWith('branch-r-')) return 'right'
  return null
}

type FlowNodeLike = {
  id: string
  position?: { x: number; y: number }
  dimensions?: { width?: number; height?: number }
  data?: MindGraphNodeData
}

/** Merge persisted toolbar styles with live vue-flow node data. */
export function resolveMindMapNodeStyle(
  nodeId: string | undefined,
  data: MindGraphNodeData | undefined,
  preservedStyles?: Record<string, NodeStyle>
): NodeStyle | undefined {
  if (!nodeId) return data?.style
  return { ...preservedStyles?.[nodeId], ...data?.style }
}

function nodeBoxSize(node: FlowNodeLike): { w: number; h: number } {
  const data = node.data
  return {
    w:
      node.dimensions?.width ??
      (data?.estimatedWidth as number | undefined) ??
      MIND_MAP_GEOMETRY.minWidth,
    h:
      node.dimensions?.height ??
      (data?.estimatedHeight as number | undefined) ??
      MIND_MAP_GEOMETRY.minHeight,
  }
}

/** Nudge endpoint slightly into the underline so stroke meets the bar (anti-alias gap). */
function joinOverlapX(
  x: number,
  side: 'left' | 'right',
  role: 'source' | 'target'
): number {
  const overlap = MINDMAP_UNDERLINE_STROKE_WIDTH / 2
  if (role === 'target') {
    return side === 'right' ? x + overlap : x - overlap
  }
  return side === 'right' ? x - overlap : x + overlap
}

/**
 * Snap edge endpoints to underline midline / branch side edge when node shape is underline.
 */
export function resolveMindMapEdgeEndpoint(
  node: FlowNodeLike | undefined,
  role: 'source' | 'target',
  fallback: { x: number; y: number },
  mergedStyle?: NodeStyle
): { x: number; y: number } {
  if (!node?.position) return fallback

  const shape = resolveNodeShape(mergedStyle ?? node.data?.style, true)
  if (shape !== 'underline') return fallback

  const { w, h } = nodeBoxSize(node)
  const y = mindMapConnectionAnchorY(node.position.y, h, shape)

  if (node.id === 'topic') {
    const side: 'left' | 'right' =
      fallback.x <= node.position.x + w / 2 ? 'left' : 'right'
    return { x: joinOverlapX(fallback.x, side, role), y }
  }

  const side = mindMapBranchSide(node.id)
  if (!side) return { x: fallback.x, y }

  let x =
    role === 'target'
      ? side === 'left'
        ? node.position.x + w
        : node.position.x
      : side === 'left'
        ? node.position.x
        : node.position.x + w

  x = joinOverlapX(x, side, role)
  return { x, y }
}

export function isMindMapUnderlineNode(
  nodeId: string | undefined,
  data: MindGraphNodeData | undefined,
  preservedStyles?: Record<string, NodeStyle>
): boolean {
  return resolveNodeShape(resolveMindMapNodeStyle(nodeId, data, preservedStyles), true) === 'underline'
}

/**
 * Underline parent → box/rounded child: keep branch horizontal at the underline Y
 * (avoid a vertical "step" before the child). Multi-child groups still use the bus.
 */
export function alignMindMapBranchTargetY(
  sourceAnchorY: number,
  target: { x: number; y: number },
  sourceNodeId: string,
  targetNodeId: string,
  sourceData: MindGraphNodeData | undefined,
  targetData: MindGraphNodeData | undefined,
  preservedStyles: Record<string, NodeStyle> | undefined,
  siblingCount: number
): { x: number; y: number } {
  if (siblingCount > 1) return target
  if (!isMindMapUnderlineNode(sourceNodeId, sourceData, preservedStyles)) return target
  if (isMindMapUnderlineNode(targetNodeId, targetData, preservedStyles)) return target
  return { x: target.x, y: sourceAnchorY }
}
