/**
 * Draft a seminar minutes card from a face-to-face transcript.
 */
import { consumeSseDataLines } from '@/utils/mindMateSseStream'
import {
  type SeminarSummaryCardModel,
  emptySeminarSummary,
  seminarSummaryHasContent,
} from '@/utils/mindmateSeminarCards'
import {
  alignMinutesGoals,
  buildMinutesPrompt,
  fallbackMinutes,
  minutesTimeRange,
  parseMinutesDraft,
} from '@/utils/mindmateSeminarMinutes'

export async function draftFaceChatSummary(input: {
  transcript: string
  topic: string
  goals: string[]
  speakers: string[]
  scope: string
  author: string
  zh: boolean
  userId: string
  startedAt: string
  signal?: AbortSignal
}): Promise<SeminarSummaryCardModel | null> {
  const text = input.transcript.trim()
  if (!text || !input.userId) {
    return null
  }
  const base = emptySeminarSummary(input.scope)
  base.topic = input.topic.trim()
  base.timeRange = minutesTimeRange([input.startedAt, new Date().toISOString()], input.zh)
  base.speakers = input.speakers.map((name) => ({ name, role: '' }))
  base.author = input.author
  base.goals = input.goals.filter(Boolean).map((goal) => ({ goal, status: 'open' as const }))
  const message = buildMinutesPrompt({
    zh: input.zh,
    topic: base.topic,
    goals: input.goals,
    speakers: input.speakers.join('、'),
    observers: '',
    files: [],
    quotes: [],
    transcript: text.slice(-12000),
  })
  const response = await fetch('/api/ai_assistant/stream', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, user_id: input.userId }),
    signal: input.signal,
  })
  if (!response.ok || !response.body) {
    throw new Error('summary_failed')
  }
  let body = ''
  await consumeSseDataLines(
    response.body.getReader(),
    (payload) => {
      const event = payload.event
      const answer = typeof payload.answer === 'string' ? payload.answer : ''
      if (event === 'message' && answer) {
        body += answer
      } else if (event === 'message_replace' && answer) {
        body = answer
      } else if (event === 'error') {
        throw new Error('summary_failed')
      }
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
