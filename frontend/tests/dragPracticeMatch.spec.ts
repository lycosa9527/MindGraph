import { describe, expect, it } from 'vitest'

import { dragPracticeSlotGroup } from '@/composables/mindMap/dragPracticeMatch'

describe('dragPracticeSlotGroup', () => {
  it('groups double-bubble differences by column, not by index', () => {
    const nodes = [
      { id: 'l1', data: { doubleBubbleRole: 'leftDiff' } },
      { id: 'l2', data: { doubleBubbleRole: 'leftDiff' } },
      { id: 'r1', data: { doubleBubbleRole: 'rightDiff' } },
      { id: 's1', data: { doubleBubbleRole: 'similarity' } },
    ]
    expect(dragPracticeSlotGroup('double_bubble_map', 'l1', nodes, [])).toBe(
      dragPracticeSlotGroup('double_bubble_map', 'l2', nodes, [])
    )
    expect(dragPracticeSlotGroup('double_bubble_map', 'l1', nodes, [])).not.toBe(
      dragPracticeSlotGroup('double_bubble_map', 'r1', nodes, [])
    )
    expect(dragPracticeSlotGroup('double_bubble_map', 's1', nodes, [])).toBe('role:similarity')
  })

  it('keeps flow steps on their own slot', () => {
    const nodes = [
      { id: 's1', parentId: 'flow-topic' },
      { id: 's2', parentId: 'flow-topic' },
    ]
    expect(dragPracticeSlotGroup('flow_map', 's1', nodes, [])).toBe('node:s1')
    expect(dragPracticeSlotGroup('flow_map', 's2', nodes, [])).toBe('node:s2')
  })

  it('groups mind-map siblings that share a parent', () => {
    const nodes = [
      { id: 'a', parentId: 'topic' },
      { id: 'b', parentId: 'topic' },
      { id: 'c', parentId: 'a' },
    ]
    expect(dragPracticeSlotGroup('mind_map', 'a', nodes, [])).toBe('parent:topic')
    expect(dragPracticeSlotGroup('mind_map', 'b', nodes, [])).toBe('parent:topic')
    expect(dragPracticeSlotGroup('mind_map', 'c', nodes, [])).toBe('parent:a')
  })
})
