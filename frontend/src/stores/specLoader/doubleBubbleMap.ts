/**
 * Double Bubble Map Loader
 */
import {
  DEFAULT_BUBBLE_RADIUS,
  DEFAULT_COLUMN_SPACING,
  DEFAULT_DIFF_RADIUS,
  DEFAULT_PADDING,
  DEFAULT_TOPIC_RADIUS,
} from '@/composables/diagrams/layoutConfig'
import type { Connection, DiagramNode } from '@/types'
import type { SpecLoaderResult } from './types'

/**
 * Load double bubble map spec into diagram nodes and connections
 *
 * @param spec - Double bubble map spec with left, right, similarities, and differences
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadDoubleBubbleMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const left = (spec.left as string) || (spec.topic1 as string) || ''
  const right = (spec.right as string) || (spec.topic2 as string) || ''
  const similarities = (spec.similarities as string[]) || (spec.shared as string[]) || []
  const leftDifferences =
    (spec.leftDifferences as string[]) ||
    (spec.left_differences as string[]) ||
    (spec.left_unique as string[]) ||
    []
  const rightDifferences =
    (spec.rightDifferences as string[]) ||
    (spec.right_differences as string[]) ||
    (spec.right_unique as string[]) ||
    []

  // Layout constants from layoutConfig
  const padding = DEFAULT_PADDING
  const topicR = DEFAULT_TOPIC_RADIUS
  const simR = DEFAULT_BUBBLE_RADIUS
  const diffR = DEFAULT_DIFF_RADIUS
  const columnSpacing = DEFAULT_COLUMN_SPACING

  // Vertical spacing
  const simVerticalSpacing = simR * 2 + 12
  const diffVerticalSpacing = diffR * 2 + 10

  // Calculate X positions (column-based layout from left to right)
  const leftDiffX = padding + diffR
  const leftTopicX = leftDiffX + diffR + columnSpacing + topicR
  const simX = leftTopicX + topicR + columnSpacing + simR
  const rightTopicX = simX + simR + columnSpacing + topicR
  const rightDiffX = rightTopicX + topicR + columnSpacing + diffR

  // Calculate heights
  const simCount = similarities.length
  const leftDiffCount = leftDifferences.length
  const rightDiffCount = rightDifferences.length

  // Calculate column heights (differences are paired, so use max count)
  const simColHeight = simCount > 0 ? (simCount - 1) * simVerticalSpacing + simR * 2 : 0
  const maxDiffCount = Math.max(leftDiffCount, rightDiffCount)
  const diffColHeight = maxDiffCount > 0 ? (maxDiffCount - 1) * diffVerticalSpacing + diffR * 2 : 0
  const maxColHeight = Math.max(simColHeight, diffColHeight, topicR * 2)

  const requiredHeight = maxColHeight + padding * 2
  const centerY = requiredHeight / 2

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Left topic (column 2) - perfect circle
  nodes.push({
    id: 'left-topic',
    text: left,
    type: 'topic',
    position: { x: leftTopicX - topicR, y: centerY - topicR },
  })

  // Right topic (column 4) - perfect circle
  nodes.push({
    id: 'right-topic',
    text: right,
    type: 'topic',
    position: { x: rightTopicX - topicR, y: centerY - topicR },
  })

  // Similarities (column 3, center)
  const simStartY = centerY - simColHeight / 2 + simR
  similarities.forEach((sim, index) => {
    nodes.push({
      id: `similarity-${index}`,
      text: sim,
      type: 'bubble',
      position: {
        x: simX - simR,
        y: simStartY + index * simVerticalSpacing - simR,
      },
    })
    connections.push(
      { id: `edge-left-sim-${index}`, source: 'left-topic', target: `similarity-${index}` },
      { id: `edge-right-sim-${index}`, source: 'right-topic', target: `similarity-${index}` }
    )
  })

  // Left and Right differences are PAIRED - they share the same Y positions
  const diffStartY = centerY - diffColHeight / 2 + diffR

  // Left differences (column 1, far left)
  leftDifferences.forEach((diff, index) => {
    nodes.push({
      id: `left-diff-${index}`,
      text: diff,
      type: 'bubble',
      position: {
        x: leftDiffX - diffR,
        y: diffStartY + index * diffVerticalSpacing - diffR,
      },
    })
    connections.push({
      id: `edge-left-diff-${index}`,
      source: 'left-topic',
      target: `left-diff-${index}`,
    })
  })

  // Right differences (column 5, far right) - same Y positions as left
  rightDifferences.forEach((diff, index) => {
    nodes.push({
      id: `right-diff-${index}`,
      text: diff,
      type: 'bubble',
      position: {
        x: rightDiffX - diffR,
        y: diffStartY + index * diffVerticalSpacing - diffR,
      },
    })
    connections.push({
      id: `edge-right-diff-${index}`,
      source: 'right-topic',
      target: `right-diff-${index}`,
    })
  })

  return { nodes, connections }
}
