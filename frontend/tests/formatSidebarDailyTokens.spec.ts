import { describe, expect, it } from 'vitest'

import { formatCompactTokenCount, formatSidebarDailyTokens } from '@/utils/formatSidebarDailyTokens'

describe('formatSidebarDailyTokens', () => {
  it('shows used over cap when a daily cap is set', () => {
    expect(formatSidebarDailyTokens(1234, 5_000_000)).toBe('1.2K / 5.0M')
  })

  it('shows only used when the cap is disabled', () => {
    expect(formatSidebarDailyTokens(99, 0)).toBe('99')
  })
})

describe('formatCompactTokenCount', () => {
  it('keeps small values as locale numbers', () => {
    expect(formatCompactTokenCount(42)).toBe('42')
  })
})
