import { describe, expect, it } from 'vitest'

import { draftFromSpec, retargetDraft, specFromDraft } from '@/utils/handdrawnImportManual'

describe('handdrawn import manual draft', () => {
  it('round-trips a double bubble, a flow, and a mind map', () => {
    const doubleSpec = {
      left: '2.4g',
      right: '5g',
      similarities: ['无线频段'],
      left_differences: ['频率较低'],
      right_differences: ['频率较高'],
    }
    const doubleDraft = draftFromSpec('double_bubble_map', doubleSpec)
    if (!doubleDraft) throw new Error('double bubble draft missing')
    expect(specFromDraft(doubleDraft)).toEqual(doubleSpec)

    const flowSpec = {
      title: '接收SSTV',
      steps: ['准备阶段'],
      substeps: [{ step: '准备阶段', stepIndex: 0, substeps: ['确认频率与模式'] }],
    }
    const flowDraft = draftFromSpec('flow_map', flowSpec)
    if (!flowDraft) throw new Error('flow draft missing')
    expect(specFromDraft(flowDraft)).toEqual(flowSpec)

    const mindDraft = draftFromSpec('mindmap', {
      topic: '露和霜',
      children: [{ text: '课程定位', children: [{ text: '学科：科学' }] }],
    })
    if (!mindDraft) throw new Error('mind map draft missing')
    expect(mindDraft.outline).toBe('课程定位\n  学科：科学')
    expect(specFromDraft(mindDraft)).toEqual({
      topic: '露和霜',
      children: [{ text: '课程定位', children: [{ text: '学科：科学' }] }],
    })
  })

  it('keeps the text when the confirmed type changes', () => {
    const draft = draftFromSpec('mindmap', {
      topic: '天气',
      children: [{ text: '露' }, { text: '霜' }],
    })
    if (!draft) throw new Error('draft missing')
    const asCircle = retargetDraft(draft, 'circle_map')
    expect(asCircle.diagramType).toBe('circle_map')
    expect(asCircle.topic).toBe('天气')
    expect(specFromDraft(asCircle)).toEqual({ topic: '天气', context: ['露', '霜'] })
  })
})
