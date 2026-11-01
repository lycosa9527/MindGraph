/**
 * Draft a seminar minutes card from a face-to-face transcript.
 */
import {
  type SeminarSummaryCardModel,
  emptySeminarSummary,
  seminarSummaryHasContent,
} from '@/utils/mindmateSeminarCards'
import {
  alignMinutesGoals,
  fallbackMinutes,
  minutesTimeRange,
  parseMinutesDraft,
  requestSeminarMinutesDraft,
} from '@/utils/mindmateSeminarMinutes'

export async function draftFaceChatSummary(input: {
  sessionId: string
  transcript: string
  topic: string
  goals: string[]
  speakers: string[]
  scope: string
  author: string
  zh: boolean
  startedAt: string
  signal?: AbortSignal
}): Promise<SeminarSummaryCardModel | null> {
  const text = input.transcript.trim()
  if (!text || !input.sessionId.trim()) {
    return null
  }
  const base = emptySeminarSummary(input.scope)
  base.topic = input.topic.trim()
  base.timeRange = minutesTimeRange([input.startedAt, new Date().toISOString()], input.zh)
  base.speakers = input.speakers.map((name) => ({ name, role: '' }))
  base.author = input.author
  base.goals = input.goals.filter(Boolean).map((goal) => ({ goal, status: 'open' as const }))
  const body = await requestSeminarMinutesDraft(
    input.sessionId,
    {
      zh: input.zh,
      topic: base.topic,
      goals: input.goals,
      speakers: input.speakers.join('、'),
      observers: '',
      files: [],
      quotes: [],
      transcript: text,
    },
    input.signal
  )
  const parsed = parseMinutesDraft(body)
  const draft = parsed
    ? {
        ...base,
        ...parsed,
        goals: alignMinutesGoals(input.goals, parsed.goals || []),
        scope: base.scope,
        topic: base.topic,
        timeRange: base.timeRange,
        speakers: base.speakers,
        observers: base.observers,
        author: base.author,
        structured: true,
        body: '',
      }
    : fallbackMinutes(body, base)
  return seminarSummaryHasContent(draft) ? draft : null
}
