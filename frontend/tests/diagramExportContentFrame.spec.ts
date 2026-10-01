import { describe, expect, it } from 'vitest'

import {
  DIAGRAM_EXPORT_CONTENT_FRAME_PAD,
  resolveDiagramExportContentFrame,
} from '@/utils/diagramExportContentFrame'

describe('resolveDiagramExportContentFrame', () => {
  it('keeps a map that fits the capture cap at native zoom', () => {
    const bounds = { x: 120, y: -40, width: 1800, height: 900 }
    const frame = resolveDiagramExportContentFrame(bounds)
    const pad = DIAGRAM_EXPORT_CONTENT_FRAME_PAD
    expect(frame.zoom).toBe(1)
    expect(frame.width).toBe(1800 + pad * 2)
    expect(frame.height).toBe(900 + pad * 2)
    expect(frame.x).toBeCloseTo(pad - bounds.x)
    expect(frame.y).toBeCloseTo(pad - bounds.y)
  })

  it('shrinks a wide map only enough to stay within the capture edge', () => {
    const frame = resolveDiagramExportContentFrame({ x: 0, y: 10, width: 8000, height: 2000 })
    expect(frame.zoom).toBeLessThan(1)
    expect(frame.zoom).toBeGreaterThan(0.4)
    expect(frame.width).toBeLessThanOrEqual(4096)
    expect(frame.height).toBeLessThanOrEqual(4096)
    expect(frame.width).toBeGreaterThan(4000)
  })

  it('places the flow origin so the bounds start at the padding', () => {
    const bounds = { x: -200, y: 80, width: 500, height: 300 }
    const frame = resolveDiagramExportContentFrame(bounds)
    expect(frame.x + bounds.x * frame.zoom).toBeCloseTo(DIAGRAM_EXPORT_CONTENT_FRAME_PAD)
    expect(frame.y + bounds.y * frame.zoom).toBeCloseTo(DIAGRAM_EXPORT_CONTENT_FRAME_PAD)
  })
})
