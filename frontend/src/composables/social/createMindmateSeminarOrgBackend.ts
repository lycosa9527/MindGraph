/**
 * MindMate collab roster backend — org colleagues or session participants.
 */
import { computed, ref } from 'vue'

import type {
  OrgMembersPage,
  OrgRosterBackend,
  OrgRosterFetchOptions,
} from '@/composables/social/types'
import { authFetch } from '@/utils/api'
import { formatMindmateSeminarCode } from '@/utils/mindmateSeminarSessions'

const ORG_ROSTER_PAGE_SIZE = 200

export function createMindmateSeminarOrgBackend(
  getRoomCode: () => string,
  getVisibility: () => string,
  onFetchError?: (messageKey: string) => void,
  getSessionId: () => string = () => ''
): OrgRosterBackend {
  const members = ref<OrgMembersPage['items']>([])
  const membersTotal = ref(0)
  const listQuery = ref('')
  const membersHasMore = computed(() => members.value.length < membersTotal.value)

  async function fetchMembers(options: OrgRosterFetchOptions): Promise<void> {
    const q = (options.q ?? listQuery.value).trim()
    const offset = options.offset ?? 0
    const append = options.append ?? false
    const limit = options.limit ?? ORG_ROSTER_PAGE_SIZE
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    })
    if (q) {
      params.set('q', q)
    }

    const visibility = getVisibility()
    const roomCode = getRoomCode().trim()
    const sessionId = getSessionId().trim()
    const useNetworkRoster = visibility === 'network' && roomCode.length > 0
    let endpoint = '/api/mindmate/seminar/org-members'
    if (useNetworkRoster) {
      params.set('code', formatMindmateSeminarCode(roomCode))
      endpoint = '/api/mindmate/seminar/session-members'
    }

    try {
      if (!useNetworkRoster && sessionId) {
        const groupParams = new URLSearchParams(params)
        groupParams.set('session_id', sessionId)
        const groupResponse = await authFetch(`/api/mindmate/seminar/group-members?${groupParams}`)
        if (groupResponse.ok) {
          const group = (await groupResponse.json()) as OrgMembersPage & { closed?: boolean }
          if (group.closed) {
            listQuery.value = q
            members.value = append ? [...members.value, ...group.items] : group.items
            membersTotal.value = group.total
            return
          }
        }
      }
      const response = await authFetch(`${endpoint}?${params}`)
      if (!response.ok) {
        if (!append && offset === 0) {
          onFetchError?.('mindmate.collabMembersLoadFailed')
        }
        return
      }
      const data = (await response.json()) as OrgMembersPage
      listQuery.value = q
      if (append) {
        members.value = [...members.value, ...data.items]
      } else {
        members.value = data.items
      }
      membersTotal.value = data.total
    } catch (err) {
      if (!append && offset === 0) {
        onFetchError?.('mindmate.collabMembersLoadFailed')
      }
      if (import.meta.env.DEV) {
        console.error('[MindmateSeminarOrgBackend] fetchMembers error:', err)
      }
    }
  }

  return {
    members,
    membersTotal,
    membersHasMore,
    listQuery,
    fetchMembers,
  }
}
