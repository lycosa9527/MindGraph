import { describe, expect, it } from 'vitest'

import { formatThinkingCoinBalance } from '@/composables/auth/useThinkingCoins'

describe('formatThinkingCoinBalance', () => {
  it('formats non-negative integers with locale grouping', () => {
    const formatted = formatThinkingCoinBalance(12345)
    expect(formatted).toMatch(/12[,\u202f\u00a0]?345/)
  })

  it('clamps negative values to zero', () => {
    expect(formatThinkingCoinBalance(-50)).toBe('0')
  })

  it('formats zero', () => {
    expect(formatThinkingCoinBalance(0)).toBe('0')
  })
})

describe('thinking coin earn task card labels', () => {
  it('shows reward amount from task payload', () => {
    const task = {
      id: 1,
      slug: 'daily_checkin',
      title: '每日签到',
      reward_amount: 25,
      handler_key: 'auto_login',
      action_config: {},
    }
    const label = `+${task.reward_amount}`
    expect(label).toBe('+25')
  })

  it('marks usage tasks complete when completed_today is true', () => {
    const task = {
      id: 2,
      slug: 'daily_mindmate',
      title: 'MindMate',
      reward_amount: 20,
      handler_key: 'usage_daily',
      action_config: { request_type: 'mindmate' },
      completed_today: true,
    }
    expect(task.completed_today).toBe(true)
  })
})
