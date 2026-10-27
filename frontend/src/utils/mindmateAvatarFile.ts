/**
 * Client checks for a school MindMate avatar, matching the desktop upload rules.
 */

const MAX_AVATAR_BYTES = 1024 * 1024

const ALLOWED_AVATAR_MIME = new Set([
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/gif',
  'image/webp',
])

export function mindmateAvatarFileErrorKey(file: File): string | null {
  const mime = (file.type || '').toLowerCase()
  if (!ALLOWED_AVATAR_MIME.has(mime)) {
    return 'admin.schoolMindmateAvatarErrorType'
  }
  if (file.size > MAX_AVATAR_BYTES) {
    return 'admin.schoolMindmateAvatarErrorTooLarge'
  }
  if (file.size < 1) {
    return 'admin.schoolMindmateAvatarErrorInvalid'
  }
  return null
}

export function mindmateAvatarUploadErrorKey(detail: string | null | undefined): string {
  const token = (detail ?? '').trim()
  if (token === 'mindmate_avatar_too_large') {
    return 'admin.schoolMindmateAvatarErrorTooLarge'
  }
  if (token === 'mindmate_avatar_unsupported_type') {
    return 'admin.schoolMindmateAvatarErrorType'
  }
  if (token === 'mindmate_avatar_invalid_image') {
    return 'admin.schoolMindmateAvatarErrorInvalid'
  }
  if (token === 'mindmate_avatar_too_small') {
    return 'admin.schoolMindmateAvatarErrorTooSmall'
  }
  if (token === 'mindmate_avatar_gif_too_many_frames') {
    return 'admin.schoolMindmateAvatarErrorGifTooManyFrames'
  }
  if (token) {
    return ''
  }
  return 'admin.schoolMindmateAvatarUploadFailed'
}
