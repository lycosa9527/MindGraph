/**
 * Workshop org members store avatar as either an image URL or a single emoji / glyph.
 */

export type WorkshopAvatarDisplay =
  | { kind: 'image'; src: string }
  | { kind: 'emoji'; text: string }
  | { kind: 'initials' }

const IMAGE_EXT_RE = /\.(png|jpe?g|gif|webp|svg|ico)(\?|#|$)/i

export function resolveWorkshopAvatarDisplay(
  avatar: string | null | undefined,
): WorkshopAvatarDisplay {
  const raw = avatar?.trim()
  if (!raw) {
    return { kind: 'initials' }
  }
  if (raw.startsWith('avatar_')) {
    return { kind: 'initials' }
  }
  const lower = raw.toLowerCase()
  if (
    lower.startsWith('http://')
    || lower.startsWith('https://')
    || lower.startsWith('//')
    || lower.startsWith('data:')
  ) {
    const src = raw.startsWith('//') ? `https:${raw}` : raw
    return { kind: 'image', src }
  }
  if (raw.startsWith('/') && IMAGE_EXT_RE.test(raw)) {
    return { kind: 'image', src: raw }
  }
  if (
    raw.startsWith('/static/')
    || raw.startsWith('/uploads/')
    || raw.startsWith('/api/')
  ) {
    return { kind: 'image', src: raw }
  }
  return { kind: 'emoji', text: raw }
}
