/**
 * Painted size of a knocked-out content-sized node.
 * Uniform circles keep the layout size; this lock is for pills and underlines.
 */
import type { CSSProperties } from 'vue'

/**
 * Pills and underlines collapse when their label is cleared, so they keep the
 * box measured before the blank. A circle or bubble disk already has a shared
 * layout diameter; locking it to the content measurement shrinks the disk
 * inside that ring.
 */
export function learningSheetLocksMeasuredFrame(
  nodeShape: string | undefined,
  capsule: boolean
): boolean {
  return capsule || nodeShape === 'underline'
}

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
