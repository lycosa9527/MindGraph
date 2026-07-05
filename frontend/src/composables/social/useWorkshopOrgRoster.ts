/**
 * Workshop Chat org roster facade — store-backed list + workshop WS presence.
 */
import { storeToRefs } from 'pinia'

import { createWorkshopChatOrgBackend } from '@/composables/social/createWorkshopChatOrgBackend'
import type { OrgContactSectionsOptions } from '@/composables/social/types'
import { useOrgContactSections } from '@/composables/social/useOrgContactSections'
import { useOrgPresenceCore } from '@/composables/social/useOrgPresenceCore'
import { useOrgRoster } from '@/composables/social/useOrgRoster'
import { useWorkshopChatStore } from '@/stores/workshopChat'

export function useWorkshopOrgRoster(options: OrgContactSectionsOptions = {}) {
  const store = useWorkshopChatStore()
  const backend = createWorkshopChatOrgBackend()
  const roster = useOrgRoster(backend)
  const { orgMembers, onlineUserIds, lastSeenOnlineAtByUserId } = storeToRefs(store)
  const presence = useOrgPresenceCore({
    members: orgMembers,
    onlineUserIds,
    lastSeenOnlineAtByUserId,
  })
  const { contactSections } = useOrgContactSections(presence, options)

  return {
    ...roster,
    presence,
    contactSections,
    store,
  }
}
