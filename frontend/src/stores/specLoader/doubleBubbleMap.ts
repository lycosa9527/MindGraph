/**
 * Double Bubble Map Loader
 * Text-adaptive radii, capsule dimensions, layout aligned with useDoubleBubbleMap.
 * Supports _doubleBubbleMapNodeSizes for empty-node saved radii.
 */
import {
  DEFAULT_COLUMN_SPACING,
  DEFAULT_PADDING,
  DOUBLE_BUBBLE_MAX_CAPSULE_HEIGHT,
} from '@/composables/diagrams/layoutConfig'
import type { Connection, DiagramNode } from '@/types'
import {
  doubleBubbleDiffRequiredRadius,
  doubleBubbleRequiredRadius,
} from './textMeasurement'

import type { SpecLoaderResult } from './types'

/** Capsule dimensions from radius (same formula as useDoubleBubbleMap) */
function capsuleFromRadius(radius: number): { width: number; height: number; diameter: number } {
  const diameter = radius * 2
  const height = Math.min(
    Math.round(diameter * 0.56),
    DOUBLE_BUBBLE_MAX_CAPSULE_HEIGHT
  )
  return {
    width: Math.round(diameter * 1.22),
    height,
    diameter,
  }
}

/** Layout from unified radii (mirrors useDoubleBubbleMap computeLayoutFromRadii) */
function computeLayout(
  simCount: number,
  leftDiffCount: number,
  rightDiffCount: number,
  padding: number,
  topicR: number,
  simR: number,
  diffR: number
): {
  centerX: number
  centerY: number
  leftDiffX: number
  leftTopicX: number
  simX: number
  rightTopicX: number
  rightDiffX: number
  simVerticalSpacing: number
  diffVerticalSpacing: number
  simCap: { width: number; height: number }
  diffCap: { width: number; height: number }
} {
  const columnSpacing = DEFAULT_COLUMN_SPACING
  const diffCap = capsuleFromRadius(diffR)
  const maxLeftW = diffCap.width
  const maxRightW = diffCap.width
  const simCap = capsuleFromRadius(simR)
  const simVerticalSpacing = simCap.height + 12
  const diffVerticalSpacing = diffCap.height + 10

  const D = simR + 2 * columnSpacing + 2 * topicR
  const requiredWidth = 2 * D + maxLeftW + maxRightW + padding * 2
  const centerX = requiredWidth / 2
  const simX = centerX
  const leftTopicX = centerX - simR - columnSpacing - topicR
  const rightTopicX = centerX + simR + columnSpacing + topicR
  const leftDiffX = centerX - D
  const rightDiffX = centerX + D + maxRightW

  const simColHeight = simCount > 0 ? (simCount - 1) * simVerticalSpacing + simCap.height : 0
  const maxDiffCount = Math.max(leftDiffCount, rightDiffCount)
  const diffColHeight =
    maxDiffCount > 0 ? (maxDiffCount - 1) * diffVerticalSpacing + diffCap.height : 0
  const maxColHeight = Math.max(simColHeight, diffColHeight, topicR * 2)
  const requiredHeight = maxColHeight + padding * 2
  const centerY = requiredHeight / 2

  return {
    centerX,
    centerY,
    leftDiffX,
    leftTopicX,
    simX,
    rightTopicX,
    rightDiffX,
    simVerticalSpacing,
    diffVerticalSpacing,
    simCap,
    diffCap,
  }
}

export interface DoubleBubbleNodeSizes {
  leftTopicR?: number
  rightTopicR?: number
  simRadii?: number[]
  leftDiffRadii?: number[]
  rightDiffRadii?: number[]
}

/**
 * Load double bubble map spec into diagram nodes and connections.
 * Uses text-adaptive radii, capsule dimensions, and _doubleBubbleMapNodeSizes for empty nodes.
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

  const sizes = (spec._doubleBubbleMapNodeSizes as DoubleBubbleNodeSizes | undefined) || {}

  const padding = DEFAULT_PADDING

  // Topic radii (text-adaptive; empty uses saved)
  const leftTopicR = doubleBubbleRequiredRadius(left, {
    isTopic: true,
    savedRadius: sizes.leftTopicR,
  })
  const rightTopicR = doubleBubbleRequiredRadius(right, {
    isTopic: true,
    savedRadius: sizes.rightTopicR,
  })
  const topicR = Math.max(leftTopicR, rightTopicR)

  // Similarity radii → unified simR
  const simRadii = similarities.map((t, i) =>
    doubleBubbleRequiredRadius(t, { isTopic: false, savedRadius: sizes.simRadii?.[i] })
  )
  const simR = simRadii.length > 0 ? Math.max(...simRadii) : 30

  // Difference radii → unified diffR (both sides)
  const leftDiffRadii = leftDifferences.map((t, i) =>
    doubleBubbleDiffRequiredRadius(t, sizes.leftDiffRadii?.[i])
  )
  const rightDiffRadii = rightDifferences.map((t, i) =>
    doubleBubbleDiffRequiredRadius(t, sizes.rightDiffRadii?.[i])
  )
  const leftDiffR = leftDiffRadii.length > 0 ? Math.max(...leftDiffRadii) : 30
  const rightDiffR = rightDiffRadii.length > 0 ? Math.max(...rightDiffRadii) : 30
  const diffR = Math.max(leftDiffR, rightDiffR)

  const layout = computeLayout(
    similarities.length,
    leftDifferences.length,
    rightDifferences.length,
    padding,
    topicR,
    simR,
    diffR
  )

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Left topic (circle)
  nodes.push({
    id: 'left-topic',
    text: left,
    type: 'topic',
    position: { x: layout.leftTopicX - topicR, y: layout.centerY - topicR },
    style: { size: topicR * 2, noWrap: true },
  })

  // Right topic (circle)
  nodes.push({
    id: 'right-topic',
    text: right,
    type: 'topic',
    position: { x: layout.rightTopicX - topicR, y: layout.centerY - topicR },
    style: { size: topicR * 2, noWrap: true },
  })

  // Similarities (capsules)
  const simCount = similarities.length
  const simColHeight =
    simCount > 0 ? (simCount - 1) * layout.simVerticalSpacing + layout.simCap.height : 0
  const simStartY = layout.centerY - simColHeight / 2 + layout.simCap.height / 2
  similarities.forEach((sim, index) => {
    const cy = simStartY + index * layout.simVerticalSpacing
    nodes.push({
      id: `similarity-${index}`,
      text: sim,
      type: 'bubble',
      position: {
        x: layout.simX - layout.simCap.width / 2,
        y: cy - layout.simCap.height / 2,
      },
      style: {
        width: layout.simCap.width,
        height: layout.simCap.height,
        size: simR * 2,
        noWrap: true,
      },
    })
    connections.push(
      {
        id: `edge-left-sim-${index}`,
        source: 'left-topic',
        target: `similarity-${index}`,
        edgeType: 'curved',
        sourcePosition: 'right',
        targetPosition: 'left',
        sourceHandle: 'right',
        targetHandle: 'left',
      },
      {
        id: `edge-right-sim-${index}`,
        source: 'right-topic',
        target: `similarity-${index}`,
        edgeType: 'curved',
        sourcePosition: 'left',
        targetPosition: 'right',
        sourceHandle: 'left',
        targetHandle: 'right',
      }
    )
  })

  // Left differences (capsules)
  const maxDiffCount = Math.max(leftDifferences.length, rightDifferences.length)
  const diffColHeight =
    maxDiffCount > 0
      ? (maxDiffCount - 1) * layout.diffVerticalSpacing + layout.diffCap.height
      : 0
  const diffStartY = layout.centerY - diffColHeight / 2 + layout.diffCap.height / 2

  leftDifferences.forEach((diff, index) => {
    const cy = diffStartY + index * layout.diffVerticalSpacing
    nodes.push({
      id: `left-diff-${index}`,
      text: diff,
      type: 'bubble',
      position: {
        x: layout.leftDiffX - layout.diffCap.width,
        y: cy - layout.diffCap.height / 2,
      },
      style: {
        width: layout.diffCap.width,
        height: layout.diffCap.height,
        size: diffR * 2,
        noWrap: true,
      },
    })
    connections.push({
      id: `edge-left-diff-${index}`,
      source: 'left-topic',
      target: `left-diff-${index}`,
      edgeType: 'curved',
      sourcePosition: 'left',
      targetPosition: 'right',
      sourceHandle: 'left',
      targetHandle: 'right',
    })
  })

  rightDifferences.forEach((diff, index) => {
    const cy = diffStartY + index * layout.diffVerticalSpacing
    nodes.push({
      id: `right-diff-${index}`,
      text: diff,
      type: 'bubble',
      position: {
        x: layout.rightDiffX - layout.diffCap.width,
        y: cy - layout.diffCap.height / 2,
      },
      style: {
        width: layout.diffCap.width,
        height: layout.diffCap.height,
        size: diffR * 2,
        noWrap: true,
      },
    })
    connections.push({
      id: `edge-right-diff-${index}`,
      source: 'right-topic',
      target: `right-diff-${index}`,
      edgeType: 'curved',
      sourcePosition: 'right',
      targetPosition: 'left',
      sourceHandle: 'right',
      targetHandle: 'left',
    })
  })

  return { nodes, connections }
}
