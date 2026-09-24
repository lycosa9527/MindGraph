import { describe, expect, it } from 'vitest'

import {
  type DiagramExportContentBounds,
  computeDiagramExportCropRegion,
  cropCanvasToContentBounds,
  measureDiagramExportContentBounds,
  measureDiagramExportFlowBounds,
  nodeToExportFlowRect,
} from '@/utils/diagramExportContentBounds'

function mockClientRect(
  element: Element,
  rect: { left: number; top: number; width: number; height: number }
): void {
  const box = {
    x: rect.left,
    y: rect.top,
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
    right: rect.left + rect.width,
    bottom: rect.top + rect.height,
    toJSON: () => ({}),
  } as DOMRect
  element.getBoundingClientRect = () => box
}

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

  it('uses absolute node position and skips hidden or unmeasured nodes', () => {
    expect(
      nodeToExportFlowRect({
        position: { x: 0, y: 0 },
        computedPosition: { x: 400, y: 80 },
        dimensions: { width: 120, height: 36 },
      })
    ).toEqual({ x: 400, y: 80, width: 120, height: 36 })
    expect(
      nodeToExportFlowRect({
        hidden: true,
        computedPosition: { x: 1, y: 1 },
        dimensions: { width: 10, height: 10 },
      })
    ).toBeNull()
    expect(
      nodeToExportFlowRect({
        computedPosition: { x: 1, y: 1 },
        dimensions: { width: 0, height: 20 },
      })
    ).toBeNull()
  })

  it('includes overlay geometry that sits outside node boxes', () => {
    const container = document.createElement('div')
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.setAttribute('class', 'brace-overlay')
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    path.getBBox = () =>
      ({
        x: 0,
        y: 200,
        width: 40,
        height: 80,
      }) as DOMRect
    svg.appendChild(path)
    container.append(svg)
    document.body.appendChild(container)

    const bounds = measureDiagramExportFlowBounds(container, [
      {
        computedPosition: { x: 10, y: 10 },
        dimensions: { width: 100, height: 40 },
      },
    ])

    expect(bounds).toEqual({ x: -12, y: -2, width: 134, height: 294 })
    container.remove()
  })

  it('crops to brace ink below the node boxes', () => {
    const container = document.createElement('div')
    mockClientRect(container, { left: 0, top: 0, width: 800, height: 600 })
    const node = document.createElement('div')
    node.className = 'vue-flow__node'
    mockClientRect(node, { left: 100, top: 100, width: 200, height: 80 })
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.setAttribute('class', 'brace-overlay')
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    mockClientRect(path, { left: 90, top: 300, width: 30, height: 120 })
    svg.appendChild(path)
    container.append(node, svg)
    document.body.appendChild(container)

    const bounds = measureDiagramExportContentBounds(container, 24)
    expect(bounds).toEqual({
      left: 66,
      top: 76,
      width: 258,
      height: 368,
    })
    container.remove()
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
