/**
 * Dev-facing voice event log for Mobile Kitty (event bus listeners).
 */
import { onUnmounted } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'

export function useKittyMobileDebugBus(options: {
  ownerId: string
  pushLine: (prefix: string, detail: string) => void
  scheduleContextSync: () => void
}): void {
  const { ownerId, pushLine, scheduleContextSync } = options

  eventBus.onWithOwner(
    'voice:debug_rx',
    (payload) => {
      if (payload.type === 'action') {
        return
      }
      pushLine(`←${payload.type}`, payload.line)
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:started',
    (payload) => {
      const sid = payload.sessionId ?? ''
      pushLine('◇ws', sid.length > 14 ? `${sid.slice(0, 14)}…` : sid)
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:stopped',
    () => {
      pushLine('◇ws', 'voice stopped')
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:connected',
    (payload) => {
      const sid = payload.sessionId ?? ''
      pushLine('◆ok', sid.length > 14 ? `${sid.slice(0, 14)}…` : sid)
      scheduleContextSync()
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:ws_closed',
    (p) => {
      pushLine('◆×', `code=${String(p.code ?? '?')}`)
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:ws_error',
    (p) => {
      pushLine('⚠ws', String(p.error ?? '').slice(0, 52))
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:server_error',
    (p) => {
      pushLine('⚠srv', String(p.error ?? '').slice(0, 52))
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:action_executed',
    (p) => {
      let extra = ''
      try {
        const j = JSON.stringify(p.params ?? {})
        extra = j.length > 52 ? `${j.slice(0, 49)}…` : j
      } catch {
        extra = ''
      }
      pushLine(`→${p.action}`, extra)
    },
    ownerId
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(ownerId)
  })
}
