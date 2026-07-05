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
import { formatMindmateCollabCode } from '@/utils/mindmateCollabSessions'

const ORG_ROSTER_PAGE_SIZE = 200

export function createMindmateCollabOrgBackend(
  getRoomCode: () => string,
  getVisibility: () => string,
  onFetchError?: (messageKey: string) => void,
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
    const useSessionRoster = visibility === 'network' && roomCode.length > 0
    if (useSessionRoster) {
      params.set('code', formatMindmateCollabCode(roomCode))
    }

    const endpoint = useSessionRoster
      ? '/api/mindmate/collab/session-members'
      : '/api/mindmate/collab/org-members'

    try {
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
        console.error('[MindmateCollabOrgBackend] fetchMembers error:', err)
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
