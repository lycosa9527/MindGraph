/**
 * Shared helpers for Learning Space teacher/student UI.
 */
import type { LearningAssignment, LearningSubmission } from '@/utils/learningSpaceApi'

export type TeacherTab = 'dashboard' | 'assignments' | 'classes'
export type StudentTab = 'home' | 'assignments' | 'works'

export type AssignmentFilter = 'all' | 'active' | 'pending' | 'closed' | 'draft'

export function formatLsDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString()
}

export function assignmentIsClosed(a: LearningAssignment): boolean {
  if (a.status === 'closed' || a.status === 'archived') return true
  if (!a.due_at) return false
  const due = new Date(a.due_at).getTime()
  return Number.isFinite(due) && due < Date.now()
}

export function assignmentProgress(
  a: LearningAssignment,
  rosterSize?: number
): {
  submitted: number
  total: number
  percent: number
  unsubmitted: number
  pendingReview: number
} {
  const submitted = a.submitted_count ?? 0
  const roster = a.student_count ?? rosterSize ?? 0
  const total = Math.max(roster, submitted)
  const percent = total > 0 ? Math.round((submitted / total) * 100) : 0
  return {
    submitted,
    total,
    percent,
    unsubmitted: Math.max(0, total - submitted),
    pendingReview: submitted,
  }
}

export function submissionStatusTone(status: string | undefined): string {
  if (status === 'submitted') return 'active'
  if (status === 'returned') return 'closed'
  return 'draft'
}

export function filterTeacherAssignments(
  items: LearningAssignment[],
  filter: AssignmentFilter,
  query: string
): LearningAssignment[] {
  const q = query.trim().toLowerCase()
  return items.filter((a) => {
    if (q && !a.title.toLowerCase().includes(q)) return false
    if (filter === 'all') return true
    if (filter === 'draft') return a.status === 'draft'
    if (filter === 'closed') return assignmentIsClosed(a)
    if (filter === 'active') return !assignmentIsClosed(a) && a.status !== 'draft'
    if (filter === 'pending') {
      return (a.submitted_count ?? 0) > 0 && !assignmentIsClosed(a)
    }
    return true
  })
}

export function studentAssignmentPending(a: LearningAssignment): boolean {
  const st = a.submission?.status
  return !st || st === 'draft' || st === 'returned'
}

export function studentAssignmentDone(a: LearningAssignment): boolean {
  return a.submission?.status === 'submitted'
}

export function assignmentAllowsLate(a: LearningAssignment | null | undefined): boolean {
  return a?.ai_permissions?.allow_late_submit === true
}

export function studentCanOpenAssignment(a: LearningAssignment): boolean {
  if (studentAssignmentDone(a)) return false
  if (a.status === 'draft' || a.status === 'closed' || a.status === 'archived') return false
  if (a.submission != null) return true
  if (!assignmentIsClosed(a)) return true
  return assignmentAllowsLate(a)
}

export function studentCanSubmitAssignment(a: LearningAssignment | null | undefined): boolean {
  if (!a || studentAssignmentDone(a)) return false
  if (a.status === 'draft' || a.status === 'closed' || a.status === 'archived') return false
  if (!assignmentIsClosed(a)) return true
  return assignmentAllowsLate(a)
}

export function greetHourLabel(hour: number): 'morning' | 'afternoon' | 'evening' {
  if (hour < 12) return 'morning'
  if (hour < 18) return 'afternoon'
  return 'evening'
}

export function assignmentDiagramType(a: LearningAssignment | null | undefined): string {
  const raw = a?.ai_permissions?.diagram_type
  if (typeof raw !== 'string' || !raw.trim()) return 'mind_map'
  return raw.trim() === 'mindmap' ? 'mind_map' : raw.trim()
}

/** Auto-created publish scaffold uses a '…' placeholder, not a teacher upload. */
export function looksLikeAutoScaffoldSpec(
  spec: Record<string, unknown> | null | undefined
): boolean {
  if (!spec) return true
  return JSON.stringify(spec).includes('…')
}

export function assignmentHasTeacherTemplate(
  a: LearningAssignment | null | undefined,
  previewSpec?: Record<string, unknown> | null
): boolean {
  const role = a?.ai_permissions?.template_role
  if (role === 'none') return false
  if (role === 'reference' || role === 'scaffold') return true
  const flag = a?.ai_permissions?.has_teacher_template
  if (flag === true) return true
  if (flag === false) return false
  if (previewSpec === undefined) return false
  return !looksLikeAutoScaffoldSpec(previewSpec)
}

export function assignmentTemplateRole(
  a: LearningAssignment | null | undefined
): 'none' | 'reference' | 'scaffold' {
  const role = a?.ai_permissions?.template_role
  if (role === 'none' || role === 'reference' || role === 'scaffold') return role
  return assignmentHasTeacherTemplate(a) ? 'scaffold' : 'none'
}

export type LsReferenceDiagram = {
  id: string
  title: string
  thumbnail: string | null
}

export function assignmentReferenceDiagrams(
  a: LearningAssignment | null | undefined
): LsReferenceDiagram[] {
  const raw = a?.ai_permissions?.reference_diagrams
  if (!Array.isArray(raw)) return []
  const out: LsReferenceDiagram[] = []
  const seen = new Set<string>()
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const id = String(item.id || '').trim()
    if (!id || seen.has(id)) continue
    seen.add(id)
    const thumb = item.thumbnail
    out.push({
      id,
      title: String(item.title || '').trim(),
      thumbnail: typeof thumb === 'string' && thumb.trim() ? thumb : null,
    })
  }
  return out
}

export function studentHomeworkDiagramTitle(
  studentName: string | null | undefined,
  studentId: string | number | null | undefined,
  assignmentTitle: string | null | undefined
): string {
  const name = (studentName || '').trim() || (studentId != null ? String(studentId) : '学生')
  const asg = (assignmentTitle || '').trim() || '作业'
  const title = `${name}_${asg}`
  return title.length > 200 ? `${title.slice(0, 197)}...` : title
}

export function unsubmittedFromRoster(
  studentIds: number[],
  submissions: LearningSubmission[]
): number[] {
  const submitted = new Set(
    submissions.filter((s) => s.status === 'submitted').map((s) => s.student_user_id)
  )
  return studentIds.filter((id) => !submitted.has(id))
}
