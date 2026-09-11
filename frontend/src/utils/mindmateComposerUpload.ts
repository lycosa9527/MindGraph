/**
 * MindMate composer paperclip: images plus Word, PDF, and PowerPoint.
 * Broader Dify types stay behind programmatic `allowDocuments` (Showcase).
 *
 * Chat `files[].type` must match ``services/dify/file_upload_types.py`` /
 * Dify ``file_factory._standardize_file_type`` (extension first, then MIME).
 */
import type { MindMateFile } from '@/stores/mindmateActiveThread'

const MB = 1024 * 1024

const DIFY_IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp', 'gif', 'svg'])
const DIFY_VIDEO_EXTENSIONS = new Set(['mp4', 'mov', 'mpeg', 'webm'])
const DIFY_AUDIO_EXTENSIONS = new Set(['mp3', 'm4a', 'wav', 'amr', 'mpga'])
const DIFY_DOCUMENT_EXTENSIONS = new Set([
  'txt',
  'markdown',
  'md',
  'mdx',
  'pdf',
  'html',
  'htm',
  'xlsx',
  'xls',
  'vtt',
  'properties',
  'doc',
  'docx',
  'csv',
  'eml',
  'msg',
  'ppt',
  'pptx',
  'xml',
  'epub',
  'odt',
])
const DIFY_GATEWAY_EXTRA_EXTENSIONS = new Set(['aac', 'mpg'])

export const DIFY_GATEWAY_UPLOAD_EXTENSIONS = new Set([
  ...DIFY_IMAGE_EXTENSIONS,
  ...DIFY_VIDEO_EXTENSIONS,
  ...DIFY_AUDIO_EXTENSIONS,
  ...DIFY_DOCUMENT_EXTENSIONS,
  ...DIFY_GATEWAY_EXTRA_EXTENSIONS,
])

const DIFY_CHAT_FILE_TYPES = new Set<MindMateFile['type']>([
  'image',
  'document',
  'audio',
  'video',
  'custom',
])

export const MINDMATE_COMPOSER_FILE_ACCEPT = [
  'image/*',
  '.doc',
  '.docx',
  '.pdf',
  '.ppt',
  '.pptx',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/pdf',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
].join(',')

const WORD_EXTENSIONS = new Set(['doc', 'docx'])
const COMPOSER_DOCUMENT_EXTENSIONS = new Set(['doc', 'docx', 'pdf', 'ppt', 'pptx'])

const WORD_MIME_TYPES = new Set([
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])

const COMPOSER_DOCUMENT_MIME_TYPES = new Set([
  ...WORD_MIME_TYPES,
  'application/pdf',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
])

export function fileExtensionFromName(filename: string): string {
  const trimmed = filename.trim()
  const dot = trimmed.lastIndexOf('.')
  if (dot <= 0 || dot === trimmed.length - 1) {
    return ''
  }
  return trimmed.slice(dot + 1).toLowerCase()
}

export function isMindmateComposerWordFile(file: Pick<File, 'name' | 'type'>): boolean {
  if (WORD_EXTENSIONS.has(fileExtensionFromName(file.name))) {
    return true
  }
  return WORD_MIME_TYPES.has(file.type.toLowerCase())
}

export function isMindmateComposerDocumentFile(file: Pick<File, 'name' | 'type'>): boolean {
  if (COMPOSER_DOCUMENT_EXTENSIONS.has(fileExtensionFromName(file.name))) {
    return true
  }
  return COMPOSER_DOCUMENT_MIME_TYPES.has(file.type.toLowerCase())
}

export function isMindmateComposerImageFile(file: Pick<File, 'name' | 'type'>): boolean {
  if (DIFY_IMAGE_EXTENSIONS.has(fileExtensionFromName(file.name))) {
    return true
  }
  return file.type.toLowerCase().startsWith('image/')
}

export function isMindmateComposerUploadableFile(file: Pick<File, 'name' | 'type'>): boolean {
  return isMindmateComposerImageFile(file) || isMindmateComposerDocumentFile(file)
}

export function isDifyGatewayUploadableFile(file: Pick<File, 'name' | 'type'>): boolean {
  const ext = fileExtensionFromName(file.name)
  if (DIFY_GATEWAY_UPLOAD_EXTENSIONS.has(ext)) {
    return true
  }
  const mime = file.type.toLowerCase()
  return mime.startsWith('image/') || mime.startsWith('audio/') || mime.startsWith('video/')
}

export function difyUploadMaxBytes(filename: string): number {
  const ext = fileExtensionFromName(filename)
  if (DIFY_IMAGE_EXTENSIONS.has(ext)) {
    return 10 * MB
  }
  if (DIFY_VIDEO_EXTENSIONS.has(ext)) {
    return 100 * MB
  }
  if (DIFY_AUDIO_EXTENSIONS.has(ext)) {
    return 50 * MB
  }
  return 15 * MB
}

export function parseDifyUploadErrorDetail(payload: unknown): string {
  if (!payload || typeof payload !== 'object' || !('detail' in payload)) {
    return 'Upload failed'
  }
  const detail = (payload as { detail: unknown }).detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    if (first && typeof first === 'object' && 'msg' in first) {
      const msg = (first as { msg: unknown }).msg
      if (typeof msg === 'string' && msg.trim()) {
        return msg
      }
    }
  }
  return 'Upload failed'
}

/**
 * Dify chat-messages ``files[].type``. Extension first, then MIME
 * (image / video / audio / text|pdf → document).
 */
export function mindMateFileTypeFromMimeAndName(
  mimeType: string,
  filename = ''
): MindMateFile['type'] {
  const ext = fileExtensionFromName(filename)
  if (DIFY_IMAGE_EXTENSIONS.has(ext)) {
    return 'image'
  }
  if (DIFY_VIDEO_EXTENSIONS.has(ext)) {
    return 'video'
  }
  if (DIFY_AUDIO_EXTENSIONS.has(ext)) {
    return 'audio'
  }
  if (DIFY_DOCUMENT_EXTENSIONS.has(ext)) {
    return 'document'
  }
  const mime = mimeType.toLowerCase()
  if (mime.includes('image')) {
    return 'image'
  }
  if (mime.includes('video')) {
    return 'video'
  }
  if (mime.includes('audio')) {
    return 'audio'
  }
  if (mime.includes('text') || mime.includes('pdf')) {
    return 'document'
  }
  return 'custom'
}

export function resolveDifyChatFileType(
  apiType: unknown,
  mimeType: string,
  filename: string
): MindMateFile['type'] {
  if (typeof apiType === 'string') {
    const normalized = apiType.toLowerCase() as MindMateFile['type']
    if (DIFY_CHAT_FILE_TYPES.has(normalized)) {
      return normalized
    }
  }
  return mindMateFileTypeFromMimeAndName(mimeType, filename)
}
