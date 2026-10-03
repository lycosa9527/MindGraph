import type { CSSProperties } from 'vue'

import { MINDMAP_UNDERLINE_STROKE_WIDTH } from '@/config/mindMapGeometry'
import type { NodeStyle } from '@/types'

export type NodeShape = 'rounded' | 'rectangle' | 'oval' | 'underline'

export const NODE_SHAPE_OPTIONS: NodeShape[] = ['rounded', 'rectangle', 'oval', 'underline']

/** Disk oval matches the toolbar mark (18×12): same height as the circle, wider. */
export const CIRCLE_MAP_OVAL_WIDTH_RATIO = 3 / 2

export function resolveNodeShape(style: NodeStyle | undefined, isMindMap: boolean): NodeShape {
  if (style?.nodeShape) return style.nodeShape
  return isMindMap ? 'rounded' : 'rounded'
}

/**
 * Shape the toolbar highlights when the node has no saved nodeShape.
 * Fully round nodes (circle or pill) match oval. Tree categories are rounded
 * rectangles. A bridge pair has no body, so nothing in the menu is selected.
 */
export function defaultDisplayedNodeShape(
  diagramType: string | null | undefined,
  nodeType: string | undefined
): NodeShape | null {
  switch (diagramType) {
    case 'circle_map':
    case 'bubble_map':
    case 'double_bubble_map':
    case 'brace_map':
    case 'flow_map':
    case 'multi_flow_map':
    case 'concept_map':
      return 'oval'
    case 'tree_map':
      return nodeType === 'topic' ? 'oval' : 'rounded'
    case 'bridge_map':
      return null
    default:
      return 'rounded'
  }
}

export function nodeShapeBorderRadius(shape: NodeShape, isMindMap: boolean): string {
  switch (shape) {
    case 'rectangle':
      return '0px'
    case 'oval':
      return '9999px'
    case 'underline':
      return '0px'
    case 'rounded':
    default:
      return isMindMap ? '4.5px' : '8px'
  }
}

export function applyNodeShapeToStyle(
  base: CSSProperties,
  shape: NodeShape,
  borderColor: string,
  isMindMap: boolean
): CSSProperties {
  if (shape !== 'underline') {
    return {
      ...base,
      borderRadius: nodeShapeBorderRadius(shape, isMindMap),
    }
  }

  return {
    ...base,
    backgroundColor: 'transparent',
    borderColor: 'transparent',
    borderWidth: '0px',
    borderStyle: 'none',
    borderRadius: '0px',
    boxShadow: 'none',
  }
}

/**
 * Distance from the center to a stadium outline (fully rounded oval).
 * The long axis is horizontal when halfWidth >= halfHeight.
 */
function stadiumRayHit(halfWidth: number, halfHeight: number, nx: number, ny: number): number {
  const majorIsX = halfWidth >= halfHeight
  const major = majorIsX ? halfWidth : halfHeight
  const minor = majorIsX ? halfHeight : halfWidth
  const alongMajor = Math.abs(majorIsX ? nx : ny)
  const alongMinor = Math.abs(majorIsX ? ny : nx)
  const capCenter = major - minor

  if (alongMinor > 1e-8) {
    const flatHit = minor / alongMinor
    if (flatHit * alongMajor <= capCenter + 1e-6) return flatHit
  }

  const disc = minor * minor - capCenter * capCenter * alongMinor * alongMinor
  if (disc < 0) return major
  const root = Math.sqrt(disc)
  const near = alongMajor * capCenter - root
  const far = alongMajor * capCenter + root
  if (near > 1e-6) return near
  if (far > 1e-6) return far
  return major
}

/**
 * Ring packing extent from the node center.
 * Unset shape and an oval on a square stay the inscribed circle.
 * A wider oval uses its long axis. Rectangle, rounded, and underline use the box diagonal.
 */
export function shapePacksAsCircle(
  shape: NodeShape | undefined,
  halfWidth: number,
  halfHeight: number
): boolean {
  if (shape === 'rectangle' || shape === 'rounded' || shape === 'underline') return false
  if (shape === 'oval' && halfWidth !== halfHeight) return false
  return true
}

export function shapePackHalfExtent(
  shape: NodeShape | undefined,
  halfWidth: number,
  halfHeight: number
): number {
  if (shape === 'oval' && halfWidth !== halfHeight) {
    return Math.max(halfWidth, halfHeight)
  }
  if (shapePacksAsCircle(shape, halfWidth, halfHeight)) {
    return Math.min(halfWidth, halfHeight)
  }
  return Math.hypot(halfWidth, halfHeight)
}

/** Distance from the node center to the outline along a unit ray. */
export function shapeRayHitDistance(
  shape: NodeShape | undefined,
  halfWidth: number,
  halfHeight: number,
  nx: number,
  ny: number
): number {
  if (shape === 'oval' && halfWidth !== halfHeight) {
    return stadiumRayHit(halfWidth, halfHeight, nx, ny)
  }
  if (shapePacksAsCircle(shape, halfWidth, halfHeight)) {
    return Math.min(halfWidth, halfHeight)
  }
  const ax = Math.abs(nx)
  const ay = Math.abs(ny)
  const alongX = ax > 1e-8 ? halfWidth / ax : Number.POSITIVE_INFINITY
  const alongY = ay > 1e-8 ? halfHeight / ay : Number.POSITIVE_INFINITY
  const hit = Math.min(alongX, alongY)
  return Number.isFinite(hit) ? hit : 0
}

/**
 * Horizontal inset from the left or right of the node box to the visible outline
 * at `topPercent`. A wide oval's end cap is a semicircle, so corners of the box
 * sit outside the fill. Rounded boxes inset only inside the corner radius.
 */
export function sideOutlineInsetPx(
  shape: NodeShape | undefined,
  nodeWidthPx: number,
  nodeHeightPx: number,
  topPercent: number,
  roundedCornerPx = 4.5
): number {
  if (nodeWidthPx <= 0 || nodeHeightPx <= 0) return 0
  if (shape !== 'oval' && shape !== 'rounded') return 0
  const y = (topPercent / 100) * nodeHeightPx
  const radius =
    shape === 'rounded'
      ? Math.min(Math.max(0, roundedCornerPx), nodeWidthPx / 2, nodeHeightPx / 2)
      : Math.min(nodeWidthPx, nodeHeightPx) / 2
  return capSideInsetPx(nodeHeightPx, y, radius)
}

function capSideInsetPx(heightPx: number, yPx: number, radiusPx: number): number {
  if (radiusPx <= 0 || heightPx <= 0) return 0
  const dy = Math.abs(yPx - heightPx / 2)
  const straightHalf = Math.max(0, heightPx / 2 - radiusPx)
  if (dy <= straightHalf) return 0
  const capDy = dy - straightHalf
  if (capDy >= radiusPx) return radiusPx
  return radiusPx - Math.sqrt(radiusPx * radiusPx - capDy * capDy)
}

export function paintNodeShape(
  base: CSSProperties,
  shape: NodeShape | undefined,
  borderColor: string,
  fallbackRadius: string
): CSSProperties {
  if (!shape) return { ...base, borderRadius: fallbackRadius }
  return applyNodeShapeToStyle(base, shape, borderColor, true)
}

/** Place vue-flow handles on the underline midline (horizontal branch join). */
export function mindMapUnderlineHandleStyle(side: 'left' | 'right'): CSSProperties {
  const half = MINDMAP_UNDERLINE_STROKE_WIDTH / 2
  const tx = side === 'left' ? '-50%' : '50%'
  return {
    top: 'auto',
    bottom: `${half}px`,
    transform: `translate(${tx}, 50%)`,
  }
}
