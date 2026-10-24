/**
 * Shared helpers for Learning Space teacher/student UI.
 */
import { beijingWallClock, parseApiInstant, parseBeijingWall } from '@/utils/beijingClock'
import type { LearningAssignment, LearningSubmission } from '@/utils/learningSpaceApi'

export type TeacherTab = 'dashboard' | 'assignments' | 'classes'
export type StudentTab = 'home' | 'assignments' | 'works'

export type AssignmentFilter = 'all' | 'active' | 'pending' | 'closed' | 'draft'
export type StudentAssignmentFilter = 'all' | 'todo' | 'submitted' | 'urgent'

/**
 * Parse an API timestamp. Columns are timezone-naive UTC, so a value with no
 * offset is UTC, not the browser's local clock.
 */
export function parseLsInstant(value: string | null | undefined): Date | null {
  return parseApiInstant(value)
}

/** `YYYY/MM/DD HH:mm:ss` in Asia/Shanghai, independent of the browser timezone. */
export function formatLsDateTime(value: string | null | undefined): string {
  if (!value?.trim()) return '—'
  const parsed = parseLsInstant(value)
  if (!parsed) return value
  const wall = beijingWallClock(parsed)
  return `${wall.year}/${wall.month}/${wall.day} ${wall.hour}:${wall.minute}:${wall.second}`
}

/**
 * Form value is `YYYY-MM-DDTHH:mm` with no timezone.
 * Teachers set deadlines on the Beijing clock.
 */
export function beijingWallClockToIso(value: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value.trim())) return null
  const parsed = parseBeijingWall(value)
  return parsed ? parsed.toISOString() : null
}

export { beijingHour } from '@/utils/beijingClock'

export function assignmentIsClosed(a: LearningAssignment): boolean {
  if (a.status === 'closed' || a.status === 'archived') return true
  if (!a.due_at) return false
  const due = parseLsInstant(a.due_at)
  return due != null && due.getTime() < Date.now()
}

export type UnsubmittedTopicRow = {
  id: number
  title: string
  className: string
  unsubmitted: number
}

/** One row per assignment, with that assignment's own unsubmitted count. */
export function unsubmittedTopicRows(
  assignments: readonly LearningAssignment[],
  classById: ReadonlyMap<number, { name: string; student_count?: number }>
): UnsubmittedTopicRow[] {
  const rows: UnsubmittedTopicRow[] = []
  for (const row of assignments) {
    const learningClass = classById.get(row.class_id)
    const progress = assignmentProgress(row, learningClass?.student_count)
    if (progress.unsubmitted <= 0) continue
    rows.push({
      id: row.id,
      title: row.title.trim() || '—',
      className: (learningClass?.name ?? '').trim(),
      unsubmitted: progress.unsubmitted,
    })
  }
  rows.sort((a, b) => b.unsubmitted - a.unsubmitted || a.title.localeCompare(b.title, 'zh'))
  const titleCounts = new Map<string, number>()
  for (const row of rows) {
    titleCounts.set(row.title, (titleCounts.get(row.title) ?? 0) + 1)
  }
  return rows.map((row) => ({
    ...row,
    className: (titleCounts.get(row.title) ?? 0) > 1 ? row.className : '',
  }))
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
  const reviewed = Math.min(submitted, Math.max(0, a.reviewed_count ?? 0))
  const roster = a.student_count ?? rosterSize ?? 0
  const total = Math.max(roster, submitted)
  const percent = total > 0 ? Math.round((submitted / total) * 100) : 0
  return {
    submitted,
    total,
    percent,
    unsubmitted: Math.max(0, total - submitted),
    pendingReview: submitted - reviewed,
  }
}

export function submissionStatusTone(status: string | undefined): string {
  if (status === 'submitted') return 'active'
  if (status === 'returned') return 'closed'
  return 'draft'
}

/** Assigned homework on the teacher tab. Drafts stay off the badge; closed work still counts. */
export function publishedAssignmentCount(
  rows: ReadonlyArray<Pick<LearningAssignment, 'status'>>
): number {
  return rows.filter((row) => row.status !== 'draft').length
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
      return assignmentProgress(a).pendingReview > 0 && !assignmentIsClosed(a)
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

/** Pending homework with a deadline that has not passed. */
export function studentAssignmentUrgent(a: LearningAssignment): boolean {
  return studentAssignmentPending(a) && Boolean(a.due_at) && !assignmentIsClosed(a)
}

export function filterStudentAssignments(
  items: readonly LearningAssignment[],
  filter: StudentAssignmentFilter
): LearningAssignment[] {
  return items.filter((row) => {
    if (filter === 'todo') return studentAssignmentPending(row)
    if (filter === 'submitted') return studentAssignmentDone(row)
    if (filter === 'urgent') return studentAssignmentUrgent(row)
    return true
  })
}

export function assignmentAllowsLate(a: LearningAssignment | null | undefined): boolean {
  return a?.ai_permissions?.allow_late_submit === true
}

export function assignmentAllowsResubmit(a: LearningAssignment | null | undefined): boolean {
  if (!a?.submission || a.submission.status !== 'submitted') return false
  if (a.status === 'draft' || a.status === 'closed' || a.status === 'archived') return false
  if (a.ai_permissions?.allow_resubmit === false) return false
  if (!assignmentIsClosed(a)) return true
  return assignmentAllowsLate(a)
}

export function studentCanResubmitAssignment(a: LearningAssignment | null | undefined): boolean {
  return assignmentAllowsResubmit(a)
}

export function studentCanOpenAssignment(a: LearningAssignment): boolean {
  if (studentCanResubmitAssignment(a)) return true
  if (studentAssignmentDone(a)) return false
  if (a.status === 'draft' || a.status === 'closed' || a.status === 'archived') return false
  if (a.submission != null) return true
  if (!assignmentIsClosed(a)) return true
  return assignmentAllowsLate(a)
}

export function studentCanSubmitAssignment(a: LearningAssignment | null | undefined): boolean {
  if (studentCanResubmitAssignment(a)) return true
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

export function normalizeDiagramTypeSlug(raw: string | null | undefined): string {
  const item = (raw ?? '').trim()
  if (!item || item === 'mindmap') return 'mind_map'
  return item
}

export function diagramTypeLabelKey(raw: string | null | undefined): string {
  return `learningSpace.diagramType.${normalizeDiagramTypeSlug(raw)}`
}

export function assignmentDiagramType(a: LearningAssignment | null | undefined): string {
  const raw = a?.ai_permissions?.diagram_type
  if (typeof raw !== 'string') return 'mind_map'
  return normalizeDiagramTypeSlug(raw)
}

/** Auto-created publish scaffold uses a '…' placeholder, not a teacher upload. */
export function looksLikeAutoScaffoldSpec(
  spec: Record<string, unknown> | null | undefined
): boolean {
  if (!spec) return true
  return JSON.stringify(spec).includes('…')
}

export function assignmentHasWorkingDiagram(a: LearningAssignment | null | undefined): boolean {
  const perms = a?.ai_permissions
  if (!perms) return false
  if (perms.has_teacher_template === true) return true
  const role = perms.template_role
  return role === 'reference' || role === 'scaffold'
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

export function formatLsStudentLabel(
  sub: Pick<LearningSubmission, 'student_name' | 'student_user_id' | 'organization_name'>
): string {
  const name = (sub.student_name || String(sub.student_user_id)).trim()
  const org = (sub.organization_name || '').trim()
  return org ? `${name} · ${org}` : name
}

/** Class work wall is visible only after the student has submitted this assignment. */
export function studentCanViewAssignmentWall(a: LearningAssignment | null | undefined): boolean {
  if (!a) return false
  return studentAssignmentDone(a)
}

export function assignmentEvalDimensions(a: LearningAssignment | null | undefined): string[] {
  const dims = a?.ai_permissions?.evaluation_dimensions
  if (!Array.isArray(dims)) return []
  return dims.map((d) => String(d).trim()).filter(Boolean)
}

export function homeworkPublisherName(name: string | null | undefined): string {
  const trimmed = (name || '').trim()
  return trimmed || '—'
}

export function homeworkGraderLabel(
  names: Array<string | null | undefined> | null | undefined
): string {
  return (names ?? [])
    .map((item) => (item || '').trim())
    .filter(Boolean)
    .join('、')
}

export function submissionGraderNames(
  submission: { reviewer_name?: string | null } | null | undefined
): string[] {
  const name = (submission?.reviewer_name || '').trim()
  return name ? [name] : []
}

export function submissionIsReviewed(
  sub:
    | Pick<
        LearningSubmission,
        | 'reviewed_at'
        | 'reviewed_by'
        | 'review_comment'
        | 'review_scores'
        | 'review_liked'
        | 'review_pinned'
      >
    | null
    | undefined
): boolean {
  if (!sub) return false
  if (sub.reviewed_by || sub.reviewed_at || sub.review_comment) return true
  if (sub.review_liked || sub.review_pinned) return true
  const scores = sub.review_scores
  return Boolean(scores && Object.keys(scores).length > 0)
}

/** A saved review whose grader account has no display name. */
export function submissionHasUnnamedReview(
  sub:
    | (Pick<LearningSubmission, 'reviewed_at' | 'review_comment' | 'review_scores'> & {
        reviewer_name?: string | null
      })
    | null
    | undefined
): boolean {
  return submissionIsReviewed(sub) && submissionGraderNames(sub).length === 0
}

/** Keep the homework card's grader line in step with a review just saved. */
export function assignmentWithGrader(
  assignment: LearningAssignment,
  reviewerName: string | null | undefined
): LearningAssignment {
  const label = (reviewerName || '').trim()
  if (!label) {
    if (assignment.has_unnamed_review) return assignment
    return { ...assignment, has_unnamed_review: true }
  }
  const names = assignment.reviewer_names ?? []
  if (names.includes(label)) return assignment
  return { ...assignment, reviewer_names: [...names, label] }
}

/** Keep pending-review counts in step with a grade just saved. */
export function assignmentWithReviewCounted(
  assignment: LearningAssignment,
  wasReviewed: boolean
): LearningAssignment {
  if (wasReviewed) return assignment
  const submitted = assignment.submitted_count ?? 0
  const reviewed = Math.min(submitted, (assignment.reviewed_count ?? 0) + 1)
  if (reviewed === assignment.reviewed_count) return assignment
  return { ...assignment, reviewed_count: reviewed }
}
