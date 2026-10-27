/**
 * Invited teachers for a school seminar. Offline members stay on the list.
 */
import { authFetch } from '@/utils/api'
import type { SeminarBriefRole } from '@/utils/mindmateSeminarBrief'
import type { SeminarFace } from '@/utils/mindmateSeminarFaces'

export interface SeminarGroupMember {
  userId: number
  name: string
  avatar: string | null
  role: SeminarBriefRole
  online: boolean
  isOwner: boolean
  /** Current seminar leader (may differ from session owner after transfer). */
  isLeader: boolean
  /** Cross-school invite that has not been accepted yet. */
  pending: boolean
  /** Server stamp from the last time their workshop socket closed. */
  lastSeenAt: string | null
}

export interface SeminarGroupPayload {
  members: SeminarGroupMember[]
  ownerUserId: number
  leaderUserId: number
  title: string
  briefTopic: string
  briefGoals: string[]
}

interface GroupMemberRow {
  id?: number
  name?: string
  avatar?: string | null
  role?: string
  online?: boolean
  is_owner?: boolean
  is_leader?: boolean
  pending?: boolean
  last_seen_at?: string | null
}

function asRole(raw: unknown): SeminarBriefRole {
  const role = String(raw || '').trim()
  if (
    role === 'leader' ||
    role === 'leadPrep' ||
    role === 'coPrep' ||
    role === 'expert' ||
    role === 'researcher' ||
    role === 'observer' ||
    role === 'none'
  ) {
    return role
  }
  return 'observer'
}

export async function fetchSeminarGroup(sessionId: string): Promise<SeminarGroupPayload | null> {
  const params = new URLSearchParams({
    session_id: sessionId,
    limit: '200',
    offset: '0',
  })
  let response: Response
  try {
    response = await authFetch(`/api/mindmate/collab/group-members?${params}`)
  } catch {
    return null
  }
  if (!response.ok) {
    return null
  }
  const data = (await response.json()) as {
    items?: GroupMemberRow[]
    owner_user_id?: number
    leader_user_id?: number
    title?: string
    brief_topic?: string | null
    brief_goals?: string[]
  }
  const ownerUserId = Number(data.owner_user_id || 0)
  const leaderUserId = Number(data.leader_user_id || ownerUserId || 0)
  const members = (data.items ?? [])
    .map((item) => {
      const userId = Number(item.id)
      if (!Number.isFinite(userId) || userId <= 0) {
        return null
      }
      const name = String(item.name || '').trim() || `User ${userId}`
      const avatar =
        typeof item.avatar === 'string' && item.avatar.trim() ? item.avatar.trim() : null
      const role = asRole(item.role)
      const isLeader =
        typeof item.is_leader === 'boolean'
          ? item.is_leader
          : role === 'leader' || (leaderUserId > 0 && userId === leaderUserId)
      return {
        userId,
        name,
        avatar,
        role: isLeader ? 'leader' : role,
        online: Boolean(item.online),
        isOwner: Boolean(item.is_owner),
        isLeader,
        pending: Boolean(item.pending),
        lastSeenAt:
          typeof item.last_seen_at === 'string' && item.last_seen_at.trim()
            ? item.last_seen_at
            : null,
      } satisfies SeminarGroupMember
    })
    .filter((row): row is SeminarGroupMember => row != null)

  return {
    members,
    ownerUserId,
    leaderUserId,
    title: String(data.title || '').trim(),
    briefTopic: String(data.brief_topic || '').trim(),
    briefGoals: Array.isArray(data.brief_goals)
      ? data.brief_goals.map((row) => String(row).trim()).filter(Boolean)
      : [],
  }
}

export async function fetchSeminarGroupFaces(sessionId: string): Promise<SeminarFace[] | null> {
  const group = await fetchSeminarGroup(sessionId)
  if (!group) {
    return null
  }
  return group.members.map((member) => ({
    userId: member.userId,
    name: member.name,
    avatar: member.avatar,
  }))
}

export async function addSeminarGroupMembers(
  sessionId: string,
  userIds: number[],
  roles?: Record<number, SeminarBriefRole>
): Promise<boolean> {
  const rolePayload: Record<string, string> = {}
  if (roles) {
    for (const [userId, role] of Object.entries(roles)) {
      rolePayload[userId] = role
    }
  }
  let response: Response
  try {
    response = await authFetch('/api/mindmate/collab/members', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        user_ids: userIds,
        roles: rolePayload,
      }),
    })
  } catch {
    return false
  }
  return response.ok
}

export async function updateSeminarMemberRole(
  sessionId: string,
  userId: number,
  role: SeminarBriefRole
): Promise<boolean> {
  let response: Response
  try {
    response = await authFetch('/api/mindmate/collab/members/role', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        user_id: userId,
        role,
      }),
    })
  } catch {
    return false
  }
  return response.ok
}

export async function removeSeminarGroupMember(
  sessionId: string,
  userId: number
): Promise<boolean> {
  let response: Response
  try {
    response = await authFetch('/api/mindmate/collab/members', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, user_id: userId }),
    })
  } catch {
    return false
  }
  return response.ok
}

export async function renameSeminarSession(
  sessionId: string,
  title: string
): Promise<string | null> {
  let response: Response
  try {
    response = await authFetch('/api/mindmate/collab/title', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, title }),
    })
  } catch {
    return null
  }
  if (!response.ok) {
    return null
  }
  const body = (await response.json()) as { title?: string }
  return String(body.title || title).trim() || null
}
