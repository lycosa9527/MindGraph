/**
 * Org roster / IM contacts — shared types for workshop chat, MindMate collab,
 * and future global IM widget.
 */
import type { ComputedRef, Ref } from 'vue'

import type { OrgMember, OrgMembersPage } from '@/stores/workshopChat'

export type { OrgMember, OrgMembersPage }

export interface OrgRosterFetchOptions {
  q?: string
  offset?: number
  append?: boolean
  limit?: number
}

/** Pluggable data source for paginated org member lists. */
export interface OrgRosterBackend {
  members: Ref<OrgMember[]>
  membersTotal: Ref<number>
  membersHasMore: ComputedRef<boolean>
  listQuery: Ref<string>
  fetchMembers: (options: OrgRosterFetchOptions) => Promise<void>
}

export interface ContactSection {
  key: string
  labelKey: string | null
  members: OrgMember[]
}

/** Where roster data and presence are resolved (workshop store vs collab API). */
export type OrgRosterSource = 'workshop' | 'mindmate-collab'

export interface OrgContactSectionsOptions {
  zulipPresence?: boolean
  collabRoomCode?: () => string
  collabVisibility?: () => string
}
