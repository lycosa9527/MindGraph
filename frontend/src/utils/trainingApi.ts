import type {
  TrainingCourse,
  TrainingCourseStep,
  TrainingOrgRow,
  TrainingReady,
  TrainingRosterRow,
  TrainingRosterSummary,
  TrainingSnapshot,
} from '@/types/training'
import { apiRequest, apiUpload, parseApiErrorDetail } from '@/utils/apiClient'
import { emptyTrainingSnapshot, TRAINING_RAIL_PAGE_SIZE } from '@/utils/trainingClient'

const API = '/api/training'

async function readJson<T>(res: Response): Promise<T> {
  return (await res.json()) as T
}

export async function fetchTrainingOrgs(
  q = ''
): Promise<{ items: TrainingOrgRow[]; total: number }> {
  const params = new URLSearchParams()
  if (q.trim()) params.set('q', q.trim())
  const res = await apiRequest(`${API}/orgs?${params.toString()}`)
  if (!res.ok) throw new Error('orgs')
  return readJson(res)
}

export async function fetchTrainingReady(orgId: number): Promise<TrainingReady> {
  const res = await apiRequest(`${API}/orgs/${orgId}/ready`)
  if (!res.ok) throw new Error('ready')
  return readJson(res)
}

export class TrainingApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'TrainingApiError'
    this.status = status
    this.code = code
  }
}

function detailCode(body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail?: unknown }).detail
    if (detail && typeof detail === 'object' && 'code' in detail) {
      return String((detail as { code?: unknown }).code || '')
    }
  }
  return ''
}

export async function startTrainingSession(
  orgId: number,
  confirmTeacherTotal: number
): Promise<TrainingSnapshot> {
  const res = await apiRequest(`${API}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ org_id: orgId, confirm_teacher_total: confirmTeacherTotal }),
  })
  if (!res.ok) {
    const body: unknown = await res.json().catch(() => null)
    throw new TrainingApiError(res.status, detailCode(body), String(res.status))
  }
  return readJson(res)
}

export async function fetchActiveTraining(orgId?: number | null): Promise<TrainingSnapshot> {
  const params = new URLSearchParams()
  if (orgId != null) params.set('org_id', String(orgId))
  const qs = params.toString()
  const res = await apiRequest(`${API}/sessions/active${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error('active')
  return readJson(res)
}

export async function fetchTrainingCommand(
  orgId: number | null,
  etag: string | null
): Promise<{ snapshot: TrainingSnapshot | null; etag: string | null; notModified: boolean }> {
  const params = new URLSearchParams()
  if (orgId != null) params.set('org_id', String(orgId))
  const headers: Record<string, string> = {}
  if (etag) headers['If-None-Match'] = etag
  const qs = params.toString()
  const res = await apiRequest(`${API}/command${qs ? `?${qs}` : ''}`, { headers })
  const nextTag = res.headers.get('ETag')
  if (res.status === 304) {
    return { snapshot: null, etag: nextTag, notModified: true }
  }
  if (!res.ok) throw new Error('command')
  return { snapshot: await readJson<TrainingSnapshot>(res), etag: nextTag, notModified: false }
}

export async function postTrainingHeartbeat(
  sessionId: string,
  orgId: number
): Promise<TrainingSnapshot> {
  const res = await apiRequest(
    `${API}/sessions/${encodeURIComponent(sessionId)}/heartbeat?org_id=${orgId}`,
    { method: 'POST' }
  )
  if (res.status === 404 || res.status === 403) {
    return emptyTrainingSnapshot()
  }
  if (!res.ok) {
    const body: unknown = await res.json().catch(() => null)
    throw new TrainingApiError(res.status, detailCode(body), 'heartbeat')
  }
  return readJson(res)
}

export async function pauseTraining(sessionId: string, orgId: number): Promise<TrainingSnapshot> {
  const res = await apiRequest(
    `${API}/sessions/${encodeURIComponent(sessionId)}/pause?org_id=${orgId}`,
    { method: 'POST' }
  )
  if (!res.ok) throw new Error('pause')
  return readJson(res)
}

export async function resumeTraining(sessionId: string, orgId: number): Promise<TrainingSnapshot> {
  const res = await apiRequest(
    `${API}/sessions/${encodeURIComponent(sessionId)}/resume?org_id=${orgId}`,
    { method: 'POST' }
  )
  if (!res.ok) throw new Error('resume')
  return readJson(res)
}

export async function endTraining(sessionId: string, orgId: number): Promise<TrainingSnapshot> {
  const res = await apiRequest(
    `${API}/sessions/${encodeURIComponent(sessionId)}/end?org_id=${orgId}`,
    { method: 'POST' }
  )
  if (!res.ok) throw new Error('end')
  return readJson(res)
}

export async function takeoverTraining(
  sessionId: string,
  orgId: number
): Promise<TrainingSnapshot> {
  const res = await apiRequest(
    `${API}/sessions/${encodeURIComponent(sessionId)}/takeover?org_id=${orgId}`,
    { method: 'POST' }
  )
  if (!res.ok) throw new Error('takeover')
  return readJson(res)
}

export async function postTrainingActivity(body: {
  diagram_type?: string | null
  option_id?: string | null
  option_label?: string | null
  generate_state?: string
}): Promise<void> {
  await apiRequest(`${API}/activity`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function fetchTrainingRoster(
  sessionId: string,
  orgId: number,
  offset = 0,
  limit = TRAINING_RAIL_PAGE_SIZE
): Promise<{ items: TrainingRosterRow[]; total: number }> {
  const params = new URLSearchParams({
    org_id: String(orgId),
    offset: String(offset),
    limit: String(limit),
  })
  const res = await apiRequest(
    `${API}/sessions/${encodeURIComponent(sessionId)}/roster?${params.toString()}`
  )
  if (!res.ok) throw new Error('roster')
  return readJson(res)
}

export async function fetchTrainingRosterSummary(
  sessionId: string,
  orgId: number
): Promise<TrainingRosterSummary> {
  const res = await apiRequest(
    `${API}/sessions/${encodeURIComponent(sessionId)}/roster/summary?org_id=${orgId}`
  )
  if (!res.ok) throw new Error('summary')
  return readJson(res)
}

export async function fetchTrainingCourses(): Promise<TrainingCourse[]> {
  const res = await apiRequest(`${API}/courses`)
  if (!res.ok) throw new Error('courses')
  const body = await readJson<{ items: TrainingCourse[] }>(res)
  return body.items
}

export async function fetchTrainingCourse(courseId: string): Promise<TrainingCourse> {
  const res = await apiRequest(`${API}/courses/${encodeURIComponent(courseId)}`)
  if (!res.ok) throw new Error('course')
  return readJson(res)
}

export async function createTrainingCourse(title?: string): Promise<TrainingCourse> {
  const res = await apiRequest(`${API}/courses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(title ? { title } : {}),
  })
  if (!res.ok) throw new Error('create')
  return readJson(res)
}

export async function saveTrainingCourse(
  courseId: string,
  body: {
    title?: unknown
    description?: unknown
    status?: string
    steps?: TrainingCourseStep[]
  }
): Promise<TrainingCourse> {
  const res = await apiRequest(`${API}/courses/${encodeURIComponent(courseId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const payload: unknown = await res.json().catch(() => null)
    throw new Error(parseApiErrorDetail(payload, 'save'))
  }
  return readJson(res)
}

export async function deleteTrainingCourse(courseId: string): Promise<void> {
  const res = await apiRequest(`${API}/courses/${encodeURIComponent(courseId)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error('delete')
}

export async function playTrainingCourse(
  sessionId: string,
  orgId: number,
  courseId: string
): Promise<TrainingSnapshot> {
  const res = await apiRequest(
    `${API}/sessions/${encodeURIComponent(sessionId)}/play?org_id=${orgId}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ course_id: courseId }),
    }
  )
  if (!res.ok) throw new Error('play')
  return readJson(res)
}

export async function freeTraining(
  sessionId: string,
  orgId: number,
  free = true
): Promise<TrainingSnapshot> {
  const res = await apiRequest(
    `${API}/sessions/${encodeURIComponent(sessionId)}/free?org_id=${orgId}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ free }),
    }
  )
  if (!res.ok) throw new Error('free')
  return readJson(res)
}

export async function stepTrainingCourse(
  sessionId: string,
  orgId: number,
  body: { index?: number; delta?: number }
): Promise<TrainingSnapshot> {
  const res = await apiRequest(
    `${API}/sessions/${encodeURIComponent(sessionId)}/step?org_id=${orgId}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }
  )
  if (!res.ok) throw new Error('step')
  return readJson(res)
}

export async function initTrainingAsset(body: {
  course_id: string
  role: 'cover' | 'slide' | 'video' | 'media' | 'thumb'
  filename: string
  content_type: string
  size_bytes: number
}): Promise<{
  key: string
  asset_id: string
  put_url: string | null
  backend: string
  headers: Record<string, string>
}> {
  const res = await apiRequest(`${API}/assets/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const payload: unknown = await res.json().catch(() => null)
    throw new Error(parseApiErrorDetail(payload, 'init'))
  }
  return readJson(res)
}

export async function completeTrainingAsset(body: {
  course_id: string
  role: 'cover' | 'slide' | 'video' | 'media' | 'thumb'
  key: string
  asset_id: string
  filename?: string
  file?: File
}): Promise<{ id: string; role: string; url: string; logical_key: string }> {
  const form = new FormData()
  form.append('course_id', body.course_id)
  form.append('role', body.role)
  form.append('key', body.key)
  form.append('asset_id', body.asset_id)
  if (body.filename) form.append('filename', body.filename)
  if (body.file) form.append('file', body.file)
  const res = await apiUpload(`${API}/assets/complete`, form)
  if (!res.ok) {
    const payload: unknown = await res.json().catch(() => null)
    throw new Error(parseApiErrorDetail(payload, 'complete'))
  }
  return readJson(res)
}
