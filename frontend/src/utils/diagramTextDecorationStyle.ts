import type { CSSProperties } from 'vue'

/**
 * Underline and strikethrough must be set on the text element.
 * CSS does not inherit `text-decoration` into inputs, and a shorthand
 * resets thickness and offset. A 1px line with a small offset stays
 * inside the line box so a tight node does not clip it.
 */
export function diagramTextDecorationStyle(value: string | null | undefined): CSSProperties {
  const decoration = value?.trim()
  if (!decoration || decoration === 'none') {
    return { textDecoration: 'none' }
  }
  return {
    textDecorationLine: decoration,
    textDecorationThickness: '1px',
    textUnderlineOffset: '0.12em',
    textDecorationSkipInk: 'none',
  }
}
