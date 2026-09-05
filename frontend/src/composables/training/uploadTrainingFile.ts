/**
 * Training media upload: init grant, then bytes through the API (server → COS).
 * Browser PUT to the bucket is skipped so Vite origins are not blocked by CORS.
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

export async function uploadTrainingFile(
  courseId: string,
  role: TrainingUploadRole,
  file: File
): Promise<{ id: string; url: string }> {
  const contentType = guessContentType(file)
  const init = await initTrainingAsset({
    course_id: courseId,
    role,
    filename: file.name,
    content_type: contentType,
    size_bytes: file.size,
  })
  return completeTrainingAsset({
    course_id: courseId,
    role,
    key: init.key,
    asset_id: init.asset_id,
    filename: file.name,
    file,
  })
}
