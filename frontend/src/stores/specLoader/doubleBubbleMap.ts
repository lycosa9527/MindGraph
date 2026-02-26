/**
 * Double Bubble Map Loader
 */
import {
  DEFAULT_BUBBLE_RADIUS,
  DEFAULT_DIFF_RADIUS,
  DEFAULT_DIFF_TO_TOPIC_SPACING,
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
  // Use same spacing for topic-to-similarity and topic-to-difference (both sides equal)
  const topicSpacing = DEFAULT_DIFF_TO_TOPIC_SPACING

  // Unified row spacing for all columns (diff, sim) - same vertical positions
  const rowSpacing = Math.max(simR * 2 + 12, diffR * 2 + 10)

  // Calculate X positions (column-based layout from left to right)
  const leftDiffX = padding + diffR
  const leftTopicX = leftDiffX + diffR + topicSpacing + topicR
  const simX = leftTopicX + topicR + topicSpacing + simR
  const rightTopicX = simX + simR + topicSpacing + topicR
  const rightDiffX = rightTopicX + topicR + topicSpacing + diffR

  const simCount = similarities.length
  const leftDiffCount = leftDifferences.length
  const rightDiffCount = rightDifferences.length
  const maxDiffCount = Math.max(leftDiffCount, rightDiffCount)
  const rowCount = Math.max(maxDiffCount, simCount, 1)

  const requiredHeight =
    (rowCount - 1) * rowSpacing + Math.max(simR * 2, diffR * 2, topicR * 2) + padding * 2
  const centerY = requiredHeight / 2

  // Row Y positions: center-aligned so middle row = centerY (topics align with middle diff row)
  const rowY = (rowIndex: number) => centerY + (rowIndex - (rowCount - 1) / 2) * rowSpacing

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Topics at centerY (aligned with middle row of diff/sim nodes)
  const topicY = centerY

  // Left topic (column 2)
  nodes.push({
    id: 'left-topic',
    text: left,
    type: 'topic',
    position: { x: leftTopicX - topicR, y: topicY - topicR },
  })

  // Right topic (column 4)
  nodes.push({
    id: 'right-topic',
    text: right,
    type: 'topic',
    position: { x: rightTopicX - topicR, y: topicY - topicR },
  })

  // Similarities: center them in available rows (e.g. 2 sims in 3 rows → rows 0 and 2)
  const simRowIndices =
    simCount <= 1
      ? [0]
      : Array.from({ length: simCount }, (_, i) =>
          simCount === rowCount ? i : Math.round((i * (rowCount - 1)) / (simCount - 1))
        )

  similarities.forEach((sim, index) => {
    const y = rowY(simRowIndices[index])
    nodes.push({
      id: `similarity-${index}`,
      text: sim,
      type: 'bubble',
      position: { x: simX - simR, y: y - simR },
    })
    connections.push(
      { id: `edge-left-sim-${index}`, source: 'left-topic', target: `similarity-${index}` },
      { id: `edge-right-sim-${index}`, source: 'right-topic', target: `similarity-${index}` }
    )
  })

  // Left and right differences: same row positions, center-aligned with topics
  leftDifferences.forEach((diff, index) => {
    const y = rowY(index)
    nodes.push({
      id: `left-diff-${index}`,
      text: diff,
      type: 'bubble',
      position: { x: leftDiffX - diffR, y: y - diffR },
    })
    connections.push({
      id: `edge-left-diff-${index}`,
      source: 'left-topic',
      target: `left-diff-${index}`,
    })
  })

  rightDifferences.forEach((diff, index) => {
    const y = rowY(index)
    nodes.push({
      id: `right-diff-${index}`,
      text: diff,
      type: 'bubble',
      position: { x: rightDiffX - diffR, y: y - diffR },
    })
    connections.push({
      id: `edge-right-diff-${index}`,
      source: 'right-topic',
      target: `right-diff-${index}`,
    })
  })

  return { nodes, connections }
}
