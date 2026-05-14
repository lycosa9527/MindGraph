import { describe, expect, it } from 'vitest'

import { countOverlappingRects, relaxTopLeftPillLayoutsEstimated } from '@/utils/cmapLayoutOverlap'

describe('cmapLayoutOverlap', () => {
  it('detects overlaps for stacked pills', () => {
    const rects = [
      { key: 'a', x: 0, y: 0, width: 140, height: 48 },
      { key: 'b', x: 5, y: 2, width: 140, height: 48 },
    ]
    expect(countOverlappingRects(rects, 0)).toBeGreaterThan(0)
  })

  it('reduces a simple pairwise overlap through iterative separation', () => {
    const positions = { alpha: { x: 220, y: 120 }, beta: { x: 210, y: 118 } }
    const sizeByKey = {
      alpha: { width: 240, height: 48 },

      beta: { width: 240, height: 48 },
    }

    const anchorByKey = { ...positions }

    const beforeRects = [
      { key: 'alpha', ...positions.alpha, ...sizeByKey.alpha },
      { key: 'beta', ...positions.beta, ...sizeByKey.beta },
    ]

    const beforePairs = countOverlappingRects(beforeRects, 4)
    expect(beforePairs).toBeGreaterThan(0)

    const relaxed = relaxTopLeftPillLayoutsEstimated(
      positions,
      sizeByKey,
      anchorByKey,
      96,
      4,
      0.015
    )
    const afterPairs = countOverlappingRects(
      [
        { key: 'alpha', ...relaxed.alpha, ...sizeByKey.alpha },
        { key: 'beta', ...relaxed.beta, ...sizeByKey.beta },
      ],
      4
    )

    expect(afterPairs).toBeLessThan(beforePairs)
  })
})
