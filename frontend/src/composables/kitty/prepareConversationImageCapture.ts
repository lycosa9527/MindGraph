/**
 * Shared type/size gate for Kitty conversation image upload (desktop + mobile).
 */
import { CONVERSATION_IMAGE_MAX_UPLOAD_BYTES } from '@/config/conversationImageApi'

const ALLOWED_IMAGE_TYPES = new Set(['image/jpeg', 'image/jpg', 'image/png', 'image/webp'])
const ALLOWED_IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.webp'])

export type ConversationImageCaptureResult =
  | { ok: true; file: File }
  | { ok: false; reason: 'no_file' | 'invalid_type' | 'too_large' }

function extensionOf(fileName: string): string {
  const i = fileName.lastIndexOf('.')
  return i >= 0 ? fileName.slice(i).toLowerCase() : ''
}

/**
 * Validate a photo before POST /api/kitty/conversation_image.
 */
export function prepareConversationImageCapture(
  file: File | null | undefined
): ConversationImageCaptureResult {
  if (!file) {
    return { ok: false, reason: 'no_file' }
  }
  const mime = (file.type || '').toLowerCase()
  const ext = extensionOf(file.name)
  const typeOk = ALLOWED_IMAGE_TYPES.has(mime) || ALLOWED_IMAGE_EXTENSIONS.has(ext)
  if (!typeOk) {
    return { ok: false, reason: 'invalid_type' }
  }
  if (file.size > CONVERSATION_IMAGE_MAX_UPLOAD_BYTES) {
    return { ok: false, reason: 'too_large' }
  }
  return { ok: true, file }
}
