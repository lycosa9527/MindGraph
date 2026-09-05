import { describe, expect, it } from 'vitest'

import {
  clampOverlayPercent,
  clampSpotlightScale,
  moveArrowHandle,
  overlayClientPercent,
  spotlightRadius,
  spotlightShape,
  translateOverlay,
} from '@/composables/training/trainingOverlayDrag'
import type { TrainingStepOverlay } from '@/types/training'

describe('trainingOverlayDrag', () => {
  it('clamps overlay percents to the stage', () => {
    expect(clampOverlayPercent(-4)).toBe(0)
    expect(clampOverlayPercent(118)).toBe(100)
    expect(clampOverlayPercent(Number.NaN)).toBe(0)
    expect(clampOverlayPercent(42.5)).toBe(42.5)
  })

  it('moves text in place and keeps arrows together', () => {
    const text: TrainingStepOverlay = { kind: 'text', x: 18, y: 18, text: 'Hi' }
    translateOverlay(text, 10, -4)
    expect(text).toMatchObject({ x: 28, y: 14 })

    const arrow: TrainingStepOverlay = { kind: 'arrow', x: 20, y: 24, x2: 72, y2: 68 }
    translateOverlay(arrow, 8, 6)
    expect(arrow).toMatchObject({ x: 28, y: 30, x2: 80, y2: 74 })
    moveArrowHandle(arrow, 'end', 40, 10)
    expect(arrow).toMatchObject({ x: 28, y: 30, x2: 40, y2: 10 })
    moveArrowHandle(arrow, 'start', 12, 18)
    expect(arrow).toMatchObject({ x: 12, y: 18, x2: 40, y2: 10 })

    const spot: TrainingStepOverlay = { kind: 'spotlight', x: 50, y: 50, r: 1 }
    translateOverlay(spot, -10, 4)
    expect(spot).toMatchObject({ x: 40, y: 54, r: 1 })
  })

  it('reads the presentation spotlight scale', () => {
    expect(clampSpotlightScale(0.2)).toBe(0.5)
    expect(clampSpotlightScale(4)).toBe(2.5)
    expect(spotlightRadius({ kind: 'spotlight', r: 1.4 })).toBe(1.4)
    expect(spotlightRadius({ kind: 'spotlight', w: 22, h: 22 })).toBe(1)
    expect(spotlightShape({ kind: 'spotlight' })).toBe('circle')
    expect(spotlightShape({ kind: 'spotlight', shape: 'rect' })).toBe('rect')
  })

  it('maps pointer clients onto the svg percent box', () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.getBoundingClientRect = () =>
      ({
        left: 100,
        top: 50,
        width: 200,
        height: 100,
        right: 300,
        bottom: 150,
        x: 100,
        y: 50,
        toJSON: () => ({}),
      }) as DOMRect
    expect(overlayClientPercent(svg, 200, 100)).toEqual({ x: 50, y: 50 })
    expect(overlayClientPercent(svg, 0, 0)).toEqual({ x: 0, y: 0 })
  })
})
