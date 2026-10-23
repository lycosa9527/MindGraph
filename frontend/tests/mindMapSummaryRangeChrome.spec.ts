import { describe, expect, it } from 'vitest'

import {
  isMindMapSummaryRangeChromeActive,
  isMindMapSummaryStyleHandleActive,
} from '@/composables/mindMap/mindMapSummaryRangeChrome'
import { mindMapSummaryChildNodeId, mindMapSummaryRootNodeId } from '@/utils/mindMapSummary'

describe('mind map summary range chrome', () => {
  const summaryId = 's1'
  const rootId = mindMapSummaryRootNodeId(summaryId)

  it('shows the range box while the 概要 node is selected after create', () => {
    expect(
      isMindMapSummaryRangeChromeActive(summaryId, {
        toolbarSummaryId: null,
        draggingSummaryId: null,
        selectedNodeIds: [rootId],
      })
    ).toBe(true)
  })

  it('hides the range box after a canvas click clears selection', () => {
    expect(
      isMindMapSummaryRangeChromeActive(summaryId, {
        toolbarSummaryId: null,
        draggingSummaryId: null,
        selectedNodeIds: [],
      })
    ).toBe(false)
  })

  it('keeps the range box while the style toolbar or range drag is active', () => {
    expect(
      isMindMapSummaryRangeChromeActive(summaryId, {
        toolbarSummaryId: summaryId,
        draggingSummaryId: null,
        selectedNodeIds: [],
      })
    ).toBe(true)
    expect(
      isMindMapSummaryRangeChromeActive(summaryId, {
        toolbarSummaryId: null,
        draggingSummaryId: summaryId,
        selectedNodeIds: [],
      })
    ).toBe(true)
  })

  it('does not show the range box for another topic or another 概要', () => {
    expect(
      isMindMapSummaryRangeChromeActive(summaryId, {
        toolbarSummaryId: null,
        draggingSummaryId: null,
        selectedNodeIds: ['r/0'],
      })
    ).toBe(false)
    expect(
      isMindMapSummaryRangeChromeActive(summaryId, {
        toolbarSummaryId: 'other',
        draggingSummaryId: null,
        selectedNodeIds: [mindMapSummaryRootNodeId('other')],
      })
    ).toBe(false)
  })

  it('hides the range box when only a 概要 child topic is selected', () => {
    expect(
      isMindMapSummaryRangeChromeActive(summaryId, {
        toolbarSummaryId: null,
        draggingSummaryId: null,
        selectedNodeIds: [mindMapSummaryChildNodeId(summaryId, [0])],
      })
    ).toBe(false)
  })

  it('shows range chrome but not the style handle when only the 概要 root is selected', () => {
    const ctx = {
      toolbarSummaryId: null,
      draggingSummaryId: null,
      selectedNodeIds: [rootId],
    }
    expect(isMindMapSummaryRangeChromeActive(summaryId, ctx)).toBe(true)
    expect(isMindMapSummaryStyleHandleActive(summaryId, ctx)).toBe(false)
  })

  it('marks the style handle active only for toolbar or range drag', () => {
    expect(
      isMindMapSummaryStyleHandleActive(summaryId, {
        toolbarSummaryId: summaryId,
        draggingSummaryId: null,
      })
    ).toBe(true)
    expect(
      isMindMapSummaryStyleHandleActive(summaryId, {
        toolbarSummaryId: null,
        draggingSummaryId: summaryId,
      })
    ).toBe(true)
    expect(
      isMindMapSummaryStyleHandleActive(summaryId, {
        toolbarSummaryId: null,
        draggingSummaryId: null,
      })
    ).toBe(false)
  })
})
