/**
 * Workshop Chat org roster backend — uses Pinia store + /api/chat/org-members.
 */
import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import type { OrgRosterBackend, OrgRosterFetchOptions } from '@/composables/social/types'
import { useWorkshopChatStore } from '@/stores/workshopChat'

export function createWorkshopChatOrgBackend(): OrgRosterBackend {
  const store = useWorkshopChatStore()
  const { orgMembers, orgMembersTotal, orgMembersListQuery } = storeToRefs(store)
  const membersHasMore = computed(() => store.orgMembersHasMore)

  async function fetchMembers(options: OrgRosterFetchOptions): Promise<void> {
    await store.fetchOrgMembers(options)
  }

  return {
    members: orgMembers,
    membersTotal: orgMembersTotal,
    membersHasMore,
    listQuery: orgMembersListQuery,
    fetchMembers,
  }
}
