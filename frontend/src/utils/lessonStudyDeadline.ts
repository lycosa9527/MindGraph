/**
 * Lesson-study (child channel) deadline display helpers.
 * Product semantics: overdue / due within 7 days / later / none / inactive.
 */

export type LessonDeadlineBadge =
  | { kind: 'inactive' }
  | { kind: 'none' }
  | { kind: 'overdue' }
  | { kind: 'soon' }
  | { kind: 'later' }
  | { kind: 'done' }

export function lessonStudyDeadlineBadge(channel: {
  parent_id?: number | null
  deadline?: string | null
  is_resolved?: boolean
  status?: string | null
}): LessonDeadlineBadge {
  if (!channel.parent_id) return { kind: 'inactive' }
  if (channel.is_resolved) return { kind: 'done' }
  const st = channel.status || ''
  if (st === 'completed' || st === 'archived') return { kind: 'done' }
  if (!channel.deadline) return { kind: 'none' }
  const t = new Date(channel.deadline).getTime()
  if (Number.isNaN(t)) return { kind: 'none' }
  const ms = t - Date.now()
  if (ms < 0) return { kind: 'overdue' }
  const weekMs = 7 * 24 * 60 * 60 * 1000
  if (ms <= weekMs) return { kind: 'soon' }
  return { kind: 'later' }
}

export function formatDeadlineRelative(iso: string, locale?: string): string {
  const target = new Date(iso).getTime()
  if (Number.isNaN(target)) return ''
  const diffMs = target - Date.now()
  const abs = Math.abs(diffMs)
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  const loc = locale?.trim() ? locale : undefined
  const rtf = new Intl.RelativeTimeFormat(loc, { numeric: 'auto' })
  if (abs < hour) {
    const m = Math.round(diffMs / minute)
    return rtf.format(m, 'minute')
  }
  if (abs < 2 * day) {
    const h = Math.round(diffMs / hour)
    return rtf.format(h, 'hour')
  }
  const d = Math.round(diffMs / day)
  return rtf.format(d, 'day')
}
