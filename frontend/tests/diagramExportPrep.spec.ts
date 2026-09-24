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

  it('waits for an async fit to finish before resolving', async () => {
    let settled = false
    const pending = prepareDiagramCanvasForRasterCapture(
      () =>
        new Promise((resolve) => {
          setTimeout(() => {
            settled = true
            resolve(undefined)
          }, 0)
        })
    )
    await Promise.resolve()
    expect(settled).toBe(false)
    await pending
    expect(settled).toBe(true)
  })

  it('waitForDiagramExportFonts resolves without throwing', async () => {
    await expect(waitForDiagramExportFonts('en')).resolves.toBeUndefined()
  })
})
