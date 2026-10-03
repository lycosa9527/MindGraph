import { describe, expect, it } from 'vitest'

import {
  buildMultiFlowTopicHandles,
  multiFlowTopicHandleTopPercent,
} from '@/utils/multiFlowTopicHandles'

describe('multi-flow topic handles', () => {
  it('spaces every effect evenly down the right side', () => {
    const handles = buildMultiFlowTopicHandles('right', 6)
    expect(handles.map((handle) => handle.id)).toEqual([
      'right-0',
      'right-1',
      'right-2',
      'right-3',
      'right-4',
      'right-5',
    ])
    const tops = handles.map((handle) => parseFloat(handle.top))
    expect(tops).toEqual([1, 2, 3, 4, 5, 6].map((n) => multiFlowTopicHandleTopPercent(n - 1, 6)))
    const gaps = tops.slice(1).map((top, index) => top - tops[index])
    for (const gap of gaps) {
      expect(gap).toBeCloseTo(gaps[0] ?? 0, 8)
    }
    expect(handles.every((handle) => handle.transform === 'translateY(-50%)')).toBe(true)
  })

  it('mirrors causes on the left side with the same even gaps', () => {
    const causes = buildMultiFlowTopicHandles('left', 6)
    const effects = buildMultiFlowTopicHandles('right', 6)
    expect(causes.map((handle) => handle.top)).toEqual(effects.map((handle) => handle.top))
    expect(causes[0]?.id).toBe('left-0')
    expect(causes[0]?.top).toBe(effects[0]?.top)
    expect(causes[5]?.top).toBe(effects[5]?.top)
  })

  it('keeps one handle on the middle of the side', () => {
    expect(buildMultiFlowTopicHandles('right', 1)[0]?.top).toBe('50%')
  })

  it('moves the top handles up and the bottom handles down when another effect is added', () => {
    const before = buildMultiFlowTopicHandles('right', 4)
    const after = buildMultiFlowTopicHandles('right', 5)
    expect(parseFloat(after[0]?.top ?? '0')).toBeLessThan(parseFloat(before[0]?.top ?? '0'))
    expect(parseFloat(after[after.length - 1]?.top ?? '0')).toBeGreaterThan(
      parseFloat(before[before.length - 1]?.top ?? '0')
    )
  })
})
