import { describe, expect, it } from 'vitest'

import {
  beijingCalendarDaysBetween,
  beijingDayStartMs,
  beijingHour,
  formatInBeijing,
  parseApiInstant,
  parseBeijingWall,
} from '@/utils/beijingClock'

describe('beijingClock', () => {
  it('shows a naive UTC timestamp as Beijing time', () => {
    expect(
      formatInBeijing('2026-10-22T06:00:49', 'en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      })
    ).toBe('10/22/2026, 14:00:49')
    expect(formatInBeijing('2026-10-22T06:00:49Z', 'zh-CN')).toContain('14:00:49')
  })

  it('keeps a Beijing calendar label on that day', () => {
    const wall = parseBeijingWall('2026-10-22')
    expect(wall).not.toBeNull()
    expect(beijingHour(wall ?? new Date())).toBe(0)
    expect(
      formatInBeijing(wall, 'en-CA', { year: 'numeric', month: '2-digit', day: '2-digit' })
    ).toBe('2026-10-22')
  })

  it('counts calendar days from Beijing midnight', () => {
    const earlier = parseApiInstant('2026-10-22T16:30:00Z')
    const later = parseApiInstant('2026-10-22T16:30:00Z')
    expect(earlier).not.toBeNull()
    expect(later).not.toBeNull()
    expect(beijingCalendarDaysBetween(earlier ?? new Date(), later ?? new Date())).toBe(0)
    expect(beijingDayStartMs(earlier ?? new Date())).toBe(Date.parse('2026-10-23T00:00:00+08:00'))
  })
})
