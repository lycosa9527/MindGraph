import { describe, expect, it, vi } from 'vitest'

import {
  PRO_LEVEL_TAG_FIT_SLACK_PX,
  flexRowSparePx,
  nextProLevelTagExpanded,
} from '@/utils/proLevelTagFit'

describe('nextProLevelTagExpanded', () => {
  it('expands when spare room covers the clipped text', () => {
    expect(nextProLevelTagExpanded(false, 80, 40)).toBe(true)
  })

  it('stays clipped when the extra text would crowd the bar', () => {
    expect(nextProLevelTagExpanded(false, 40, 40)).toBe(false)
  })

  it('stays clipped when the current cap already fits the name', () => {
    expect(nextProLevelTagExpanded(false, 200, 0)).toBe(false)
    expect(nextProLevelTagExpanded(false, 200, 1)).toBe(false)
  })

  it('keeps the full name while the bar still has a little slack', () => {
    expect(nextProLevelTagExpanded(true, 4, 0)).toBe(true)
    expect(nextProLevelTagExpanded(true, -PRO_LEVEL_TAG_FIT_SLACK_PX, 0)).toBe(true)
  })

  it('clips again once the bar overflows', () => {
    expect(nextProLevelTagExpanded(true, -PRO_LEVEL_TAG_FIT_SLACK_PX - 1, 0)).toBe(false)
  })

  it('ignores a measurement that has not been laid out', () => {
    expect(nextProLevelTagExpanded(false, Number.NaN, 40)).toBe(false)
    expect(nextProLevelTagExpanded(true, Number.POSITIVE_INFINITY, 0)).toBe(true)
  })
})

describe('flexRowSparePx', () => {
  it('subtracts children and the column gap from the row width', () => {
    const slot = document.createElement('div')
    const first = document.createElement('span')
    const second = document.createElement('span')
    slot.append(first, second)
    Object.defineProperty(slot, 'clientWidth', { value: 200 })
    Object.defineProperty(first, 'offsetWidth', { value: 40 })
    Object.defineProperty(second, 'offsetWidth', { value: 60 })
    vi.spyOn(window, 'getComputedStyle').mockReturnValue({
      columnGap: '8px',
    } as CSSStyleDeclaration)
    expect(flexRowSparePx(slot)).toBe(92)
  })

  it('returns 0 before the row has a width', () => {
    const slot = document.createElement('div')
    Object.defineProperty(slot, 'clientWidth', { value: 0 })
    expect(flexRowSparePx(slot)).toBe(0)
  })
})
