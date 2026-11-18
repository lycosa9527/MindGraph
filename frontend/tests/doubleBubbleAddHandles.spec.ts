import { describe, expect, it } from 'vitest'

import {
  layoutDoubleBubbleAddHandles,
  resolveDoubleBubbleAddSelectionKind,
} from '@/utils/doubleBubbleAddHandles'
import {
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
  DOUBLE_BUBBLE_ROLE_DATA_KEY,
} from '@/utils/doubleBubbleMapIdentity'

const rect = {
  left: 100,
  top: 200,
  right: 180,
  bottom: 260,
  width: 80,
  height: 60,
}

describe('doubleBubbleAddHandles', () => {
  it('resolves topic and role selection kinds', () => {
    expect(resolveDoubleBubbleAddSelectionKind({ id: DOUBLE_BUBBLE_LEFT_TOPIC_ID })).toBe(
      'leftTopic'
    )
    expect(resolveDoubleBubbleAddSelectionKind({ id: DOUBLE_BUBBLE_RIGHT_TOPIC_ID })).toBe(
      'rightTopic'
    )
    expect(
      resolveDoubleBubbleAddSelectionKind({
        id: 'abc',
        data: { [DOUBLE_BUBBLE_ROLE_DATA_KEY]: 'similarity' },
      })
    ).toBe('similarity')
    expect(
      resolveDoubleBubbleAddSelectionKind({
        id: 'abc',
        data: { [DOUBLE_BUBBLE_ROLE_DATA_KEY]: 'leftDiff' },
      })
    ).toBe('leftDiff')
  })

  it('places a bottom + for similarity and difference bubbles', () => {
    expect(layoutDoubleBubbleAddHandles('similarity', rect)).toEqual([
      { action: 'similarity', left: 140, top: 260 },
    ])
    expect(layoutDoubleBubbleAddHandles('leftDiff', rect)).toEqual([
      { action: 'difference', left: 140, top: 260 },
    ])
    expect(layoutDoubleBubbleAddHandles('rightDiff', rect)).toEqual([
      { action: 'difference', left: 140, top: 260 },
    ])
  })

  it('places outer difference and inner similarity on topic bubbles', () => {
    // Topic A (left): left = difference, right = similarity
    expect(layoutDoubleBubbleAddHandles('leftTopic', rect)).toEqual([
      { action: 'difference', left: 100, top: 230 },
      { action: 'similarity', left: 180, top: 230 },
    ])
    // Topic B (right): left = similarity, right = difference
    expect(layoutDoubleBubbleAddHandles('rightTopic', rect)).toEqual([
      { action: 'similarity', left: 100, top: 230 },
      { action: 'difference', left: 180, top: 230 },
    ])
  })
})
