/**
 * MindMate composer paperclip: images plus Word .doc / .docx.
 * Broader Dify types stay behind programmatic `allowDocuments` (Showcase).
 */
import type { MindMateFile } from '@/stores/mindmateActiveThread'

export const MINDMATE_COMPOSER_FILE_ACCEPT =
  'image/*,.doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document'

const WORD_EXTENSIONS = new Set(['doc', 'docx'])

const WORD_MIME_TYPES = new Set([
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
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

export function isMindmateComposerUploadableFile(file: Pick<File, 'name' | 'type'>): boolean {
  return file.type.startsWith('image/') || isMindmateComposerWordFile(file)
}

export function mindMateFileTypeFromMimeAndName(
  mimeType: string,
  filename = ''
): MindMateFile['type'] {
  if (mimeType.startsWith('image/')) {
    return 'image'
  }
  if (mimeType.startsWith('audio/')) {
    return 'audio'
  }
  if (mimeType.startsWith('video/')) {
    return 'video'
  }
  const mime = mimeType.toLowerCase()
  if (
    mime.includes('pdf') ||
    mime.includes('document') ||
    mime.includes('msword') ||
    mime.includes('text') ||
    mime.includes('spreadsheet') ||
    mime.includes('presentation') ||
    mime.includes('ms-excel') ||
    mime.includes('ms-powerpoint') ||
    WORD_EXTENSIONS.has(fileExtensionFromName(filename))
  ) {
    return 'document'
  }
  return 'custom'
}
