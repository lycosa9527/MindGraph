import { describe, expect, it } from 'vitest'

import {
  buildSidebarPromoSlides,
  formatThinkingCoinTaskPromoTitle,
  nextThinkingCoinPromoIndex,
  pickInitialThinkingCoinPromoIndex,
  resolveSidebarPromoSlide,
  resolveThinkingCoinPromoTask,
  shouldPickFreshThinkingCoinPromoIndex,
  thinkingCoinPromoTaskPool,
} from '@/composables/sidebar/sidebarThinkingCoinTaskPromo'
import type { ThinkingCoinEarnTask } from '@/types/thinkingCoins'

function task(
  overrides: Partial<ThinkingCoinEarnTask> & Pick<ThinkingCoinEarnTask, 'id' | 'slug' | 'title'>
): ThinkingCoinEarnTask {
  return {
    reward_amount: 5,
    handler_key: 'usage_daily',
    action_config: {},
    ...overrides,
  }
}

describe('thinkingCoinPromoTaskPool', () => {
  it('lists pending tasks first then completed tasks', () => {
    const pool = thinkingCoinPromoTaskPool([
      task({ id: 1, slug: 'a', title: 'Done', completed_today: true }),
      task({ id: 2, slug: 'b', title: 'Pending', completed_today: false }),
      task({ id: 3, slug: 'c', title: 'Also pending', completed_today: false }),
    ])
    expect(pool.map((row) => row.slug)).toEqual(['b', 'c', 'a'])
  })

  it('falls back to all tasks when every task is completed', () => {
    const rows = [
      task({ id: 1, slug: 'a', title: 'Done A', completed_today: true }),
      task({ id: 2, slug: 'b', title: 'Done B', completed_today: true }),
    ]
    expect(thinkingCoinPromoTaskPool(rows)).toEqual(rows)
  })
})

describe('buildSidebarPromoSlides', () => {
  it('appends invite slide when no referral task exists', () => {
    const slides = buildSidebarPromoSlides([
      task({ id: 1, slug: 'daily_checkin', title: '每日签到' }),
    ])
    expect(slides.map((slide) => slide.key)).toEqual(['task-1', 'invite'])
  })

  it('skips duplicate invite slide when referral task is present', () => {
    const slides = buildSidebarPromoSlides([
      task({ id: 1, slug: 'referral_register', title: '邀请好友注册' }),
      task({ id: 2, slug: 'daily_checkin', title: '每日签到' }),
    ])
    expect(slides.map((slide) => slide.key)).toEqual(['task-1', 'task-2'])
  })

  it('returns invite-only slide when wallet tasks are empty', () => {
    expect(buildSidebarPromoSlides([])).toEqual([{ key: 'invite', kind: 'invite' }])
  })
})

describe('nextThinkingCoinPromoIndex', () => {
  it('wraps at the end of the list', () => {
    expect(nextThinkingCoinPromoIndex(0, 3)).toBe(1)
    expect(nextThinkingCoinPromoIndex(2, 3)).toBe(0)
    expect(nextThinkingCoinPromoIndex(0, 0)).toBe(0)
  })
})

describe('pickInitialThinkingCoinPromoIndex', () => {
  it('returns 0 for a single slide', () => {
    expect(pickInitialThinkingCoinPromoIndex(1)).toBe(0)
  })

  it('picks a random index within range', () => {
    expect(pickInitialThinkingCoinPromoIndex(4, () => 0.5)).toBe(2)
    expect(pickInitialThinkingCoinPromoIndex(4, () => 0.99)).toBe(3)
  })
})

describe('shouldPickFreshThinkingCoinPromoIndex', () => {
  it('is true when tasks first become rotatable after login or refresh', () => {
    expect(shouldPickFreshThinkingCoinPromoIndex(undefined, 3)).toBe(true)
    expect(shouldPickFreshThinkingCoinPromoIndex('invite', 4)).toBe(true)
  })

  it('is false when the promo pool was already rotatable', () => {
    expect(shouldPickFreshThinkingCoinPromoIndex('task-1|task-2|invite', 3)).toBe(false)
  })
})

describe('resolveThinkingCoinPromoTask', () => {
  it('returns null for an empty pool', () => {
    expect(resolveThinkingCoinPromoTask([], 0)).toBeNull()
  })

  it('wraps negative and overflow indices', () => {
    const rows = [
      task({ id: 1, slug: 'a', title: 'A' }),
      task({ id: 2, slug: 'b', title: 'B' }),
    ]
    expect(resolveThinkingCoinPromoTask(rows, 3)?.slug).toBe('b')
  })
})

describe('formatThinkingCoinTaskPromoTitle', () => {
  it('uses English title when UI is not Chinese', () => {
    expect(
      formatThinkingCoinTaskPromoTitle(
        task({ id: 1, slug: 'checkin', title: '每日签到', title_en: 'Daily check-in' }),
        false
      )
    ).toBe('Daily check-in')
  })

  it('uses Chinese title for zh UI', () => {
    expect(
      formatThinkingCoinTaskPromoTitle(
        task({ id: 1, slug: 'checkin', title: '每日签到', title_en: 'Daily check-in' }),
        true
      )
    ).toBe('每日签到')
  })
})
