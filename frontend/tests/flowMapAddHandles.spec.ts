import { describe, expect, it } from 'vitest'

import { layoutFlowMapAddHandles, resolveFlowMapAddSelectionKind } from '@/utils/flowMapAddHandles'
import { FLOW_TOPIC_NODE_ID } from '@/utils/flowMapIdentity'

const rect = {
  left: 100,
  top: 200,
  right: 220,
  bottom: 260,
  width: 120,
  height: 60,
}

describe('flowMapAddHandles', () => {
  it('resolves topic, step, and substep selection kinds', () => {
    expect(resolveFlowMapAddSelectionKind({ id: FLOW_TOPIC_NODE_ID, type: 'topic' })).toBe('topic')
    expect(
      resolveFlowMapAddSelectionKind({
        id: 's1',
        type: 'flow',
        data: { stepIndex: 0 },
      })
    ).toBe('step')
    expect(
      resolveFlowMapAddSelectionKind({
        id: 'ss1',
        type: 'flowSubstep',
        data: { stepIndex: 0, substepIndex: 0 },
      })
    ).toBe('substep')
    expect(resolveFlowMapAddSelectionKind({ id: 'other', type: 'branch' })).toBeNull()
  })

  it('places horizontal row handles: topic right, step L/B/R, substep L/R', () => {
    expect(layoutFlowMapAddHandles('topic', 'horizontal', rect, 'row')).toEqual([
      { action: 'step-after', left: 220, top: 230 },
    ])
    expect(layoutFlowMapAddHandles('step', 'horizontal', rect, 'row')).toEqual([
      { action: 'step-before', left: 100, top: 230 },
      { action: 'substep-append', left: 160, top: 260 },
      { action: 'step-after', left: 220, top: 230 },
    ])
    expect(layoutFlowMapAddHandles('substep', 'horizontal', rect, 'row')).toEqual([
      { action: 'substep-before', left: 100, top: 230 },
      { action: 'substep-after', left: 220, top: 230 },
    ])
  })

  it('places horizontal stack substep handles top/bottom for before/after', () => {
    expect(layoutFlowMapAddHandles('substep', 'horizontal', rect, 'stack')).toEqual([
      { action: 'substep-before', left: 160, top: 200 },
      { action: 'substep-after', left: 160, top: 260 },
    ])
    // Step + sides stay L/B/R in horizontal stack.
    expect(layoutFlowMapAddHandles('step', 'horizontal', rect, 'stack')).toEqual([
      { action: 'step-before', left: 100, top: 230 },
      { action: 'substep-append', left: 160, top: 260 },
      { action: 'step-after', left: 220, top: 230 },
    ])
  })

  it('places vertical handles: topic bottom, step T/B/R, substep T/B', () => {
    expect(layoutFlowMapAddHandles('topic', 'vertical', rect)).toEqual([
      { action: 'step-after', left: 160, top: 260 },
    ])
    expect(layoutFlowMapAddHandles('step', 'vertical', rect)).toEqual([
      { action: 'step-before', left: 160, top: 200 },
      { action: 'step-after', left: 160, top: 260 },
      { action: 'substep-append', left: 220, top: 230 },
    ])
    expect(layoutFlowMapAddHandles('substep', 'vertical', rect)).toEqual([
      { action: 'substep-before', left: 160, top: 200 },
      { action: 'substep-after', left: 160, top: 260 },
    ])
  })
})
