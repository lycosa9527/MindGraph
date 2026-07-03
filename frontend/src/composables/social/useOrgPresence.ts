/**
 * Org contact presence ranking (online / recently online / offline).
 */
import { computed } from 'vue'

import { useTimestamp } from '@vueuse/core'

import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { type OrgMember, useWorkshopChatStore } from '@/stores/workshopChat'
import { formatContactLastOnlineLabel } from '@/utils/formatContactLastOnline'
import { LAST_SEEN_ONLINE_MAX_AGE_MS } from '@/utils/workshopContactLastSeenStorage'

export function useOrgPresence() {
  const store = useWorkshopChatStore()
  const authStore = useAuthStore()
  const { t } = useLanguage()
  const nowMs = useTimestamp({ interval: 60_000 })

  const selfContactUserId = computed(() => Number(authStore.user?.id) || 0)

  function effectiveContactLastSeenMs(memberId: number): number | undefined {
    const member = store.orgMembers.find((m) => m.id === memberId)
    let serverMs: number | undefined
    if (member?.last_seen_at) {
      const parsed = Date.parse(member.last_seen_at)
      if (!Number.isNaN(parsed)) {
        serverMs = parsed
      }
    }
    const localMs = store.lastSeenOnlineAtByUserId[memberId]
    if (serverMs === undefined && localMs === undefined) {
      return undefined
    }
    if (serverMs === undefined) {
      return localMs
    }
    if (localMs === undefined) {
      return serverMs
    }
    return Math.max(serverMs, localMs)
  }

  function contactPresenceRank(memberId: number): number {
    void nowMs.value
    if (store.onlineUserIds.has(memberId)) {
      return 0
    }
    const ts = effectiveContactLastSeenMs(memberId)
    if (
      ts !== undefined &&
      nowMs.value - ts >= 0 &&
      nowMs.value - ts <= LAST_SEEN_ONLINE_MAX_AGE_MS
    ) {
      return 1
    }
    return 2
  }

  function sortContactsWithSelfFirst(members: OrgMember[]): OrgMember[] {
    const sid = selfContactUserId.value
    const copy = [...members]
    copy.sort((a, b) => {
      const d = contactPresenceRank(a.id) - contactPresenceRank(b.id)
      if (d !== 0) return d
      if (sid) {
        if (a.id === sid) return -1
        if (b.id === sid) return 1
      }
      return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
    })
    return copy
  }

  function sortRecentlyContactsWithSelfFirst(members: OrgMember[]): OrgMember[] {
    const sid = selfContactUserId.value
    const copy = [...members]
    copy.sort((a, b) => {
      if (sid) {
        if (a.id === sid) return -1
        if (b.id === sid) return 1
      }
      const ta = effectiveContactLastSeenMs(a.id) ?? 0
      const tb = effectiveContactLastSeenMs(b.id) ?? 0
      return tb - ta
    })
    return copy
  }

  const contactsOnline = computed(() => {
    void nowMs.value
    const list = store.orgMembers.filter((m) => contactPresenceRank(m.id) === 0)
    return sortContactsWithSelfFirst(list)
  })

  const contactsRecentlyOnline = computed(() => {
    void nowMs.value
    const list = store.orgMembers.filter((m) => contactPresenceRank(m.id) === 1)
    return sortRecentlyContactsWithSelfFirst(list)
  })

  const contactsOffline = computed(() => {
    void nowMs.value
    const list = store.orgMembers.filter((m) => contactPresenceRank(m.id) === 2)
    return sortContactsWithSelfFirst(list)
  })

  const contactsOnlineCount = computed(
    () => store.orgMembers.filter((m) => store.onlineUserIds.has(m.id)).length
  )

  function isContactSelf(memberId: number): boolean {
    const sid = selfContactUserId.value
    return sid !== 0 && memberId === sid
  }

  function contactLastOnlineSubtitle(memberId: number): string {
    void nowMs.value
    const ts = effectiveContactLastSeenMs(memberId)
    if (ts === undefined) {
      return ''
    }
    return formatContactLastOnlineLabel(ts, nowMs.value, t)
  }

  return {
    contactsOnline,
    contactsRecentlyOnline,
    contactsOffline,
    contactsOnlineCount,
    isContactSelf,
    contactLastOnlineSubtitle,
    contactPresenceRank,
  }
}
