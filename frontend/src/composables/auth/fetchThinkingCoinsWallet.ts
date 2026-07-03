/**
 * Thinking coins wallet API — single source for GET /wallet and auth summary sync.
 */
import { useAuthStore } from '@/stores/auth'
import type { ThinkingCoinsWallet } from '@/types/thinkingCoins'
import { apiRequestJson } from '@/utils/apiClient'

/** Stable scope key: refetch wallet earn-tasks only when this value changes. */
export function thinkingCoinsWalletScopeKey(
  eligible: boolean,
  userId: string | null | undefined,
): string {
  if (!eligible) {
    return ''
  }
  return userId ?? ''
}

export async function fetchThinkingCoinsWallet(): Promise<ThinkingCoinsWallet> {
  return apiRequestJson<ThinkingCoinsWallet>('/api/auth/thinking-coins/wallet', {
    method: 'GET',
  })
}

export function syncThinkingCoinsWalletSummary(wallet: ThinkingCoinsWallet): void {
  if (!wallet.eligible) {
    return
  }
  useAuthStore().patchThinkingCoinsSummary({
    balance: wallet.balance,
    eligible: wallet.eligible,
  })
}

/** Fetch wallet and mirror balance/eligibility into the auth store when eligible. */
export async function loadThinkingCoinsWallet(): Promise<ThinkingCoinsWallet> {
  const wallet = await fetchThinkingCoinsWallet()
  syncThinkingCoinsWalletSummary(wallet)
  return wallet
}
