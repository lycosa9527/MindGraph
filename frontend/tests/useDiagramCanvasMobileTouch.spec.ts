import { describe, expect, it } from 'vitest'

import { PANE_TAP_MAX_MOVE_PX } from '@/composables/diagramCanvas/useDiagramCanvasMobileTouch'

describe('useDiagramCanvasMobileTouch constants', () => {
  it('uses a reasonable pane tap movement threshold', () => {
    expect(PANE_TAP_MAX_MOVE_PX).toBeGreaterThan(0)
    expect(PANE_TAP_MAX_MOVE_PX).toBeLessThanOrEqual(20)
  })
})
