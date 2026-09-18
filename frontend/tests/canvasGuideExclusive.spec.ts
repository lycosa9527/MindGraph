import { describe, expect, it } from 'vitest'

import {
  activeCanvasGuideId,
  isCanvasGuideOpen,
  openCanvasGuide,
  toggleCanvasGuide,
} from '@/composables/canvas/canvasGuideExclusive'

describe('canvasGuideExclusive', () => {
  it('opens one status-bar guide at a time', () => {
    activeCanvasGuideId.value = null
    expect(toggleCanvasGuide('shortcut')).toBe(true)
    expect(isCanvasGuideOpen('shortcut')).toBe(true)
    expect(toggleCanvasGuide('gesture')).toBe(true)
    expect(isCanvasGuideOpen('shortcut')).toBe(false)
    expect(isCanvasGuideOpen('gesture')).toBe(true)
    expect(toggleCanvasGuide('gesture')).toBe(false)
    expect(activeCanvasGuideId.value).toBeNull()
    openCanvasGuide('shortcut')
    expect(isCanvasGuideOpen('shortcut')).toBe(true)
    activeCanvasGuideId.value = null
  })
})
