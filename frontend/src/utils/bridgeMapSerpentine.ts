/**
 * Bridge maps run left to right, then U-turn.
 * After five pairs the next pair sits under the last one and the row
 * runs back the other way. The bridge line follows that path.
 */
import { bridgeGapCenterY } from '@/utils/bridgeMapLabelLayout'
import { bridgeSectionRight } from '@/utils/bridgeMapPairBox'

export const BRIDGE_PAIRS_PER_ROW = 5
export const BRIDGE_ROW_GAP = 72

/** How far a bridge U-turn steps out past the outer pair before it drops. */
export const BRIDGE_TURN_OUTSET_PX = 45

export type BridgeRowDirection = 'ltr' | 'rtl'

export interface BridgePairSlot {
  row: number
  column: number
  direction: BridgeRowDirection
}

export interface BridgePairBox {
  upperWidth: number
  upperHeight: number
  lowerWidth: number
  lowerHeight: number
}

export interface BridgePairPlacement extends BridgePairSlot {
  x: number
  upperY: number
  lowerY: number
}

export interface BridgeInkRect {
  x: number
  y: number
  width: number
  height: number
}

export interface BridgeInkPair {
  pairIndex: number
  upper: BridgeInkRect
  lower: BridgeInkRect
}

export interface BridgeInkLine {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface BridgeAlongMarker {
  pairIndex: number
  x: number
  y: number
}

export interface BridgeSerpentineInk {
  lines: BridgeInkLine[]
  along: BridgeAlongMarker[]
}

export function bridgePairSlot(index: number, perRow = BRIDGE_PAIRS_PER_ROW): BridgePairSlot {
  const row = Math.floor(index / perRow)
  const offset = index % perRow
  const direction: BridgeRowDirection = row % 2 === 0 ? 'ltr' : 'rtl'
  const column = direction === 'ltr' ? offset : perRow - 1 - offset
  return { row, column, direction }
}

export function placeBridgeSerpentine(
  pairs: readonly BridgePairBox[],
  originX: number,
  firstRowCenterY: number,
  verticalGap: number,
  columnGap: number,
  rowGap = BRIDGE_ROW_GAP
): BridgePairPlacement[] {
  if (pairs.length === 0) return []

  const columnCount = Math.min(BRIDGE_PAIRS_PER_ROW, pairs.length)
  const columnWidth = Array.from({ length: columnCount }, () => 0)
  pairs.forEach((pair, index) => {
    const slot = bridgePairSlot(index)
    const column = Math.min(slot.column, columnCount - 1)
    columnWidth[column] = Math.max(columnWidth[column], pair.upperWidth, pair.lowerWidth)
  })

  const columnLeft: number[] = []
  let cursor = originX
  for (let column = 0; column < columnCount; column += 1) {
    columnLeft.push(cursor)
    cursor += columnWidth[column] + columnGap
  }

  const placed: BridgePairPlacement[] = []
  let rowCenterY = firstRowCenterY
  let index = 0
  while (index < pairs.length) {
    const rowEnd = Math.min(index + BRIDGE_PAIRS_PER_ROW, pairs.length)
    let rowBottom = rowCenterY
    for (let pairIndex = index; pairIndex < rowEnd; pairIndex += 1) {
      const pair = pairs[pairIndex]
      const slot = bridgePairSlot(pairIndex)
      const column = Math.min(slot.column, columnCount - 1)
      const upperY = rowCenterY - verticalGap - pair.upperHeight
      const lowerY = rowCenterY + verticalGap
      rowBottom = Math.max(rowBottom, lowerY + pair.lowerHeight)
      placed.push({
        row: slot.row,
        column,
        direction: slot.direction,
        x: columnLeft[column],
        upperY,
        lowerY,
      })
    }
    index = rowEnd
    if (index >= pairs.length) break
    const nextEnd = Math.min(index + BRIDGE_PAIRS_PER_ROW, pairs.length)
    let nextMaxUpper = 0
    for (let pairIndex = index; pairIndex < nextEnd; pairIndex += 1) {
      nextMaxUpper = Math.max(nextMaxUpper, pairs[pairIndex].upperHeight)
    }
    rowCenterY = rowBottom + rowGap + verticalGap + nextMaxUpper
  }
  return placed
}

function sectionLeft(pair: BridgeInkPair): number {
  return Math.min(pair.upper.x, pair.lower.x)
}

function sectionRight(pair: BridgeInkPair): number {
  return bridgeSectionRight(pair.upper.x, pair.upper.width, pair.lower.x, pair.lower.width)
}

/** Midpoint of the gutter, whether the next pair sits to the right or the left. */
function gutterCenter(current: BridgeInkPair, following: BridgeInkPair): number {
  const currentLeft = sectionLeft(current)
  const currentRight = sectionRight(current)
  const followingLeft = sectionLeft(following)
  const followingRight = sectionRight(following)
  if (currentLeft <= followingLeft) {
    return (currentRight + followingLeft) / 2
  }
  return (followingRight + currentLeft) / 2
}

interface RowInk {
  pairs: BridgeInkPair[]
  left: number
  right: number
  y: number
  direction: BridgeRowDirection
}

/** Bridge stroke and the "as" marks, including the vertical U-turn. */
export function bridgeSerpentineInk(pairs: readonly BridgeInkPair[]): BridgeSerpentineInk {
  const ordered = pairs
    .filter((pair) => Number.isFinite(pair.pairIndex))
    .slice()
    .sort((left, right) => left.pairIndex - right.pairIndex)
  if (ordered.length === 0) return { lines: [], along: [] }

  const rows: RowInk[] = []
  ordered.forEach((pair, sequenceIndex) => {
    const slot = bridgePairSlot(sequenceIndex)
    let row = rows[slot.row]
    if (!row) {
      row = {
        pairs: [],
        left: sectionLeft(pair),
        right: sectionRight(pair),
        y: 0,
        direction: slot.direction,
      }
      rows[slot.row] = row
    }
    row.pairs.push(pair)
    row.left = Math.min(row.left, sectionLeft(pair))
    row.right = Math.max(row.right, sectionRight(pair))
  })

  for (const row of rows) {
    if (!row) continue
    const center =
      bridgeGapCenterY(
        row.pairs.map((pair) => ({
          upperBottom: pair.upper.y + pair.upper.height,
          lowerTop: pair.lower.y,
        }))
      ) ?? row.pairs[0].upper.y
    row.y = center
  }

  const lines: BridgeInkLine[] = []
  const drops: BridgeInkLine[] = []
  const along: BridgeAlongMarker[] = []

  for (let rowIndex = 0; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex]
    const next = rows[rowIndex + 1]
    if (!row) continue
    if (next && row.direction === 'ltr') {
      const turnX = Math.max(row.right, next.right) + BRIDGE_TURN_OUTSET_PX
      row.right = turnX
      next.right = turnX
      drops.push({ x1: turnX, y1: row.y, x2: turnX, y2: next.y })
    } else if (next && row.direction === 'rtl') {
      const turnX = Math.min(row.left, next.left) - BRIDGE_TURN_OUTSET_PX
      row.left = turnX
      next.left = turnX
      drops.push({ x1: turnX, y1: row.y, x2: turnX, y2: next.y })
    }
    lines.push({ x1: row.left, y1: row.y, x2: row.right, y2: row.y })

    for (let pairIndex = 0; pairIndex < row.pairs.length - 1; pairIndex += 1) {
      const current = row.pairs[pairIndex]
      const following = row.pairs[pairIndex + 1]
      along.push({
        pairIndex: current.pairIndex,
        x: gutterCenter(current, following),
        y: row.y,
      })
    }
  }

  lines.push(...drops)
  return { lines, along }
}

/**
 * The separator is the same translucent color as the stroke.
 * The stroke stops at the separator so the two layers do not darken where they meet.
 */
export function openBridgeSeparatorGaps(
  lines: readonly BridgeInkLine[],
  markers: readonly { x: number; y: number }[],
  opening: number
): BridgeInkLine[] {
  const half = opening / 2
  const opened: BridgeInkLine[] = []
  for (const line of lines) {
    if (line.y1 !== line.y2) {
      opened.push(line)
      continue
    }
    const y = line.y1
    const start = Math.min(line.x1, line.x2)
    const end = Math.max(line.x1, line.x2)
    const cuts = markers
      .filter((marker) => marker.y === y)
      .map((marker) => ({ left: marker.x - half, right: marker.x + half }))
      .filter((cut) => cut.right > start && cut.left < end)
      .sort((left, right) => left.left - right.left)
    let cursor = start
    for (const cut of cuts) {
      const gapLeft = Math.max(cut.left, cursor)
      if (gapLeft - cursor > 0.5) {
        opened.push({ x1: cursor, y1: y, x2: gapLeft, y2: y })
      }
      cursor = Math.max(cursor, Math.min(cut.right, end))
    }
    if (end - cursor > 0.5) {
      opened.push({ x1: cursor, y1: y, x2: end, y2: y })
    }
  }
  return opened
}
