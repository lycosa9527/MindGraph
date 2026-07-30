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

function contentTypeFromExtension(name: string): string {
  const lower = name.toLowerCase()
  if (lower.endsWith('.png')) return 'image/png'
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg'
  if (lower.endsWith('.gif')) return 'image/gif'
  if (lower.endsWith('.webp')) return 'image/webp'
  if (lower.endsWith('.pdf')) return 'application/pdf'
  if (lower.endsWith('.doc')) return 'application/msword'
  if (lower.endsWith('.docx')) {
    return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  }
  if (lower.endsWith('.pptx')) {
    return 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
  }
  if (lower.endsWith('.mp4') || lower.endsWith('.m4v')) return 'video/mp4'
  if (lower.endsWith('.webm')) return 'video/webm'
  if (lower.endsWith('.mov')) return 'video/quicktime'
  if (lower.endsWith('.mg')) return 'application/json'
  return 'application/octet-stream'
}

function guessContentType(file: File): string {
  const raw = (file.type || '').trim().toLowerCase()
  const unusable =
    !raw || raw === 'application/octet-stream' || raw === 'binary/octet-stream'
  if (!unusable) return file.type
  return contentTypeFromExtension(file.name)
}

function isBrowserCorsOrNetworkFailure(error: unknown): boolean {
  if (!(error instanceof Error)) return false
  const message = error.message || ''
  // Chromium/Firefox: TypeError Failed to fetch; Safari: Load failed / NetworkError
  return (
    error.name === 'TypeError' ||
    error.name === 'NetworkError' ||
    /failed to fetch|networkerror|load failed|network request failed/i.test(message)
  )
}

async function putToPresignedUrl(
  putUrl: string,
  file: File,
  headers: Record<string, string>,
): Promise<void> {
  const contentType = headers['Content-Type'] || guessContentType(file)
  let response: Response
  try {
    response = await fetch(putUrl, {
      method: 'PUT',
      headers: {
        ...headers,
        'Content-Type': contentType,
      },
      body: file,
    })
  } catch (error) {
    if (isBrowserCorsOrNetworkFailure(error)) {
      // Browser→COS blocked: bucket CORS, CSP connect-src, or offline
      throw new Error('SHOWCASE_STORAGE_CORS_OR_NETWORK')
    }
    throw error
  }
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
