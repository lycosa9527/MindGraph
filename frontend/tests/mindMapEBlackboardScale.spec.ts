import { describe, expect, it } from 'vitest'

import {
  MIND_MAP_E_BLACKBOARD_CONTROL_SCALE,
  mindMapControlScale,
} from '@/config/mindMapEBlackboard'

describe('mindMap classroom-board control scale', () => {
  it('stays 1x for mouse, laptop, and mobile', () => {
    expect(mindMapControlScale('mouse')).toBe(1)
    expect(mindMapControlScale('laptop')).toBe(1)
    expect(mindMapControlScale('mobile')).toBe(1)
  })

  it('uses the shared constant on the classroom board', () => {
    expect(MIND_MAP_E_BLACKBOARD_CONTROL_SCALE).toBe(2)
    expect(mindMapControlScale('board')).toBe(MIND_MAP_E_BLACKBOARD_CONTROL_SCALE)
  })
})
