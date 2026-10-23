/**
 * Surname glyph + color tone for MindMate seminar participant avatars.
 *
 * Chinese display names use the first CJK character (姓).
 * Latin names use the first letter of the last token.
 */

export interface SeminarAvatarTone {
  background: string
  color: string
}

const SEMINAR_AVATAR_TONES: readonly SeminarAvatarTone[] = [
  { background: '#5B8DEF', color: '#ffffff' },
  { background: '#34B27B', color: '#ffffff' },
  { background: '#F472B6', color: '#ffffff' },
  { background: '#FB923C', color: '#ffffff' },
  { background: '#8B7CF7', color: '#ffffff' },
]

export function seminarAvatarSurname(name: string | null | undefined): string {
  const trimmed = (name ?? '').trim()
  if (!trimmed) {
    return '?'
  }
  const cjkMatch = trimmed.match(/[\u3400-\u9fff\uf900-\ufaff]/)
  if (cjkMatch) {
    return cjkMatch[0]
  }
  const parts = trimmed.split(/\s+/).filter((part) => part.length > 0)
  const token = (parts.length >= 2 ? parts[parts.length - 1] : parts[0]) || ''
  const letter = token.charAt(0)
  return letter ? letter.toUpperCase() : '?'
}

/** Stable pastel/solid tone keyed by user id or display name. */
export function seminarAvatarTone(seed: string | number | null | undefined): SeminarAvatarTone {
  const fallback = SEMINAR_AVATAR_TONES[0] ?? {
    background: '#5B8DEF',
    color: '#ffffff',
  }
  const raw = String(seed ?? '').trim()
  if (!raw) {
    return fallback
  }
  let hash = 0
  for (let i = 0; i < raw.length; i += 1) {
    hash = (hash * 31 + raw.charCodeAt(i)) >>> 0
  }
  return SEMINAR_AVATAR_TONES[hash % SEMINAR_AVATAR_TONES.length] ?? fallback
}
