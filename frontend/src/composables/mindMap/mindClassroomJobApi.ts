/**
 * Mind Classroom job enqueue / SSE watch.
 */
import { apiGet, apiPost } from '@/utils/apiClient'

export type MindClassroomJobStatus =
  | 'queued'
  | 'planning'
  | 'generating'
  | 'ready'
  | 'partial'
  | 'failed'
  | 'cancelled'

export interface MindClassroomRemoteStep {
  id?: string
  kind?: string
  title?: string
  caption?: string
  bullets?: string[]
  focus_node_ids?: string[]
  branch_node_id?: string | null
  image_url?: string | null
}

export interface MindClassroomSlideRow {
  id: string
  slide_index: number
  title?: string | null
  teacher_script?: string | null
  focus_node_ids?: string[] | null
  image_url?: string | null
  size?: string | null
}

export interface MindClassroomJobDetail {
  id: string
  status: MindClassroomJobStatus | string
  current_stage?: string | null
  progress?: Record<string, unknown> | null
  error_message?: string | null
  diagram_id?: string | null
  settings?: Record<string, unknown>
  result_json?: {
    steps?: MindClassroomRemoteStep[]
    transcript_key?: string
    transcript_uploaded?: boolean
  } | null
  transcript_url?: string | null
  lesson_plan_json?: Record<string, unknown> | null
  slides?: MindClassroomSlideRow[]
  legacy_zhihui?: boolean
  generations?: Array<Record<string, unknown>>
}

export async function enqueueMindClassroomJob(body: Record<string, unknown>): Promise<{
  job_id: string
  status: string
  reused?: boolean
}> {
  const res = await apiPost('/api/mind-classroom/jobs', body)
  if (!res.ok) {
    const raw = await res.text()
    let message = raw || `HTTP ${res.status}`
    try {
      const parsed = JSON.parse(raw) as { detail?: string }
      if (parsed.detail) message = String(parsed.detail)
    } catch {
      /* keep raw */
    }
    throw new Error(message)
  }
  return (await res.json()) as { job_id: string; status: string; reused?: boolean }
}

export async function fetchMindClassroomJob(jobId: string): Promise<MindClassroomJobDetail> {
  const res = await apiGet(`/api/mind-classroom/jobs/${encodeURIComponent(jobId)}`)
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  return (await res.json()) as MindClassroomJobDetail
}

export function isClassroomJobActive(status: string | null | undefined): boolean {
  return status === 'queued' || status === 'planning' || status === 'generating'
}

export function isClassroomJobPlayable(status: string | null | undefined): boolean {
  return status === 'ready' || status === 'partial'
}

export async function cancelMindClassroomJob(jobId: string): Promise<void> {
  const res = await apiPost(`/api/mind-classroom/jobs/${encodeURIComponent(jobId)}/cancel`, {})
  if (!res.ok && res.status !== 404) {
    throw new Error(`HTTP ${res.status}`)
  }
}

export async function fetchMindClassroomJobByDiagram(
  diagramId: string,
  mode?: string
): Promise<MindClassroomJobDetail> {
  const query = mode ? `?mode=${encodeURIComponent(mode)}` : ''
  const res = await apiGet(
    `/api/mind-classroom/jobs/by-diagram/${encodeURIComponent(diagramId)}${query}`
  )
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`)
  }
  return (await res.json()) as MindClassroomJobDetail
}

function applyClassroomJobEvent(
  data: unknown,
  options: {
    shouldStop?: () => boolean
    onUpdate?: (detail: MindClassroomJobDetail) => void
  }
): MindClassroomJobDetail | 'heartbeat' | 'cancelled' {
  if (options.shouldStop?.()) {
    return 'cancelled'
  }
  if (!data || typeof data !== 'object') {
    return 'heartbeat'
  }
  const payload = data as { type?: string; job?: MindClassroomJobDetail; error?: string }
  if (payload.type === 'heartbeat') {
    return 'heartbeat'
  }
  if (payload.type === 'error') {
    throw new Error(payload.error || 'stream_unavailable')
  }
  const detail = payload.job
  if (!detail || typeof detail.status !== 'string') {
    return 'heartbeat'
  }
  options.onUpdate?.(detail)
  if (isClassroomJobPlayable(detail.status)) {
    return detail
  }
  if (detail.status === 'failed' || detail.status === 'cancelled') {
    throw new Error(detail.error_message || detail.status)
  }
  return 'heartbeat'
}

export async function watchMindClassroomJob(
  jobId: string,
  options: {
    shouldStop?: () => boolean
    onUpdate?: (detail: MindClassroomJobDetail) => void
  } = {}
): Promise<MindClassroomJobDetail> {
  const url = `/api/mind-classroom/jobs/${encodeURIComponent(jobId)}/stream`
  return new Promise((resolve, reject) => {
    if (typeof EventSource === 'undefined') {
      reject(new Error('stream_unavailable'))
      return
    }
    const source = new EventSource(url, { withCredentials: true })
    let settled = false
    const finish = (action: () => void) => {
      if (settled) return
      settled = true
      source.close()
      action()
    }
    source.onmessage = (event) => {
      try {
        const parsed = event.data ? (JSON.parse(event.data) as unknown) : null
        const next = applyClassroomJobEvent(parsed, options)
        if (next === 'cancelled') {
          finish(() => reject(new Error('cancelled')))
          return
        }
        if (next !== 'heartbeat') {
          finish(() => resolve(next))
        }
      } catch (err) {
        finish(() => reject(err instanceof Error ? err : new Error(String(err))))
      }
    }
    source.onerror = () => {
      if (settled) return
      if (options.shouldStop?.()) {
        finish(() => reject(new Error('cancelled')))
        return
      }
      if (source.readyState === EventSource.CLOSED) {
        finish(() => reject(new Error('stream_unavailable')))
      }
    }
  })
}

/** @deprecated Use watchMindClassroomJob — kept for existing test spies. */
export const pollMindClassroomJob = watchMindClassroomJob
