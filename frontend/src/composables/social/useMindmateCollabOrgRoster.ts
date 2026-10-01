/**
 * MindMate collab org roster facade — collab API + notify WS presence bridge.
 */
import { useNotifications } from '@/composables'
import { useMindmateCollabPresenceBridge } from '@/composables/mindmate/mindmateCollabPresenceBridge'
import { createMindmateCollabOrgBackend } from '@/composables/social/createMindmateCollabOrgBackend'
import type { OrgContactSectionsOptions } from '@/composables/social/types'
import { useOrgContactSections } from '@/composables/social/useOrgContactSections'
import { useOrgPresenceCore } from '@/composables/social/useOrgPresenceCore'
import { useOrgRoster } from '@/composables/social/useOrgRoster'

export function useMindmateCollabOrgRoster(options: OrgContactSectionsOptions = {}) {
  const notify = useNotifications()
  const backend = createMindmateCollabOrgBackend(
    options.collabRoomCode ?? (() => ''),
    options.collabVisibility ?? (() => 'organization'),
    (messageKey) => {
      notify.warningKey(messageKey)
    }
  )
  const roster = useOrgRoster(backend)
  const { onlineUserIds } = useMindmateCollabPresenceBridge()
  const presence = useOrgPresenceCore({
    members: roster.members,
    onlineUserIds,
  })
  const sectionOptions: OrgContactSectionsOptions = {
    ...options,
    zulipPresence: options.zulipPresence ?? true,
  }
  const { contactSections } = useOrgContactSections(presence, sectionOptions)

  return {
    ...roster,
    presence,
    contactSections,
  }
}
