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
  const { pollKey, intervalMs, fetch, immediate = true } = options
  const adminPanel = useAdminPanelStore()

  let intervalId: ReturnType<typeof setInterval> | null = null
  let tornDown = false

  function stopPolling(): void {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  function dispose(): void {
    if (tornDown) {
      return
    }
    tornDown = true
    document.removeEventListener('visibilitychange', onVisibility)
    stopPolling()
    adminPanel.unregisterPoll(pollKey)
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
    stopPolling()
    adminPanel.registerPoll(pollKey)
    void fetch()
    intervalId = setInterval(() => {
      if (document.visibilityState === 'hidden') {
        return
      }
      void fetch()
    }, intervalMs)
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
