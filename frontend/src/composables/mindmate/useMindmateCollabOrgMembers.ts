/**
 * MindMate collab org roster — fetches school colleagues without workshop chat access.
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { useTimestamp } from '@vueuse/core'

import { useLanguage } from '@/composables'
import { useMindmateCollabPresenceBridge } from '@/composables/mindmate/mindmateCollabPresenceBridge'
import { useAuthStore } from '@/stores/auth'
import { type OrgMember } from '@/stores/workshopChat'
import { authFetch } from '@/utils/api'
import { formatContactLastOnlineLabel } from '@/utils/formatContactLastOnline'
import { LAST_SEEN_ONLINE_MAX_AGE_MS } from '@/utils/workshopContactLastSeenStorage'

interface OrgMembersPageResponse {
  items: OrgMember[]
  total: number
  limit: number
  offset: number
}

export function useMindmateCollabOrgMembers() {
  const authStore = useAuthStore()
  const { t } = useLanguage()
  const nowMs = useTimestamp({ interval: 60_000 })

  const members = ref<OrgMember[]>([])
  const membersTotal = ref(0)
  const listQuery = ref('')
  const loading = ref(false)
  const loadingMore = ref(false)
  const contactsSearchInput = ref('')
  const { onlineUserIds } = useMindmateCollabPresenceBridge()

  let searchDebounce: ReturnType<typeof setTimeout> | null = null

  const membersHasMore = computed(() => members.value.length < membersTotal.value)

  const selfUserId = computed(() => Number(authStore.user?.id) || 0)

  function contactPresenceRank(memberId: number): number {
    void nowMs.value
    if (onlineUserIds.value.has(memberId)) {
      return 0
    }
    const member = members.value.find((m) => m.id === memberId)
    let serverMs: number | undefined
    if (member?.last_seen_at) {
      const parsed = Date.parse(member.last_seen_at)
      if (!Number.isNaN(parsed)) {
        serverMs = parsed
      }
    }
    if (
      serverMs !== undefined &&
      nowMs.value - serverMs >= 0 &&
      nowMs.value - serverMs <= LAST_SEEN_ONLINE_MAX_AGE_MS
    ) {
      return 1
    }
    return 2
  }

  function sortMembers(list: OrgMember[]): OrgMember[] {
    const sid = selfUserId.value
    const copy = [...list]
    copy.sort((a, b) => {
      const d = contactPresenceRank(a.id) - contactPresenceRank(b.id)
      if (d !== 0) {
        return d
      }
      if (sid) {
        if (a.id === sid) {
          return -1
        }
        if (b.id === sid) {
          return 1
        }
      }
      return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
    })
    return copy
  }

  const contactsOnline = computed(() => {
    void nowMs.value
    return sortMembers(members.value.filter((m) => contactPresenceRank(m.id) === 0))
  })

  const contactsRecentlyOnline = computed(() => {
    void nowMs.value
    return sortMembers(members.value.filter((m) => contactPresenceRank(m.id) === 1))
  })

  const contactsOffline = computed(() => {
    void nowMs.value
    return sortMembers(members.value.filter((m) => contactPresenceRank(m.id) === 2))
  })

  const contactsOnlineCount = computed(
    () => members.value.filter((m) => onlineUserIds.value.has(m.id)).length,
  )

  const displaySections = computed(() => {
    const sections: Array<{
      key: string
      labelKey: string
      members: OrgMember[]
      count: number
    }> = []
    const online = contactsOnline.value
    const offline = [...contactsRecentlyOnline.value, ...contactsOffline.value]
    if (online.length > 0) {
      sections.push({
        key: 'online',
        labelKey: 'workshop.contactsOnlineNow',
        members: online,
        count: online.length,
      })
    }
    if (offline.length > 0) {
      sections.push({
        key: 'offline',
        labelKey: 'workshop.contactsOffline',
        members: offline,
        count: offline.length,
      })
    }
    return sections
  })

  function isContactSelf(memberId: number): boolean {
    const sid = selfUserId.value
    return sid !== 0 && memberId === sid
  }

  async function fetchMembers(options?: {
    q?: string
    offset?: number
    append?: boolean
    limit?: number
  }): Promise<void> {
    const q = (options?.q ?? listQuery.value).trim()
    const offset = options?.offset ?? 0
    const append = options?.append ?? false
    const limit = options?.limit ?? 200
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    })
    if (q) {
      params.set('q', q)
    }
    try {
      const response = await authFetch(`/api/mindmate/collab/org-members?${params}`)
      if (!response.ok) {
        return
      }
      const data = (await response.json()) as OrgMembersPageResponse
      listQuery.value = q
      if (append) {
        members.value = [...members.value, ...data.items]
      } else {
        members.value = data.items
      }
      membersTotal.value = data.total
    } catch (err) {
      console.error('[MindmateCollabOrgMembers] fetchMembers error:', err)
    }
  }

  async function refreshContacts(): Promise<void> {
    loading.value = true
    try {
      await fetchMembers({ q: contactsSearchInput.value.trim(), offset: 0 })
    } finally {
      loading.value = false
    }
  }

  async function loadMoreContacts(): Promise<void> {
    if (!membersHasMore.value || loadingMore.value) {
      return
    }
    loadingMore.value = true
    try {
      await fetchMembers({
        q: listQuery.value,
        offset: members.value.length,
        append: true,
      })
    } finally {
      loadingMore.value = false
    }
  }

  watch(contactsSearchInput, (val) => {
    if (searchDebounce != null) {
      clearTimeout(searchDebounce)
    }
    searchDebounce = setTimeout(() => {
      searchDebounce = null
      void fetchMembers({ q: val.trim(), offset: 0 })
    }, 350)
  })

  onUnmounted(() => {
    if (searchDebounce != null) {
      clearTimeout(searchDebounce)
    }
  })

  return {
    members,
    membersTotal,
    membersHasMore,
    loading,
    loadingMore,
    contactsSearchInput,
    displaySections,
    contactsOnlineCount,
    isContactSelf,
    refreshContacts,
    loadMoreContacts,
  }
}
