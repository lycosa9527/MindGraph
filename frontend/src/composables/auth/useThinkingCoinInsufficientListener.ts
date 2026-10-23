/**
 * Toast plus wallet when AI usage is blocked for insufficient thinking coins.
 * Mounted once from the app root so canvas and mobile see it as well as the sidebar.
 */
import { onBeforeUnmount, onMounted } from 'vue'

import { notify } from '@/composables/core/notifications'
import { eventBus } from '@/composables/core/useEventBus'
import { bilingualNotifyMessage, joinNotifyMessages } from '@/i18n/bilingualNotifyMessage'
import { useAuthStore } from '@/stores/auth'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'

const NOTICE_GAP_MS = 4000

export function useThinkingCoinInsufficientListener(
  openModal: (tab?: 'wallet' | 'subscription') => void
): void {
  const authStore = useAuthStore()

  let offStream: (() => void) | undefined
  let offCoins: (() => void) | undefined
  let lastNoticeAt = 0

  function handleInsufficient(): void {
    if (isMindgraphHeadlessExportSession()) {
      return
    }
    const now = Date.now()
    if (now - lastNoticeAt < NOTICE_GAP_MS) {
      return
    }
    lastNoticeAt = now
    notify.warning(
      joinNotifyMessages(
        [
          bilingualNotifyMessage('thinkingCoins.insufficientTitle'),
          bilingualNotifyMessage('thinkingCoins.insufficientBody'),
        ],
        ' — '
      ),
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
