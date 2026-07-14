/**
 * Showcase media upload: init → (presigned PUT | local multipart) → complete.
 */
import {
  completeShowcaseUpload,
  initShowcaseUpload,
  type ShowcasePost,
  type ShowcaseUploadInitResponse,
} from '@/utils/apiClient'

export type ShowcaseUploadRole =
  | 'thumbnail'
  | 'attachment'
  | 'source'
  | 'reflection'
  | 'classroom'
  | `gallery_${number}`

function guessContentType(file: File): string {
  if (file.type) return file.type
  const name = file.name.toLowerCase()
  if (name.endsWith('.png')) return 'image/png'
  if (name.endsWith('.jpg') || name.endsWith('.jpeg')) return 'image/jpeg'
  if (name.endsWith('.gif')) return 'image/gif'
  if (name.endsWith('.webp')) return 'image/webp'
  if (name.endsWith('.pdf')) return 'application/pdf'
  if (name.endsWith('.doc')) return 'application/msword'
  if (name.endsWith('.docx')) {
    return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  }
  if (name.endsWith('.mp4') || name.endsWith('.m4v')) return 'video/mp4'
  if (name.endsWith('.webm')) return 'video/webm'
  if (name.endsWith('.mov')) return 'video/quicktime'
  if (name.endsWith('.mg')) return 'application/json'
  return 'application/octet-stream'
}

async function putToPresignedUrl(
  putUrl: string,
  file: File,
  headers: Record<string, string>,
): Promise<void> {
  const response = await fetch(putUrl, {
    method: 'PUT',
    headers: {
      ...headers,
      'Content-Type': headers['Content-Type'] || guessContentType(file),
    },
    body: file,
  })
  if (!response.ok) {
    throw new Error(`SHOWCASE_STORAGE_PUT_FAILED:${response.status}`)
  }
}

export async function uploadShowcaseFile(options: {
  postId: string
  role: ShowcaseUploadRole
  file: File
  filename?: string
}): Promise<{ key: string; url: string; post: ShowcasePost }> {
  const filename = options.filename || options.file.name
  const contentType = guessContentType(options.file)
  const init: ShowcaseUploadInitResponse = await initShowcaseUpload(options.postId, {
    role: options.role,
    filename,
    content_type: contentType,
    size_bytes: options.file.size,
  })

  if (init.put_url) {
    await putToPresignedUrl(init.put_url, options.file, init.headers || {})
    return completeShowcaseUpload(options.postId, {
      role: options.role,
      key: init.key,
      filename,
    })
  }

  // Local fallback: complete accepts multipart file body
  return completeShowcaseUpload(options.postId, {
    role: options.role,
    key: init.key,
    filename,
    file: options.file,
  })
}

export async function uploadShowcaseFilesSequential(
  postId: string,
  items: Array<{ role: ShowcaseUploadRole; file: File; filename?: string }>,
): Promise<ShowcasePost | null> {
  let lastPost: ShowcasePost | null = null
  for (const item of items) {
    const result = await uploadShowcaseFile({
      postId,
      role: item.role,
      file: item.file,
      filename: item.filename,
    })
    lastPost = result.post
  }
  return lastPost
}
