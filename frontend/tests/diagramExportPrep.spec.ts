import { describe, expect, it, vi } from 'vitest'

import {
  prepareDiagramCanvasForRasterCapture,
  waitForDiagramExportFonts,
} from '@/utils/diagramExportPrep'

describe('diagramExportPrep', () => {
  it('prepareDiagramCanvasForRasterCapture runs fit callback before waiting', async () => {
    const order: string[] = []
    const fitForExport = vi.fn(() => {
      order.push('fit')
    })

    await prepareDiagramCanvasForRasterCapture(() => {
      fitForExport()
      order.push('after-fit')
    })

    expect(fitForExport).toHaveBeenCalledOnce()
    expect(order[0]).toBe('fit')
    expect(order[1]).toBe('after-fit')
  })

  it('waitForDiagramExportFonts resolves without throwing', async () => {
    await expect(waitForDiagramExportFonts('en')).resolves.toBeUndefined()
  })
})
