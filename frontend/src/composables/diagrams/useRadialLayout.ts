/**
 * useRadialLayout - Shared radial/circular layout calculation
 *
 * Used by bubble map, circle map, and similar diagrams.
 * First child at 0° (top, 12 o'clock); even distribution clockwise.
 * Uses no-overlap formula: (nodeR + gap) / sin(π/n) for circumferential spacing.
 */

/** Gap between adjacent nodes on the ring (edge-to-edge) */
const RADIAL_NODE_GAP = 8

/** Minimum ring radius (px) */
const RADIAL_MIN_RADIUS = 100

/**
 * Compute polar position for a node on a ring.
 * 0° = top (12 o'clock), angles increase clockwise.
 *
 * @param index - Node index (0 = first)
 * @param nodeCount - Total nodes on the ring
 * @param centerX - Center X
 * @param centerY - Center Y
 * @param radius - Distance from center to node center
 * @param centerOffsetX - Distance from node left edge to node center (e.g. width/2)
 * @param centerOffsetY - Distance from node top edge to node center (e.g. height/2)
 * @returns { x, y } top-left position for Vue Flow
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
  // 0° = top (12 o'clock); index 0 gets 0°, then 360/n, 2*360/n, ...
  // In math: top = -90°, so angleRad = (angleDeg - 90) * PI/180
  const angleDeg = (index * 360) / nodeCount
  const angleRad = ((angleDeg - 90) * Math.PI) / 180

  const centerXAtRadius = centerX + radius * Math.cos(angleRad)
  const centerYAtRadius = centerY + radius * Math.sin(angleRad)

  return {
    x: centerXAtRadius - centerOffsetX,
    y: centerYAtRadius - centerOffsetY,
  }
}

/**
 * Compute minimum ring radius so adjacent nodes don't overlap.
 * Formula: (nodeR + gap/2) / sin(π/n)
 *
 * @param nodeCount - Number of nodes on the ring
 * @param nodeR - Radius of each node (half of diameter)
 * @param gap - Edge-to-edge gap between nodes (default RADIAL_NODE_GAP)
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
 * Compute effective half-extent of a pill for no-overlap on a ring.
 * Pills extend farther diagonally than along axes. For a pill with half-width a and
 * half-height b, the extent in direction φ is a|cos(φ)| + b|sin(φ)|. The maximum
 * over all φ (worst case for diagonal overlap) is sqrt(a² + b²).
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
 * Compute bubble map ring radius: max of (topic distance, no-overlap, minimum).
 * Circles: use radius directly. Pills: use diagonal half-extent.
 * packAsBox keeps the diagonal even when the box is square.
 */
export function bubbleMapChildrenRadius(
  nodeCount: number,
  topicR: number,
  halfWidth: number,
  halfHeight: number,
  topicToRingGap: number = 50,
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
