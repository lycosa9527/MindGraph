import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  applyThinkingCoinMutation,
  extractThinkingCoinsFooter,
  patchEarnTasksFromMutation,
} from '@/composables/auth/useThinkingCoinSync'
import { eventBus } from '@/composables/core/useEventBus'
import { useAuthStore } from '@/stores/auth'
import type { ThinkingCoinEarnTask } from '@/types/thinkingCoins'

describe('useThinkingCoinSync', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
  })

  it('extractThinkingCoinsFooter parses eligible footer', () => {
    const footer = extractThinkingCoinsFooter({
      thinking_coins: {
        eligible: true,
        balance: 42,
        credited: 5,
        debited: 0,
        completed_slugs_today: ['diagram_save'],
      },
    })
    expect(footer).toEqual({
      eligible: true,
      balance: 42,
      credited: 5,
      debited: 0,
      task_slug: null,
      earn_events: [],
      completed_slugs_today: ['diagram_save'],
    })
  })

  it('applyThinkingCoinMutation patches auth balance and emits bus event', () => {
    const authStore = useAuthStore()
    authStore.user = {
      id: '1',
      username: 'trial',
      role: 'personal_trial',
      thinkingCoins: { balance: 10, eligible: true },
    }
    const emitSpy = vi.spyOn(eventBus, 'emit')

    applyThinkingCoinMutation({
      eligible: true,
      balance: 25,
      completed_slugs_today: ['daily_checkin'],
    })

    expect(authStore.user?.thinkingCoins?.balance).toBe(25)
    expect(emitSpy).toHaveBeenCalledWith('thinking_coins:mutation', {
      eligible: true,
      balance: 25,
      completed_slugs_today: ['daily_checkin'],
    })
  })

  it('patchThinkingCoinsSummary skips replace when balance and eligible unchanged', () => {
    const authStore = useAuthStore()
    authStore.user = {
      id: '1',
      username: 'trial',
      role: 'personal_trial',
      thinkingCoins: { balance: 42, eligible: true },
    }
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')

    authStore.patchThinkingCoinsSummary({ balance: 42, eligible: true })

    expect(setItemSpy).not.toHaveBeenCalled()
    setItemSpy.mockRestore()
  })

  it('patchEarnTasksFromMutation marks completed slugs', () => {
    const tasks: ThinkingCoinEarnTask[] = [
      {
        id: 1,
        slug: 'diagram_save',
        title: 'Save',
        reward_amount: 5,
        handler_key: 'usage_daily',
      },
      {
        id: 2,
        slug: 'diagram_export',
        title: 'Export',
        reward_amount: 5,
        handler_key: 'usage_daily',
      },
    ]

    const patched = patchEarnTasksFromMutation(tasks, {
      eligible: true,
      balance: 100,
      completed_slugs_today: ['diagram_save'],
    })

    expect(patched[0].completed_today).toBe(true)
    expect(patched[1].completed_today).toBeUndefined()
  })
})
