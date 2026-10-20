import { CANVAS_INPUT_MODES } from '@/config/canvasInputMode'
import type { CanvasInputMode } from '@/config/canvasInputMode'

/** Mind-map canvas gesture guide rows. The card shows the active segment only. */

export type MindMapGestureGuideRow = {
  id: string
  labelKey: string
  hintKey: string
  hintKeyByMode?: Partial<Record<CanvasInputMode, string>>
  modes: readonly CanvasInputMode[]
}

const ALL_MODES: readonly CanvasInputMode[] = CANVAS_INPUT_MODES
const SLASH_MODES: readonly CanvasInputMode[] = ['mouse', 'board']
const BOARD_ONLY: readonly CanvasInputMode[] = ['board']

export const MIND_MAP_GESTURE_GUIDE_ROWS: MindMapGestureGuideRow[] = [
  {
    id: 'tap',
    labelKey: 'canvas.gestureGuide.tap',
    hintKey: 'canvas.gestureGuide.tapHint',
    modes: ALL_MODES,
  },
  {
    id: 'dragDrop',
    labelKey: 'canvas.gestureGuide.dragDrop',
    hintKey: 'canvas.gestureGuide.dragDropHintLaptop',
    hintKeyByMode: {
      mobile: 'canvas.gestureGuide.dragDropHintTouch',
      board: 'canvas.gestureGuide.dragDropHintTouch',
    },
    modes: ALL_MODES,
  },
  {
    id: 'pan',
    labelKey: 'canvas.gestureGuide.pan',
    hintKey: 'canvas.gestureGuide.panHint',
    hintKeyByMode: {
      mouse: 'canvas.gestureGuide.panHintMouse',
      mobile: 'canvas.gestureGuide.panHintMobile',
    },
    modes: ALL_MODES,
  },
  {
    id: 'pinch',
    labelKey: 'canvas.gestureGuide.pinch',
    hintKey: 'canvas.gestureGuide.pinchHint',
    hintKeyByMode: {
      mouse: 'canvas.gestureGuide.pinchHintMouse',
    },
    modes: ALL_MODES,
  },
  {
    id: 'editNode',
    labelKey: 'canvas.gestureGuide.editNode',
    hintKey: 'canvas.gestureGuide.editNodeHint',
    modes: ALL_MODES,
  },
  {
    id: 'fitView',
    labelKey: 'canvas.gestureGuide.fitView',
    hintKey: 'canvas.gestureGuide.fitViewHint',
    modes: ALL_MODES,
  },
  {
    id: 'contextMenu',
    labelKey: 'canvas.gestureGuide.contextMenu',
    hintKey: 'canvas.gestureGuide.contextMenuHint',
    modes: ALL_MODES,
  },
  {
    id: 'slashDelete',
    labelKey: 'canvas.gestureGuide.slashDelete',
    hintKey: 'canvas.gestureGuide.slashDeleteBoardHint',
    hintKeyByMode: {
      mouse: 'canvas.gestureGuide.slashDeleteMouseHint',
    },
    modes: SLASH_MODES,
  },
  {
    id: 'slashSibling',
    labelKey: 'canvas.gestureGuide.slashSibling',
    hintKey: 'canvas.gestureGuide.slashSiblingBoardHint',
    hintKeyByMode: {
      mouse: 'canvas.gestureGuide.slashSiblingMouseHint',
    },
    modes: SLASH_MODES,
  },
  {
    id: 'resetZoom',
    labelKey: 'canvas.gestureGuide.resetZoom',
    hintKey: 'canvas.gestureGuide.resetZoomHint',
    modes: BOARD_ONLY,
  },
  {
    id: 'slideSwipe',
    labelKey: 'canvas.gestureGuide.slideSwipe',
    hintKey: 'canvas.gestureGuide.slideSwipeHint',
    modes: BOARD_ONLY,
  },
  {
    id: 'undoRedo',
    labelKey: 'canvas.gestureGuide.undoRedo',
    hintKey: 'canvas.gestureGuide.undoRedoHint',
    modes: BOARD_ONLY,
  },
  {
    id: 'tools',
    labelKey: 'canvas.gestureGuide.tools',
    hintKey: 'canvas.gestureGuide.toolsHint',
    modes: BOARD_ONLY,
  },
]

export function gestureGuideHint(row: MindMapGestureGuideRow, mode: CanvasInputMode): string {
  return row.hintKeyByMode?.[mode] ?? row.hintKey
}

export function gestureGuideRowsForMode(mode: CanvasInputMode): MindMapGestureGuideRow[] {
  return MIND_MAP_GESTURE_GUIDE_ROWS.filter((row) => row.modes.includes(mode))
}
