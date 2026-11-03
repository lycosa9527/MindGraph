import { describe, expect, it } from 'vitest'

import {
  DIAGRAM_RASTER_BUDGET_DESKTOP,
  DIAGRAM_RASTER_BUDGET_MOBILE,
  diagramRasterExportBudget,
  resolveDiagramExportZoom,
  resolveDiagramRasterPixelRatio,
  scaleExportSvgDataUrl,
  svgMarkupFromDataUrl,
} from '@/utils/diagramExportRasterScale'

function svgDataUrl(width: number, height: number): string {
  const markup = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`
}

describe('diagramRasterExportBudget', () => {
  it('uses the phone budget for a touch browser and the desktop budget otherwise', () => {
    expect(
      diagramRasterExportBudget('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')
    ).toBe(DIAGRAM_RASTER_BUDGET_MOBILE)
    expect(diagramRasterExportBudget('Mozilla/5.0 (Windows NT 10.0; Win64; x64)')).toBe(
      DIAGRAM_RASTER_BUDGET_DESKTOP
    )
  })
})

describe('resolveDiagramExportZoom', () => {
  it('stays at native zoom while a 2× bitmap still fits', () => {
    expect(resolveDiagramExportZoom(6000, 3500, 48)).toBe(1)
  })

  it('shrinks a square map when the pixel area is the limit', () => {
    const zoom = resolveDiagramExportZoom(14000, 14000, 48)
    expect(zoom).toBeLessThan(1)
    expect(zoom).toBeGreaterThan(0.65)
  })
})

describe('resolveDiagramRasterPixelRatio', () => {
  it('keeps the requested ratio when a 2× capture is already sharp', () => {
    expect(resolveDiagramRasterPixelRatio(1600, 900, 2)).toBe(2)
  })

  it('raises the ratio for a phone-sized canvas', () => {
    const ratio = resolveDiagramRasterPixelRatio(390, 700, 2)
    expect(ratio).toBeGreaterThan(3)
    expect(Math.round(700 * ratio)).toBeGreaterThanOrEqual(2400)
  })

  it('leaves 1× captures unchanged', () => {
    expect(resolveDiagramRasterPixelRatio(390, 700, 1)).toBe(1)
  })

  it('keeps 2× on a large diagram until the desktop canvas budget', () => {
    const ratio = resolveDiagramRasterPixelRatio(6000, 3500, 2)
    expect(ratio).toBe(2)
    expect(Math.round(6000 * ratio)).toBe(12000)
    expect(Math.round(6000 * ratio)).toBeLessThanOrEqual(DIAGRAM_RASTER_BUDGET_DESKTOP.maxEdge)
  })

  it('shrinks only enough for a diagram that cannot fit at 2×', () => {
    const ratio = resolveDiagramRasterPixelRatio(12000, 8000, 2)
    const width = Math.round(12000 * ratio)
    const height = Math.round(8000 * ratio)
    expect(ratio).toBeGreaterThan(1)
    expect(width).toBeGreaterThan(4096)
    expect(width).toBeLessThanOrEqual(DIAGRAM_RASTER_BUDGET_DESKTOP.maxEdge)
    expect(height).toBeLessThanOrEqual(DIAGRAM_RASTER_BUDGET_DESKTOP.maxEdge)
    expect(width * height).toBeLessThanOrEqual(DIAGRAM_RASTER_BUDGET_DESKTOP.maxPixels)
  })

  it('caps a print-DPI ratio on the phone canvas budget', () => {
    const ratio = resolveDiagramRasterPixelRatio(2000, 1400, 3.125, DIAGRAM_RASTER_BUDGET_MOBILE)
    expect(Math.round(2000 * ratio)).toBeLessThanOrEqual(DIAGRAM_RASTER_BUDGET_MOBILE.maxEdge)
    expect(Math.round(1400 * ratio)).toBeLessThanOrEqual(DIAGRAM_RASTER_BUDGET_MOBILE.maxEdge)
    expect(Math.round(2000 * ratio) * Math.round(1400 * ratio)).toBeLessThanOrEqual(
      DIAGRAM_RASTER_BUDGET_MOBILE.maxPixels
    )
  })
})

describe('scaleExportSvgDataUrl', () => {
  it('rasterizes a small export at output pixels without changing the viewBox', () => {
    const scaled = scaleExportSvgDataUrl(svgDataUrl(390, 700), 2)
    const markup = svgMarkupFromDataUrl(scaled.dataUrl)
    const svg = new DOMParser().parseFromString(markup, 'image/svg+xml').documentElement
    expect(svg.getAttribute('viewBox')).toBe('0 0 390 700')
    expect(Number(svg.getAttribute('width'))).toBe(scaled.width)
    expect(Number(svg.getAttribute('height'))).toBe(scaled.height)
    expect(scaled.width).toBeGreaterThan(390 * 2)
    expect(scaled.height).toBeGreaterThanOrEqual(2400)
  })

  it('keeps a large export at the requested 2× size', () => {
    const scaled = scaleExportSvgDataUrl(svgDataUrl(1600, 900), 2)
    expect(scaled.pixelRatio).toBe(2)
    expect(scaled.width).toBe(3200)
    expect(scaled.height).toBe(1800)
  })

  it('exports a wide diagram larger than a fixed 4096 edge', () => {
    const scaled = scaleExportSvgDataUrl(svgDataUrl(7000, 2000), 2)
    expect(scaled.pixelRatio).toBe(2)
    expect(scaled.width).toBe(14000)
    expect(scaled.height).toBe(4000)
  })
})
