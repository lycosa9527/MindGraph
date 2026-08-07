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

  it('uses branch for branch_intro even when a child is present', () => {
    expect(
      resolveZhihuiSlideFocusHints({
        slideIndex: 1,
        focusNodeIds: ['branch-a'],
        lessonPlan: {
          frames: [
            {},
            {
              frame_role: 'branch_intro',
              focus_branch: 'branch-a',
              focus_child: 'child-x',
            },
          ],
        },
      })
    ).toEqual(['branch-a'])
  })

  it('prefers focus_child for child_detail so highlight tracks the PPT', () => {
    expect(
      resolveZhihuiSlideFocusHints({
        slideIndex: 2,
        focusNodeIds: ['branch-a'],
        lessonPlan: {
          frames: [
            {},
            {},
            {
              frame_role: 'child_detail',
              focus_branch: 'branch-a',
              focus_child: '叶绿体',
            },
          ],
        },
      })
    ).toEqual(['叶绿体'])
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

  it('uses slide title when plan child is missing on detail slides', () => {
    expect(
      resolveZhihuiSlideFocusHints({
        slideIndex: 1,
        focusNodeIds: ['branch-a'],
        slideTitle: '光反应',
        lessonPlan: {
          frames: [{}, { frame_role: 'child_detail', focus_branch: 'branch-a' }],
        },
      })
    ).toEqual(['光反应'])
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
