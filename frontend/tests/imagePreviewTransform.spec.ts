import { describe, expect, it } from 'vitest'

import {
  IMAGE_PREVIEW_MAX_SCALE,
  IMAGE_PREVIEW_MIN_SCALE,
  clampPreviewPan,
  nextPreviewScale,
  zoomAboutPoint,
} from '@/utils/imagePreviewTransform'

describe('imagePreviewTransform', () => {
  it('zooms in on wheel up and out on wheel down', () => {
    const zoomed = nextPreviewScale(1, -100, 0)
    expect(zoomed).toBeGreaterThan(1)
    expect(nextPreviewScale(zoomed, 100, 0)).toBeLessThan(zoomed)
  })

  it('stays inside the scale limits', () => {
    expect(nextPreviewScale(1, 500, 0)).toBe(IMAGE_PREVIEW_MIN_SCALE)
    let scale = 1
    for (let step = 0; step < 40; step += 1) {
      scale = nextPreviewScale(scale, -120, 0)
    }
    expect(scale).toBe(IMAGE_PREVIEW_MAX_SCALE)
  })

  it('keeps the point under the cursor fixed while zooming', () => {
    const start = { scale: 1, x: 0, y: 0 }
    const cursorX = 40
    const cursorY = -20
    const next = zoomAboutPoint(start, 2, cursorX, cursorY)
    const localX = (cursorX - start.x) / start.scale
    const localY = (cursorY - start.y) / start.scale
    expect(localX * next.scale + next.x).toBeCloseTo(cursorX)
    expect(localY * next.scale + next.y).toBeCloseTo(cursorY)
  })

  it('clamps pan so the scaled image stays in the frame', () => {
    const clamped = clampPreviewPan({ scale: 2, x: 999, y: -999 }, 200, 100, 200, 100)
    expect(clamped.x).toBe(100)
    expect(clamped.y).toBe(-50)
  })

  it('clears pan when the image fits the frame', () => {
    const clamped = clampPreviewPan({ scale: 1, x: 30, y: -12 }, 400, 300, 200, 100)
    expect(clamped).toEqual({ scale: 1, x: 0, y: 0 })
  })

  it('treats a line-mode wheel tick as pixels', () => {
    expect(nextPreviewScale(1, -3, 1)).toBeCloseTo(nextPreviewScale(1, -48, 0))
  })
})
