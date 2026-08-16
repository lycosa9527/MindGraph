/**
 * Mind Classroom job enqueue / poll.
 */
import { apiGet, apiPost } from '@/utils/apiClient'

const POLL_MS = 1500

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

export async function pollMindClassroomJob(
  jobId: string,
  options: {
    intervalMs?: number
    shouldStop?: () => boolean
    onUpdate?: (detail: MindClassroomJobDetail) => void
  } = {}
): Promise<MindClassroomJobDetail> {
  const interval = options.intervalMs ?? POLL_MS
  while (!options.shouldStop?.()) {
    const detail = await fetchMindClassroomJob(jobId)
    options.onUpdate?.(detail)
    if (isClassroomJobPlayable(detail.status)) {
      return detail
    }
    if (detail.status === 'failed' || detail.status === 'cancelled') {
      throw new Error(detail.error_message || detail.status)
    }
    await new Promise((resolve) => {
      window.setTimeout(resolve, interval)
    })
  }
  throw new Error('cancelled')
}
