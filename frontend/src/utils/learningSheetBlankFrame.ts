/**
 * Painted size of a knocked-out content-sized node.
 * Uniform circles keep the layout size; this lock is for pills and underlines.
 */
import type { CSSProperties } from 'vue'

type HoldSize = {
  learningSheetHoldWidth?: unknown
  learningSheetHoldHeight?: unknown
}

export function learningSheetBlankFrameStyle(data: object | undefined): CSSProperties {
  const held = data as HoldSize | undefined
  const width = held?.learningSheetHoldWidth
  const height = held?.learningSheetHoldHeight
  const style: CSSProperties = {}
  if (typeof width === 'number' && width > 0) {
    style.boxSizing = 'border-box'
    style.width = `${width}px`
    style.minWidth = `${width}px`
    style.maxWidth = `${width}px`
  }
  if (typeof height === 'number' && height > 0) {
    style.boxSizing = 'border-box'
    style.height = `${height}px`
    style.minHeight = `${height}px`
    style.maxHeight = `${height}px`
  }
  return style
}
