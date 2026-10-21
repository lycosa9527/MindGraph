/**
 * Cross-school seminar invites: show the basics, then agree or decline.
 */
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import router from '@/router'
import { authFetch } from '@/utils/api'
import {
  formatMindmateCollabCode,
  trackLocalMindmateCollabSession,
} from '@/utils/mindmateCollabSessions'

interface SeminarInvite {
  sessionId: string
  fromName: string
  seminar: string
  topic: string
  org: string
  visibility: string
}

const queue: SeminarInvite[] = []
const seen = new Set<string>()
let showing = false
let translate: UseLanguageTranslate | null = null

function rememberTranslator(t: UseLanguageTranslate): void {
  translate = t
}

export function enqueueSeminarConsent(invite: SeminarInvite, t: UseLanguageTranslate): void {
  rememberTranslator(t)
  if (!invite.sessionId || seen.has(invite.sessionId)) {
    return
  }
  seen.add(invite.sessionId)
  queue.push(invite)
  void pump()
}

export async function loadPendingSeminarInvites(t: UseLanguageTranslate): Promise<void> {
  rememberTranslator(t)
  try {
    const response = await authFetch('/api/mindmate/collab/members/invites')
    if (!response.ok) {
      return
    }
    const data = (await response.json()) as {
      invites?: Array<{
        session_id?: string
        title?: string
        brief_topic?: string
        from_name?: string
        host_org?: string
        visibility?: string
      }>
    }
    for (const row of data.invites || []) {
      enqueueSeminarConsent(
        {
          sessionId: String(row.session_id || ''),
          fromName: String(row.from_name || ''),
          seminar: String(row.title || ''),
          topic: String(row.brief_topic || ''),
          org: String(row.host_org || ''),
          visibility: String(row.visibility || 'network'),
        },
        t
      )
    }
  } catch {
    // The next poke or reconnect can ask again.
  }
}

async function pump(): Promise<void> {
  if (showing || queue.length === 0 || !translate) {
    return
  }
  showing = true
  const invite = queue.shift()
  if (!invite) {
    showing = false
    return
  }
  const t = translate
  const lines = [
    t('mindmate.seminarConsentBody', {
      name: invite.fromName || t('mindmate.collabPokeSomeone'),
      seminar: invite.seminar || t('mindmate.collabPill'),
    }),
  ]
  if (invite.topic) {
    lines.push(t('mindmate.seminarConsentTopic', { topic: invite.topic }))
  }
  if (invite.org) {
    lines.push(t('mindmate.seminarConsentOrg', { org: invite.org }))
  }
  lines.push(
    invite.visibility === 'network'
      ? t('mindmate.collabSeminarPublic')
      : t('mindmate.collabSeminarOrg')
  )
  let agreed = false
  try {
    await swissGlassConfirm(lines.join('\n'), t('mindmate.seminarConsentTitle'), {
      confirmButtonText: t('mindmate.seminarConsentAgree'),
      cancelButtonText: t('mindmate.seminarConsentDecline'),
      type: 'info',
    })
    agreed = true
  } catch {
    // Closing the dialog declines the invite.
  }
  try {
    const response = await authFetch('/api/mindmate/collab/members/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: invite.sessionId, accept: agreed }),
    })
    if (agreed && response.ok) {
      const data = (await response.json()) as {
        accepted?: boolean
        code?: string
        title?: string
        visibility?: string
        owner_user_id?: number
        session_id?: string
      }
      const code = String(data.code || '')
      if (data.accepted && code) {
        const formatted = formatMindmateCollabCode(code)
        trackLocalMindmateCollabSession({
          session_id: String(data.session_id || invite.sessionId),
          code: formatted,
          title: String(data.title || invite.seminar),
          owner_user_id: Number(data.owner_user_id || 0) || undefined,
          visibility: String(data.visibility || invite.visibility),
        })
        await router.push({ path: '/mindmate/collab', query: { code: formatted } })
      }
    }
  } catch {
    seen.delete(invite.sessionId)
  } finally {
    showing = false
    void pump()
  }
}
