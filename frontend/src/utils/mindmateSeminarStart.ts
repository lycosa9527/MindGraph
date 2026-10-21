/**
 * Create a seminar room from the MindMate home actions.
 * The toolbar collab panel is feature-gated and may be unmounted, so home
 * actions call this directly.
 */
import { authFetch } from '@/utils/api'
import type { SeminarBriefRole } from '@/utils/mindmateSeminarBrief'
import { seminarTitleFromTopic } from '@/utils/mindmateSeminarHome'

export interface SeminarRoomStart {
  code: string
  sessionId: string
  ownerUserId: number
  participantCount: number
  visibility: string
  title: string
  briefTopic: string
  briefGoals: string[]
  expiresAt: string | null
  body: Record<string, unknown>
}

export function seminarSeedFromTopic(topic: string): {
  title: string
  seedMessages: Array<{ role: string; content: string }>
} {
  const text = topic.trim()
  return {
    title: seminarTitleFromTopic(text),
    seedMessages: [{ role: 'user', content: text }],
  }
}

export async function startSeminarRoom(input: {
  visibility: 'organization' | 'network'
  title: string
  seedMessages: Array<{ role: string; content: string }>
  memberUserIds?: number[]
  memberRoles?: Record<number, SeminarBriefRole>
  briefTopic?: string
  briefGoals?: string[]
  closeGroup?: boolean
}): Promise<{ ok: true; room: SeminarRoomStart } | { ok: false; detail: string }> {
  const rolePayload: Record<string, string> = {}
  if (input.memberRoles) {
    for (const [userId, role] of Object.entries(input.memberRoles)) {
      rolePayload[userId] = role
    }
  }
  let response: Response
  try {
    response = await authFetch('/api/mindmate/collab/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        visibility: input.visibility,
        title: input.title || undefined,
        seed_messages: input.seedMessages,
        member_user_ids: input.memberUserIds ?? [],
        member_roles: rolePayload,
        brief_topic: input.briefTopic || undefined,
        brief_goals: input.briefGoals ?? [],
        close_group: Boolean(input.closeGroup),
      }),
    })
  } catch {
    return { ok: false, detail: '' }
  }
  if (!response.ok) {
    const err = (await response.json().catch(() => ({}))) as { detail?: unknown }
    return { ok: false, detail: typeof err.detail === 'string' ? err.detail : '' }
  }
  const body = (await response.json()) as Record<string, unknown>
  const code = String(body.code || '').trim()
  const sessionId = String(body.session_id || '').trim()
  if (!code || !sessionId) {
    return { ok: false, detail: '' }
  }
  const goals = Array.isArray(body.brief_goals)
    ? body.brief_goals.map((row) => String(row).trim()).filter(Boolean)
    : (input.briefGoals ?? [])
  return {
    ok: true,
    room: {
      code,
      sessionId,
      ownerUserId: Number(body.owner_user_id || 0),
      participantCount: Number(body.participant_count || 1),
      visibility: String(body.visibility || input.visibility),
      title: String(body.title || input.title || ''),
      briefTopic: String(body.brief_topic || input.briefTopic || '').trim(),
      briefGoals: goals,
      expiresAt: typeof body.expires_at === 'string' ? body.expires_at : null,
      body,
    },
  }
}
