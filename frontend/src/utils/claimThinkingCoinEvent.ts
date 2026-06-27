/**
 * Fire-and-forget thinking coin claim after a product exploration action.
 */
import { applyThinkingCoinMutation } from '@/composables/auth/useThinkingCoinSync'
import { useAuthStore } from '@/stores/auth'
import type { ThinkingCoinMutationPayload } from '@/types/thinkingCoins'
import { apiRequestJson } from '@/utils/apiClient'

export async function claimThinkingCoinEvent(eventKey: string): Promise<number> {
  const authStore = useAuthStore()
  if (!authStore.user?.thinkingCoins?.eligible) {
    return 0
  }

  try {
    const result = await apiRequestJson<{
      credited: number
      balance: number
      thinking_coins?: ThinkingCoinMutationPayload
    }>('/api/auth/thinking-coins/claim-event', {
      method: 'POST',
      body: JSON.stringify({ event_key: eventKey }),
    })
    const footer =
      result.thinking_coins ??
      ({
        eligible: true,
        balance: result.balance,
        credited: result.credited,
      } satisfies ThinkingCoinMutationPayload)
    applyThinkingCoinMutation(footer)
    return result.credited
  } catch {
    return 0
  }
}
