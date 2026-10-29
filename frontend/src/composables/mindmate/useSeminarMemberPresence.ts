/**
 * Seminar member dots follow the workshop contact list:
 * live org presence, then "last online" from this browser or the server stamp.
 */
import { useTimestamp } from '@vueuse/core'

import { useLanguage } from '@/composables'
import { useMindmateSeminarPresenceBridge } from '@/composables/mindmate/mindmateSeminarPresenceBridge'
import { useAuthStore } from '@/stores/auth'
import { formatContactLastOnlineLabel } from '@/utils/formatContactLastOnline'
import { LAST_SEEN_ONLINE_MAX_AGE_MS } from '@/utils/workshopContactLastSeenStorage'

export function useSeminarMemberPresence() {
  const { t } = useLanguage()
  const auth = useAuthStore()
  const { onlineUserIds, lastSeenOnlineAtByUserId, presenceReady } =
    useMindmateSeminarPresenceBridge()
  const nowMs = useTimestamp({ interval: 60_000 })

  function freshMs(ts: number | undefined): number | undefined {
    if (ts === undefined) {
      return undefined
    }
    const age = nowMs.value - ts
    if (age < 0 || age > LAST_SEEN_ONLINE_MAX_AGE_MS) {
      return undefined
    }
    return ts
  }

  function isOnline(userId: number, roomOnline: boolean): boolean {
    if (!presenceReady.value) {
      const selfId = Number(auth.user?.id) || 0
      if (selfId > 0 && userId === selfId && onlineUserIds.value.has(selfId)) {
        return true
      }
      return roomOnline
    }
    return onlineUserIds.value.has(userId)
  }

  function lastSeenMs(userId: number, serverLastSeen?: string | null): number | undefined {
    const local = freshMs(lastSeenOnlineAtByUserId.value[userId])
    let server: number | undefined
    if (serverLastSeen) {
      const parsed = Date.parse(serverLastSeen)
      if (!Number.isNaN(parsed)) {
        server = freshMs(parsed)
      }
    }
    if (local === undefined) {
      return server
    }
    if (server === undefined) {
      return local
    }
    return Math.max(local, server)
  }

  function presenceRank(
    userId: number,
    roomOnline: boolean,
    serverLastSeen?: string | null
  ): number {
    if (isOnline(userId, roomOnline)) {
      return 0
    }
    if (lastSeenMs(userId, serverLastSeen) !== undefined) {
      return 1
    }
    return 2
  }

  function statusText(userId: number, roomOnline: boolean, serverLastSeen?: string | null): string {
    if (isOnline(userId, roomOnline)) {
      return t('mindmate.home.memberOnline')
    }
    const ts = lastSeenMs(userId, serverLastSeen)
    if (ts !== undefined) {
      const label = formatContactLastOnlineLabel(ts, nowMs.value, (key, named) =>
        named ? t(key, named) : t(key)
      )
      if (label) {
        return label
      }
    }
    return t('mindmate.home.memberOffline')
  }

  return { isOnline, presenceRank, statusText }
}
