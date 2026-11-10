import { afterEach, describe, expect, it } from 'vitest'

import {
  DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
  loadCanvasWorksheetTextOptions,
  saveCanvasWorksheetTextOptions,
} from '@/config/canvasWorksheetText'
import {
  applyWorksheetDiagramCropToSvg,
  cropEdgeFromDelta,
  offsetForAnchoredEdge,
  worksheetDiagramCropKeyDelta,
  worksheetDiagramFrameOrigin,
} from '@/utils/worksheetDiagramCrop'

describe('worksheetDiagramCrop', () => {
  afterEach(() => {
    sessionStorage.clear()
  })

  it('grows the top crop when the top bar is dragged down', () => {
    const next = cropEdgeFromDelta('top', { top: 0, right: 0, bottom: 0, left: 0 }, 20, 100)
    expect(next.top).toBeCloseTo(0.2)
    expect(next.bottom).toBe(0)
  })

  it('shrinks the bottom crop when the bottom bar is dragged down', () => {
    const next = cropEdgeFromDelta('bottom', { top: 0, right: 0, bottom: 0.3, left: 0 }, 10, 100)
    expect(next.bottom).toBeCloseTo(0.2)
  })

  it('maps arrow keys to the inward crop direction', () => {
    expect(worksheetDiagramCropKeyDelta('top', 'ArrowDown')).toBe(1)
    expect(worksheetDiagramCropKeyDelta('bottom', 'ArrowUp')).toBe(-1)
    expect(worksheetDiagramCropKeyDelta('left', 'ArrowRight')).toBe(1)
    expect(worksheetDiagramCropKeyDelta('right', 'ArrowLeft')).toBe(-1)
    expect(worksheetDiagramCropKeyDelta('top', 'Enter')).toBe(0)
    const grown = cropEdgeFromDelta(
      'bottom',
      { top: 0, right: 0, bottom: 0, left: 0 },
      worksheetDiagramCropKeyDelta('bottom', 'ArrowUp') * 20,
      100
    )
    expect(grown.bottom).toBeCloseTo(0.2)
  })

  it('keeps the opposite edge fixed while the cropped frame changes size', () => {
    const origin = worksheetDiagramFrameOrigin(200, 200, 100, 100, 0, 0)
    const offset = offsetForAnchoredEdge({
      bodySize: 200,
      visibleSize: 80,
      fixedEdge: origin.bottom,
      anchor: 'end',
    })
    const moved = worksheetDiagramFrameOrigin(200, 200, 100, 80, 0, offset)
    expect(moved.bottom).toBeCloseTo(origin.bottom)
    expect(moved.top).toBeGreaterThan(origin.top)
  })

  it('crops only the root svg viewBox', () => {
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 100 50">' +
      '<rect width="10" height="4"/></svg>'
    const cropped = applyWorksheetDiagramCropToSvg(
      svg,
      { minX: 0, minY: 0, width: 100, height: 50 },
      {
        top: 0,
        right: 0.25,
        bottom: 0,
        left: 0.25,
      }
    )
    expect(cropped.viewBox).toEqual({ minX: 25, minY: 0, width: 50, height: 50 })
    expect(cropped.svg).toContain('viewBox="25 0 50 50"')
    expect(cropped.svg).toContain('overflow="hidden"')
    expect(cropped.svg).toContain('<rect width="10" height="4"/>')
  })

  it('clamps a stored crop so opposite edges leave the diagram visible', () => {
    saveCanvasWorksheetTextOptions({
      ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
      diagramCropTop: 0.9,
      diagramCropBottom: 0.9,
      diagramCropLeft: 0.1,
    })
    const loaded = loadCanvasWorksheetTextOptions()
    expect(loaded.diagramCropTop + loaded.diagramCropBottom).toBeLessThanOrEqual(0.8 + 1e-9)
    expect(loaded.diagramCropLeft).toBeCloseTo(0.1)
    expect(loaded.diagramCropRight).toBe(0)
  })
})
