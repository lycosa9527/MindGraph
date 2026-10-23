import { describe, expect, it } from 'vitest'

import { viewportZoomedAboutCenter } from '@/composables/diagramCanvas/useDiagramCanvasEventBus'

describe('viewportZoomedAboutCenter', () => {
  it('keeps the viewport center on the same flow point', () => {
    const next = viewportZoomedAboutCenter({ x: 100, y: 40, zoom: 1 }, 2, 800, 600)
    expect(next.zoom).toBe(2)
    expect(next.x).toBeCloseTo(100 - 300)
    expect(next.y).toBeCloseTo(40 - 260)
    const flowX = (400 - next.x) / next.zoom
    const flowY = (300 - next.y) / next.zoom
    expect(flowX).toBeCloseTo((400 - 100) / 1)
    expect(flowY).toBeCloseTo((300 - 40) / 1)
  })

  it('leaves pan unchanged when the container size is unknown', () => {
    expect(viewportZoomedAboutCenter({ x: 12, y: 8, zoom: 1 }, 1.5, 0, 0)).toEqual({
      x: 12,
      y: 8,
      zoom: 1.5,
    })
  })
})
