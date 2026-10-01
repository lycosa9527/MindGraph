/**
 * Learning Space API helpers (admin / teacher / student).
 */
import { apiRequestJson, apiUpload } from '@/utils/apiClient'

const BASE = '/api/learning-space'

export type LearningSpaceContextRole =
  | 'student'
  | 'pilot_teacher'
  | 'assistant'
  | 'learner'
  | 'superadmin'
  | 'platform_bd'
  | 'expert'
  | 'school_admin'
  | 'none'

export interface LearningSpaceContext {
  role: LearningSpaceContextRole
  can_learn?: boolean
  can_review?: boolean
  can_publish?: boolean
  can_manage_classes?: boolean
  must_change_password?: boolean
  organization_id?: number
  class?: { id: number; name: string; class_code: string } | null
}

export interface LearningAiPermissions {
  ai_assist?: boolean
  topic_generate?: boolean
  file_generate?: boolean
  web_generate?: boolean
  voice_summary?: boolean
  ai_brainstorm?: boolean
  conversational_edit?: boolean
  node_subgraph?: boolean
  node_explain?: boolean
  mind_classroom?: boolean
  generate_diagram?: boolean
  node_palette?: boolean
  inline_recommend?: boolean
  translate?: boolean
  doc_summary?: boolean
  evaluation_dimensions?: string[]
  allow_late_submit?: boolean
  remind_24h?: boolean
  diagram_type?: string
  has_teacher_template?: boolean
  template_role?: 'none' | 'reference' | 'scaffold'
  start_mode?: 'blank' | 'scaffold'
  reference_diagrams?: Array<{ id: string; title?: string; thumbnail?: string | null }>
}

export interface LearningAssignment {
  id: number
  class_id: number
  title: string
  instructions: string
  instruction_images?: string[]
  template_diagram_id: string
  template_thumbnail?: string | null
  due_at: string | null
  ai_permissions: LearningAiPermissions
  status: string
  created_by: number
  created_at: string | null
  submission_count?: number
  submitted_count?: number
  student_count?: number
  submission?: LearningSubmission | null
}

export interface LearningSubmission {
  id: number
  assignment_id: number
  student_user_id: number
  student_name?: string
  assignment_title?: string
  diagram_id: string
  diagram_thumbnail?: string | null
  status: string
  submitted_at: string | null
  due_at_override: string | null
  review_scores?: Record<string, number> | null
  review_comment?: string | null
  review_liked?: boolean
  review_pinned?: boolean
  reviewed_at?: string | null
  preview_spec?: Record<string, unknown> | null
  preview_diagram_type?: string
  preview_title?: string
}

export interface LearningTemplatePreview {
  template_diagram_id: string
  title: string
  diagram_type: string
  language: string
  preview_spec: Record<string, unknown> | null
  thumbnail: string | null
}

export interface LearningReviewPayload {
  scores: Record<string, number>
  comment: string
  liked: boolean
  pinned: boolean
}

export interface LearningPilot {
  id: number
  teacher_user_id: number
  teacher_name?: string
  organization_id: number
  organization_name?: string
  enabled: boolean
  class_count?: number
  created_at: string | null
}

export interface LearningClassAssistant {
  id: number
  name: string
  phone?: string | null
  organization_name?: string
}

export interface LearningClassRow {
  id: number
  name: string
  class_code: string
  teacher_user_id?: number
  teacher_name?: string
  organization_id?: number
  organization_name?: string
  status: string
  max_students?: number
  student_count: number
  assignment_count?: number
  submission_count?: number
  can_publish?: boolean
  assistants?: LearningClassAssistant[]
}

export interface LearningTeacherSearchRow {
  id: number
  name: string
  phone: string | null
  email: string | null
  role: string
  organization_id: number | null
  organization_name: string
  already_pilot: boolean
}

export interface LearningStudentRow {
  id: number
  name: string
  phone?: string | null
  role?: string
  school_tier?: string | null
  organization_name?: string
  member_kind?: 'classroom' | 'enrolled'
  membership_role?: 'learner' | 'assistant' | null
  initial_password?: string
  must_change_password: boolean
  last_login?: string | null
}

export interface ImportPreviewRow {
  name: string
  initial_password: string
  ok: boolean
  error: string | null
}

export interface AccountImportPreviewRow {
  phone: string
  ok: boolean
  error: string | null
  user_id: number | null
  name: string | null
  organization_name: string | null
  role: string | null
}

function postJson<T>(path: string, body?: unknown): Promise<T> {
  return apiRequestJson<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

function patchJson<T>(path: string, body?: unknown): Promise<T> {
  return apiRequestJson<T>(path, {
    method: 'PATCH',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export async function fetchLearningSpaceContext(): Promise<LearningSpaceContext> {
  return apiRequestJson<LearningSpaceContext>(`${BASE}/me/context`)
}

export async function studentChangePassword(newPassword: string): Promise<{ ok: boolean }> {
  return postJson(`${BASE}/student/change-password`, { new_password: newPassword })
}

export async function listStudentAssignments(): Promise<{ items: LearningAssignment[] }> {
  return apiRequestJson(`${BASE}/student/assignments`)
}

export async function openStudentAssignment(
  assignmentId: number
): Promise<{ assignment: LearningAssignment; submission: LearningSubmission }> {
  return postJson(`${BASE}/student/assignments/${assignmentId}/open`)
}

export async function bindStudentDraftDiagram(
  assignmentId: number,
  diagramId: string
): Promise<LearningSubmission> {
  return postJson(`${BASE}/student/assignments/${assignmentId}/draft`, {
    diagram_id: diagramId,
  })
}

export async function submitStudentAssignment(assignmentId: number): Promise<LearningSubmission> {
  return postJson(`${BASE}/student/assignments/${assignmentId}/submit`)
}

export async function listTeacherClasses(): Promise<{ items: LearningClassRow[] }> {
  return apiRequestJson(`${BASE}/teacher/classes`)
}

export async function listTeacherStudents(
  classId: number
): Promise<{ items: LearningStudentRow[] }> {
  return apiRequestJson(`${BASE}/teacher/classes/${classId}/students`)
}

export async function teacherResetPassword(
  studentId: number
): Promise<{ student_id: number; name: string; initial_password: string }> {
  return postJson(`${BASE}/teacher/students/${studentId}/reset-password`)
}

export async function uploadInstructionImage(
  file: File,
  classId?: number
): Promise<{ ref: string }> {
  const form = new FormData()
  form.append('file', file)
  if (classId != null) {
    form.append('class_id', String(classId))
  }
  const response = await apiUpload(`${BASE}/teacher/instruction-images`, form)
  if (!response.ok) {
    throw new Error('upload failed')
  }
  return (await response.json()) as { ref: string }
}

export async function createTeacherAssignment(body: {
  class_id: number
  title: string
  instructions: string
  template_diagram_id: string
  due_at?: string | null
  ai_permissions: Partial<LearningAiPermissions> & Record<string, unknown>
  instruction_images?: string[]
  status?: 'active' | 'draft'
}): Promise<LearningAssignment> {
  return postJson(`${BASE}/teacher/assignments`, body)
}

export async function listTeacherAssignments(
  classId: number
): Promise<{ items: LearningAssignment[] }> {
  return apiRequestJson(`${BASE}/teacher/classes/${classId}/assignments`)
}

export async function deleteTeacherAssignment(assignmentId: number): Promise<{ ok: boolean }> {
  return postJson(`${BASE}/teacher/assignments/${assignmentId}/delete`)
}

export async function fetchAssignmentAiPermissions(assignmentId: number): Promise<{
  assignment_id: number
  ai_permissions: LearningAiPermissions
  assignment: LearningAssignment
}> {
  return apiRequestJson(`${BASE}/ai-permissions/${assignmentId}`)
}

export async function listTeacherSubmissions(
  assignmentId: number
): Promise<{ items: LearningSubmission[] }> {
  return apiRequestJson(`${BASE}/teacher/assignments/${assignmentId}/submissions`)
}

export async function saveTeacherReview(
  submissionId: number,
  body: LearningReviewPayload
): Promise<LearningSubmission> {
  return postJson(`${BASE}/teacher/submissions/${submissionId}/review`, body)
}

export async function fetchSubmissionPreview(submissionId: number): Promise<LearningSubmission> {
  return apiRequestJson(`${BASE}/submissions/${submissionId}/preview`)
}

export async function fetchAssignmentTemplatePreview(
  assignmentId: number
): Promise<LearningTemplatePreview> {
  return apiRequestJson(`${BASE}/assignments/${assignmentId}/template-preview`)
}

export async function listStudentClassWall(): Promise<{ items: LearningSubmission[] }> {
  return apiRequestJson(`${BASE}/student/class-wall`)
}

export async function returnSubmission(submissionId: number): Promise<LearningSubmission> {
  return postJson(`${BASE}/teacher/submissions/${submissionId}/return`)
}

export async function extendSubmission(
  submissionId: number,
  dueAt: string
): Promise<LearningSubmission> {
  return postJson(`${BASE}/teacher/submissions/${submissionId}/extend`, { due_at: dueAt })
}

export async function listAdminPilots(): Promise<{ items: LearningPilot[] }> {
  return apiRequestJson(`${BASE}/admin/pilots`)
}

export async function searchAdminTeachers(params: {
  q?: string
  organization_id?: number | null
  limit?: number
}): Promise<{ items: LearningTeacherSearchRow[] }> {
  const search = new URLSearchParams()
  if (params.q?.trim()) {
    search.set('q', params.q.trim())
  }
  // Use org_id — must not collide with AdminScope's organization_id query param.
  if (params.organization_id != null && Number.isFinite(params.organization_id)) {
    search.set('org_id', String(params.organization_id))
  }
  if (params.limit != null) {
    search.set('limit', String(params.limit))
  }
  const qs = search.toString()
  return apiRequestJson(`${BASE}/admin/teachers/search${qs ? `?${qs}` : ''}`)
}

export async function createAdminPilot(body: {
  teacher_user_id: number
  organization_id: number
}): Promise<{ id: number; teacher_user_id: number; enabled: boolean }> {
  return postJson(`${BASE}/admin/pilots`, body)
}

export async function patchAdminPilot(
  pilotId: number,
  enabled: boolean
): Promise<{ id: number; enabled: boolean }> {
  return patchJson(`${BASE}/admin/pilots/${pilotId}?enabled=${enabled ? 'true' : 'false'}`)
}

export async function deleteAdminPilot(pilotId: number): Promise<{ ok: boolean; id: number }> {
  // Prefer POST action path — some reloads only had PATCH on /pilots/{id} (405 on DELETE).
  return postJson(`${BASE}/admin/pilots/${pilotId}/delete`)
}

export async function listAdminClasses(): Promise<{ items: LearningClassRow[] }> {
  return apiRequestJson(`${BASE}/admin/classes`)
}

export async function createAdminClass(body: {
  name: string
  teacher_user_id: number
  max_students?: number
}): Promise<{ id: number; name: string; class_code: string; teacher_user_id: number }> {
  return postJson(`${BASE}/admin/classes`, body)
}

export async function patchAdminClass(
  classId: number,
  body: {
    name?: string
    status?: string
    max_students?: number
    class_code?: string
    assistant_user_ids?: number[]
  }
): Promise<{ id: number; name: string; status: string; class_code: string }> {
  return patchJson(`${BASE}/admin/classes/${classId}`, body)
}

export async function rotateAdminClassCode(
  classId: number
): Promise<{ id: number; class_code: string }> {
  return postJson(`${BASE}/admin/classes/${classId}/rotate-code`)
}

export async function previewAdminImport(
  classId: number,
  names: string[]
): Promise<{ items: ImportPreviewRow[] }> {
  return postJson(`${BASE}/admin/classes/${classId}/import/preview`, { names })
}

export async function runAdminImport(
  classId: number,
  names: string[]
): Promise<{
  created: Array<{ name: string; initial_password: string; user_id?: number }>
  failed: Array<{ name: string; error: string }>
}> {
  return postJson(`${BASE}/admin/classes/${classId}/import`, { names })
}

export async function previewAdminAccountImport(
  classId: number,
  phones: string[]
): Promise<{ items: AccountImportPreviewRow[] }> {
  return postJson(`${BASE}/admin/classes/${classId}/import/accounts/preview`, { phones })
}

export async function runAdminAccountImport(
  classId: number,
  phones: string[]
): Promise<{
  created: Array<{ user_id: number; phone: string; name?: string | null; organization_name?: string | null }>
  failed: Array<{ phone: string; error: string }>
}> {
  return postJson(`${BASE}/admin/classes/${classId}/import/accounts`, { phones })
}

export async function listAdminStudents(
  classId: number
): Promise<{ items: LearningStudentRow[] }> {
  return apiRequestJson(`${BASE}/admin/classes/${classId}/students`)
}

export async function adminResetPassword(
  studentId: number
): Promise<{ student_id: number; name: string; initial_password: string }> {
  return postJson(`${BASE}/admin/students/${studentId}/reset-password`)
}
