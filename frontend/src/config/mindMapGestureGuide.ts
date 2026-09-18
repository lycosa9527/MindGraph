/** Mind-map / canvas multi-touch guide rows (display-only). */

export type MindMapGestureGuideRow = {
  id: string
  labelKey: string
  hintKey: string
}

export const MIND_MAP_GESTURE_GUIDE_ROWS: MindMapGestureGuideRow[] = [
  {
    id: 'tap',
    labelKey: 'canvas.gestureGuide.tap',
    hintKey: 'canvas.gestureGuide.tapHint',
  },
  {
    id: 'dragNode',
    labelKey: 'canvas.gestureGuide.dragNode',
    hintKey: 'canvas.gestureGuide.dragNodeHint',
  },
  {
    id: 'pinch',
    labelKey: 'canvas.gestureGuide.pinch',
    hintKey: 'canvas.gestureGuide.pinchHint',
  },
  {
    id: 'pan',
    labelKey: 'canvas.gestureGuide.pan',
    hintKey: 'canvas.gestureGuide.panHint',
  },
  {
    id: 'editNode',
    labelKey: 'canvas.gestureGuide.editNode',
    hintKey: 'canvas.gestureGuide.editNodeHint',
  },
  {
    id: 'fitView',
    labelKey: 'canvas.gestureGuide.fitView',
    hintKey: 'canvas.gestureGuide.fitViewHint',
  },
  {
    id: 'resetZoom',
    labelKey: 'canvas.gestureGuide.resetZoom',
    hintKey: 'canvas.gestureGuide.resetZoomHint',
  },
  {
    id: 'contextMenu',
    labelKey: 'canvas.gestureGuide.contextMenu',
    hintKey: 'canvas.gestureGuide.contextMenuHint',
  },
  {
    id: 'slideSwipe',
    labelKey: 'canvas.gestureGuide.slideSwipe',
    hintKey: 'canvas.gestureGuide.slideSwipeHint',
  },
  {
    id: 'undoRedo',
    labelKey: 'canvas.gestureGuide.undoRedo',
    hintKey: 'canvas.gestureGuide.undoRedoHint',
  },
  {
    id: 'tools',
    labelKey: 'canvas.gestureGuide.tools',
    hintKey: 'canvas.gestureGuide.toolsHint',
  },
]
