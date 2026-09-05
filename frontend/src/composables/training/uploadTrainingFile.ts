/**
 * Training media upload: init grant, browser→COS when a put URL exists,
 * otherwise bytes through the API (local / CORS fallback).
 */
import { completeTrainingAsset, initTrainingAsset } from '@/utils/trainingApi'

export type TrainingUploadRole = 'cover' | 'slide' | 'video' | 'media' | 'thumb'

function contentTypeFromExtension(name: string): string {
  const lower = name.toLowerCase()
  if (lower.endsWith('.png')) return 'image/png'
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg'
  if (lower.endsWith('.webp')) return 'image/webp'
  if (lower.endsWith('.pdf')) return 'application/pdf'
  if (lower.endsWith('.mp4') || lower.endsWith('.m4v')) return 'video/mp4'
  if (lower.endsWith('.webm')) return 'video/webm'
  if (lower.endsWith('.mov')) return 'video/quicktime'
  return 'application/octet-stream'
}

function guessContentType(file: File): string {
  const raw = (file.type || '').trim().toLowerCase()
  if (raw && raw !== 'application/octet-stream' && raw !== 'binary/octet-stream') {
    return file.type
  }
  return contentTypeFromExtension(file.name)
}

const EXTENSION_BY_TYPE: Record<string, string> = {
  'image/png': '.png',
  'image/jpeg': '.jpg',
  'image/webp': '.webp',
  'application/pdf': '.pdf',
  'video/mp4': '.mp4',
  'video/webm': '.webm',
  'video/quicktime': '.mov',
}

export function filenameForTrainingUpload(file: File, contentType: string): string {
  const name = (file.name || 'upload').trim() || 'upload'
  if (/\.[a-z0-9]{1,8}$/i.test(name)) return name
  const mime = contentType.split(';')[0].trim().toLowerCase()
  const ext = EXTENSION_BY_TYPE[mime]
  return ext ? `${name}${ext}` : name
}

function isBrowserCorsOrNetworkFailure(error: unknown): boolean {
  if (!(error instanceof Error)) return false
  const message = error.message || ''
  return (
    error.name === 'TypeError' ||
    error.name === 'NetworkError' ||
    /failed to fetch|networkerror|load failed|network request failed/i.test(message)
  )
}

async function putToPresignedUrl(
  putUrl: string,
  file: File,
  headers: Record<string, string>
): Promise<void> {
  const contentType = headers['Content-Type'] || guessContentType(file)
  const response = await fetch(putUrl, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': contentType },
    body: file,
  })
  if (!response.ok) {
    throw new Error(`TRAINING_STORAGE_PUT_FAILED:${response.status}`)
  }
}

async function completeUpload(
  courseId: string,
  role: TrainingUploadRole,
  init: { key: string; asset_id: string },
  filename: string,
  file?: File
): Promise<{ id: string; url: string }> {
  return completeTrainingAsset({
    course_id: courseId,
    role,
    key: init.key,
    asset_id: init.asset_id,
    filename,
    file,
  })
}

let uploadChain: Promise<unknown> = Promise.resolve()

function enqueueUpload<T>(work: () => Promise<T>): Promise<T> {
  const run = uploadChain.then(work, work)
  uploadChain = run.then(
    () => undefined,
    () => undefined
  )
  return run
}

export async function uploadTrainingFile(
  courseId: string,
  role: TrainingUploadRole,
  file: File
): Promise<{ id: string; url: string }> {
  if (file.size < 1) {
    throw new Error('empty')
  }
  return enqueueUpload(async () => {
    const contentType = guessContentType(file)
    const filename = filenameForTrainingUpload(file, contentType)
    const init = await initTrainingAsset({
      course_id: courseId,
      role,
      filename,
      content_type: contentType,
      size_bytes: file.size,
    })
    if (init.put_url) {
      try {
        await putToPresignedUrl(init.put_url, file, init.headers || {})
        return completeUpload(courseId, role, init, filename)
      } catch (error) {
        if (!isBrowserCorsOrNetworkFailure(error)) {
          throw error
        }
      }
    }
    return completeUpload(courseId, role, init, filename, file)
  })
}
