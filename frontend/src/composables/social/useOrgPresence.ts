/**
 * Org contact presence ranking (online / recently online / offline).
 * Workshop Chat store adapter; prefer useOrgPresenceCore for new code.
 */
import { storeToRefs } from 'pinia'

import { useOrgPresenceCore } from '@/composables/social/useOrgPresenceCore'
import { useWorkshopChatStore } from '@/stores/workshopChat'

export function useOrgPresence() {
  const store = useWorkshopChatStore()
  const { orgMembers, onlineUserIds, lastSeenOnlineAtByUserId } = storeToRefs(store)
  return useOrgPresenceCore({
    members: orgMembers,
    onlineUserIds,
    lastSeenOnlineAtByUserId,
  })
}
