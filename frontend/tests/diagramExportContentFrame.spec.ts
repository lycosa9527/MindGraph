import { describe, expect, it } from 'vitest'

import {
  DIAGRAM_EXPORT_CONTENT_FRAME_PAD,
  resolveDiagramExportContentFrame,
} from '@/utils/diagramExportContentFrame'
import {
  DIAGRAM_RASTER_BUDGET_DESKTOP,
  DIAGRAM_RASTER_BUDGET_MOBILE,
} from '@/utils/diagramExportRasterScale'

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

  it('keeps a wide map at native zoom when it still fits the canvas budget', () => {
    const frame = resolveDiagramExportContentFrame({ x: 0, y: 10, width: 8000, height: 2000 })
    const pad = DIAGRAM_EXPORT_CONTENT_FRAME_PAD
    expect(frame.zoom).toBe(1)
    expect(frame.width).toBe(8000 + pad * 2)
    expect(frame.height).toBe(2000 + pad * 2)
  })

  it('shrinks a huge map only enough to stay within the capture edge', () => {
    const maxEdge = DIAGRAM_RASTER_BUDGET_DESKTOP.maxEdge
    const frame = resolveDiagramExportContentFrame({ x: 0, y: 10, width: 20000, height: 4000 })
    expect(frame.zoom).toBeLessThan(1)
    expect(frame.zoom).toBeGreaterThan(0.7)
    expect(frame.width).toBeLessThanOrEqual(maxEdge)
    expect(frame.height).toBeLessThanOrEqual(maxEdge)
    expect(frame.width).toBeGreaterThan(maxEdge - 2)
  })

  it('shrinks a square map when the pixel area is the limit', () => {
    const frame = resolveDiagramExportContentFrame({ x: 0, y: 0, width: 14000, height: 14000 })
    const edge = DIAGRAM_RASTER_BUDGET_DESKTOP.maxEdge
    expect(14000 + DIAGRAM_EXPORT_CONTENT_FRAME_PAD * 2).toBeLessThan(edge)
    expect(frame.zoom).toBeLessThan(1)
    expect(frame.zoom).toBeGreaterThan(0.65)
    expect(frame.width).toBeLessThan(14000)
    expect(frame.width).toBeLessThanOrEqual(edge)
  })

  it('uses the phone edge when that budget is passed', () => {
    const frame = resolveDiagramExportContentFrame(
      { x: 0, y: 0, width: 8000, height: 2000 },
      DIAGRAM_EXPORT_CONTENT_FRAME_PAD,
      DIAGRAM_RASTER_BUDGET_MOBILE
    )
    expect(frame.zoom).toBeLessThan(1)
    expect(frame.width).toBeLessThanOrEqual(DIAGRAM_RASTER_BUDGET_MOBILE.maxEdge)
    expect(frame.width).toBeGreaterThan(DIAGRAM_RASTER_BUDGET_MOBILE.maxEdge - 2)
  })

  it('places the flow origin so the bounds start at the padding', () => {
    const bounds = { x: -200, y: 80, width: 500, height: 300 }
    const frame = resolveDiagramExportContentFrame(bounds)
    expect(frame.x + bounds.x * frame.zoom).toBeCloseTo(DIAGRAM_EXPORT_CONTENT_FRAME_PAD)
    expect(frame.y + bounds.y * frame.zoom).toBeCloseTo(DIAGRAM_EXPORT_CONTENT_FRAME_PAD)
  })
})
