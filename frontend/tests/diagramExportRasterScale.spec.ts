import { describe, expect, it } from 'vitest'

import {
  resolveDiagramRasterPixelRatio,
  scaleExportSvgDataUrl,
  svgMarkupFromDataUrl,
} from '@/utils/diagramExportRasterScale'

function svgDataUrl(width: number, height: number): string {
  const markup = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`
}

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

  it('caps a print-DPI ratio so the canvas stays within mobile limits', () => {
    const ratio = resolveDiagramRasterPixelRatio(2000, 1400, 3.125)
    expect(Math.round(2000 * ratio)).toBeLessThanOrEqual(4096)
    expect(Math.round(1400 * ratio)).toBeLessThanOrEqual(4096)
    expect(Math.round(2000 * ratio) * Math.round(1400 * ratio)).toBeLessThanOrEqual(16_777_216)
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
})
