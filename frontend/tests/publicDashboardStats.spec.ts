import { describe, expect, it } from 'vitest'

import {
  EMPTY_DASHBOARD_STATS,
  applyDashboardStats,
  formatCompactNumber,
} from '@/utils/publicDashboardStats'

describe('publicDashboardStats', () => {
  it('formats compact token counts', () => {
    expect(formatCompactNumber(0)).toBe('0')
    expect(formatCompactNumber(950)).toBe((950).toLocaleString())
    expect(formatCompactNumber(1500)).toBe('1.5K')
    expect(formatCompactNumber(2_400_000)).toBe('2.4M')
  })

  it('does not let SSE connected-user ticks wipe token totals', () => {
    const loaded = applyDashboardStats(EMPTY_DASHBOARD_STATS, {
      connected_users: 4,
      registered_users: 1200,
      tokens_used_today: 88000,
      total_tokens_used: 9_500_000,
    })
    const afterSse = applyDashboardStats(loaded, { connected_users: 6 })
    expect(afterSse).toEqual({
      connected_users: 6,
      registered_users: 1200,
      tokens_used_today: 88000,
      total_tokens_used: 9_500_000,
    })
  })

  it('ignores non-numeric SSE leftovers', () => {
    const current = applyDashboardStats(EMPTY_DASHBOARD_STATS, {
      tokens_used_today: 42,
      total_tokens_used: 99,
    })
    const next = applyDashboardStats(current, {
      tokens_used_today: undefined,
      total_tokens_used: '0' as unknown as number,
    })
    expect(next.tokens_used_today).toBe(42)
    expect(next.total_tokens_used).toBe(99)
  })
})
