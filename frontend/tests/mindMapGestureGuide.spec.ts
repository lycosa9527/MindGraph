import { describe, expect, it } from 'vitest'

import type { CanvasInputMode } from '@/config/canvasInputMode'
import { gestureGuideHint, gestureGuideRowsForMode } from '@/config/mindMapGestureGuide'

const SLASH = ['slashDelete', 'slashSibling']
const BOARD_SHORTCUTS = ['resetZoom', 'slideSwipe', 'undoRedo', 'tools']

describe('mindMapGestureGuide', () => {
  it('lists one column per segment and hides board shortcuts elsewhere', () => {
    const modes: CanvasInputMode[] = ['mouse', 'laptop', 'mobile', 'board']
    for (const mode of modes) {
      const rows = gestureGuideRowsForMode(mode)
      const ids = rows.map((row) => row.id)
      expect(ids).toContain('dragDrop')
      expect(ids).toContain('pan')
      expect(ids).not.toContain('rotate')
      expect(ids).not.toContain('slashChild')
      for (const row of rows) {
        expect(gestureGuideHint(row, mode).startsWith('canvas.gestureGuide.')).toBe(true)
      }
      if (mode === 'mouse' || mode === 'board') {
        for (const id of SLASH) expect(ids).toContain(id)
      } else {
        for (const id of SLASH) expect(ids).not.toContain(id)
      }
      if (mode === 'board') {
        for (const id of BOARD_SHORTCUTS) expect(ids).toContain(id)
      } else {
        for (const id of BOARD_SHORTCUTS) expect(ids).not.toContain(id)
      }
    }
  })

  it('says one-finger pan on mobile and two-finger pan on laptop and the board', () => {
    const pan = (mode: CanvasInputMode) => {
      const row = gestureGuideRowsForMode(mode).find((item) => item.id === 'pan')
      if (!row) throw new Error('missing pan row')
      return gestureGuideHint(row, mode)
    }
    expect(pan('mouse')).toBe('canvas.gestureGuide.panHintMouse')
    expect(pan('mobile')).toBe('canvas.gestureGuide.panHintMobile')
    expect(pan('laptop')).toBe('canvas.gestureGuide.panHint')
    expect(pan('board')).toBe('canvas.gestureGuide.panHint')
  })
})
