/**
 * Mind-map association lines (关联线): left/right handles only, both ends
 * use the outer side so the curve bows around the tree (not through siblings).
 */
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { mindMapTextCenterAnchorY } from '@/config/mindMapGeometry'
import type { Connection, DiagramNode, MindMapSummaryLineStyle, NodeStyle } from '@/types'
import { parseCubicBezierPath, pointOnCubicBezierPath } from '@/utils/bezierSplit'
import {
  isMindMapAssociationConnection,
  isMindMapTopicId,
  mindMapNodeSide,
  type MindMapSide,
} from '@/utils/mindMapLocation'
import {
  MINDMAP_SUMMARY_DEFAULT_STROKE_WIDTH,
  MINDMAP_SUMMARY_STROKE_WIDTH_MAX,
  MINDMAP_SUMMARY_STROKE_WIDTH_MIN,
  mindMapSummaryStrokeDasharray,
  parseMindMapSummaryStrokeColor,
  parseMindMapSummaryStrokeWidth,
} from '@/utils/mindMapSummary'

/** Minimum outward bow so same-X left/left (or right/right) never becomes a straight. */
const ASSOCIATION_CURVE_MIN_BOW = 64
const ASSOCIATION_DEFAULT_STROKE = '#64748b'

export type AssociationLineStyle = MindMapSummaryLineStyle
export type AssociationArrowhead = 'none' | 'source' | 'target' | 'both'

export type AssociationCurveOffset = { x: number; y: number }

export type AssociationChromePatch = {
  lineStyle?: AssociationLineStyle
  strokeColor?: string
  strokeWidth?: number
  arrowheadDirection?: AssociationArrowhead
  curveOffset?: AssociationCurveOffset
}

export type HorizontalSide = 'left' | 'right'

export type MindMapAssociationHandles = {
  sourcePosition: HorizontalSide
  targetPosition: HorizontalSide
  sourceHandle: string
  targetHandle: string
}

type NodeBox = {
  id?: string
  type?: string
  position?: { x: number; y: number }
  data?: Record<string, unknown>
  style?: NodeStyle
}

type SideLookup = {
  nodes?: readonly { id?: string; type?: string; data?: Record<string, unknown> }[] | null
  connections?: readonly Pick<Connection, 'source' | 'target' | 'sourceHandle' | 'edgeType'>[] | null
}

function nodeCenterX(node: NodeBox): number {
  const width = Number(node.data?.estimatedWidth) || Number(node.style?.width) || 120
  return (node.position?.x ?? 0) + width / 2
}

function isTopicLike(node: NodeBox | undefined): boolean {
  if (!node) return false
  return isMindMapTopicId(node.id) || node.type === 'topic' || node.type === 'center'
}

function nodeSide(node: NodeBox, options?: SideLookup): MindMapSide | null {
  if (!node.id) return null
  return mindMapNodeSide(node.id, {
    node,
    nodes: options?.nodes,
    connections: options?.connections,
  })
}

export function mindMapAssociationHandleId(
  node: NodeBox | undefined,
  side: HorizontalSide,
  role: 'source' | 'target'
): string {
  if (isTopicLike(node)) {
    return side === 'left' ? 'mindmap-left' : 'mindmap-right'
  }
  if (role === 'source') {
    return side === 'left' ? 'left-source' : 'right'
  }
  return side === 'left' ? 'left' : 'right-target'
}

function facingHandles(sourceNode: NodeBox, targetNode: NodeBox): MindMapAssociationHandles {
  const sourceOnRight = nodeCenterX(targetNode) >= nodeCenterX(sourceNode)
  const sourcePosition: HorizontalSide = sourceOnRight ? 'right' : 'left'
  const targetPosition: HorizontalSide = sourceOnRight ? 'left' : 'right'
  return {
    sourcePosition,
    targetPosition,
    sourceHandle: mindMapAssociationHandleId(sourceNode, sourcePosition, 'source'),
    targetHandle: mindMapAssociationHandleId(targetNode, targetPosition, 'target'),
  }
}

/**
 * Same-side branches share the outer handle (left+left or right+right) so the
 * curve stays outside the tree. Topic inherits the other endpoint's side.
 */
export function computeMindMapAssociationHandles(
  sourceNode: NodeBox,
  targetNode: NodeBox,
  options?: SideLookup
): MindMapAssociationHandles {
  const outer = nodeSide(sourceNode, options) ?? nodeSide(targetNode, options)
  if (!outer) return facingHandles(sourceNode, targetNode)
  return {
    sourcePosition: outer,
    targetPosition: outer,
    sourceHandle: mindMapAssociationHandleId(sourceNode, outer, 'source'),
    targetHandle: mindMapAssociationHandleId(targetNode, outer, 'target'),
  }
}

export function withMindMapAssociationHandles(
  conn: Connection,
  nodes: readonly DiagramNode[],
  connections?: readonly Connection[]
): Connection {
  const sourceNode = nodes.find((node) => node.id === conn.source)
  const targetNode = nodes.find((node) => node.id === conn.target)
  if (!sourceNode || !targetNode) return conn
  return {
    ...conn,
    ...computeMindMapAssociationHandles(sourceNode, targetNode, { nodes, connections }),
  }
}

export type MindMapAssociationCurve = {
  edgePath: string
  labelX: number
  labelY: number
}

export function parseAssociationCurveOffset(raw: unknown): AssociationCurveOffset | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const record = raw as { x?: unknown; y?: unknown }
  const x = Number(record.x)
  const y = Number(record.y)
  if (!Number.isFinite(x) || !Number.isFinite(y)) return undefined
  return { x, y }
}

/**
 * Sit a chrome control on the curve, but never on the midpoint label chip.
 * If the path sample is too close, push it outward along the bow.
 */
export function associationChromePointAwayFromLabel(
  edgePath: string,
  label: { x: number; y: number },
  pathT: number,
  minDist: number
): { x: number; y: number } {
  const onPath = pointOnCubicBezierPath(edgePath, pathT)
  let dx = (onPath?.x ?? label.x) - label.x
  let dy = (onPath?.y ?? label.y) - label.y
  let dist = Math.hypot(dx, dy)
  if (dist < 1) {
    const ends = parseCubicBezierPath(edgePath)
    if (ends) {
      dx = label.x - (ends[0].x + ends[3].x) / 2
      dy = label.y - (ends[0].y + ends[3].y) / 2
      dist = Math.hypot(dx, dy)
    }
  }
  if (dist < 1) {
    return { x: label.x, y: label.y - minDist }
  }
  const scale = Math.max(minDist, dist) / dist
  return { x: label.x + dx * scale, y: label.y + dy * scale }
}

export function associationCurveOffsetFromApex(
  source: { x: number; y: number },
  target: { x: number; y: number },
  apex: { x: number; y: number }
): AssociationCurveOffset {
  return {
    x: apex.x - (source.x + target.x) / 2,
    y: apex.y - (source.y + target.y) / 2,
  }
}

/** Quadratic-through-apex written as a cubic so existing path helpers still apply. */
function cubicThroughApex(
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
  offset: AssociationCurveOffset
): MindMapAssociationCurve {
  const midX = (sourceX + targetX) / 2
  const midY = (sourceY + targetY) / 2
  const apexX = midX + offset.x
  const apexY = midY + offset.y
  const ctrlX = 2 * apexX - midX
  const ctrlY = 2 * apexY - midY
  const p1x = sourceX + (2 / 3) * (ctrlX - sourceX)
  const p1y = sourceY + (2 / 3) * (ctrlY - sourceY)
  const p2x = targetX + (2 / 3) * (ctrlX - targetX)
  const p2y = targetY + (2 / 3) * (ctrlY - targetY)
  return {
    edgePath: `M${sourceX},${sourceY} C${p1x},${p1y} ${p2x},${p2y} ${targetX},${targetY}`,
    labelX: apexX,
    labelY: apexY,
  }
}

/**
 * Outward C-curve between two outer handles. Vue Flow's getBezierPath goes
 * straight when both ends share X and the same side. A stored offset replaces
 * the default bow with a curve that passes through midpoint + offset.
 */
export function mindMapAssociationCurvePath(
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
  side: HorizontalSide,
  offset?: AssociationCurveOffset | null
): MindMapAssociationCurve {
  if (offset) {
    return cubicThroughApex(sourceX, sourceY, targetX, targetY, offset)
  }
  const spanX = Math.abs(targetX - sourceX)
  const spanY = Math.abs(targetY - sourceY)
  const bow = Math.max(ASSOCIATION_CURVE_MIN_BOW, spanY * 0.34, spanX * 0.5)
  const controlX =
    side === 'left' ? Math.min(sourceX, targetX) - bow : Math.max(sourceX, targetX) + bow
  const edgePath = `M${sourceX},${sourceY} C${controlX},${sourceY} ${controlX},${targetY} ${targetX},${targetY}`
  const mid = pointOnCubicBezierPath(edgePath, 0.5)
  return {
    edgePath,
    labelX: mid?.x ?? (sourceX + targetX) / 2,
    labelY: mid?.y ?? (sourceY + targetY) / 2,
  }
}

function associationNodeStyle(node: NodeBox): NodeStyle | undefined {
  const fromData = node.data?.style
  const dataStyle =
    fromData && typeof fromData === 'object' ? (fromData as NodeStyle) : undefined
  return { ...dataStyle, ...node.style }
}

function associationNodeHeight(node: NodeBox, measuredHeight?: number): number {
  if (measuredHeight != null && measuredHeight > 0) return measuredHeight
  const estimated = Number(node.data?.estimatedHeight)
  if (Number.isFinite(estimated) && estimated > 0) return estimated
  const styled = Number(node.style?.height)
  if (Number.isFinite(styled) && styled > 0) return styled
  return 0
}

/** Keep handle X (left/right edge); snap Y to the text vertical center. */
export function snapMindMapAssociationEndpoint(
  node: NodeBox | undefined,
  fallback: { x: number; y: number },
  options?: { measuredHeight?: number; diagramStyleId?: string | null }
): { x: number; y: number } {
  if (!node?.position) return fallback
  const height = associationNodeHeight(node, options?.measuredHeight)
  if (!(height > 0)) return fallback
  const shape = resolveMindMapNodeShape(
    {
      id: node.id ?? '',
      type: isTopicLike(node) ? 'topic' : 'branch',
      style: associationNodeStyle(node),
    },
    options?.diagramStyleId
  )
  return {
    x: fallback.x,
    y: mindMapTextCenterAnchorY(node.position.y, height, shape),
  }
}

export function mindMapAssociationCurveFromEnds(
  source: { x: number; y: number },
  target: { x: number; y: number },
  side: HorizontalSide,
  sourceNode: NodeBox | undefined,
  targetNode: NodeBox | undefined,
  options?: {
    sourceHeight?: number
    targetHeight?: number
    diagramStyleId?: string | null
    curveOffset?: AssociationCurveOffset | null
  }
): MindMapAssociationCurve {
  const snappedSource = snapMindMapAssociationEndpoint(sourceNode, source, {
    measuredHeight: options?.sourceHeight,
    diagramStyleId: options?.diagramStyleId,
  })
  const snappedTarget = snapMindMapAssociationEndpoint(targetNode, target, {
    measuredHeight: options?.targetHeight,
    diagramStyleId: options?.diagramStyleId,
  })
  return mindMapAssociationCurvePath(
    snappedSource.x,
    snappedSource.y,
    snappedTarget.x,
    snappedTarget.y,
    side,
    options?.curveOffset
  )
}

export function associationLineStyleFromDash(
  dash: string | undefined
): AssociationLineStyle {
  if (!dash || dash === 'none') return 'solid'
  const first = Number.parseFloat(dash)
  if (Number.isFinite(first) && first <= 2) return 'dotted'
  return 'dashed'
}

export function associationStrokeDasharray(
  lineStyle: AssociationLineStyle,
  strokeWidth: number
): string | undefined {
  return mindMapSummaryStrokeDasharray(lineStyle, strokeWidth)
}

export function associationStrokeWidth(raw: unknown): number {
  return parseMindMapSummaryStrokeWidth(raw) ?? MINDMAP_SUMMARY_DEFAULT_STROKE_WIDTH
}

export function associationStrokeColor(raw: unknown): string {
  return parseMindMapSummaryStrokeColor(raw) ?? ASSOCIATION_DEFAULT_STROKE
}

export function clampAssociationStrokeWidth(width: number): number {
  return Math.min(
    MINDMAP_SUMMARY_STROKE_WIDTH_MAX,
    Math.max(MINDMAP_SUMMARY_STROKE_WIDTH_MIN, Math.round(width))
  )
}

export function associationArrowheadFromEnds(
  start: boolean,
  end: boolean
): AssociationArrowhead {
  if (start && end) return 'both'
  if (start) return 'source'
  if (end) return 'target'
  return 'none'
}

export function associationEndsFromArrowhead(direction: AssociationArrowhead | undefined): {
  start: boolean
  end: boolean
} {
  return {
    start: direction === 'source' || direction === 'both',
    end: direction === 'target' || direction === 'both',
  }
}

export function applyAssociationChromePatch(
  conn: Connection,
  patch: AssociationChromePatch
): Connection {
  const width = associationStrokeWidth(patch.strokeWidth ?? conn.style?.strokeWidth)
  const lineStyle =
    patch.lineStyle ?? associationLineStyleFromDash(conn.style?.strokeDasharray)
  const strokeColor = associationStrokeColor(patch.strokeColor ?? conn.style?.strokeColor)
  const dash = associationStrokeDasharray(lineStyle, width)
  conn.style = {
    ...conn.style,
    strokeColor,
    strokeWidth: width,
    strokeDasharray: dash ?? 'none',
  }
  if (patch.arrowheadDirection !== undefined) {
    conn.arrowheadDirection = patch.arrowheadDirection
    conn.arrowheadLocked = true
  }
  if (patch.curveOffset !== undefined) {
    const parsed = parseAssociationCurveOffset(patch.curveOffset)
    if (parsed) conn.curveOffset = parsed
  }
  return conn
}

/** Topic (no side) may link either side; two branches must share a side. */
export function mindMapAssociationSameSide(
  sourceId: string,
  targetId: string,
  options?: SideLookup
): boolean {
  const sourceSide = mindMapNodeSide(sourceId, options)
  const targetSide = mindMapNodeSide(targetId, options)
  if (sourceSide == null || targetSide == null) return true
  return sourceSide === targetSide
}

function associationNodeCenterX(node: NodeBox | undefined): number | null {
  if (!node) return null
  return nodeCenterX(node)
}

/**
 * True when both ends sit on opposite sides of the topic after layout
 * (stamped side or X), so the curve would cut across the diagram.
 */
export function mindMapAssociationShouldVoid(
  sourceId: string,
  targetId: string,
  options?: SideLookup
): boolean {
  if (!mindMapAssociationSameSide(sourceId, targetId, options)) return true
  if (isMindMapTopicId(sourceId) || isMindMapTopicId(targetId)) return false
  const nodes = options?.nodes
  if (!nodes) return false
  const topic = nodes.find((node) => isTopicLike(node))
  const source = nodes.find((node) => node.id === sourceId)
  const target = nodes.find((node) => node.id === targetId)
  const mid = associationNodeCenterX(topic)
  const sourceX = associationNodeCenterX(source)
  const targetX = associationNodeCenterX(target)
  if (mid == null || sourceX == null || targetX == null) return false
  const slop = 8
  if (Math.abs(sourceX - mid) < slop || Math.abs(targetX - mid) < slop) return false
  return (sourceX - mid) * (targetX - mid) < 0
}

/** Drop association overlays that would cross the topic after a side change. */
export function voidMindMapAssociationsAcrossSides(
  connections: readonly Connection[],
  nodes: readonly DiagramNode[]
): Connection[] {
  const options = { nodes, connections }
  let dropped = false
  const kept: Connection[] = []
  for (const conn of connections) {
    if (
      isMindMapAssociationConnection(conn) &&
      mindMapAssociationShouldVoid(conn.source, conn.target, options)
    ) {
      dropped = true
      continue
    }
    kept.push(conn)
  }
  return dropped ? kept : (connections as Connection[])
}
