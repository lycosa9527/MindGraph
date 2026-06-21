/**
 * Opens the thinking coins modal when AI usage is blocked for insufficient balance.
 */
import { onBeforeUnmount, onMounted } from 'vue'

import { useNotifications } from '@/composables'
import { useLanguage } from '@/composables/core/useLanguage'
import { eventBus } from '@/composables/core/useEventBus'
import { useAuthStore } from '@/stores/auth'

export function useThinkingCoinInsufficientListener(
  openModal: (tab?: 'wallet' | 'subscription') => void
): void {
  const { t } = useLanguage()
  const notify = useNotifications()
  const authStore = useAuthStore()

  let offStream: (() => void) | undefined
  let offCoins: (() => void) | undefined

  function handleInsufficient(): void {
    notify.warning(
      `${t('thinkingCoins.insufficientTitle')} — ${t('thinkingCoins.insufficientBody')}`,
      6000
    )
    void authStore.refreshUserProfile({ bypassThrottle: true })
    openModal('wallet')
  }

  onMounted(() => {
    offStream = eventBus.on('mindmate:stream_error', ({ error_type }) => {
      if (error_type === 'thinking_coin_insufficient') {
        handleInsufficient()
      }
    })
    offCoins = eventBus.on('thinking_coins:insufficient', () => {
      handleInsufficient()
    })
  })

  onBeforeUnmount(() => {
    offStream?.()
    offCoins?.()
  })
}
