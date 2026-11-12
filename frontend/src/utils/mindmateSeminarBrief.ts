/**
 * Pre-seminar brief the host fills before a group seminar can start.
 */
import { seminarBriefSeedContent } from '@/utils/mindmateSeminarCards'
import { seminarTitleFromTopic } from '@/utils/mindmateSeminarHome'

export const SEMINAR_BRIEF_TOPIC_MAX = 200
export const SEMINAR_BRIEF_ROW_MAX = 200

export type SeminarBriefVisibility = 'organization' | 'network'

/** Built-in seats plus free-text labels the leader may assign (max 32 chars). */
export type SeminarBriefRole =
  | 'leader'
  | 'leadPrep'
  | 'coPrep'
  | 'expert'
  | 'researcher'
  | 'observer'
  | 'none'
  | (string & {})

export const SEMINAR_BRIEF_ROLE_OPTIONS = [
  'leader',
  'leadPrep',
  'coPrep',
  'expert',
  'researcher',
  'observer',
] as const

export type SeminarBuiltinAssignableRole = (typeof SEMINAR_BRIEF_ROLE_OPTIONS)[number]

/** Sentinel value in role <select> for the free-text field. */
export const SEMINAR_CUSTOM_ROLE_VALUE = '__custom__'

export const SEMINAR_CUSTOM_ROLE_MAX = 32

export function isSeminarBuiltinRole(role: string): role is SeminarBuiltinAssignableRole | 'none' {
  return (
    role === 'none' ||
    (SEMINAR_BRIEF_ROLE_OPTIONS as readonly string[]).includes(role)
  )
}

export function isSeminarCustomRole(role: string): boolean {
  const cleaned = role.trim()
  if (!cleaned || isSeminarBuiltinRole(cleaned)) {
    return false
  }
  return cleaned.length <= SEMINAR_CUSTOM_ROLE_MAX
}

export function normalizeSeminarBriefRole(role: string): SeminarBriefRole {
  const cleaned = role.trim()
  if (!cleaned) {
    return 'observer'
  }
  if (isSeminarBuiltinRole(cleaned)) {
    return cleaned
  }
  if (isSeminarCustomRole(cleaned)) {
    return cleaned
  }
  return 'observer'
}

export type SeminarBriefParticipantSource = 'school' | 'external'

export interface SeminarBriefParticipant {
  userId: number
  name: string
  role: SeminarBriefRole
  /** School roster pick vs phone lookup for cross-school invites. */
  source: SeminarBriefParticipantSource
}

export interface SeminarBrief {
  topic: string
  goals: string[]
  visibility: SeminarBriefVisibility
  participants: SeminarBriefParticipant[]
  skipRoles: boolean
  resourceFiles: File[]
  skipResources: boolean
  /** Pre-generated room code for invite-link sharing before start. */
  preferredInviteCode?: string
}

export type SeminarBriefSection = 'topic' | 'goals' | 'participants' | 'resources'

export interface SeminarBriefLabels {
  topic: string
  goals: string
  participants: string
  resources: string
  roleLabels: Record<SeminarBuiltinAssignableRole | 'none', string>
  visibilityOrg: string
  visibilityNetwork: string
  skipRoles: string
  skipResources: string
  pendingConsent: string
}

export function filledBriefLines(lines: string[]): string[] {
  return lines.map((line) => line.trim()).filter((line) => line.length > 0)
}

/** Invitees besides the host (host is always pre-selected as leader). */
export function seminarBriefInviteeCount(brief: SeminarBrief, hostUserId = 0): number {
  if (hostUserId > 0) {
    return brief.participants.filter((row) => row.userId !== hostUserId).length
  }
  return brief.participants.length
}

export function seminarBriefHasInvitePath(brief: SeminarBrief, hostUserId = 0): boolean {
  if (seminarBriefInviteeCount(brief, hostUserId) > 0) {
    return true
  }
  return (
    brief.visibility === 'network' && Boolean((brief.preferredInviteCode || '').trim())
  )
}

export function seminarBriefMissing(brief: SeminarBrief, hostUserId = 0): SeminarBriefSection[] {
  const missing: SeminarBriefSection[] = []
  if (!brief.topic.trim()) {
    missing.push('topic')
  }
  if (!seminarBriefHasInvitePath(brief, hostUserId)) {
    missing.push('participants')
  }
  return missing
}

export function seminarBriefIsComplete(brief: SeminarBrief, hostUserId = 0): boolean {
  return seminarBriefMissing(brief, hostUserId).length === 0
}

export function seminarBriefSectionFilled(
  brief: SeminarBrief,
  section: SeminarBriefSection,
  hostUserId = 0
): boolean {
  if (section === 'topic') {
    return brief.topic.trim().length > 0
  }
  if (section === 'goals') {
    return filledBriefLines(brief.goals).length > 0
  }
  if (section === 'participants') {
    return seminarBriefHasInvitePath(brief, hostUserId)
  }
  return brief.skipResources || brief.resourceFiles.length > 0
}

function numberedLines(lines: string[]): string {
  return lines.map((line, index) => `${index + 1}. ${line}`).join('\n')
}

export function seminarSeedFromBrief(
  brief: SeminarBrief,
  labels: SeminarBriefLabels
): {
  title: string
  seedMessages: Array<{ role: string; content: string }>
} {
  const topic = brief.topic.trim()
  const visibilityLabel =
    brief.visibility === 'network' ? labels.visibilityNetwork : labels.visibilityOrg
  const goalLines = filledBriefLines(brief.goals)
  const parts = [`${labels.topic}\n${topic}`]
  if (goalLines.length > 0) {
    parts.push(`${labels.goals}\n${numberedLines(goalLines)}`)
  }
  parts.push(`${labels.participants}\n${visibilityLabel}`)

  if (brief.participants.length > 0) {
    const lines = brief.participants.map((row, index) => {
      const roleText =
        row.role === 'none'
          ? ''
          : isSeminarBuiltinRole(row.role)
            ? labels.roleLabels[row.role]
            : row.role
      const role = roleText ? `（${roleText}）` : ''
      const sourceTag =
        row.source === 'external' && labels.pendingConsent ? `（${labels.pendingConsent}）` : ''
      return `${index + 1}. ${row.name}${role}${sourceTag}`
    })
    parts.push(lines.join('\n'))
  }

  if (brief.skipResources) {
    parts.push(`${labels.resources}\n${labels.skipResources}`)
  } else if (brief.resourceFiles.length > 0) {
    parts.push(
      `${labels.resources}\n${numberedLines(brief.resourceFiles.map((file) => file.name))}`
    )
  }

  return {
    title: seminarTitleFromTopic(topic),
    seedMessages: [{ role: 'user', content: seminarBriefSeedContent(parts.join('\n\n')) }],
  }
}
