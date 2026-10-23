/**
 * Double Bubble Map Loader
 * Text-adaptive radii and capsule dimensions. This loader is the layout source.
 * Supports _doubleBubbleMapNodeSizes for empty-node saved radii.
 * _doubleBubbleMeasureHints (fontSize/fontWeight per node id) drives radii when users customize typography.
 * Similarities stay default blue; difference pairs use mindmap color palette (same color for left-diff and right-diff).
 */
import {
  DEFAULT_COLUMN_SPACING,
  DEFAULT_PADDING,
  DOUBLE_BUBBLE_MAX_CAPSULE_HEIGHT,
} from '@/composables/diagrams/layoutConfig'
import { mirrorString, mirrorStringList, readSecondaryMirror } from '@/diagramBilingual/mirror'
import type { Connection, DiagramNode, MindMapAdornmentsByPath } from '@/types'
import {
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
  DOUBLE_BUBBLE_UID_DATA_KEY,
  readDoubleBubbleIndex,
  readDoubleBubbleRole,
  stampDoubleBubbleData,
  takeDoubleBubbleMapStableId,
} from '@/utils/doubleBubbleMapIdentity'
import { textWithIconAdornment } from '@/utils/mindMapAdornments'
import { thinkingMapStampedBranchColor } from '@/utils/thinkingMapChrome'

import { learningSheetLayoutSecondary, learningSheetLayoutText } from './mindMapLearningSheet'
import { doubleBubbleDiffRequiredRadius, doubleBubbleRequiredRadius } from './textMeasurement'
import type { SpecLoaderResult } from './types'

/** Vertical center of the first item when a column is centered on `centerY`. */
function columnAnchorY(
  count: number,
  centerY: number,
  spacing: number,
  itemHeight: number
): number {
  if (count <= 0) return centerY
  const colHeight = (count - 1) * spacing + itemHeight
  return centerY - colHeight / 2 + itemHeight / 2
}

/** Capsule box from a text radius. Width tracks the diameter; height is capped. */
function capsuleFromRadius(radius: number): { width: number; height: number } {
  const diameter = radius * 2
  const height = Math.min(Math.round(diameter * 0.56), DOUBLE_BUBBLE_MAX_CAPSULE_HEIGHT)
  return {
    width: Math.round(diameter * 1.22),
    height,
  }
}

function columnRadius(radii: number[]): number {
  return radii.length > 0 ? Math.max(...radii) : 0
}

/** Layout from per-column radii. Difference columns size independently. */
function computeLayout(
  simCount: number,
  leftDiffCount: number,
  rightDiffCount: number,
  padding: number,
  topicR: number,
  simR: number,
  leftDiffR: number,
  rightDiffR: number
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
  leftDiffCap: { width: number; height: number }
  rightDiffCap: { width: number; height: number }
  diffSlotHeight: number
} {
  const columnSpacing = DEFAULT_COLUMN_SPACING
  const leftDiffCap = capsuleFromRadius(leftDiffR)
  const rightDiffCap = capsuleFromRadius(rightDiffR)
  const maxLeftW = leftDiffCount > 0 ? leftDiffCap.width : 0
  const maxRightW = rightDiffCount > 0 ? rightDiffCap.width : 0
  const simCap = capsuleFromRadius(simR)
  const simVerticalSpacing = simCap.height + 12
  // Shared row pitch so an equal-length pair stays on one horizontal center.
  // An empty column contributes no height.
  const diffSlotHeight = Math.max(
    leftDiffCount > 0 ? leftDiffCap.height : 0,
    rightDiffCount > 0 ? rightDiffCap.height : 0
  )
  const diffVerticalSpacing = diffSlotHeight + 10

  const D = simR + 2 * columnSpacing + 2 * topicR
  // Left difference edge sits on `padding` when that column exists.
  // Equal widths match a centered origin; a wider left column stays at x >= padding.
  const centerX = padding + D + maxLeftW
  const simX = centerX
  const leftTopicX = centerX - simR - columnSpacing - topicR
  const rightTopicX = centerX + simR + columnSpacing + topicR
  const leftDiffX = centerX - D
  const rightDiffX = centerX + D + maxRightW

  const simColHeight = simCount > 0 ? (simCount - 1) * simVerticalSpacing + simCap.height : 0
  const maxDiffCount = Math.max(leftDiffCount, rightDiffCount)
  const diffColHeight =
    maxDiffCount > 0 ? (maxDiffCount - 1) * diffVerticalSpacing + diffSlotHeight : 0
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
    leftDiffCap,
    rightDiffCap,
    diffSlotHeight,
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
      const record = item as Exclude<DoubleBubbleSpecItem, string>
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
  const mirror = readSecondaryMirror(spec)
  const leftSecondary = mirrorString(mirror, 'left')
  const rightSecondary = mirrorString(mirror, 'right')
  const similaritySecondary = mirrorStringList(mirror, 'similarities')
  const leftDiffSecondary = mirrorStringList(mirror, 'left_differences').length
    ? mirrorStringList(mirror, 'left_differences')
    : mirrorStringList(mirror, 'leftDifferences')
  const rightDiffSecondary = mirrorStringList(mirror, 'right_differences').length
    ? mirrorStringList(mirror, 'right_differences')
    : mirrorStringList(mirror, 'rightDifferences')

  const leftTopicR = doubleBubbleRequiredRadius(left, {
    isTopic: true,
    savedRadius: sizes.leftTopicR,
    fontSize: leftHint?.fontSize,
    fontWeight: leftHint?.fontWeight,
    secondary: leftSecondary,
  })
  const rightTopicR = doubleBubbleRequiredRadius(right, {
    isTopic: true,
    savedRadius: sizes.rightTopicR,
    fontSize: rightHint?.fontSize,
    fontWeight: rightHint?.fontWeight,
    secondary: rightSecondary,
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
      secondary: similaritySecondary[i],
    })
  })
  const simR = simRadii.length > 0 ? Math.max(...simRadii) : 30

  // Each difference column uses its own longest label. The other side does not stretch it.
  const leftDiffRadii = leftDifferences.map((item, i) => {
    const h = hints[item.id ?? `left-diff-${i}`]
    return doubleBubbleDiffRequiredRadius(item.text, sizes.leftDiffRadii?.[i], {
      fontSize: h?.fontSize,
      fontWeight: h?.fontWeight,
      secondary: leftDiffSecondary[i],
    })
  })
  const rightDiffRadii = rightDifferences.map((item, i) => {
    const h = hints[item.id ?? `right-diff-${i}`]
    return doubleBubbleDiffRequiredRadius(item.text, sizes.rightDiffRadii?.[i], {
      fontSize: h?.fontSize,
      fontWeight: h?.fontWeight,
      secondary: rightDiffSecondary[i],
    })
  })
  const leftDiffR = columnRadius(leftDiffRadii)
  const rightDiffR = columnRadius(rightDiffRadii)

  const layout = computeLayout(
    similarities.length,
    leftDifferences.length,
    rightDifferences.length,
    padding,
    topicR,
    simR,
    leftDiffR,
    rightDiffR
  )

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Left topic (circle)
  nodes.push({
    id: DOUBLE_BUBBLE_LEFT_TOPIC_ID,
    text: left,
    ...(leftSecondary ? { textSecondary: leftSecondary } : {}),
    type: 'topic',
    position: { x: layout.leftTopicX - topicR, y: layout.centerY - topicR },
    style: { size: topicR * 2, noWrap: true },
  })

  // Right topic (circle)
  nodes.push({
    id: DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
    text: right,
    ...(rightSecondary ? { textSecondary: rightSecondary } : {}),
    type: 'topic',
    position: { x: layout.rightTopicX - topicR, y: layout.centerY - topicR },
    style: { size: topicR * 2, noWrap: true },
  })

  // Similarities (capsules)
  const simStartY = columnAnchorY(
    similarities.length,
    layout.centerY,
    layout.simVerticalSpacing,
    layout.simCap.height
  )
  similarities.forEach((sim, index) => {
    const cy = simStartY + index * layout.simVerticalSpacing
    const simId = takeDoubleBubbleMapStableId(claimedIds, sim.id)
    nodes.push({
      id: simId,
      text: sim.text,
      ...(similaritySecondary[index] ? { textSecondary: similaritySecondary[index] } : {}),
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

  // Each difference column centers on its own count so a shorter side
  // does not stay pinned to the top of the taller side.
  const leftDiffStartY = columnAnchorY(
    leftDifferences.length,
    layout.centerY,
    layout.diffVerticalSpacing,
    layout.diffSlotHeight
  )
  const rightDiffStartY = columnAnchorY(
    rightDifferences.length,
    layout.centerY,
    layout.diffVerticalSpacing,
    layout.diffSlotHeight
  )

  leftDifferences.forEach((diff, index) => {
    const cy = leftDiffStartY + index * layout.diffVerticalSpacing
    const leftGloss = leftDiffSecondary[index]
    const pairColor = thinkingMapStampedBranchColor(index)
    const leftId = takeDoubleBubbleMapStableId(claimedIds, diff.id)
    nodes.push({
      id: leftId,
      text: diff.text,
      ...(leftGloss ? { textSecondary: leftGloss } : {}),
      type: 'bubble',
      position: {
        x: layout.leftDiffX - layout.leftDiffCap.width,
        y: cy - layout.leftDiffCap.height / 2,
      },
      data: stampDoubleBubbleData('leftDiff', index, {
        [DOUBLE_BUBBLE_UID_DATA_KEY]: leftId,
      }),
      style: {
        width: layout.leftDiffCap.width,
        height: layout.leftDiffCap.height,
        size: leftDiffR * 2,
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
    const cy = rightDiffStartY + index * layout.diffVerticalSpacing
    const rightGloss = rightDiffSecondary[index]
    const pairColor = thinkingMapStampedBranchColor(index)
    const rightId = takeDoubleBubbleMapStableId(claimedIds, diff.id)
    nodes.push({
      id: rightId,
      text: diff.text,
      ...(rightGloss ? { textSecondary: rightGloss } : {}),
      type: 'bubble',
      position: {
        x: layout.rightDiffX - layout.rightDiffCap.width,
        y: cy - layout.rightDiffCap.height / 2,
      },
      data: stampDoubleBubbleData('rightDiff', index, {
        [DOUBLE_BUBBLE_UID_DATA_KEY]: rightId,
      }),
      style: {
        width: layout.rightDiffCap.width,
        height: layout.rightDiffCap.height,
        size: rightDiffR * 2,
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

function doubleBubbleMeasureFont(node: DiagramNode): { fontSize?: number; fontWeight?: string } {
  const fontSize = typeof node.style?.fontSize === 'number' ? node.style.fontSize : undefined
  const weight = node.style?.fontWeight
  const fontWeight = typeof weight === 'string' ? weight : undefined
  return { fontSize, fontWeight }
}

/** Radius of the label with a leading icon, matching a typed emoji. */
function doubleBubbleNodeRadius(node: DiagramNode, adornments: MindMapAdornmentsByPath): number {
  const text = textWithIconAdornment(learningSheetLayoutText(node), adornments[node.id])
  const { fontSize, fontWeight } = doubleBubbleMeasureFont(node)
  const secondary = learningSheetLayoutSecondary(node)
  const isTopic =
    node.id === DOUBLE_BUBBLE_LEFT_TOPIC_ID || node.id === DOUBLE_BUBBLE_RIGHT_TOPIC_ID
  if (isTopic || readDoubleBubbleRole(node) === 'similarity') {
    return doubleBubbleRequiredRadius(text, { isTopic, fontSize, fontWeight, secondary })
  }
  return doubleBubbleDiffRequiredRadius(text, undefined, { fontSize, fontWeight, secondary })
}

function nodesByIndex(list: DiagramNode[]): DiagramNode[] {
  return [...list].sort((a, b) => readDoubleBubbleIndex(a) - readDoubleBubbleIndex(b))
}

/**
 * Grow double-bubble disks when an icon is part of the label.
 * Columns stay put when the current radius already fits that string.
 */
export function expandDoubleBubbleNodesForIcons(
  nodes: DiagramNode[],
  adornments: MindMapAdornmentsByPath = {}
): DiagramNode[] {
  if (!nodes.some((node) => (adornments[node.id]?.icon ?? '').trim())) return nodes

  const leftTopic = nodes.find((node) => node.id === DOUBLE_BUBBLE_LEFT_TOPIC_ID)
  const rightTopic = nodes.find((node) => node.id === DOUBLE_BUBBLE_RIGHT_TOPIC_ID)
  const similarities = nodesByIndex(
    nodes.filter((node) => readDoubleBubbleRole(node) === 'similarity')
  )
  const leftDiffs = nodesByIndex(nodes.filter((node) => readDoubleBubbleRole(node) === 'leftDiff'))
  const rightDiffs = nodesByIndex(
    nodes.filter((node) => readDoubleBubbleRole(node) === 'rightDiff')
  )

  const halfSize = (node: DiagramNode | undefined): number => (node?.style?.size ?? 0) / 2
  const grownRadius = (node: DiagramNode): number =>
    Math.max(doubleBubbleNodeRadius(node, adornments), halfSize(node))
  const topicR = Math.max(
    leftTopic ? grownRadius(leftTopic) : 0,
    rightTopic ? grownRadius(rightTopic) : 0
  )
  const simR = similarities.length > 0 ? Math.max(...similarities.map(grownRadius)) : 30
  const leftDiffR = columnRadius(leftDiffs.map(grownRadius))
  const rightDiffR = columnRadius(rightDiffs.map(grownRadius))

  const columnHalf = (list: DiagramNode[]): number =>
    list.reduce((max, node) => Math.max(max, halfSize(node)), 0)
  const fits =
    topicR <= Math.max(halfSize(leftTopic), halfSize(rightTopic)) + 0.5 &&
    simR <= columnHalf(similarities) + 0.5 &&
    leftDiffR <= columnHalf(leftDiffs) + 0.5 &&
    rightDiffR <= columnHalf(rightDiffs) + 0.5
  if (fits) return nodes

  const layout = computeLayout(
    similarities.length,
    leftDiffs.length,
    rightDiffs.length,
    DEFAULT_PADDING,
    topicR,
    simR,
    leftDiffR,
    rightDiffR
  )
  const placed = new Map<string, Pick<DiagramNode, 'position' | 'style'>>()
  const place = (node: DiagramNode, x: number, y: number, style: DiagramNode['style']): void => {
    placed.set(node.id, { position: { x, y }, style })
  }

  if (leftTopic) {
    place(leftTopic, layout.leftTopicX - topicR, layout.centerY - topicR, {
      ...leftTopic.style,
      size: topicR * 2,
      noWrap: true,
    })
  }
  if (rightTopic) {
    place(rightTopic, layout.rightTopicX - topicR, layout.centerY - topicR, {
      ...rightTopic.style,
      size: topicR * 2,
      noWrap: true,
    })
  }

  const simStartY = columnAnchorY(
    similarities.length,
    layout.centerY,
    layout.simVerticalSpacing,
    layout.simCap.height
  )
  similarities.forEach((node, index) => {
    const cy = simStartY + index * layout.simVerticalSpacing
    place(node, layout.simX - layout.simCap.width / 2, cy - layout.simCap.height / 2, {
      ...node.style,
      width: layout.simCap.width,
      height: layout.simCap.height,
      size: simR * 2,
      noWrap: true,
    })
  })

  const leftDiffStartY = columnAnchorY(
    leftDiffs.length,
    layout.centerY,
    layout.diffVerticalSpacing,
    layout.diffSlotHeight
  )
  const rightDiffStartY = columnAnchorY(
    rightDiffs.length,
    layout.centerY,
    layout.diffVerticalSpacing,
    layout.diffSlotHeight
  )
  leftDiffs.forEach((node, index) => {
    const cy = leftDiffStartY + index * layout.diffVerticalSpacing
    place(node, layout.leftDiffX - layout.leftDiffCap.width, cy - layout.leftDiffCap.height / 2, {
      ...node.style,
      width: layout.leftDiffCap.width,
      height: layout.leftDiffCap.height,
      size: leftDiffR * 2,
      noWrap: true,
    })
  })
  rightDiffs.forEach((node, index) => {
    const cy = rightDiffStartY + index * layout.diffVerticalSpacing
    place(
      node,
      layout.rightDiffX - layout.rightDiffCap.width,
      cy - layout.rightDiffCap.height / 2,
      {
        ...node.style,
        width: layout.rightDiffCap.width,
        height: layout.rightDiffCap.height,
        size: rightDiffR * 2,
        noWrap: true,
      }
    )
  })

  return nodes.map((node) => {
    const next = placed.get(node.id)
    if (!next) return node
    return { ...node, position: next.position, style: next.style }
  })
}
