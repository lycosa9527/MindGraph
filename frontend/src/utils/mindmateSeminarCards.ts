/**
 * Structured seminar cards stored inside collab message text.
 * The brief seed and a posted summary render as cards, not chat bubbles.
 */

export const SEMINAR_BRIEF_MARKER = '[[seminar-brief]]'
export const SEMINAR_SUMMARY_MARKER = '[[seminar-summary]]'

const TOPIC_HEADERS = new Set(['教研主题', 'Seminar topic'])
const GOAL_HEADERS = new Set(['教研目标', 'Seminar goals'])
const PEOPLE_HEADERS = new Set(['参与人员', 'Participants'])
const FILE_HEADERS = new Set(['资源准备', 'Materials'])

export interface SeminarBriefCardModel {
  topic: string
  goals: string[]
  visibility: string
  participants: Array<{ name: string; role: string }>
  resources: string[]
}

export interface SeminarBriefEditPayload {
  topic: string
  goals: string[]
}

export type SeminarMinutesGoalStatus = 'met' | 'partial' | 'open'

export interface SeminarMinutesGoal {
  goal: string
  status: SeminarMinutesGoalStatus
}

export interface SeminarMinutesSpeaker {
  name: string
  role: string
}

export interface SeminarSummaryCardModel {
  scope: string
  body: string
  topic: string
  timeRange: string
  speakers: SeminarMinutesSpeaker[]
  observers: string[]
  goals: SeminarMinutesGoal[]
  consensus: string[]
  open: string[]
  materials: string[]
  tasks: string[]
  quotes: string[]
  author: string
  /** False for summaries saved before the structured minutes card. */
  structured: boolean
}

function stripNumber(line: string): string {
  return line.replace(/^\d+\.\s*/, '').trim()
}

function splitParticipant(line: string): { name: string; role: string } {
  const text = stripNumber(line)
  const match = text.match(/^(.+?)（([^）]+)）(.*)$/)
  if (!match) {
    return { name: text, role: '' }
  }
  const extra = match[3].replace(/[（）]/g, '').trim()
  return {
    name: match[1].trim(),
    role: extra ? `${match[2]} · ${extra}` : match[2],
  }
}

export function parseSeminarBriefCard(content: string): SeminarBriefCardModel | null {
  let text = (content || '').trim()
  if (text.startsWith(SEMINAR_SUMMARY_MARKER)) {
    return null
  }
  if (text.startsWith(SEMINAR_BRIEF_MARKER)) {
    text = text.slice(SEMINAR_BRIEF_MARKER.length).trim()
  }
  const lines = text.split('\n')
  if (!TOPIC_HEADERS.has(lines[0]?.trim() || '')) {
    return null
  }

  let section: 'topic' | 'goals' | 'people' | 'files' | null = null
  const buckets: Record<'topic' | 'goals' | 'people' | 'files', string[]> = {
    topic: [],
    goals: [],
    people: [],
    files: [],
  }
  for (const raw of lines) {
    const line = raw.trim()
    if (!line) {
      continue
    }
    if (TOPIC_HEADERS.has(line)) {
      section = 'topic'
      continue
    }
    if (GOAL_HEADERS.has(line)) {
      section = 'goals'
      continue
    }
    if (PEOPLE_HEADERS.has(line)) {
      section = 'people'
      continue
    }
    if (FILE_HEADERS.has(line)) {
      section = 'files'
      continue
    }
    if (section) {
      buckets[section].push(line)
    }
  }

  const topic = buckets.topic.join(' ').trim()
  if (!topic) {
    return null
  }
  const people = buckets.people
  const visibility = people.find((line) => !/^\d+\.\s*/.test(line)) || ''
  return {
    topic,
    goals: buckets.goals.map(stripNumber).filter(Boolean),
    visibility,
    participants: people.filter((line) => /^\d+\.\s*/.test(line)).map(splitParticipant),
    resources: buckets.files.map(stripNumber).filter(Boolean),
  }
}

export function seminarBriefSeedContent(body: string): string {
  const text = body.trim()
  if (text.startsWith(SEMINAR_BRIEF_MARKER)) {
    return text
  }
  return `${SEMINAR_BRIEF_MARKER}\n${text}`
}

function asLines(raw: unknown): string[] {
  if (!Array.isArray(raw)) {
    return []
  }
  return raw.map((item) => String(item || '').trim()).filter(Boolean)
}

function asStatus(raw: unknown): SeminarMinutesGoalStatus {
  if (raw === 'met' || raw === 'partial' || raw === 'open') {
    return raw
  }
  return 'open'
}

function asGoals(raw: unknown): SeminarMinutesGoal[] {
  if (!Array.isArray(raw)) {
    return []
  }
  const goals: SeminarMinutesGoal[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') {
      continue
    }
    const row = item as { goal?: unknown; status?: unknown }
    const goal = typeof row.goal === 'string' ? row.goal.trim() : ''
    if (!goal) {
      continue
    }
    goals.push({ goal, status: asStatus(row.status) })
  }
  return goals
}

function asSpeakers(raw: unknown): SeminarMinutesSpeaker[] {
  if (!Array.isArray(raw)) {
    return []
  }
  const speakers: SeminarMinutesSpeaker[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') {
      continue
    }
    const row = item as { name?: unknown; role?: unknown }
    const name = typeof row.name === 'string' ? row.name.trim() : ''
    if (!name) {
      continue
    }
    speakers.push({
      name,
      role: typeof row.role === 'string' ? row.role.trim() : '',
    })
  }
  return speakers
}

export function emptySeminarSummary(scope = ''): SeminarSummaryCardModel {
  return {
    scope,
    body: '',
    topic: '',
    timeRange: '',
    speakers: [],
    observers: [],
    goals: [],
    consensus: [],
    open: [],
    materials: [],
    tasks: [],
    quotes: [],
    author: '',
    structured: false,
  }
}

export function seminarSummaryHasContent(model: SeminarSummaryCardModel): boolean {
  return Boolean(
    model.body.trim() ||
    model.consensus.length ||
    model.goals.length ||
    model.open.length ||
    model.materials.length ||
    model.tasks.length ||
    model.quotes.length
  )
}

export function parseSeminarSummaryCard(content: string): SeminarSummaryCardModel | null {
  const text = (content || '').trim()
  if (!text.startsWith(SEMINAR_SUMMARY_MARKER)) {
    return null
  }
  const raw = text.slice(SEMINAR_SUMMARY_MARKER.length).trim()
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>
    const body = typeof parsed.body === 'string' ? parsed.body.trim() : ''
    const scope = typeof parsed.scope === 'string' ? parsed.scope.trim() : ''
    const goals = asGoals(parsed.goals)
    const consensus = asLines(parsed.consensus)
    const open = asLines(parsed.open)
    const materials = asLines(parsed.materials)
    const tasks = asLines(parsed.tasks)
    const quotes = asLines(parsed.quotes).slice(0, 3)
    const structured = Boolean(
      parsed.structured ||
      goals.length ||
      consensus.length ||
      open.length ||
      materials.length ||
      tasks.length ||
      quotes.length
    )
    if (!body && !structured) {
      return null
    }
    return {
      scope,
      body,
      topic: typeof parsed.topic === 'string' ? parsed.topic.trim() : '',
      timeRange: typeof parsed.timeRange === 'string' ? parsed.timeRange.trim() : '',
      speakers: asSpeakers(parsed.speakers),
      observers: asLines(parsed.observers),
      goals,
      consensus,
      open,
      materials,
      tasks,
      quotes,
      author: typeof parsed.author === 'string' ? parsed.author.trim() : '',
      structured,
    }
  } catch {
    return null
  }
}

export function seminarSummaryMessage(scope: string, body: string): string {
  return `${SEMINAR_SUMMARY_MARKER}\n${JSON.stringify({ scope, body })}`
}

export function seminarMinutesMessage(model: SeminarSummaryCardModel): string {
  const payload = {
    scope: model.scope,
    body: model.body,
    topic: model.topic,
    timeRange: model.timeRange,
    speakers: model.speakers,
    observers: model.observers,
    goals: model.goals,
    consensus: model.consensus,
    open: model.open,
    materials: model.materials,
    tasks: model.tasks,
    quotes: model.quotes.slice(0, 3),
    author: model.author,
    structured: true,
  }
  return `${SEMINAR_SUMMARY_MARKER}\n${JSON.stringify(payload)}`
}

export function seminarSummaryPlainText(model: SeminarSummaryCardModel): string {
  if (!model.structured) {
    return [model.scope, model.body].filter(Boolean).join('\n\n')
  }
  const lines: string[] = []
  if (model.topic) {
    lines.push(model.topic)
  }
  if (model.timeRange) {
    lines.push(model.timeRange)
  }
  if (model.scope) {
    lines.push(model.scope)
  }
  const speak = model.speakers
    .map((row) => (row.role ? `${row.name}（${row.role}）` : row.name))
    .join('、')
  if (speak) {
    lines.push(speak)
  }
  if (model.consensus.length) {
    lines.push(model.consensus.map((item) => `· ${item}`).join('\n'))
  }
  return lines.filter(Boolean).join('\n')
}
