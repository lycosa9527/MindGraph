import { describe, expect, it, vi } from 'vitest'

import { releaseChartInstance } from '@/utils/lazyChartJs'

describe('releaseChartInstance', () => {
  it('stops and destroys a chart that still has a canvas', () => {
    const chart = {
      canvas: document.createElement('canvas'),
      stop: vi.fn(),
      destroy: vi.fn(),
    }
    releaseChartInstance(chart)
    expect(chart.stop).toHaveBeenCalledOnce()
    expect(chart.destroy).toHaveBeenCalledOnce()
  })

  it('does nothing when the canvas is already gone', () => {
    const chart = {
      canvas: null,
      stop: vi.fn(),
      destroy: vi.fn(),
    }
    releaseChartInstance(chart)
    expect(chart.stop).not.toHaveBeenCalled()
    expect(chart.destroy).not.toHaveBeenCalled()
  })
})
