/**
 * Build and parse a structured seminar minutes card from a chosen transcript.
 */
import type { SeminarHighlight } from '@/composables/mindmate/mindmateSeminarChrome'
import type { MindmateSeminarMessage } from '@/composables/mindmate/useMindmateSeminar'
import { apiRequestJson } from '@/utils/apiClient'
import { formatInBeijing } from '@/utils/beijingClock'
import type { SeminarBriefRole } from '@/utils/mindmateSeminarBrief'
import {
  type SeminarMinutesGoal,
  type SeminarMinutesGoalStatus,
  type SeminarMinutesSpeaker,
  type SeminarSummaryCardModel,
  parseSeminarSummaryCard,
} from '@/utils/mindmateSeminarCards'
import type { SeminarGroupMember } from '@/utils/mindmateSeminarGroup'

const FILE_TOKEN = /\[\[sf:[0-9a-fA-F-]{36}\|([^\]]*)\]\]/g

export type SeminarMinutesScope = 'all' | 'since' | 'highlights' | 'part'

/** Chat line posted before the minutes card when sending to the seminar. */
export function seminarSummaryRequestLine(
  agentName: string,
  scope: SeminarMinutesScope,
  translate: (key: string) => string
): string {
  const name = agentName.trim() || translate('mindmate.summary.author')
  const scopeKey =
    scope === 'since'
      ? 'mindmate.summary.request.since'
      : scope === 'highlights'
        ? 'mindmate.summary.request.highlights'
        : scope === 'part'
          ? 'mindmate.summary.request.part'
          : 'mindmate.summary.request.all'
  return `@${name} ${translate(scopeKey)}`
}

export interface MinutesSource {
  key: string
  author: string
  preview: string
  content: string
  createdAt: string
  messageId: number | null
  senderId: number | null
  assistant: boolean
}

export function minutesLines(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

/** Coerce LLM list fields that may mix strings and objects into newline text. */
export function minutesFieldText(raw: unknown): string {
  if (typeof raw === 'string') {
    return raw
  }
  if (!Array.isArray(raw)) {
    return ''
  }
  return raw
    .map((item) => {
      if (typeof item === 'string') {
        return item.trim()
      }
      if (typeof item === 'number' || typeof item === 'boolean') {
        return String(item)
      }
      if (!item || typeof item !== 'object') {
        return ''
      }
      const row = item as Record<string, unknown>
      for (const key of ['text', 'name', 'title', 'file', 'filename', 'label', 'value'] as const) {
        const value = row[key]
        if (typeof value === 'string' && value.trim()) {
          return value.trim()
        }
      }
      return ''
    })
    .filter(Boolean)
    .join('\n')
}

export function mentionedFileNames(content: string): string[] {
  const names: string[] = []
  for (const match of content.matchAll(FILE_TOKEN)) {
    const raw = match[1] || ''
    try {
      names.push(decodeURIComponent(raw))
    } catch {
      names.push(raw)
    }
  }
  return names
}

export function minutesTimeRange(stamps: string[], zh: boolean): string {
  const dates = stamps
    .map((stamp) => new Date(stamp))
    .filter((date) => !Number.isNaN(date.getTime()))
    .sort((left, right) => left.getTime() - right.getTime())
  if (dates.length === 0) {
    return ''
  }
  const format = (date: Date) =>
    formatInBeijing(date, zh ? 'zh-CN' : 'en-US', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  const start = format(dates[0])
  const end = format(dates[dates.length - 1])
  return start === end ? start : `${start} – ${end}`
}

export function latestSummaryStamp(messages: MindmateSeminarMessage[]): string {
  let cutoff = ''
  for (const message of messages) {
    if (!parseSeminarSummaryCard(message.content)) {
      continue
    }
    const stamp = message.created_at || ''
    if (stamp > cutoff) {
      cutoff = stamp
    }
  }
  return cutoff
}

export function selectMinutesSources(
  sources: MinutesSource[],
  mode: SeminarMinutesScope,
  picked: Record<string, boolean>,
  highlights: SeminarHighlight[],
  sinceCutoff: string
): MinutesSource[] {
  if (mode === 'part') {
    return sources.filter((row) => picked[row.key])
  }
  if (mode === 'highlights') {
    const ids = new Set(
      highlights.map((item) => item.messageId).filter((id): id is number => Boolean(id && id > 0))
    )
    const texts = highlights.map((item) => item.text.trim()).filter(Boolean)
    return sources.filter((row) => {
      if (row.messageId && ids.has(row.messageId)) {
        return true
      }
      return texts.some((text) => row.content.includes(text))
    })
  }
  if (mode === 'since' && sinceCutoff) {
    return sources.filter((row) => row.createdAt > sinceCutoff)
  }
  return sources
}

function roleText(
  member: SeminarGroupMember | undefined,
  label: (role: SeminarBriefRole) => string
): string {
  if (!member || member.role === 'none') {
    return ''
  }
  return label(member.role)
}

export function minutesPeople(
  selected: MinutesSource[],
  members: SeminarGroupMember[],
  label: (role: SeminarBriefRole) => string
): { speakers: SeminarMinutesSpeaker[]; observers: string[] } {
  const speakers: SeminarMinutesSpeaker[] = []
  const seen = new Set<string>()
  for (const row of selected) {
    if (row.assistant) {
      continue
    }
    const key = row.senderId ? `id:${row.senderId}` : `name:${row.author}`
    if (seen.has(key)) {
      continue
    }
    seen.add(key)
    const member =
      members.find((item) => row.senderId != null && item.userId === row.senderId) ||
      members.find((item) => item.name.trim() === row.author.trim())
    speakers.push({ name: row.author, role: roleText(member, label) })
  }
  const speakerIds = new Set(
    selected.map((row) => row.senderId).filter((id): id is number => id != null && id > 0)
  )
  const observers = members
    .filter(
      (member) => member.role === 'observer' && member.online && !speakerIds.has(member.userId)
    )
    .map((member) => member.name)
  return { speakers, observers }
}

function stripFence(raw: string): string {
  const trimmed = raw.trim()
  const fenced = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/)
  return (fenced?.[1] || trimmed).trim()
}

export function parseMinutesDraft(raw: string): Partial<SeminarSummaryCardModel> | null {
  const text = stripFence(raw)
  const start = text.indexOf('{')
  const end = text.lastIndexOf('}')
  if (start < 0 || end <= start) {
    return null
  }
  try {
    const parsed = JSON.parse(text.slice(start, end + 1)) as Record<string, unknown>
    const goals = Array.isArray(parsed.goals)
      ? parsed.goals
          .map((item) => {
            if (!item || typeof item !== 'object') {
              return null
            }
            const row = item as { goal?: unknown; status?: unknown }
            const goal = typeof row.goal === 'string' ? row.goal.trim() : ''
            const status = row.status
            if (!goal) {
              return null
            }
            const known: SeminarMinutesGoalStatus =
              status === 'met' || status === 'partial' || status === 'open' ? status : 'open'
            return { goal, status: known }
          })
          .filter((item): item is SeminarMinutesGoal => item != null)
      : []
    return {
      goals,
      consensus: minutesLines(minutesFieldText(parsed.consensus)),
      open: minutesLines(minutesFieldText(parsed.open)),
      materials: minutesLines(minutesFieldText(parsed.materials)),
      tasks: minutesLines(minutesFieldText(parsed.tasks)),
      quotes: minutesLines(minutesFieldText(parsed.quotes)).slice(0, 3),
    }
  } catch {
    return null
  }
}

export function alignMinutesGoals(
  briefGoals: string[],
  generated: SeminarMinutesGoal[]
): SeminarMinutesGoal[] {
  if (briefGoals.length === 0) {
    return generated
  }
  return briefGoals.map((goal) => {
    const hit = generated.find((row) => row.goal.trim() === goal.trim())
    return { goal, status: hit?.status || 'open' }
  })
}

export const SEMINAR_MINUTES_TRANSCRIPT_LIMIT = 48000

export interface SeminarMinutesDraftRequest {
  zh: boolean
  topic: string
  goals: string[]
  speakers: string
  observers: string
  files: string[]
  quotes: string[]
  transcript: string
}

function clipLines(items: string[], maxItems: number, maxChars: number): string[] {
  const kept: string[] = []
  for (const item of items) {
    const text = item.trim()
    if (!text) {
      continue
    }
    kept.push(text.slice(0, maxChars))
    if (kept.length >= maxItems) {
      break
    }
  }
  return kept
}

/** Ask qwen3.8-flash for minutes JSON. The room edits the card before sending it. */
export async function requestSeminarMinutesDraft(
  sessionId: string,
  body: SeminarMinutesDraftRequest,
  signal?: AbortSignal
): Promise<string> {
  const id = sessionId.trim()
  if (!id) {
    throw new Error('summary_failed')
  }
  const data = await apiRequestJson<{ text?: unknown }>(
    `/api/mindmate/seminar/${encodeURIComponent(id)}/minutes`,
    {
      method: 'POST',
      body: JSON.stringify({
        zh: body.zh,
        topic: body.topic.trim().slice(0, 200),
        goals: clipLines(body.goals, 12, 200),
        speakers: body.speakers.trim().slice(0, 2000),
        observers: body.observers.trim().slice(0, 2000),
        files: clipLines(body.files, 30, 180),
        quotes: clipLines(body.quotes, 3, 400),
        transcript: body.transcript.trim().slice(-SEMINAR_MINUTES_TRANSCRIPT_LIMIT),
      }),
      signal,
    }
  )
  return typeof data.text === 'string' ? data.text.trim() : ''
}

const DRAFT_PREFIX = 'mindmate.seminar.minutesDraft.'

export function loadMinutesDraft(sessionId: string): SeminarSummaryCardModel | null {
  if (!sessionId || typeof localStorage === 'undefined') {
    return null
  }
  try {
    const raw = localStorage.getItem(`${DRAFT_PREFIX}${sessionId}`)
    if (!raw) {
      return null
    }
    return parseSeminarSummaryCard(`[[seminar-summary]]\n${raw}`)
  } catch {
    return null
  }
}

export function saveMinutesDraft(sessionId: string, model: SeminarSummaryCardModel): void {
  if (!sessionId || typeof localStorage === 'undefined') {
    return
  }
  const stored = { ...model, structured: true }
  localStorage.setItem(`${DRAFT_PREFIX}${sessionId}`, JSON.stringify(stored))
}

export function clearMinutesDraft(sessionId: string): void {
  if (!sessionId || typeof localStorage === 'undefined') {
    return
  }
  localStorage.removeItem(`${DRAFT_PREFIX}${sessionId}`)
}

export function fallbackMinutes(
  text: string,
  base: SeminarSummaryCardModel
): SeminarSummaryCardModel {
  return {
    ...base,
    consensus: text.trim() ? [text.trim()] : [],
    open: [],
    materials: [],
    tasks: [],
    quotes: [],
    structured: true,
    body: text.trim(),
  }
}
