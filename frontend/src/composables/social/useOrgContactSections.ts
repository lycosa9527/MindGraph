/**
 * Build presence-grouped contact sections for org roster panels.
 */
import { type ComputedRef, computed } from 'vue'

import type { ContactSection, OrgContactSectionsOptions } from '@/composables/social/types'
import type { OrgPresenceCore } from '@/composables/social/useOrgPresenceCore'

export function useOrgContactSections(
  presence: OrgPresenceCore,
  options: OrgContactSectionsOptions = {}
): { contactSections: ComputedRef<ContactSection[]> } {
  const zulipPresence = options.zulipPresence ?? false

  const contactSections = computed((): ContactSection[] => {
    void presence.contactsOnline.value
    const on = presence.contactsOnline.value
    const recent = presence.contactsRecentlyOnline.value
    const off = presence.contactsOffline.value

    if (zulipPresence) {
      const offline = [...recent, ...off]
      const sections: ContactSection[] = []
      if (on.length > 0) {
        sections.push({
          key: 'online',
          labelKey: 'workshop.contactsOnlineNow',
          members: on,
        })
      }
      if (offline.length > 0) {
        sections.push({
          key: 'offline',
          labelKey: 'workshop.contactsOffline',
          members: offline,
        })
      }
      return sections
    }

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

  return { contactSections }
}
