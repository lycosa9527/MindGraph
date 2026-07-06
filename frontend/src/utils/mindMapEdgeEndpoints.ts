import {
  MIND_MAP_GEOMETRY,
  mindMapConnectionAnchorY,
} from '@/config/mindMapGeometry'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import type { MindGraphNodeData, NodeStyle } from '@/types'

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

/** DOM-measured size from the shared Pinia store (same source the layout uses). */
export type MeasuredNodeSize = { width?: number; height?: number } | undefined

/**
 * Resolve the node box size, preferring the Pinia-measured dimensions that drive
 * the layout. This keeps connector endpoints on the exact pixel the layout
 * anchored to, instead of vue-flow's independently-measured `node.dimensions`
 * (which can lag or round differently and fall back to the stale estimate).
 */
function nodeBoxSize(node: FlowNodeLike, measured?: MeasuredNodeSize): { w: number; h: number } {
  const data = node.data
  return {
    w:
      measured?.width ??
      node.dimensions?.width ??
      (data?.estimatedWidth as number | undefined) ??
      MIND_MAP_GEOMETRY.minWidth,
    h:
      measured?.height ??
      node.dimensions?.height ??
      (data?.estimatedHeight as number | undefined) ??
      MIND_MAP_GEOMETRY.minHeight,
  }
}

/**
 * Underline join X: the node's side edge. The bar (drawn in the SVG edge layer, spanning the
 * full node width) and the connector are collinear in one SVG coordinate space, so meeting
 * exactly at the edge is seamless — no overlap nudge, which would double-draw the stroke.
 */
function underlineTargetJoinX(
  x: number,
  _side: 'left' | 'right',
  _role: 'source' | 'target'
): number {
  return x
}

/**
 * Underline connector Y: deterministic midline of the underline bar.
 *
 * The bar is the bottom-most element of the node (padding-top → text → gap → 2px bar,
 * no bottom padding), so its midline is `nodeTopY + nodeHeight - stroke/2` — exactly
 * `mindMapConnectionAnchorY`. This is the same source the layout and the DOM bar use,
 * so the connector, the bar, and the node position all evaluate to one Y.
 *
 * Vue Flow's handle-bounds Y (`fallbackY`) is only a last resort when the node height
 * is unknown: it is measured asynchronously, is never force-refreshed after a height
 * change (no `updateNodeInternals`), and can lag the bar by a few pixels on the live
 * canvas — the drift the headless export never shows because it fully settles first.
 */
function resolveMindMapUnderlineAnchorY(
  nodeTopY: number,
  nodeHeight: number,
  fallbackY: number | undefined
): number {
  if (Number.isFinite(nodeHeight) && nodeHeight > 0) {
    return mindMapConnectionAnchorY(nodeTopY, nodeHeight, 'underline')
  }
  const minHandleY = nodeTopY + 8
  if (fallbackY != null && Number.isFinite(fallbackY) && fallbackY >= minHandleY) {
    return fallbackY
  }
  return mindMapConnectionAnchorY(nodeTopY, nodeHeight, 'underline')
}

/**
 * Snap edge endpoints to underline midline / branch side edge when node shape is underline.
 */
export function resolveMindMapEdgeEndpoint(
  node: FlowNodeLike | undefined,
  role: 'source' | 'target',
  fallback: { x: number; y: number },
  mergedStyle?: NodeStyle,
  measured?: MeasuredNodeSize,
  diagramStyleId?: string | null
): { x: number; y: number } {
  if (!node?.position) return fallback

  const shape = resolveMindMapNodeShape(
    {
      id: node.id,
      type: node.id === 'topic' ? 'topic' : 'branch',
      style: mergedStyle ?? node.data?.style,
    },
    diagramStyleId
  )
  if (shape !== 'underline') return fallback

  const { w, h } = nodeBoxSize(node, measured)
  const y = resolveMindMapUnderlineAnchorY(node.position.y, h, fallback.y)

  if (node.id === 'topic') {
    const side: 'left' | 'right' =
      fallback.x <= node.position.x + w / 2 ? 'left' : 'right'
    return { x: underlineTargetJoinX(fallback.x, side, role), y }
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

  x = underlineTargetJoinX(x, side, role)
  return { x, y }
}
