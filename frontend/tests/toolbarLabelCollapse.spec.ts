import { describe, expect, it } from 'vitest'

import { createLabelCollapseSnapshot, nextLabelCollapse } from '@/utils/toolbarLabelCollapse'

describe('nextLabelCollapse', () => {
  it('keeps labels when they fit', () => {
    const next = nextLabelCollapse(createLabelCollapseSnapshot(), 800, 640)
    expect(next.collapsed).toBe(false)
    expect(next.fullLabelsWidth).toBe(640)
  })

  it('collapses when labels are wider than the slot', () => {
    const next = nextLabelCollapse(createLabelCollapseSnapshot(), 700, 980)
    expect(next.collapsed).toBe(true)
    expect(next.fullLabelsWidth).toBe(980)
  })

  it('stays collapsed while the slot is still narrower than the labeled width', () => {
    const collapsed = nextLabelCollapse(createLabelCollapseSnapshot(), 700, 980)
    const still = nextLabelCollapse(collapsed, 720, 280)
    expect(still).toBe(collapsed)
    expect(still.collapsed).toBe(true)
  })

  it('reopens labels once the slot can hold the labeled width', () => {
    const collapsed = nextLabelCollapse(createLabelCollapseSnapshot(), 700, 980)
    const reopened = nextLabelCollapse(collapsed, 980, 280)
    expect(reopened.collapsed).toBe(false)
    expect(reopened.fullLabelsWidth).toBe(980)
  })

  it('ignores a slot that has not been laid out', () => {
    const snapshot = createLabelCollapseSnapshot()
    expect(nextLabelCollapse(snapshot, -1, 400)).toBe(snapshot)
    expect(nextLabelCollapse(snapshot, Number.NaN, 400)).toBe(snapshot)
  })
})
