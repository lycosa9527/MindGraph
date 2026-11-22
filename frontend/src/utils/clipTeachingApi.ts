/**
 * Clip-teaching lesson API.
 */
import { apiDelete, apiGet, apiRequestJson, apiUpload } from '@/utils/apiClient'

export interface ClipChapter {
  id: string
  title: string
  start_ms: number
}

export type ClipPreviewStatus = 'none' | 'pending' | 'ready' | 'failed'

export interface ClipLessonDetail {
  id: string
  organization_id: number
  owner_id: number
  owner_name: string
  is_owner: boolean
  title: string
  vod_media_id: string | null
  has_video: boolean
  video_storage: 'local' | 'vod'
  video_status: string | null
  duration_ms: number | null
  trim_start_ms: number
  trim_end_ms: number | null
  preview_status: ClipPreviewStatus
  has_deck: boolean
  chapters: ClipChapter[]
  created_at: string | null
  updated_at: string | null
}

export interface ClipLessonSummary {
  id: string
  owner_id: number
  owner_name: string
  is_owner: boolean
  title: string
  has_video: boolean
  preview_status: ClipPreviewStatus
  updated_at: string | null
}

export interface ClipComment {
  id: number
  user_id: number
  author_name: string
  body: string
  created_at: string | null
  can_delete: boolean
  replies: ClipComment[]
}

export interface ClipUploadSign {
  signature: string
  source_context: string
}

export async function listClipLessons(): Promise<ClipLessonSummary[]> {
  const payload = await apiRequestJson<{ items: ClipLessonSummary[] }>('/api/clip-lessons')
  return payload.items
}

export async function createClipLesson(title: string): Promise<ClipLessonDetail> {
  return apiRequestJson<ClipLessonDetail>('/api/clip-lessons', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export async function fetchClipLesson(lessonId: string): Promise<ClipLessonDetail> {
  return apiRequestJson<ClipLessonDetail>(`/api/clip-lessons/${lessonId}`)
}

export async function renameClipLesson(lessonId: string, title: string): Promise<ClipLessonDetail> {
  return apiRequestJson<ClipLessonDetail>(`/api/clip-lessons/${lessonId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export async function deleteClipLesson(lessonId: string): Promise<void> {
  const response = await apiDelete(`/api/clip-lessons/${lessonId}`)
  if (!response.ok) {
    throw new Error('save_failed')
  }
}

export async function saveClipTrim(
  lessonId: string,
  trimStartMs: number,
  trimEndMs: number | null
): Promise<ClipLessonDetail> {
  return apiRequestJson<ClipLessonDetail>(`/api/clip-lessons/${lessonId}/trim`, {
    method: 'PUT',
    body: JSON.stringify({ trim_start_ms: trimStartMs, trim_end_ms: trimEndMs }),
  })
}

export async function saveClipChapters(
  lessonId: string,
  chapters: Array<{ title: string; start_ms: number }>
): Promise<ClipLessonDetail> {
  return apiRequestJson<ClipLessonDetail>(`/api/clip-lessons/${lessonId}/chapters`, {
    method: 'PUT',
    body: JSON.stringify({ chapters }),
  })
}

export async function signClipUpload(lessonId: string): Promise<ClipUploadSign> {
  return apiRequestJson<ClipUploadSign>(`/api/clip-lessons/${lessonId}/uploads/sign`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function registerClipMedia(
  lessonId: string,
  payload: { fileId: string; sourceContext: string }
): Promise<ClipLessonDetail> {
  return apiRequestJson<ClipLessonDetail>(`/api/clip-lessons/${lessonId}/media`, {
    method: 'POST',
    body: JSON.stringify({
      file_id: payload.fileId,
      source_context: payload.sourceContext,
    }),
  })
}

export type ClipPlayTicket =
  | { mode: 'local'; url: string }
  | {
      mode?: 'vod'
      appId: string
      fileId: string
      psign: string
      licenseUrl: string
      licenseKey: string
    }

export async function playClipLesson(lessonId: string): Promise<ClipPlayTicket> {
  return apiRequestJson(`/api/clip-lessons/${lessonId}/play`)
}

export async function uploadClipVideo(lessonId: string, file: File): Promise<ClipLessonDetail> {
  const form = new FormData()
  form.append('upload', file)
  const response = await apiUpload(`/api/clip-lessons/${lessonId}/video`, form)
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload ? String(payload.detail) : ''
    throw new Error(detail || 'video_invalid')
  }
  return (await response.json()) as ClipLessonDetail
}

export async function uploadClipDeck(lessonId: string, file: File): Promise<ClipLessonDetail> {
  const form = new FormData()
  form.append('upload', file)
  const response = await apiUpload(`/api/clip-lessons/${lessonId}/deck`, form)
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload ? String(payload.detail) : ''
    throw new Error(detail || 'deck_invalid')
  }
  return (await response.json()) as ClipLessonDetail
}

export async function fetchClipPreview(lessonId: string): Promise<Uint8Array> {
  const response = await apiGet(`/api/clip-lessons/${lessonId}/deck/preview`)
  if (!response.ok) {
    throw new Error('preview_pending')
  }
  return new Uint8Array(await response.arrayBuffer())
}

export async function listClipComments(lessonId: string): Promise<ClipComment[]> {
  const payload = await apiRequestJson<{ items: ClipComment[] }>(
    `/api/clip-lessons/${lessonId}/comments`
  )
  return payload.items
}

export async function addClipComment(
  lessonId: string,
  body: string,
  parentId: number | null
): Promise<ClipComment[]> {
  const payload = await apiRequestJson<{ items: ClipComment[] }>(
    `/api/clip-lessons/${lessonId}/comments`,
    {
      method: 'POST',
      body: JSON.stringify({ body, parent_id: parentId }),
    }
  )
  return payload.items
}

export async function deleteClipComment(
  lessonId: string,
  commentId: number
): Promise<ClipComment[]> {
  const payload = await apiRequestJson<{ items: ClipComment[] }>(
    `/api/clip-lessons/${lessonId}/comments/${commentId}`,
    { method: 'DELETE' }
  )
  return payload.items
}
