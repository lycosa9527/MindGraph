import { describe, expect, it } from 'vitest'

import { FLOW_TURN_OUTSET_PX } from '@/composables/diagrams/layoutConfig'
import { flowTurnEdgePath } from '@/utils/flowTurnEdge'

describe('flow turn arrow', () => {
  it('steps past the right side, drops, then comes back', () => {
    const path = flowTurnEdgePath(100, 40, 100, 200, 'right', 10)
    expect(path.edgePath).toBe('M 100 40 L 145 40 L 145 200 L 110 200')
    expect(path.labelX).toBe(100 + FLOW_TURN_OUTSET_PX)
  })

  it('steps past the left side on the way back to the next row', () => {
    const path = flowTurnEdgePath(80, 40, 80, 220, 'left', 10)
    expect(path.edgePath).toBe('M 80 40 L 35 40 L 35 220 L 70 220')
  })

  it('clears the wider of the two steps', () => {
    const path = flowTurnEdgePath(100, 40, 140, 200, 'right', 10)
    expect(path.edgePath.startsWith('M 100 40 L 185 40 L 185 200')).toBe(true)
  })
})
