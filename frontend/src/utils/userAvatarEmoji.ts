/**
 * User avatar emoji resolution for cross-browser display (esp. Windows Edge).
 * Avatars are stored as emoji strings; ZWJ composites and missing emoji fonts
 * can render as black boxes without normalization and an emoji font stack.
 */

/** MindGraph brand default — black cat (ZWJ composite). */
export const DEFAULT_USER_AVATAR_EMOJI = '🐈‍⬛'

const ZWJ = '\u200d'
const LEGACY_AVATAR_PREFIX = 'avatar_'

/**
 * Return the emoji to show for a stored user avatar value.
 * Empty and legacy `avatar_*` resolve to the brand black cat.
 * Other ZWJ picker choices use the leading emoji for Edge safety.
 */
export function resolveUserAvatarEmoji(raw: string | null | undefined): string {
  const trimmed = raw?.trim()
  if (!trimmed || trimmed.startsWith(LEGACY_AVATAR_PREFIX)) {
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
