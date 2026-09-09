/**
 * Curly-brace + range-rect geometry for mind-map summary (XMind-style 概要).
 */
import type { MindMapSummaryKind } from '@/types'

export type SummaryBraceBox = {
  x: number
  y: number
  width: number
  height: number
}

export type SummaryBraceOptions = {
  inset?: number
  kind?: MindMapSummaryKind
  /** When set, brace and range chrome use this box instead of the node-union pad. */
  rangeRect?: SummaryBraceBox
}

export type SummaryBraceLayout = {
  bracePath: string
  tipX: number
  tipY: number
  handleX: number
  handleY: number
  rangeRect: SummaryBraceBox
  side: 'left' | 'right'
}

export const MINDMAP_SUMMARY_RANGE_PAD = 6
const BRACE_GAP = 10
const END_CURVE = 10
const TIP_OUT = 8
const TIP_SPAN = 8
/** Air between the brace tip and the 概要 node edge. */
export const MINDMAP_SUMMARY_TIP_NODE_GAP = 14
const CONNECTOR_END_GAP = 10

function unionBoxes(boxes: readonly SummaryBraceBox[]): SummaryBraceBox {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const box of boxes) {
    minX = Math.min(minX, box.x)
    minY = Math.min(minY, box.y)
    maxX = Math.max(maxX, box.x + box.width)
    maxY = Math.max(maxY, box.y + box.height)
  }
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY }
}

function curlyBracePath(
  innerX: number,
  stemX: number,
  tipX: number,
  topY: number,
  tipY: number,
  bottomY: number
): string {
  return [
    `M ${innerX} ${topY}`,
    `Q ${stemX} ${topY} ${stemX} ${topY + END_CURVE}`,
    `L ${stemX} ${tipY - TIP_SPAN}`,
    `Q ${stemX} ${tipY} ${tipX} ${tipY}`,
    `Q ${stemX} ${tipY} ${stemX} ${tipY + TIP_SPAN}`,
    `L ${stemX} ${bottomY - END_CURVE}`,
    `Q ${stemX} ${bottomY} ${innerX} ${bottomY}`,
  ].join(' ')
}

function bracketPath(innerX: number, stemX: number, topY: number, bottomY: number): string {
  return [
    `M ${innerX} ${topY}`,
    `L ${stemX} ${topY}`,
    `L ${stemX} ${bottomY}`,
    `L ${innerX} ${bottomY}`,
  ].join(' ')
}

function parenPath(innerX: number, midX: number, topY: number, bottomY: number): string {
  return `M ${innerX} ${topY} C ${midX} ${topY} ${midX} ${bottomY} ${innerX} ${bottomY}`
}

export function mindMapSummaryPaddedRangeRect(
  boxes: readonly SummaryBraceBox[]
): SummaryBraceBox | null {
  if (boxes.length === 0) return null
  const union = unionBoxes(boxes)
  return {
    x: union.x - MINDMAP_SUMMARY_RANGE_PAD,
    y: union.y - MINDMAP_SUMMARY_RANGE_PAD,
    width: union.width + MINDMAP_SUMMARY_RANGE_PAD * 2,
    height: union.height + MINDMAP_SUMMARY_RANGE_PAD * 2,
  }
}

/** `}` / `{` / `[` / `(` spanning the covered nodes, tip toward the summary topic. */
export function mindMapSummaryBracePath(
  boxes: readonly SummaryBraceBox[],
  side: 'left' | 'right',
  options?: SummaryBraceOptions
): SummaryBraceLayout | null {
  if (boxes.length === 0 && !options?.rangeRect) return null
  const inset = options?.inset ?? BRACE_GAP
  const kind = options?.kind ?? 'brace'
  const rangeRect = options?.rangeRect ?? mindMapSummaryPaddedRangeRect(boxes)
  if (!rangeRect) return null

  const topY = rangeRect.y
  const bottomY = rangeRect.y + rangeRect.height
  const tipY = (topY + bottomY) / 2
  const outward = side === 'right' ? 1 : -1
  const innerX = side === 'right' ? rangeRect.x + rangeRect.width + inset : rangeRect.x - inset
  const stemX = innerX + outward * END_CURVE
  const handleX = stemX
  const handleY = topY + (tipY - topY) * 0.38

  let tipX = stemX + outward * TIP_OUT
  let bracePath = curlyBracePath(innerX, stemX, tipX, topY, tipY, bottomY)
  if (kind === 'bracket') {
    tipX = stemX
    bracePath = bracketPath(innerX, stemX, topY, bottomY)
  } else if (kind === 'paren') {
    tipX = stemX + outward * TIP_OUT
    bracePath = parenPath(innerX, tipX, topY, bottomY)
  }

  return { bracePath, tipX, tipY, handleX, handleY, rangeRect, side }
}

export function mindMapSummaryConnectorPath(
  tipX: number,
  tipY: number,
  summaryBox: SummaryBraceBox,
  side: 'left' | 'right'
): string {
  const nodeEdgeX = side === 'right' ? summaryBox.x : summaryBox.x + summaryBox.width
  const targetX = side === 'right' ? nodeEdgeX - CONNECTOR_END_GAP : nodeEdgeX + CONNECTOR_END_GAP
  const targetY = summaryBox.y + summaryBox.height / 2
  const span = side === 'right' ? targetX - tipX : tipX - targetX
  if (span <= 2) return ''
  return `M ${tipX} ${tipY} L ${targetX} ${targetY}`
}
