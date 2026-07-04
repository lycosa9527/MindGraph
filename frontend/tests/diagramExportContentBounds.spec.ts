import { describe, expect, it } from 'vitest'

import {
  computeDiagramExportCropRegion,
  cropCanvasToContentBounds,
  type DiagramExportContentBounds,
} from '@/utils/diagramExportContentBounds'

describe('diagramExportContentBounds', () => {
  it('maps css bounds to raster pixels using container scale', () => {
    const bounds: DiagramExportContentBounds = {
      left: 100,
      top: 50,
      width: 800,
      height: 600,
    }
    const region = computeDiagramExportCropRegion(1920, 1080, 960, 540, bounds)
    expect(region).toEqual({ sx: 200, sy: 100, sw: 1600, sh: 980 })
  })

  it('clamps crop region inside source canvas', () => {
    const bounds: DiagramExportContentBounds = {
      left: 900,
      top: 400,
      width: 200,
      height: 200,
    }
    const region = computeDiagramExportCropRegion(1000, 800, 1000, 800, bounds)
    expect(region.sx).toBeLessThan(1000)
    expect(region.sy).toBeLessThan(800)
    expect(region.sx + region.sw).toBeLessThanOrEqual(1000)
    expect(region.sy + region.sh).toBeLessThanOrEqual(800)
  })

  it('returns the same canvas when crop covers full image', () => {
    const source = document.createElement('canvas')
    source.width = 400
    source.height = 300
    const bounds: DiagramExportContentBounds = { left: 0, top: 0, width: 800, height: 600 }
    const cropped = cropCanvasToContentBounds(source, 800, 600, bounds)
    expect(cropped).toBe(source)
  })
})
