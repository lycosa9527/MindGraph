/**
 * Keep the instructor pad inside the visible viewport (chrome, zoom, rail).
 */
export type TrainingPadBox = {
  right: number
  bottom: number
  maxHeight: number
}

export type TrainingPadViewport = {
  innerWidth: number
  innerHeight: number
  viewOffsetLeft: number
  viewOffsetTop: number
  viewWidth: number
  viewHeight: number
  railOpen: boolean
  gap?: number
  railWidth?: number
}

const DEFAULT_GAP = 16
const DEFAULT_RAIL_WIDTH = 18 * 16 + 12

export function trainingPadBox(input: TrainingPadViewport): TrainingPadBox {
  const gap = input.gap ?? DEFAULT_GAP
  const rail = input.railOpen ? (input.railWidth ?? DEFAULT_RAIL_WIDTH) : 0
  const insetRight = Math.max(0, input.innerWidth - input.viewOffsetLeft - input.viewWidth)
  const insetBottom = Math.max(0, input.innerHeight - input.viewOffsetTop - input.viewHeight)
  const avail = Math.max(0, input.viewHeight)
  return {
    right: gap + insetRight + rail,
    bottom: gap + insetBottom,
    maxHeight: Math.max(96, avail - gap * 2),
  }
}

export function readTrainingPadViewport(railOpen: boolean): TrainingPadViewport {
  const view = typeof window !== 'undefined' ? window.visualViewport : null
  return {
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    viewOffsetLeft: view?.offsetLeft ?? 0,
    viewOffsetTop: view?.offsetTop ?? 0,
    viewWidth: view?.width ?? window.innerWidth,
    viewHeight: view?.height ?? window.innerHeight,
    railOpen,
  }
}
