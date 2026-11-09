/**
 * Serpentine grid shared by flow and bridge maps: rows of `perRow` cells run
 * left to right, then the next row runs back right to left, and so on.
 * Columns line up across rows, so each column is as wide as its widest cell.
 */

export type SerpentineDirection = 'ltr' | 'rtl'

export interface SerpentineSlot {
  row: number
  column: number
  direction: SerpentineDirection
}

export interface SerpentineCell {
  width: number
  /** Extent above the row center line. */
  above: number
  /** Extent below the row center line. */
  below: number
}

export interface SerpentineCellPlacement extends SerpentineSlot {
  columnLeft: number
  columnWidth: number
  rowCenterY: number
}

export function serpentineSlot(index: number, perRow: number): SerpentineSlot {
  const row = Math.floor(index / perRow)
  const offset = index % perRow
  const direction: SerpentineDirection = row % 2 === 0 ? 'ltr' : 'rtl'
  const column = direction === 'ltr' ? offset : perRow - 1 - offset
  return { row, column, direction }
}

export function placeSerpentine(
  cells: readonly SerpentineCell[],
  perRow: number,
  originX: number,
  firstRowCenterY: number,
  columnGap: number,
  rowGap: number
): SerpentineCellPlacement[] {
  if (cells.length === 0) return []

  const columnCount = Math.min(perRow, cells.length)
  const columnOf = (index: number): number =>
    Math.min(serpentineSlot(index, perRow).column, columnCount - 1)

  const columnWidth = Array.from({ length: columnCount }, () => 0)
  cells.forEach((cell, index) => {
    const column = columnOf(index)
    columnWidth[column] = Math.max(columnWidth[column], cell.width)
  })

  const columnLeft: number[] = []
  let cursor = originX
  for (let column = 0; column < columnCount; column += 1) {
    columnLeft.push(cursor)
    cursor += columnWidth[column] + columnGap
  }

  const placed: SerpentineCellPlacement[] = []
  let rowCenterY = firstRowCenterY
  let index = 0
  while (index < cells.length) {
    const rowEnd = Math.min(index + perRow, cells.length)
    let rowBottom = rowCenterY
    for (let cellIndex = index; cellIndex < rowEnd; cellIndex += 1) {
      const slot = serpentineSlot(cellIndex, perRow)
      const column = columnOf(cellIndex)
      rowBottom = Math.max(rowBottom, rowCenterY + cells[cellIndex].below)
      placed.push({
        ...slot,
        column,
        columnLeft: columnLeft[column],
        columnWidth: columnWidth[column],
        rowCenterY,
      })
    }
    index = rowEnd
    if (index >= cells.length) break
    const nextEnd = Math.min(index + perRow, cells.length)
    let nextAbove = 0
    for (let cellIndex = index; cellIndex < nextEnd; cellIndex += 1) {
      nextAbove = Math.max(nextAbove, cells[cellIndex].above)
    }
    rowCenterY = rowBottom + rowGap + nextAbove
  }
  return placed
}
