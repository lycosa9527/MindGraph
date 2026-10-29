/**
 * MindMate collab org roster facade — collab API + notify WS presence bridge.
 */
import { useNotifications } from '@/composables'
import { useMindmateSeminarPresenceBridge } from '@/composables/mindmate/mindmateSeminarPresenceBridge'
import { createMindmateSeminarOrgBackend } from '@/composables/social/createMindmateSeminarOrgBackend'
import type { OrgContactSectionsOptions } from '@/composables/social/types'
import { useOrgContactSections } from '@/composables/social/useOrgContactSections'
import { useOrgPresenceCore } from '@/composables/social/useOrgPresenceCore'
import { useOrgRoster } from '@/composables/social/useOrgRoster'

export function useMindmateSeminarOrgRoster(options: OrgContactSectionsOptions = {}) {
  const notify = useNotifications()
  const backend = createMindmateSeminarOrgBackend(
    options.collabRoomCode ?? (() => ''),
    options.collabVisibility ?? (() => 'organization'),
    (messageKey) => {
      notify.warningKey(messageKey)
    },
    options.collabSessionId ?? (() => '')
  )
  const roster = useOrgRoster(backend)
  const { onlineUserIds, lastSeenOnlineAtByUserId } = useMindmateSeminarPresenceBridge()
  const presence = useOrgPresenceCore({
    members: roster.members,
    onlineUserIds,
    lastSeenOnlineAtByUserId,
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
