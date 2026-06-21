/**
 * Fire-and-forget thinking coin claim after a product exploration action.
 */
import { useAuthStore } from '@/stores/auth'
import { apiRequestJson } from '@/utils/apiClient'

export async function claimThinkingCoinEvent(eventKey: string): Promise<number> {
  const authStore = useAuthStore()
  if (!authStore.user?.thinkingCoins?.eligible) {
    return 0
  }

  try {
    const result = await apiRequestJson<{ credited: number; balance: number }>(
      '/api/auth/thinking-coins/claim-event',
      {
        method: 'POST',
        body: JSON.stringify({ event_key: eventKey }),
      }
    )
    if (result.credited > 0) {
      authStore.patchThinkingCoinsSummary({
        balance: result.balance,
        eligible: true,
      })
    }
    return result.credited
  } catch {
    return 0
  }
}
