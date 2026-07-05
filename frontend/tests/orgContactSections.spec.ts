import { computed, ref } from 'vue'

import { describe, expect, it } from 'vitest'

import { useOrgContactSections } from '@/composables/social/useOrgContactSections'
import type { OrgPresenceCore } from '@/composables/social/useOrgPresenceCore'
import type { OrgMember } from '@/stores/workshopChat'

function makeMember(id: number, name: string): OrgMember {
  return { id, name, avatar: null }
}

function stubPresence(members: OrgMember[], onlineIds: number[]): OrgPresenceCore {
  const onlineSet = new Set(onlineIds)
  return {
    contactsOnline: computed(() => members.filter((m) => onlineSet.has(m.id))),
    contactsRecentlyOnline: computed(() => []),
    contactsOffline: computed(() => members.filter((m) => !onlineSet.has(m.id))),
    contactsOnlineCount: computed(() => onlineIds.length),
    isContactSelf: () => false,
    contactLastOnlineSubtitle: () => '',
    contactPresenceRank: (id) => (onlineSet.has(id) ? 0 : 2),
    isUserOnline: (id) => onlineSet.has(id),
  }
}

describe('useOrgContactSections', () => {
  it('builds three workshop sections when zulipPresence is false', () => {
    const alice = makeMember(1, 'Alice')
    const bob = makeMember(2, 'Bob')
    const members = ref([alice, bob])
    const presence = stubPresence(members.value, [1])
    const { contactSections } = useOrgContactSections(presence, { zulipPresence: false })
    const keys = contactSections.value.map((s) => s.key)
    expect(keys).toContain('online')
    expect(keys).toContain('offline')
  })

  it('collapses to online/offline when zulipPresence is true', () => {
    const alice = makeMember(1, 'Alice')
    const bob = makeMember(2, 'Bob')
    const members = ref([alice, bob])
    const presence = stubPresence(members.value, [1])
    const { contactSections } = useOrgContactSections(presence, { zulipPresence: true })
    expect(contactSections.value.map((s) => s.key)).toEqual(['online', 'offline'])
    expect(contactSections.value[1]?.members).toHaveLength(1)
  })
})
