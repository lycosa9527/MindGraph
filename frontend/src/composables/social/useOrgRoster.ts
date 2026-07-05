/**
 * Org roster list controller — search debounce, refresh, and load-more
 * on top of a pluggable OrgRosterBackend.
 */
import { onUnmounted, ref, watch } from 'vue'

import type { OrgRosterBackend } from '@/composables/social/types'

const ORG_ROSTER_SEARCH_DEBOUNCE_MS = 350
const ORG_ROSTER_PAGE_SIZE = 200

export function useOrgRoster(backend: OrgRosterBackend) {
  const contactsSearchInput = ref('')
  const loading = ref(false)
  const loadingMore = ref(false)
  let contactsSearchDebounce: ReturnType<typeof setTimeout> | null = null

  watch(contactsSearchInput, (val) => {
    if (contactsSearchDebounce != null) {
      clearTimeout(contactsSearchDebounce)
    }
    contactsSearchDebounce = setTimeout(async () => {
      contactsSearchDebounce = null
      await backend.fetchMembers({ q: val.trim(), offset: 0, limit: ORG_ROSTER_PAGE_SIZE })
    }, ORG_ROSTER_SEARCH_DEBOUNCE_MS)
  })

  async function refreshContacts(): Promise<void> {
    loading.value = true
    try {
      await backend.fetchMembers({
        q: contactsSearchInput.value.trim(),
        offset: 0,
        limit: ORG_ROSTER_PAGE_SIZE,
      })
    } finally {
      loading.value = false
    }
  }

  async function loadMoreContacts(): Promise<void> {
    if (!backend.membersHasMore.value || loadingMore.value) {
      return
    }
    loadingMore.value = true
    try {
      await backend.fetchMembers({
        q: backend.listQuery.value,
        offset: backend.members.value.length,
        append: true,
        limit: ORG_ROSTER_PAGE_SIZE,
      })
    } finally {
      loadingMore.value = false
    }
  }

  onUnmounted(() => {
    if (contactsSearchDebounce != null) {
      clearTimeout(contactsSearchDebounce)
    }
  })

  return {
    members: backend.members,
    membersTotal: backend.membersTotal,
    membersHasMore: backend.membersHasMore,
    listQuery: backend.listQuery,
    contactsSearchInput,
    loading,
    loadingMore,
    refreshContacts,
    loadMoreContacts,
  }
}
