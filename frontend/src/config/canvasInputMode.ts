/**
 * Canvas input profile. The settings segment is the only switch.
 * A touch laptop stays on laptop until the user picks another segment.
 */

export const CANVAS_INPUT_MODES = ['mouse', 'laptop', 'mobile', 'board'] as const

export type CanvasInputMode = (typeof CANVAS_INPUT_MODES)[number]

export const CANVAS_INPUT_MODE_KEY = 'mindgraph_canvas_input_mode'

/** Settings segment and the canvas gesture card share these labels. */
export const CANVAS_INPUT_MODE_LABEL: Record<CanvasInputMode, string> = {
  mouse: 'settings.language.canvasInputMouse',
  laptop: 'settings.language.canvasInputLaptop',
  mobile: 'settings.language.canvasInputMobile',
  board: 'settings.language.canvasInputBoard',
}

/** Previous on/off classroom toggle. Read once, then stored as `board`. */
export const E_BLACKBOARD_OPTIMIZE_KEY = 'mindgraph_e_blackboard_optimize'

type ModeStorage = Pick<Storage, 'getItem'>

export function parseCanvasInputMode(value: string | null): CanvasInputMode | null {
  if (value === 'mouse' || value === 'laptop' || value === 'mobile' || value === 'board')
    return value
  return null
}

/** Missing value is laptop. The old on toggle migrates to the classroom board. */
export function readCanvasInputMode(storage: ModeStorage): CanvasInputMode {
  const stored = parseCanvasInputMode(storage.getItem(CANVAS_INPUT_MODE_KEY))
  if (stored) return stored
  if (storage.getItem(E_BLACKBOARD_OPTIMIZE_KEY) === '1') return 'board'
  return 'laptop'
}

/** Phone shell always uses the mobile profile, whatever the saved segment is. */
export function effectiveCanvasInputMode(
  stored: CanvasInputMode,
  mobileShell: boolean
): CanvasInputMode {
  return mobileShell ? 'mobile' : stored
}

/** Left-drag or finger slash adds and deletes nodes on mouse and the classroom board. */
export function canvasInputUsesSlash(mode: CanvasInputMode): boolean {
  return mode === 'mouse' || mode === 'board'
}

/**
 * Attach the touch pan/pinch layer.
 * Board and mobile always listen. Mouse and laptop listen only when the hardware has a touch screen.
 */
export function shouldAttachCanvasTouchLayer(
  mode: CanvasInputMode,
  maxTouchPoints: number
): boolean {
  if (mode === 'mobile' || mode === 'board') return true
  return maxTouchPoints >= 2
}
