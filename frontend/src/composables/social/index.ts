/**
 * Unified org roster entry — picks workshop or MindMate collab adapter.
 * Future IM circle widget should call this with source + layout props.
 */
import type { OrgContactSectionsOptions, OrgRosterSource } from '@/composables/social/types'
import { useMindmateSeminarOrgRoster } from '@/composables/social/useMindmateSeminarOrgRoster'
import { useWorkshopOrgRoster } from '@/composables/social/useWorkshopOrgRoster'

export interface UseOrgRosterPanelOptions extends OrgContactSectionsOptions {
  source?: OrgRosterSource
}

export function useOrgRosterPanel(options: UseOrgRosterPanelOptions = {}) {
  const source = options.source ?? 'workshop'
  if (source === 'mindmate-seminar') {
    return useMindmateSeminarOrgRoster(options)
  }
  return useWorkshopOrgRoster(options)
}

export { createMindmateSeminarOrgBackend } from '@/composables/social/createMindmateSeminarOrgBackend'
export { createWorkshopChatOrgBackend } from '@/composables/social/createWorkshopChatOrgBackend'
export { useMindmateSeminarOrgRoster } from '@/composables/social/useMindmateSeminarOrgRoster'
export { useOrgContactSections } from '@/composables/social/useOrgContactSections'
export { useOrgPresenceCore } from '@/composables/social/useOrgPresenceCore'
export type {
  OrgPresenceCore,
  OrgPresenceCoreOptions,
} from '@/composables/social/useOrgPresenceCore'
export { useOrgRoster } from '@/composables/social/useOrgRoster'
export { useWorkshopOrgRoster } from '@/composables/social/useWorkshopOrgRoster'
export type {
  ContactSection,
  OrgContactSectionsOptions,
  OrgRosterBackend,
  OrgRosterFetchOptions,
  OrgRosterSource,
} from '@/composables/social/types'
export type { OrgMember, OrgMembersPage } from '@/composables/social/types'
