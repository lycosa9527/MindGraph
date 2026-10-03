/**
 * User avatar emoji resolution for cross-browser display (esp. Windows Edge).
 * Emoji values stay emoji. Photo values are https URLs loaded from COS.
 */

/** MindGraph brand default — black cat (ZWJ composite). */
export const DEFAULT_USER_AVATAR_EMOJI = '🐈‍⬛'

const ZWJ = '\u200d'
const LEGACY_AVATAR_PREFIX = 'avatar_'

const IMAGE_URL = /^https?:\/\//i

export type UserAvatarDisplay = { kind: 'image'; src: string } | { kind: 'emoji'; text: string }

/** Deployed hosts load COS photos. Local Vite keeps the emoji. */
export function photoAvatarsEnabled(): boolean {
  return !import.meta.env.DEV
}

/**
 * COS photo URL, or empty when the value is an emoji or photo avatars are off.
 * Pass `photosEnabled` in tests. The app default follows local Vite vs a build.
 */
export function userAvatarImageSrc(
  raw: string | null | undefined,
  photosEnabled: boolean = photoAvatarsEnabled()
): string {
  if (!photosEnabled) {
    return ''
  }
  const trimmed = raw?.trim() ?? ''
  return IMAGE_URL.test(trimmed) ? trimmed : ''
}

/**
 * Photo URLs render as images. Everything else stays an emoji, including the
 * brand cat for empty and legacy `avatar_*` values.
 */
export function resolveUserAvatarDisplay(raw: string | null | undefined): UserAvatarDisplay {
  const src = userAvatarImageSrc(raw)
  if (src) {
    return { kind: 'image', src }
  }
  return { kind: 'emoji', text: resolveUserAvatarEmoji(raw) }
}

/**
 * Return the emoji to show for a stored user avatar value.
 * Empty, legacy `avatar_*`, and photo URLs resolve to the brand black cat.
 * Other ZWJ picker choices use the leading emoji for Edge safety.
 */
export function resolveUserAvatarEmoji(raw: string | null | undefined): string {
  const trimmed = raw?.trim()
  if (!trimmed || trimmed.startsWith(LEGACY_AVATAR_PREFIX) || IMAGE_URL.test(trimmed)) {
    return DEFAULT_USER_AVATAR_EMOJI
  }
  return edgeSafeEmojiDisplay(trimmed)
}

/**
 * ZWJ composites from the picker can show only the trailing glyph on Edge.
 * The brand black cat is kept intact and relies on `.mg-user-avatar-emoji`.
 */
function edgeSafeEmojiDisplay(emoji: string): string {
  if (!emoji.includes(ZWJ)) {
    return emoji
  }
  if (emoji === DEFAULT_USER_AVATAR_EMOJI) {
    return DEFAULT_USER_AVATAR_EMOJI
  }
  const firstSegment = emoji.split(ZWJ)[0]?.trim()
  if (!firstSegment) {
    return DEFAULT_USER_AVATAR_EMOJI
  }
  return firstSegment
}
