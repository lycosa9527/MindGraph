/**
 * Double-bubble positions follow measured boxes once a node carries an image.
 * Text-only maps keep the loader geometry. An image node uses the larger of the
 * DOM box and the text box plus the shared image frame, then columns restack.
 */
import { DEFAULT_COLUMN_SPACING, DEFAULT_PADDING } from '@/composables/diagrams/layoutConfig'
import type { DiagramNode } from '@/types'
import {
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
  readDoubleBubbleIndex,
  readDoubleBubbleRole,
} from '@/utils/doubleBubbleMapIdentity'
import {
  NODE_IMAGE_FRAME_MIN_WIDTH,
  NODE_IMAGE_GAP,
  NODE_IMAGE_THUMB_HEIGHT,
} from '@/utils/nodeImageFrame'

const SIM_GAP = 12
const DIFF_GAP = 10

type Box = { width: number; height: number }

function positive(value: unknown): number | undefined {
  return typeof value === 'number' && value > 0 ? value : undefined
}

function textBox(node: DiagramNode): Box {
  const size = positive(node.style?.size)
  const width = positive(node.style?.width) ?? size ?? 80
  const height = positive(node.style?.height) ?? size ?? 40
  return { width, height }
}

function resolvedBox(
  node: DiagramNode,
  nodeDimensions: Record<string, { width: number; height: number }>,
  imageNodeIds: ReadonlySet<string>
): Box {
  const text = textBox(node)
  const measured = nodeDimensions[node.id]
  let width = measured && measured.width > 0 ? measured.width : text.width
  let height = measured && measured.height > 0 ? measured.height : text.height
  if (imageNodeIds.has(node.id)) {
    width = Math.max(width, NODE_IMAGE_FRAME_MIN_WIDTH)
    height = Math.max(height, text.height + NODE_IMAGE_THUMB_HEIGHT + NODE_IMAGE_GAP)
  }
  return { width, height }
}

function columnHeight(boxes: Box[], gap: number): number {
  if (boxes.length === 0) return 0
  const sum = boxes.reduce((total, box) => total + box.height, 0)
  return sum + gap * (boxes.length - 1)
}

function placeColumn(
  nodes: DiagramNode[],
  boxes: Map<string, Box>,
  columnLeft: number,
  columnWidth: number,
  centerY: number,
  gap: number,
  align: 'left' | 'center' | 'right'
): DiagramNode[] {
  const heights = nodes.map((node) => boxes.get(node.id)?.height ?? 0)
  const total = columnHeight(
    heights.map((height) => ({ width: 0, height })),
    gap
  )
  let y = centerY - total / 2
  return nodes.map((node) => {
    const box = boxes.get(node.id) ?? { width: columnWidth, height: 0 }
    let x = columnLeft
    if (align === 'center') x = columnLeft + (columnWidth - box.width) / 2
    if (align === 'right') x = columnLeft + columnWidth - box.width
    const placed: DiagramNode = {
      ...node,
      position: { x: Math.round(x), y: Math.round(y) },
    }
    y += box.height + gap
    return placed
  })
}

/**
 * Restack a double bubble map around image nodes.
 * Returns the input array unchanged when no node has an image.
 */
export function recalculateDoubleBubbleMapLayout(
  nodes: DiagramNode[],
  nodeDimensions: Record<string, { width: number; height: number }> = {},
  imageNodeIds: ReadonlySet<string> = new Set()
): DiagramNode[] {
  if (imageNodeIds.size === 0 || nodes.length === 0) return nodes

  const boxes = new Map<string, Box>()
  for (const node of nodes) {
    boxes.set(node.id, resolvedBox(node, nodeDimensions, imageNodeIds))
  }

  const byRole = (role: 'similarity' | 'leftDiff' | 'rightDiff') =>
    nodes
      .filter((node) => readDoubleBubbleRole(node) === role)
      .sort((a, b) => readDoubleBubbleIndex(a) - readDoubleBubbleIndex(b))

  const leftTopic = nodes.find((node) => node.id === DOUBLE_BUBBLE_LEFT_TOPIC_ID)
  const rightTopic = nodes.find((node) => node.id === DOUBLE_BUBBLE_RIGHT_TOPIC_ID)
  const similarities = byRole('similarity')
  const leftDiffs = byRole('leftDiff')
  const rightDiffs = byRole('rightDiff')

  const widthOf = (node: DiagramNode | undefined): number =>
    node ? (boxes.get(node.id)?.width ?? 0) : 0
  const maxWidth = (list: DiagramNode[]): number =>
    list.reduce((max, node) => Math.max(max, widthOf(node)), 0)

  const leftW = maxWidth(leftDiffs)
  const simW = maxWidth(similarities)
  const rightW = maxWidth(rightDiffs)
  const leftTopicW = widthOf(leftTopic)
  const rightTopicW = widthOf(rightTopic)

  const leftBoxes = leftDiffs.map((node) => boxes.get(node.id) ?? { width: 0, height: 0 })
  const simBoxes = similarities.map((node) => boxes.get(node.id) ?? { width: 0, height: 0 })
  const rightBoxes = rightDiffs.map((node) => boxes.get(node.id) ?? { width: 0, height: 0 })
  const topicH = Math.max(
    leftTopic ? (boxes.get(leftTopic.id)?.height ?? 0) : 0,
    rightTopic ? (boxes.get(rightTopic.id)?.height ?? 0) : 0
  )
  const maxCol = Math.max(
    columnHeight(leftBoxes, DIFF_GAP),
    columnHeight(simBoxes, SIM_GAP),
    columnHeight(rightBoxes, DIFF_GAP),
    topicH
  )
  const centerY = maxCol / 2 + DEFAULT_PADDING

  let cursor = DEFAULT_PADDING
  const placed = new Map<string, DiagramNode>()

  if (leftDiffs.length > 0) {
    for (const node of placeColumn(leftDiffs, boxes, cursor, leftW, centerY, DIFF_GAP, 'right')) {
      placed.set(node.id, node)
    }
    cursor += leftW + DEFAULT_COLUMN_SPACING
  }

  if (leftTopic) {
    const box = boxes.get(leftTopic.id) ?? { width: leftTopicW, height: topicH }
    placed.set(leftTopic.id, {
      ...leftTopic,
      position: { x: Math.round(cursor), y: Math.round(centerY - box.height / 2) },
    })
    cursor += box.width + DEFAULT_COLUMN_SPACING
  }

  if (similarities.length > 0) {
    for (const node of placeColumn(similarities, boxes, cursor, simW, centerY, SIM_GAP, 'center')) {
      placed.set(node.id, node)
    }
    cursor += simW + DEFAULT_COLUMN_SPACING
  }

  if (rightTopic) {
    const box = boxes.get(rightTopic.id) ?? { width: rightTopicW, height: topicH }
    placed.set(rightTopic.id, {
      ...rightTopic,
      position: { x: Math.round(cursor), y: Math.round(centerY - box.height / 2) },
    })
    cursor += box.width + DEFAULT_COLUMN_SPACING
  }

  if (rightDiffs.length > 0) {
    for (const node of placeColumn(rightDiffs, boxes, cursor, rightW, centerY, DIFF_GAP, 'left')) {
      placed.set(node.id, node)
    }
  }

  return nodes.map((node) => placed.get(node.id) ?? node)
}
