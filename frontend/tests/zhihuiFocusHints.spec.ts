import { describe, expect, it } from 'vitest'

import {
  flattenLessonPlanFrames,
  resolveZhihuiSlideFocusHints,
} from '@/components/zhihui/zhihuiFocus'

describe('resolveZhihuiSlideFocusHints', () => {
  it('keeps slide 0 as topic overview even when focus_branch is set', () => {
    expect(
      resolveZhihuiSlideFocusHints({
        slideIndex: 0,
        focusNodeIds: ['b1'],
        lessonPlan: { frames: [{ focus_branch: 'b1' }] },
      })
    ).toEqual([])
  })

  it('prefers stored focus_node_ids on branch slides', () => {
    expect(
      resolveZhihuiSlideFocusHints({
        slideIndex: 1,
        focusNodeIds: ['branch-a'],
        lessonPlan: { frames: [{}, { focus_branch: 'other' }] },
      })
    ).toEqual(['branch-a'])
  })

  it('falls back to nested batches[].frames focus_branch', () => {
    expect(
      resolveZhihuiSlideFocusHints({
        slideIndex: 2,
        focusNodeIds: [],
        lessonPlan: {
          batches: [
            { frames: [{ focus_branch: '' }, { focus_branch: 'x' }] },
            { frames: [{ focus_branch: '分支二' }] },
          ],
        },
      })
    ).toEqual(['分支二'])
  })

  it('flattens planner batches in order', () => {
    const flat = flattenLessonPlanFrames({
      batches: [
        { frames: [{ title: 'a' }, { title: 'b' }] },
        { frames: [{ title: 'c' }] },
      ],
    })
    expect(flat.map((frame) => frame.title)).toEqual(['a', 'b', 'c'])
  })
})
