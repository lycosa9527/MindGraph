/**
 * Visibility-aware admin polling — registers poll keys in adminPanel store.
 */
import { onBeforeUnmount, onMounted } from 'vue'

import { onBeforeRouteLeave } from 'vue-router'

import { useAdminPanelStore, type AdminPollKey } from '@/stores/adminPanel'

export interface UseAdminPollingOptions {
  pollKey: AdminPollKey
  intervalMs: number
  fetch: () => void | Promise<void>
  immediate?: boolean
}

export function useAdminPolling(options: UseAdminPollingOptions) {
  const { pollKey, fetch, immediate = true } = options
  const adminPanel = useAdminPanelStore()

  let tornDown = false

  function stopPolling(): void {
    adminPanel.unregisterPoll(pollKey)
  }

  function dispose(): void {
    if (tornDown) {
      return
    }
    tornDown = true
    document.removeEventListener('visibilitychange', onVisibility)
    stopPolling()
  }

  function onVisibility(): void {
    if (document.visibilityState === 'visible') {
      void fetch()
    }
  }

  function startPolling(): void {
    if (tornDown) {
      return
    }
    adminPanel.registerPoll(pollKey)
    void fetch()
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', onVisibility)
    if (immediate) {
      startPolling()
    }
  })

  onBeforeRouteLeave(() => {
    dispose()
  })

  onBeforeUnmount(() => {
    dispose()
  })

  return {
    startPolling,
    stopPolling,
    dispose,
    refetch: fetch,
    isPollActive: () => adminPanel.isPollActive(pollKey),
  }
}
