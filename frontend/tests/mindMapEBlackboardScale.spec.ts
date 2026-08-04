import { describe, expect, it } from 'vitest'

import {
  MIND_MAP_E_BLACKBOARD_CONTROL_SCALE,
  mindMapControlScale,
} from '@/config/mindMapEBlackboard'

describe('mindMap e-blackboard control scale', () => {
  it('defaults to 1x when optimization is off', () => {
    expect(mindMapControlScale(false)).toBe(1)
  })

  it('uses the shared constant when optimization is on', () => {
    expect(MIND_MAP_E_BLACKBOARD_CONTROL_SCALE).toBe(2)
    expect(mindMapControlScale(true)).toBe(MIND_MAP_E_BLACKBOARD_CONTROL_SCALE)
  })
})
