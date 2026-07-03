import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  fetchThinkingCoinsWallet,
  loadThinkingCoinsWallet,
  syncThinkingCoinsWalletSummary,
  thinkingCoinsWalletScopeKey,
} from '@/composables/auth/fetchThinkingCoinsWallet'
import { useAuthStore } from '@/stores/auth'
import type { ThinkingCoinsWallet } from '@/types/thinkingCoins'

vi.mock('@/utils/apiClient', () => ({
  apiRequestJson: vi.fn(),
}))

import { apiRequestJson } from '@/utils/apiClient'

const walletFixture: ThinkingCoinsWallet = {
  balance: 120,
  eligible: true,
  earn_tasks: [
    {
      id: 1,
      slug: 'daily_checkin',
      title: 'Check in',
      reward_amount: 5,
      handler_key: 'auto_login',
      action_config: {},
    },
  ],
}

describe('thinkingCoinsWalletScopeKey', () => {
  it('returns empty string when user is not eligible', () => {
    expect(thinkingCoinsWalletScopeKey(false, '3')).toBe('')
  })

  it('returns user id when eligible', () => {
    expect(thinkingCoinsWalletScopeKey(true, '3')).toBe('3')
  })

  it('stays stable for the same eligible session (balance patch must not refetch)', () => {
    const before = thinkingCoinsWalletScopeKey(true, '3')
    const after = thinkingCoinsWalletScopeKey(true, '3')
    expect(after).toBe(before)
  })

  it('changes when account switches', () => {
    expect(thinkingCoinsWalletScopeKey(true, '3')).not.toBe(thinkingCoinsWalletScopeKey(true, '4'))
  })
})

describe('fetchThinkingCoinsWallet', () => {
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
    vi.mocked(apiRequestJson).mockReset()
  })

  it('fetchThinkingCoinsWallet calls wallet endpoint', async () => {
    vi.mocked(apiRequestJson).mockResolvedValue(walletFixture)

    const wallet = await fetchThinkingCoinsWallet()

    expect(apiRequestJson).toHaveBeenCalledWith('/api/auth/thinking-coins/wallet', {
      method: 'GET',
    })
    expect(wallet).toEqual(walletFixture)
  })

  it('syncThinkingCoinsWalletSummary patches auth when eligible', () => {
    const authStore = useAuthStore()
    authStore.user = {
      id: '1',
      username: 'trial',
      role: 'personal_trial',
      thinkingCoins: { balance: 10, eligible: true },
    }

    syncThinkingCoinsWalletSummary(walletFixture)

    expect(authStore.user?.thinkingCoins?.balance).toBe(120)
  })

  it('loadThinkingCoinsWallet fetches and syncs auth summary', async () => {
    vi.mocked(apiRequestJson).mockResolvedValue(walletFixture)
    const authStore = useAuthStore()
    authStore.user = {
      id: '1',
      username: 'trial',
      role: 'personal_trial',
      thinkingCoins: { balance: 10, eligible: true },
    }

    const wallet = await loadThinkingCoinsWallet()

    expect(wallet).toEqual(walletFixture)
    expect(authStore.user?.thinkingCoins?.balance).toBe(120)
  })
})
