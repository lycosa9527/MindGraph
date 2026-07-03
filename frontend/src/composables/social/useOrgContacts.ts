/**
 * Org contacts roster — search, pagination, and presence sections.
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { useOrgPresence } from '@/composables/social/useOrgPresence'
import { type OrgMember, useWorkshopChatStore } from '@/stores/workshopChat'

export interface ContactSection {
  key: string
  labelKey: string | null
  members: OrgMember[]
}

export function useOrgContacts() {
  const store = useWorkshopChatStore()
  const presence = useOrgPresence()

  const contactsSearchInput = ref('')
  const loadingMoreContacts = ref(false)
  let contactsSearchDebounce: ReturnType<typeof setTimeout> | null = null

  const contactSections = computed((): ContactSection[] => {
    void presence.contactsOnline.value
    const on = presence.contactsOnline.value
    const recent = presence.contactsRecentlyOnline.value
    const off = presence.contactsOffline.value
    const sections: ContactSection[] = []
    if (on.length > 0) {
      sections.push({
        key: 'online',
        labelKey: 'workshop.contactsOnlineNow',
        members: on,
      })
    }
    if (recent.length > 0) {
      sections.push({
        key: 'recently_online',
        labelKey: 'workshop.contactsRecentlyOnline',
        members: recent,
      })
    }
    if (off.length > 0) {
      sections.push({
        key: 'offline',
        labelKey: 'workshop.contactsOffline',
        members: off,
      })
    }
    return sections
  })

  watch(contactsSearchInput, (val) => {
    if (contactsSearchDebounce != null) {
      clearTimeout(contactsSearchDebounce)
    }
    contactsSearchDebounce = setTimeout(async () => {
      contactsSearchDebounce = null
      const q = val.trim()
      await store.fetchOrgMembers({ q, offset: 0, limit: 200 })
    }, 350)
  })

  async function loadMoreContacts(): Promise<void> {
    if (!store.orgMembersHasMore || loadingMoreContacts.value) {
      return
    }
    loadingMoreContacts.value = true
    try {
      await store.fetchOrgMembers({
        q: store.orgMembersListQuery,
        offset: store.orgMembers.length,
        append: true,
        limit: 200,
      })
    } finally {
      loadingMoreContacts.value = false
    }
  }

  async function refreshContacts(): Promise<void> {
    await store.fetchOrgMembers({ q: contactsSearchInput.value.trim(), offset: 0, limit: 200 })
  }

  onUnmounted(() => {
    if (contactsSearchDebounce != null) {
      clearTimeout(contactsSearchDebounce)
    }
  })

  return {
    store,
    presence,
    contactsSearchInput,
    loadingMoreContacts,
    contactSections,
    loadMoreContacts,
    refreshContacts,
  }
}
