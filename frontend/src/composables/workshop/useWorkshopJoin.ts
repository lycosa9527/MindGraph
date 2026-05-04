import type { Ref } from 'vue'

import type { UseLanguageTranslate } from '@/composables/core/useLanguage'

const COLLAB_AUTH_REFRESH_RECONNECT_MS = 50 * 60 * 1000

interface WorkshopJoinAuthStore {
  refreshAccessToken: () => Promise<{ success: boolean }>
}

interface WorkshopJoinNotify {
  warning: (message: string) => void
}

interface UseWorkshopJoinOptions {
  workshopCode: Ref<string | null>
  joinResumeToken: Ref<string | null>
  ws: Ref<WebSocket | null>
  authStore: WorkshopJoinAuthStore
  notify: WorkshopJoinNotify
  t: UseLanguageTranslate
  connect: () => void
}

export function useWorkshopJoin(options: UseWorkshopJoinOptions) {
  let authRefreshReconnectTimeout: ReturnType<typeof setTimeout> | null = null

  function getWebSocketUrl(code: string): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    let base = `${protocol}//${host}/api/ws/canvas-collab/${code}`
    const resume = options.joinResumeToken.value?.trim()
    if (resume) {
      const sep = base.includes('?') ? '&' : '?'
      base += `${sep}resume=${encodeURIComponent(resume)}`
    }
    return base
  }

  function clearAuthRefreshReconnect(): void {
    if (authRefreshReconnectTimeout) {
      clearTimeout(authRefreshReconnectTimeout)
      authRefreshReconnectTimeout = null
    }
  }

  function scheduleAuthRefreshReconnect(): void {
    clearAuthRefreshReconnect()
    authRefreshReconnectTimeout = setTimeout(() => {
      void (async () => {
        if (!options.workshopCode.value || !options.ws.value) {
          return
        }
        const refreshed = await options.authStore.refreshAccessToken()
        if (!refreshed.success) {
          options.notify.warning(options.t('workshopCanvas.sessionRefreshFailed'))
          return
        }
        const sock = options.ws.value
        if (sock && sock.readyState <= WebSocket.OPEN) {
          sock.addEventListener('close', () => options.connect(), { once: true })
          sock.close(1000, 'auth_refreshed_reconnect')
        } else {
          options.connect()
        }
      })()
    }, COLLAB_AUTH_REFRESH_RECONNECT_MS)
  }

  return {
    getWebSocketUrl,
    clearAuthRefreshReconnect,
    scheduleAuthRefreshReconnect,
  }
}
