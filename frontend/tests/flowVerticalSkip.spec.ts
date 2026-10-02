import { describe, expect, it } from 'vitest'

import { nodeSpansCrossingVertical, verticalSegmentsOutsideSpans } from '@/utils/flowVerticalLine'

describe('flow map vertical line skips nodes', () => {
  it('keeps the gaps between a step and the substeps under it', () => {
    const parts = verticalSegmentsOutsideSpans(100, 400, [
      { top: 80, bottom: 140 },
      { top: 180, bottom: 230 },
      { top: 280, bottom: 420 },
    ])
    expect(parts).toEqual([
      { from: 140, to: 180 },
      { from: 230, to: 280 },
    ])
  })

  it('ignores a node the vertical line does not cross', () => {
    const spans = nodeSpansCrossingVertical(
      [
        {
          position: { x: 0, y: 180 },
          dimensions: { width: 80, height: 40 },
        },
        {
          position: { x: 200, y: 180 },
          dimensions: { width: 80, height: 40 },
        },
      ],
      40,
      100,
      300
    )
    expect(spans).toEqual([{ top: 180, bottom: 220 }])
  })
})
