/**
 * Build and parse a structured seminar minutes card from a chosen transcript.
 */
import type { SeminarHighlight } from '@/composables/mindmate/mindmateSeminarChrome'
import type { MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
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

export function latestSummaryStamp(messages: MindmateCollabMessage[]): string {
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
      consensus: minutesLines(Array.isArray(parsed.consensus) ? parsed.consensus.join('\n') : ''),
      open: minutesLines(Array.isArray(parsed.open) ? parsed.open.join('\n') : ''),
      materials: minutesLines(Array.isArray(parsed.materials) ? parsed.materials.join('\n') : ''),
      tasks: minutesLines(Array.isArray(parsed.tasks) ? parsed.tasks.join('\n') : ''),
      quotes: minutesLines(Array.isArray(parsed.quotes) ? parsed.quotes.join('\n') : '').slice(
        0,
        3
      ),
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

export function buildMinutesPrompt(input: {
  zh: boolean
  topic: string
  goals: string[]
  speakers: string
  observers: string
  files: string[]
  quotes: string[]
  transcript: string
}): string {
  const facts = [
    input.topic ? `主题：${input.topic}` : '',
    input.goals.length ? `教研目标：\n${input.goals.map((goal) => `- ${goal}`).join('\n')}` : '',
    input.speakers ? `发言人：${input.speakers}` : '',
    input.observers ? `到场观摩：${input.observers}` : '',
    input.files.length
      ? `对话中出现的文件：\n${input.files.map((name) => `- ${name}`).join('\n')}`
      : '',
    input.quotes.length ? `已标精华：\n${input.quotes.map((line) => `- ${line}`).join('\n')}` : '',
  ]
    .filter(Boolean)
    .join('\n')
  const instruction = input.zh
    ? [
        '请根据研讨记录写一份教研纪要，只输出 JSON，不要 Markdown。',
        '键：goals, consensus, open, materials, tasks, quotes。',
        'goals 是数组，每项为 {"goal":"目标原文","status":"met|partial|open"}。status 只能是已回应 met、部分回应 partial、尚未讨论 open。',
        '其余键是字符串数组。consensus 写已经说定的判断。open 写尚未决定的分歧，不要替组里选边。',
        'materials 只写记录里真正用到的材料，以及它用来说明什么。tasks 写谁来做什么；没有说时间就不要写时间。',
        'quotes 最多 3 条，优先使用已标精华，格式「姓名：原话」。',
        '没有依据的决定不要写。空的数组用 []。',
      ].join('\n')
    : [
        'Write seminar minutes as JSON only, with no Markdown.',
        'Keys: goals, consensus, open, materials, tasks, quotes.',
        'goals is an array of {"goal":"...","status":"met|partial|open"} using the goal text given above.',
        'The other keys are string arrays. consensus holds agreed points. open holds unresolved disagreements without picking a side.',
        'materials names only files actually used, and what they were used to show. tasks name who does what, and include a time only if one was stated.',
        'quotes has at most 3 lines, preferring the marked highlights, formatted as "Name: quote".',
        'Do not invent decisions. Use [] for an empty array.',
      ].join('\n')
  return `${instruction}\n\n${facts}\n\n记录：\n${input.transcript}`
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
