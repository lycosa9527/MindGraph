import { describe, expect, it } from 'vitest'

import { nextGlassesViewport } from '@/composables/diagramCanvas/glassesCanvasRemote'
import { ZOOM } from '@/config/uiConfig'

const origin = { x: 10, y: 20, zoom: 1 }

describe('glasses canvas remote', () => {
  it('pans by a fixed screen step and clamps zoom', () => {
    expect(nextGlassesViewport(origin, 'pan_left')).toEqual({ x: 150, y: 20, zoom: 1 })
    expect(nextGlassesViewport(origin, 'pan_right')).toEqual({ x: -130, y: 20, zoom: 1 })
    expect(nextGlassesViewport(origin, 'pan_up')).toEqual({ x: 10, y: 160, zoom: 1 })
    expect(nextGlassesViewport(origin, 'zoom_in')).toEqual({
      x: 10,
      y: 20,
      zoom: ZOOM.STEP,
    })
    expect(nextGlassesViewport({ x: 0, y: 0, zoom: ZOOM.MAX }, 'zoom_in')).toEqual({
      x: 0,
      y: 0,
      zoom: ZOOM.MAX,
    })
    expect(nextGlassesViewport(origin, 'fit')).toBe('fit')
    expect(nextGlassesViewport(origin, 'spin')).toBeNull()
  })
})
