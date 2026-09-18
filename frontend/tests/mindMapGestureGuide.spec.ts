import { describe, expect, it } from 'vitest'

import { MIND_MAP_GESTURE_GUIDE_ROWS } from '@/config/mindMapGestureGuide'

describe('mindMapGestureGuide', () => {
  it('documents classroom multi-touch rows without rotate', () => {
    const ids = MIND_MAP_GESTURE_GUIDE_ROWS.map((row) => row.id)
    expect(ids).toEqual([
      'tap',
      'dragNode',
      'pinch',
      'pan',
      'editNode',
      'fitView',
      'resetZoom',
      'contextMenu',
      'slideSwipe',
      'undoRedo',
      'tools',
    ])
    expect(ids).not.toContain('rotate')
    for (const row of MIND_MAP_GESTURE_GUIDE_ROWS) {
      expect(row.labelKey.startsWith('canvas.gestureGuide.')).toBe(true)
      expect(row.hintKey.startsWith('canvas.gestureGuide.')).toBe(true)
    }
  })
})
