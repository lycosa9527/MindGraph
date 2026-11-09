/**
 * Ring layout primitives shared by circle map, bubble map, and concept map.
 * First node at 12 o'clock, then even spacing clockwise. Adjacent nodes clear
 * each other with (nodeR + gap/2) / sin(π/n).
 */
import {
  CIRCLE_MAP_OVAL_WIDTH_RATIO,
  type NodeShape,
  shapePackHalfExtent,
} from '@/utils/nodeShapeStyle'

/** Gap between adjacent nodes on the ring (edge-to-edge) */
const RADIAL_NODE_GAP = 8

/** Minimum ring radius (px) */
const RADIAL_MIN_RADIUS = 100

/** Edge-to-edge gap between the bubble map topic and its attribute ring (px). */
export const BUBBLE_TOPIC_TO_RING_GAP = 50

type MeasuredBox = { width: number; height: number } | undefined

/**
 * Top-left position for a node on a ring.
 * 0° = top (12 o'clock), angles increase clockwise.
 *
 * @param centerOffsetX - Distance from node left edge to node center (e.g. width/2)
 * @param centerOffsetY - Distance from node top edge to node center (e.g. height/2)
 */
export function polarToPosition(
  index: number,
  nodeCount: number,
  centerX: number,
  centerY: number,
  radius: number,
  centerOffsetX: number,
  centerOffsetY: number
): { x: number; y: number } {
  const angleDeg = (index * 360) / nodeCount
  const angleRad = ((angleDeg - 90) * Math.PI) / 180
  return {
    x: centerX + radius * Math.cos(angleRad) - centerOffsetX,
    y: centerY + radius * Math.sin(angleRad) - centerOffsetY,
  }
}

/**
 * Minimum ring radius so adjacent nodes don't overlap: (nodeR + gap/2) / sin(π/n).
 */
export function minRadiusForNoOverlap(
  nodeCount: number,
  nodeR: number,
  gap: number = RADIAL_NODE_GAP
): number {
  if (nodeCount <= 0) return 0
  return (nodeR + gap / 2) / Math.sin(Math.PI / nodeCount)
}

/**
 * Worst-case (diagonal) half-extent of a pill with half-width a and half-height b:
 * the extent along φ is a|cos φ| + b|sin φ|, maximised at sqrt(a² + b²).
 */
export function pillHalfExtentForOverlap(halfWidth: number, halfHeight: number): number {
  return Math.sqrt(halfWidth * halfWidth + halfHeight * halfHeight)
}

export interface BubbleRingPack {
  /** Square nodes whose corners must clear the ring (rectangle, rounded, underline). */
  packAsBox?: boolean
  /** Topic outline extent. Defaults to topicR (inscribed circle). */
  topicPackR?: number
  /** Child outline extent. Defaults to the circle radius, or the pill diagonal. */
  childPackR?: number
}

/**
 * Bubble map ring radius: max of (topic distance, no-overlap, minimum).
 * Circles use the radius directly; pills use the diagonal half-extent.
 * packAsBox keeps the diagonal even when the box is square.
 */
export function bubbleMapChildrenRadius(
  nodeCount: number,
  topicR: number,
  halfWidth: number,
  halfHeight: number,
  topicToRingGap: number = BUBBLE_TOPIC_TO_RING_GAP,
  pack?: BubbleRingPack
): number {
  const packAsBox = pack?.packAsBox === true
  const circleLike = !packAsBox && halfWidth === halfHeight
  const defaultChildPack = circleLike ? halfWidth : pillHalfExtentForOverlap(halfWidth, halfHeight)
  const effectiveR = pack?.childPackR ?? defaultChildPack
  const towardCenter = packAsBox ? effectiveR : Math.max(halfWidth, halfHeight)
  const topicPack = pack?.topicPackR ?? topicR
  const targetDistance = topicPack + towardCenter + topicToRingGap
  const noOverlap = minRadiusForNoOverlap(nodeCount, effectiveR)
  return Math.max(targetDistance, noOverlap, RADIAL_MIN_RADIUS)
}

function hasMeasuredBox(measured: MeasuredBox): measured is { width: number; height: number } {
  return measured != null && measured.width > 0 && measured.height > 0
}

/** Disk radius implied by a painted ring node: oval keeps its height, others the larger side. */
export function ringNodeDiskRadius(
  shape: NodeShape | undefined,
  measured: MeasuredBox
): number | undefined {
  if (!hasMeasuredBox(measured)) return undefined
  if (shape === 'oval') return measured.height / 2
  return Math.max(measured.width, measured.height) / 2
}

/** Outline extent a ring node needs to clear its neighbours and the topic. */
export function ringNodeOutlinePackR(
  shape: NodeShape | undefined,
  visualR: number,
  measured: MeasuredBox
): number {
  if (shape === 'underline' && hasMeasuredBox(measured)) {
    return shapePackHalfExtent('underline', measured.width / 2, measured.height / 2)
  }
  if (shape === 'oval') return visualR * CIRCLE_MAP_OVAL_WIDTH_RATIO
  if (shape === 'rectangle' || shape === 'rounded') {
    return shapePackHalfExtent(shape, visualR, visualR)
  }
  return visualR
}

/**
 * Half extents used to centre a ring node on its slot. A measured underline
 * label is sized by its text box (`packed`); every other shape by the disk.
 */
export function ringNodePlacement(
  shape: NodeShape | undefined,
  visualR: number,
  measured: MeasuredBox
): { halfX: number; halfY: number; packed: boolean } {
  if (shape === 'underline' && hasMeasuredBox(measured)) {
    return { halfX: measured.width / 2, halfY: measured.height / 2, packed: true }
  }
  if (shape === 'oval') {
    return { halfX: visualR * CIRCLE_MAP_OVAL_WIDTH_RATIO, halfY: visualR, packed: false }
  }
  return { halfX: visualR, halfY: visualR, packed: false }
}
