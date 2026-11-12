/**
 * Full seminar membership list shared by header roster, task pane, and room chrome.
 * Every seat in the room can read this; write actions stay gated elsewhere.
 */
import { computed, ref } from 'vue'

import {
  type SeminarGroupMember,
  type SeminarGroupPayload,
  fetchSeminarGroup,
} from '@/utils/mindmateSeminarGroup'
import { clearSeminarCustomRoles, syncSeminarCustomRoles } from '@/utils/seminarCustomRoles'

export const seminarGroupMembers = ref<SeminarGroupMember[]>([])
export const seminarGroupOwnerUserId = ref(0)
export const seminarGroupLeaderUserId = ref(0)
/** Last session id successfully targeted by loadSeminarGroupRoster. */
export const seminarGroupSessionId = ref('')
export const seminarGroupVisibility = ref('organization')
export const seminarGroupCrossSchool = ref(false)

/** True when the open room spans more than one school (or is a network room). */
export const seminarShowsMemberOrg = computed(
  () =>
    seminarGroupCrossSchool.value &&
    seminarGroupMembers.value.some((member) => Boolean(member.organizationName))
)

let loadToken = 0

export function setSeminarGroupRoster(payload: {
  members: SeminarGroupMember[]
  ownerUserId?: number
  leaderUserId?: number
  sessionId?: string
  visibility?: string
  crossSchool?: boolean
}): void {
  seminarGroupMembers.value = payload.members
  syncSeminarCustomRoles(payload.members.map((member) => member.role))
  if (payload.sessionId != null) {
    seminarGroupSessionId.value = payload.sessionId
  }
  if (payload.ownerUserId != null) {
    seminarGroupOwnerUserId.value = payload.ownerUserId
  }
  if (payload.leaderUserId != null) {
    seminarGroupLeaderUserId.value = payload.leaderUserId
  }
  if (payload.visibility != null) {
    seminarGroupVisibility.value = payload.visibility
  }
  if (payload.crossSchool != null) {
    seminarGroupCrossSchool.value = payload.crossSchool
  }
}

export function clearSeminarGroupRoster(): void {
  loadToken += 1
  seminarGroupMembers.value = []
  seminarGroupOwnerUserId.value = 0
  seminarGroupLeaderUserId.value = 0
  seminarGroupSessionId.value = ''
  seminarGroupVisibility.value = 'organization'
  seminarGroupCrossSchool.value = false
  clearSeminarCustomRoles()
}

export async function loadSeminarGroupRoster(
  sessionId: string
): Promise<SeminarGroupPayload | null> {
  const trimmed = sessionId.trim()
  if (!trimmed) {
    clearSeminarGroupRoster()
    return null
  }
  const token = ++loadToken
  seminarGroupSessionId.value = trimmed
  const group = await fetchSeminarGroup(trimmed)
  if (token !== loadToken) {
    return null
  }
  if (!group) {
    return null
  }
  setSeminarGroupRoster({
    members: group.members,
    ownerUserId: group.ownerUserId,
    leaderUserId: group.leaderUserId,
    sessionId: trimmed,
    visibility: group.visibility,
    crossSchool: group.crossSchool,
  })
  return group
}
