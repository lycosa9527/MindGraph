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
 * Calculate adaptive circle size based on text length
 * For context nodes in circle maps, adapts size to fit text content
 *
 * @param text - Text content of the node
 * @param isTopic - Whether this is a topic node (larger) or context node
 * @returns Diameter in pixels
 */
export function calculateAdaptiveCircleSize(text: string, isTopic: boolean = false): number {
  if (!text || !text.trim()) {
    return isTopic ? 120 : 70
  }

  const textLength = text.trim().length

  if (isTopic) {
    // Topic nodes: larger circles, adapt based on text length
    if (textLength <= 10) {
      return 120
    } else if (textLength <= 20) {
      return 140
    } else if (textLength <= 30) {
      return 160
    } else {
      // For very long text, calculate based on estimated width
      // Approximate: ~8px per character at 20px font size
      const estimatedWidth = textLength * 8
      // Add padding (40px) and ensure minimum size
      return Math.max(180, Math.min(estimatedWidth + 40, 250))
    }
  } else {
    // Context nodes: smaller circles, adapt based on text length
    if (textLength <= 6) {
      return 70
    } else if (textLength <= 12) {
      return 85
    } else if (textLength <= 18) {
      return 100
    } else if (textLength <= 24) {
      return 115
    } else {
      // For very long text, calculate based on estimated width
      // Approximate: ~7px per character at 14px font size
      const estimatedWidth = textLength * 7
      // Add padding (30px) and ensure minimum size
      return Math.max(130, Math.min(estimatedWidth + 30, 200))
    }
  }
}

/**
 * Calculate circle map layout based on node count and context texts
 * Uses adaptive sizing for context nodes based on text length
 * Shared by both loadCircleMapSpec and recalculateCircleMapLayout
 *
 * @param nodeCount - Number of context nodes
 * @param contextTexts - Array of context node texts for adaptive sizing
 * @returns Layout calculation result with positions and radii
 */
export function calculateCircleMapLayout(
  nodeCount: number,
  contextTexts: string[] = []
): CircleMapLayoutResult {
  const topicR = DEFAULT_TOPIC_RADIUS
  const padding = DEFAULT_PADDING

  // Calculate adaptive sizes for context nodes and find maximum radius
  // Default minimum radius for layout calculations
  const defaultContextR = DEFAULT_CONTEXT_RADIUS
  let maxContextR = defaultContextR

  if (contextTexts.length > 0) {
    // Calculate adaptive size for each context node and find maximum radius
    contextTexts.forEach((text) => {
      const adaptiveSize = calculateAdaptiveCircleSize(text, false)
      const adaptiveRadius = adaptiveSize / 2
      maxContextR = Math.max(maxContextR, adaptiveRadius)
    })
  }

  // Use maxContextR for layout calculations to ensure all nodes fit
  const uniformContextR = maxContextR

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
