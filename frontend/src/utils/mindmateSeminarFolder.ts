/**
 * Shared seminar background files.
 */
import {
  apiDelete,
  apiGet,
  apiPost,
  apiRequestJson,
  apiUpload,
  parseApiErrorDetail,
} from '@/utils/apiClient'

export const SEMINAR_BACKGROUND_FILE_ACCEPT =
  '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md,.png,.jpg,.jpeg,.webp,.gif'

export interface SeminarBackgroundFile {
  id: string
  filename: string
  contentType: string
  sizeBytes: number
  uploaderName: string
  pinned: boolean
  pinnedAt: string | null
  createdAt: string
  sourceMessageId: number | null
  listed: boolean
  artifact: boolean
  diagramId: string | null
}

interface SeminarBackgroundFileRaw {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  uploader_name?: string
  pinned?: boolean
  pinned_at?: string | null
  created_at: string
  source_message_id?: number | null
  listed?: boolean
  artifact?: boolean
  diagram_id?: string | null
}

function mapFile(raw: SeminarBackgroundFileRaw): SeminarBackgroundFile {
  return {
    id: raw.id,
    filename: raw.filename,
    contentType: raw.content_type,
    sizeBytes: raw.size_bytes,
    uploaderName: raw.uploader_name || '',
    pinned: Boolean(raw.pinned),
    pinnedAt: raw.pinned_at || null,
    createdAt: raw.created_at,
    sourceMessageId: typeof raw.source_message_id === 'number' ? raw.source_message_id : null,
    listed: Boolean(raw.listed),
    artifact: Boolean(raw.artifact),
    diagramId: typeof raw.diagram_id === 'string' && raw.diagram_id ? raw.diagram_id : null,
  }
}

const SEMINAR_MESSAGE_FILE_RE = /\[\[sf:([0-9a-fA-F-]{36})\|([^\]]*)\]\]/g

export interface SeminarMessageFileRef {
  id: string
  filename: string
}

const SEMINAR_VOICE_EXTS = new Set(['webm', 'weba', 'mp3', 'm4a', 'wav', 'ogg'])

export function isSeminarVoiceFilename(filename: string): boolean {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  return SEMINAR_VOICE_EXTS.has(ext)
}

export function seminarMessageFileToken(id: string, filename: string): string {
  const encoded = encodeURIComponent(filename).replace(/\]/g, '%5D')
  return `[[sf:${id}|${encoded}]]`
}

export function splitSeminarMessageFiles(content: string): {
  text: string
  files: SeminarMessageFileRef[]
} {
  const files: SeminarMessageFileRef[] = []
  const text = (content || '')
    .replace(SEMINAR_MESSAGE_FILE_RE, (_match, id: string, encoded: string) => {
      let filename: string
      try {
        filename = decodeURIComponent(encoded)
      } catch {
        try {
          filename = decodeURIComponent(encoded.replace(/%(?![0-9A-Fa-f]{2})/g, '%25'))
        } catch {
          filename = encoded
        }
      }
      files.push({ id, filename })
      return ''
    })
    .replace(/\n{3,}/g, '\n\n')
    .trim()
  return { text, files }
}

export function seminarBubblePlainText(content: string): string {
  const split = splitSeminarMessageFiles(content)
  const names = split.files.map((file) => file.filename).filter(Boolean)
  return [split.text, ...names].filter(Boolean).join('\n')
}

export function formatSeminarFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function seminarFolderErrorKey(error: unknown): string {
  const message = error instanceof Error ? error.message : ''
  const normalized = message.trim().toLowerCase()
  if (
    message === 'file_too_large' ||
    normalized.includes('file_too_large') ||
    normalized.includes('too large') ||
    normalized.includes('413')
  ) {
    return 'mindmate.folder.tooLarge'
  }
  if (message === 'file_type' || normalized.includes('file_type')) {
    return 'mindmate.folder.badType'
  }
  if (message === 'file_limit' || normalized.includes('file_limit')) {
    return 'mindmate.folder.limit'
  }
  if (normalized.includes('forbidden') || normalized.includes('csrf')) {
    return 'mindmate.folder.uploadFailed'
  }
  return 'mindmate.folder.uploadFailed'
}

const seminarFileMetaCache = new Map<string, SeminarBackgroundFile>()

export async function fetchSeminarBackgroundFile(
  sessionId: string,
  fileId: string
): Promise<SeminarBackgroundFile | null> {
  const session = sessionId.trim()
  const id = fileId.trim()
  if (!session || !id) {
    return null
  }
  const cacheKey = `${session}:${id}`
  const cached = seminarFileMetaCache.get(cacheKey)
  if (cached) {
    return cached
  }
  try {
    const raw = await apiRequestJson<SeminarBackgroundFileRaw>(
      `/api/mindmate/seminar/background-files/${encodeURIComponent(id)}?session_id=${encodeURIComponent(session)}`
    )
    const file = mapFile(raw)
    seminarFileMetaCache.set(cacheKey, file)
    return file
  } catch {
    return null
  }
}

export function seminarArtifactFromPayload(raw: unknown): SeminarBackgroundFile | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const row = raw as SeminarBackgroundFileRaw
  if (!row.id || !row.filename) {
    return null
  }
  return mapFile({
    ...row,
    content_type: row.content_type || '',
    size_bytes: row.size_bytes || 0,
    created_at: row.created_at || new Date().toISOString(),
  })
}

export async function listSeminarReplyArtifacts(
  sessionId: string
): Promise<SeminarBackgroundFile[]> {
  const payload = await apiRequestJson<{ items: SeminarBackgroundFileRaw[] }>(
    `/api/mindmate/seminar/${encodeURIComponent(sessionId)}/reply-artifacts`
  )
  return (payload.items || []).map(mapFile)
}

export async function shelveSeminarItem(
  sessionId: string,
  body: {
    kind: 'file' | 'diagram'
    destination: 'resource' | 'artifact'
    fileId?: string
    diagramId?: string
    title?: string
  }
): Promise<SeminarBackgroundFile> {
  const raw = await apiRequestJson<SeminarBackgroundFileRaw>(
    `/api/mindmate/seminar/${encodeURIComponent(sessionId)}/shelf`,
    {
      method: 'POST',
      body: JSON.stringify({
        kind: body.kind,
        destination: body.destination,
        file_id: body.fileId || '',
        diagram_id: body.diagramId || '',
        title: body.title || '',
      }),
    }
  )
  const file = mapFile(raw)
  seminarFileMetaCache.set(`${sessionId.trim()}:${file.id}`, file)
  return file
}

export async function archiveSeminarReplyDocx(
  sessionId: string,
  messageId: number
): Promise<SeminarBackgroundFile> {
  const raw = await apiRequestJson<SeminarBackgroundFileRaw>(
    `/api/mindmate/seminar/${encodeURIComponent(sessionId)}/reply-artifacts`,
    {
      method: 'POST',
      body: JSON.stringify({ message_id: messageId }),
    }
  )
  return mapFile(raw)
}

export async function listSeminarBackgroundFiles(
  sessionId: string
): Promise<SeminarBackgroundFile[]> {
  const payload = await apiRequestJson<{ items: SeminarBackgroundFileRaw[] }>(
    `/api/mindmate/seminar/background-files?session_id=${encodeURIComponent(sessionId)}`
  )
  return (payload.items || []).map(mapFile)
}

export async function uploadSeminarBackgroundFile(
  sessionId: string,
  file: File,
  options: { listed?: boolean } = {}
): Promise<SeminarBackgroundFile> {
  const body = new FormData()
  body.append('session_id', sessionId)
  body.append('file', file, file.name)
  if (options.listed === false) {
    body.append('listed', 'false')
  }
  const response = await apiUpload('/api/mindmate/seminar/background-files', body)
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(parseApiErrorDetail(payload, response.statusText || 'upload_failed'))
  }
  const payload = (await response.json()) as SeminarBackgroundFileRaw
  return mapFile(payload)
}

export async function renameSeminarBackgroundFile(
  sessionId: string,
  fileId: string,
  filename: string
): Promise<SeminarBackgroundFile> {
  const payload = await apiRequestJson<SeminarBackgroundFileRaw>(
    `/api/mindmate/seminar/background-files/${encodeURIComponent(fileId)}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ session_id: sessionId, filename }),
    }
  )
  return mapFile(payload)
}

export async function pinSeminarBackgroundFile(
  sessionId: string,
  fileId: string,
  pinned: boolean
): Promise<SeminarBackgroundFile> {
  const response = await apiPost(
    `/api/mindmate/seminar/background-files/${encodeURIComponent(fileId)}/pin`,
    {
      session_id: sessionId,
      pinned,
    }
  )
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(parseApiErrorDetail(payload, response.statusText || 'pin_failed'))
  }
  const payload = (await response.json()) as SeminarBackgroundFileRaw
  return mapFile(payload)
}

export async function deleteSeminarBackgroundFile(
  sessionId: string,
  fileId: string
): Promise<void> {
  const response = await apiDelete(
    `/api/mindmate/seminar/background-files/${encodeURIComponent(fileId)}?session_id=${encodeURIComponent(sessionId)}`
  )
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(parseApiErrorDetail(payload, response.statusText || 'delete_failed'))
  }
}

export async function fetchSeminarBackgroundBlob(sessionId: string, fileId: string): Promise<Blob> {
  const response = await apiGet(
    `/api/mindmate/seminar/background-files/${encodeURIComponent(fileId)}/download?session_id=${encodeURIComponent(sessionId)}`
  )
  if (!response.ok) {
    throw new Error('download')
  }
  return response.blob()
}

export async function downloadSeminarBackgroundFile(
  sessionId: string,
  file: SeminarBackgroundFile
): Promise<void> {
  const blob = await fetchSeminarBackgroundBlob(sessionId, file.id)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = file.filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export type SeminarFilePreviewMode = 'image' | 'pdf' | 'text' | 'office' | 'unsupported'

const OFFICE_EXTS = new Set(['doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx'])

export function seminarFilePreviewMode(
  contentType: string,
  filename: string
): SeminarFilePreviewMode {
  const type = (contentType || '').toLowerCase()
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  if (type.startsWith('image/') || ['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) {
    return 'image'
  }
  if (type === 'application/pdf' || ext === 'pdf') {
    return 'pdf'
  }
  if (
    type.startsWith('text/') ||
    type === 'application/json' ||
    ['txt', 'md', 'markdown', 'csv', 'json', 'log'].includes(ext)
  ) {
    return 'text'
  }
  if (
    OFFICE_EXTS.has(ext) ||
    type.includes('officedocument') ||
    type.includes('msword') ||
    type.includes('ms-powerpoint') ||
    type.includes('ms-excel')
  ) {
    return 'office'
  }
  return 'unsupported'
}

export async function fetchSeminarBackgroundPreviewPdf(
  sessionId: string,
  fileId: string
): Promise<Uint8Array> {
  const response = await apiGet(
    `/api/mindmate/seminar/background-files/${encodeURIComponent(fileId)}/preview?session_id=${encodeURIComponent(sessionId)}`
  )
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(parseApiErrorDetail(payload, response.statusText || 'preview_failed'))
  }
  return new Uint8Array(await response.arrayBuffer())
}
