/**
 * Shared utilities for spec loaders
 * Contains common layout calculations and type definitions
 */
import {
  DEFAULT_CONTEXT_RADIUS,
  DEFAULT_PADDING,
  DEFAULT_TOPIC_RADIUS,
} from '@/composables/diagrams/layoutConfig'

/**
 * Circle map layout calculation result
 */
export interface CircleMapLayoutResult {
  centerX: number
  centerY: number
  topicR: number
  uniformContextR: number
  childrenRadius: number
  outerCircleR: number
}

/**
 * Calculate circle map layout based on node count
 * Shared by both loadCircleMapSpec and recalculateCircleMapLayout
 *
 * @param nodeCount - Number of context nodes
 * @returns Layout calculation result with positions and radii
 */
export function calculateCircleMapLayout(nodeCount: number): CircleMapLayoutResult {
  const uniformContextR = DEFAULT_CONTEXT_RADIUS
  const topicR = DEFAULT_TOPIC_RADIUS
  const padding = DEFAULT_PADDING

  // Calculate childrenRadius using both constraints (matching original D3 logic)
  const targetRadialDistance = topicR + topicR * 0.5 + uniformContextR + 5
  const spacingMultiplier = nodeCount <= 3 ? 2.0 : nodeCount <= 6 ? 2.05 : 2.1
  const circumferentialMinRadius =
    nodeCount > 0 ? (uniformContextR * nodeCount * spacingMultiplier) / (2 * Math.PI) : 0
  const childrenRadius = Math.max(targetRadialDistance, circumferentialMinRadius, 100)
  const outerCircleR = childrenRadius + uniformContextR + 10
  const centerX = outerCircleR + padding
  const centerY = outerCircleR + padding

  return { centerX, centerY, topicR, uniformContextR, childrenRadius, outerCircleR }
}
