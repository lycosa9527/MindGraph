import { describe, expect, it } from 'vitest'

import { ledgerItemLabel } from '@/composables/auth/thinkingCoinsLedgerLabel'
import type { ThinkingCoinLedgerItem } from '@/types/thinkingCoins'

const t = (key: string) => {
  const messages: Record<string, string> = {
    'thinkingCoins.reason.task_reward': '任务奖励',
    'thinkingCoins.reason.daily_checkin': '每日签到',
    'thinkingCoins.reason.ai_spend': 'AI 消耗',
  }
  return messages[key] ?? key
}

function item(overrides: Partial<ThinkingCoinLedgerItem>): ThinkingCoinLedgerItem {
  return {
    id: 1,
    delta: 10,
    balance_after: 100,
    reason: 'task_reward',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('ledgerItemLabel', () => {
  it('shows localized task title for task_reward rows', () => {
    const label = ledgerItemLabel(
      item({
        reason: 'task_reward',
        task_title: '分享 MindMate 对话',
        task_title_en: 'Share a MindMate chat',
      }),
      t,
      true
    )
    expect(label).toBe('分享 MindMate 对话')
  })

  it('uses English task title when locale is not zh', () => {
    const label = ledgerItemLabel(
      item({
        reason: 'task_reward',
        task_title: '分享 MindMate 对话',
        task_title_en: 'Share a MindMate chat',
      }),
      t,
      false
    )
    expect(label).toBe('Share a MindMate chat')
  })

  it('falls back to reason label when task title is missing', () => {
    const label = ledgerItemLabel(item({ reason: 'task_reward' }), t, true)
    expect(label).toBe('任务奖励')
  })

  it('keeps generic reason labels for non-task rows', () => {
    expect(ledgerItemLabel(item({ reason: 'daily_checkin' }), t, true)).toBe('每日签到')
    expect(ledgerItemLabel(item({ reason: 'ai_spend', delta: -6 }), t, true)).toBe('AI 消耗')
  })
})
