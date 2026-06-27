import { describe, expect, it } from 'vitest'

import {
  UPGRADE_PAGE_INVITE_REWARD_DEFAULT,
  buildUpgradePageTaskCards,
  taskIsActionable,
} from '@/composables/auth/thinkingCoinsUpgradeUi'
import type { ThinkingCoinEarnTask } from '@/types/thinkingCoins'

function task(
  overrides: Partial<ThinkingCoinEarnTask> & Pick<ThinkingCoinEarnTask, 'id' | 'slug' | 'title'>
): ThinkingCoinEarnTask {
  return {
    reward_amount: 30,
    handler_key: 'usage_daily',
    action_config: {},
    ...overrides,
  }
}

describe('buildUpgradePageTaskCards', () => {
  it('lists all wallet tasks with pending first, then appends invite when no referral task', () => {
    const cards = buildUpgradePageTaskCards([
      task({ id: 3, slug: 'publish_case', title: '发布案例', completed_today: true }),
      task({ id: 1, slug: 'daily_checkin', title: '每日签到', completed_today: false }),
      task({ id: 9, slug: 'daily_mindmate', title: 'MindMate', completed_today: false }),
    ])

    expect(cards).toHaveLength(4)
    expect(cards.map((card) => (card.kind === 'task' ? card.task.slug : card.kind))).toEqual([
      'daily_checkin',
      'daily_mindmate',
      'publish_case',
      'invite',
    ])
    expect(cards[3]?.kind).toBe('invite')
    if (cards[3]?.kind === 'invite') {
      expect(cards[3].rewardAmount).toBe(UPGRADE_PAGE_INVITE_REWARD_DEFAULT)
    }
  })

  it('skips synthetic invite when referral task is present', () => {
    const cards = buildUpgradePageTaskCards([
      task({ id: 1, slug: 'daily_checkin', title: '每日签到' }),
      task({ id: 2, slug: 'referral_register', title: '邀请好友注册', reward_amount: 100 }),
      task({ id: 3, slug: 'publish_case', title: '发布案例' }),
    ])

    expect(cards.every((card) => card.kind === 'task')).toBe(true)
    expect(cards).toHaveLength(3)
  })
})

describe('taskIsActionable', () => {
  it('blocks publish_case while coming soon', () => {
    expect(
      taskIsActionable(
        task({
          id: 1,
          slug: 'publish_case',
          title: '发布案例',
          handler_key: 'navigate',
          coming_soon: true,
        })
      )
    ).toBe(false)
  })
})
