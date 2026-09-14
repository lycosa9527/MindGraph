/**
 * Shared collab palette: user colors and emoji pens for workshop avatars.
 *
 * This is the frontend mirror of ``services/online_collab/common/collab_palette.py`` —
 * the two lists must stay in sync so that a user sees the same color/emoji in
 * the rail and on every peer's screen. See ``tests/test_collab_palette_sync.py``
 * for the CI parity check.
 */

export const USER_COLORS: readonly string[] = Object.freeze([
  '#FF6B6B',
  '#4ECDC4',
  '#45B7D1',
  '#FFA07A',
  '#98D8C8',
  '#F7DC6F',
  '#BB8FCE',
  '#85C1E2',
  '#E11D48',
  '#F59E0B',
  '#65A30D',
  '#059669',
  '#0284C7',
  '#4F46E5',
  '#C026D3',
  '#DB2777',
  '#EA580C',
  '#0D9488',
  '#7C3AED',
  '#2563EB',
])

export const USER_EMOJIS: readonly string[] = Object.freeze([
  '\u270F\uFE0F',
  '\uD83D\uDD8A\uFE0F',
  '\u2712\uFE0F',
  '\uD83D\uDD8B\uFE0F',
  '\uD83D\uDCDD',
  '\u270D\uFE0F',
  '\uD83D\uDD8D\uFE0F',
  '\uD83D\uDD8C\uFE0F',
  '\uD83D\uDCCE',
  '\uD83D\uDCD0',
  '\uD83D\uDCCF',
  '\uD83D\uDCCC',
  '\uD83D\uDCCD',
  '\uD83D\uDD16',
  '\u2702\uFE0F',
  '\u2B50',
  '\uD83C\uDF40',
  '\uD83C\uDFB5',
  '\uD83C\uDFAF',
  '\uD83D\uDD2E',
])

export function colorForUser(userId: number): string {
  const idx = Number.isFinite(userId) ? Math.abs(userId) % USER_COLORS.length : 0
  return USER_COLORS[idx]
}

export function emojiForUser(userId: number): string {
  const idx = Number.isFinite(userId) ? Math.abs(userId) % USER_EMOJIS.length : 0
  return USER_EMOJIS[idx]
}

/** Lock-ring / sticker color: session assignment, else deterministic palette. */
export function lockRingColorForUser(userId: number, assignedColor?: string | null): string {
  const trimmed = assignedColor?.trim()
  if (trimmed) {
    return trimmed
  }
  return colorForUser(userId)
}
