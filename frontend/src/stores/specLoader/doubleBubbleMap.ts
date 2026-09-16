/**
 * Double Bubble Map Loader
 * Text-adaptive radii, capsule dimensions, layout aligned with useDoubleBubbleMap.
 * Supports _doubleBubbleMapNodeSizes for empty-node saved radii.
 * _doubleBubbleMeasureHints (fontSize/fontWeight per node id) drives radii when users customize typography.
 * Similarities stay default blue; difference pairs use mindmap color palette (same color for left-diff and right-diff).
 */
import {
  DEFAULT_COLUMN_SPACING,
  DEFAULT_PADDING,
  DOUBLE_BUBBLE_MAX_CAPSULE_HEIGHT,
} from '@/composables/diagrams/layoutConfig'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'
import {
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
  DOUBLE_BUBBLE_UID_DATA_KEY,
  stampDoubleBubbleData,
  takeDoubleBubbleMapStableId,
} from '@/utils/doubleBubbleMapIdentity'

import { doubleBubbleDiffRequiredRadius, doubleBubbleRequiredRadius } from './textMeasurement'
import type { SpecLoaderResult } from './types'

/** Capsule dimensions from radius (same formula as useDoubleBubbleMap) */
function capsuleFromRadius(radius: number): { width: number; height: number; diameter: number } {
  const diameter = radius * 2
  const height = Math.min(Math.round(diameter * 0.56), DOUBLE_BUBBLE_MAX_CAPSULE_HEIGHT)
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

export interface DoubleBubbleMeasureHint {
  fontSize?: number
  fontWeight?: string
}

type DoubleBubbleSpecItem = string | { id?: string; text?: string; name?: string }

function normalizeDoubleBubbleItems(raw: unknown): Array<{ id?: string; text: string }> {
  if (!Array.isArray(raw)) return []
  return raw.map((item) => {
    if (typeof item === 'string') return { text: item }
    if (item && typeof item === 'object') {
      const record = item as { id?: string; text?: string; name?: string }
      return {
        id: typeof record.id === 'string' ? record.id : undefined,
        text: record.text ?? record.name ?? '',
      }
    }
    return { text: '' }
  })
}

/**
 * Load double bubble map spec into diagram nodes and connections.
 * Uses text-adaptive radii, capsule dimensions, and _doubleBubbleMapNodeSizes for empty nodes.
 */
export function loadDoubleBubbleMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const left = (spec.left as string) || (spec.topic1 as string) || ''
  const right = (spec.right as string) || (spec.topic2 as string) || ''
  const similarities = normalizeDoubleBubbleItems(spec.similarities ?? spec.shared)
  const leftDifferences = normalizeDoubleBubbleItems(
    spec.leftDifferences ?? spec.left_differences ?? spec.left_unique
  )
  const rightDifferences = normalizeDoubleBubbleItems(
    spec.rightDifferences ?? spec.right_differences ?? spec.right_unique
  )
  const claimedIds = new Set<string>([DOUBLE_BUBBLE_LEFT_TOPIC_ID, DOUBLE_BUBBLE_RIGHT_TOPIC_ID])

  const sizes = (spec._doubleBubbleMapNodeSizes as DoubleBubbleNodeSizes | undefined) || {}
  const hints =
    (spec._doubleBubbleMeasureHints as Record<string, DoubleBubbleMeasureHint> | undefined) || {}

  const padding = DEFAULT_PADDING

  const leftHint = hints[DOUBLE_BUBBLE_LEFT_TOPIC_ID]
  const rightHint = hints[DOUBLE_BUBBLE_RIGHT_TOPIC_ID]

  // Topic radii (text-adaptive; empty uses saved)
  const leftTopicR = doubleBubbleRequiredRadius(left, {
    isTopic: true,
    savedRadius: sizes.leftTopicR,
    fontSize: leftHint?.fontSize,
    fontWeight: leftHint?.fontWeight,
  })
  const rightTopicR = doubleBubbleRequiredRadius(right, {
    isTopic: true,
    savedRadius: sizes.rightTopicR,
    fontSize: rightHint?.fontSize,
    fontWeight: rightHint?.fontWeight,
  })
  const topicR = Math.max(leftTopicR, rightTopicR)

  // Similarity radii → unified simR
  const simRadii = similarities.map((item, i) => {
    const h = hints[item.id ?? `similarity-${i}`]
    return doubleBubbleRequiredRadius(item.text, {
      isTopic: false,
      savedRadius: sizes.simRadii?.[i],
      fontSize: h?.fontSize,
      fontWeight: h?.fontWeight,
    })
  })
  const simR = simRadii.length > 0 ? Math.max(...simRadii) : 30

  // Difference radii → unified diffR (both sides)
  const leftDiffRadii = leftDifferences.map((item, i) => {
    const h = hints[item.id ?? `left-diff-${i}`]
    return doubleBubbleDiffRequiredRadius(item.text, sizes.leftDiffRadii?.[i], {
      fontSize: h?.fontSize,
      fontWeight: h?.fontWeight,
    })
  })
  const rightDiffRadii = rightDifferences.map((item, i) => {
    const h = hints[item.id ?? `right-diff-${i}`]
    return doubleBubbleDiffRequiredRadius(item.text, sizes.rightDiffRadii?.[i], {
      fontSize: h?.fontSize,
      fontWeight: h?.fontWeight,
    })
  })
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
    id: DOUBLE_BUBBLE_LEFT_TOPIC_ID,
    text: left,
    type: 'topic',
    position: { x: layout.leftTopicX - topicR, y: layout.centerY - topicR },
    style: { size: topicR * 2, noWrap: true },
  })

  // Right topic (circle)
  nodes.push({
    id: DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
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
    const simId = takeDoubleBubbleMapStableId(claimedIds, sim.id)
    nodes.push({
      id: simId,
      text: sim.text,
      type: 'bubble',
      position: {
        x: layout.simX - layout.simCap.width / 2,
        y: cy - layout.simCap.height / 2,
      },
      data: stampDoubleBubbleData('similarity', index, {
        [DOUBLE_BUBBLE_UID_DATA_KEY]: simId,
      }),
      style: {
        width: layout.simCap.width,
        height: layout.simCap.height,
        size: simR * 2,
        noWrap: true,
      },
    })
    connections.push(
      {
        id: `edge-${DOUBLE_BUBBLE_LEFT_TOPIC_ID}-${simId}`,
        source: DOUBLE_BUBBLE_LEFT_TOPIC_ID,
        target: simId,
        edgeType: 'curved',
        sourcePosition: 'right',
        targetPosition: 'left',
        sourceHandle: 'right',
        targetHandle: 'left',
      },
      {
        id: `edge-${DOUBLE_BUBBLE_RIGHT_TOPIC_ID}-${simId}`,
        source: DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
        target: simId,
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
    maxDiffCount > 0 ? (maxDiffCount - 1) * layout.diffVerticalSpacing + layout.diffCap.height : 0
  const diffStartY = layout.centerY - diffColHeight / 2 + layout.diffCap.height / 2

  leftDifferences.forEach((diff, index) => {
    const cy = diffStartY + index * layout.diffVerticalSpacing
    const pairColor = getMindmapBranchColor(index)
    const leftId = takeDoubleBubbleMapStableId(claimedIds, diff.id)
    nodes.push({
      id: leftId,
      text: diff.text,
      type: 'bubble',
      position: {
        x: layout.leftDiffX - layout.diffCap.width,
        y: cy - layout.diffCap.height / 2,
      },
      data: stampDoubleBubbleData('leftDiff', index, {
        [DOUBLE_BUBBLE_UID_DATA_KEY]: leftId,
      }),
      style: {
        width: layout.diffCap.width,
        height: layout.diffCap.height,
        size: diffR * 2,
        noWrap: true,
        backgroundColor: pairColor.fill,
        borderColor: pairColor.border,
      },
    })
    connections.push({
      id: `edge-${DOUBLE_BUBBLE_LEFT_TOPIC_ID}-${leftId}`,
      source: DOUBLE_BUBBLE_LEFT_TOPIC_ID,
      target: leftId,
      edgeType: 'curved',
      sourcePosition: 'left',
      targetPosition: 'right',
      sourceHandle: 'left',
      targetHandle: 'right',
      style: { strokeColor: pairColor.border },
    })
  })

  rightDifferences.forEach((diff, index) => {
    const cy = diffStartY + index * layout.diffVerticalSpacing
    const pairColor = getMindmapBranchColor(index)
    const rightId = takeDoubleBubbleMapStableId(claimedIds, diff.id)
    nodes.push({
      id: rightId,
      text: diff.text,
      type: 'bubble',
      position: {
        x: layout.rightDiffX - layout.diffCap.width,
        y: cy - layout.diffCap.height / 2,
      },
      data: stampDoubleBubbleData('rightDiff', index, {
        [DOUBLE_BUBBLE_UID_DATA_KEY]: rightId,
      }),
      style: {
        width: layout.diffCap.width,
        height: layout.diffCap.height,
        size: diffR * 2,
        noWrap: true,
        backgroundColor: pairColor.fill,
        borderColor: pairColor.border,
      },
    })
    connections.push({
      id: `edge-${DOUBLE_BUBBLE_RIGHT_TOPIC_ID}-${rightId}`,
      source: DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
      target: rightId,
      edgeType: 'curved',
      sourcePosition: 'right',
      targetPosition: 'left',
      sourceHandle: 'right',
      targetHandle: 'left',
      style: { strokeColor: pairColor.border },
    })
  })

  return { nodes, connections }
}
