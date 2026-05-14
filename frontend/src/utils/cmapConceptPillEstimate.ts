/**
 * Heuristic pillar sizes for cmap-import layout overlap checks.
 * Aligns loosely with ConceptNode min sizes and max-inline-width caps (~480 branch / ~560 topic)
 * without reading `vw` (import happens off-DOM).
 */
export type ConceptMapPillFootprintPx = Readonly<{ halfWidth: number; halfHeight: number }>

export type ConceptMapPillEstimateRole = 'topic' | 'branch'

/** Min inner pill widths from ConceptNode styles (concept vs topic). */
const BRANCH_MIN_HALF_W = 40
const TOPIC_MIN_HALF_W = 60
const BRANCH_MIN_HALF_H = 18
const TOPIC_MIN_HALF_H = 24

/** Mirrors max-width caps approximated as px (omit vw). Half of nominal max. */
const BRANCH_HALF_W_CAP = 240
const TOPIC_HALF_W_CAP = 280

const LETTER_LATIN_APPROX_PX = 8.75
const LETTER_CJK_APPROX_PX = 15.75
const HORIZONTAL_PADDING_APPROX_BRANCH = 40
const HORIZONTAL_PADDING_APPROX_TOPIC = 56

function hasHanScript(label: string): boolean {
  return /\p{Script=Han}/u.test(label)
}

function graphemeCount(label: string): number {
  try {
    if (typeof Intl !== 'undefined') {
      const Seg = (
        Intl as unknown as {
          Segmenter?: new (
            locales?: Intl.LocalesArgument,
            options?: { granularity: string }
          ) => {
            segment: (input: string) => Iterable<{ segment: string }>
          }
        }
      ).Segmenter
      if (typeof Seg === 'function') {
        const seg = new Seg('und', { granularity: 'grapheme' })
        let count = 0
        for (const _ of seg.segment(label)) count += 1
        return Math.max(count, 1)
      }
    }
  } catch {
    /* Segmenter unsupported in test env etc. — fall through */
  }
  const codePoints = [...label].length || label.length || 1
  return Math.max(codePoints, 1)
}

/**
 * Estimated half extents (pixels) used when scaling IHMC positions before measure.
 */

export function estimateConceptMapPillFootprintPx(
  label: string,
  role: ConceptMapPillEstimateRole
): ConceptMapPillFootprintPx {
  const capHalfW = role === 'topic' ? TOPIC_HALF_W_CAP : BRANCH_HALF_W_CAP
  const minHalfW = role === 'topic' ? TOPIC_MIN_HALF_W : BRANCH_MIN_HALF_W
  const minHalfH = role === 'topic' ? TOPIC_MIN_HALF_H : BRANCH_MIN_HALF_H
  const pad = role === 'topic' ? HORIZONTAL_PADDING_APPROX_TOPIC : HORIZONTAL_PADDING_APPROX_BRANCH
  const letter = hasHanScript(label) ? LETTER_CJK_APPROX_PX : LETTER_LATIN_APPROX_PX
  const glyphs = graphemeCount(label.trim() || '?')
  const textHalf = Math.min(capHalfW, (glyphs * letter + pad) / 2)
  const halfWidth = Math.min(capHalfW, Math.max(minHalfW, textHalf))

  const lineBreakPenalty = /\n|\\n/.test(label) ? minHalfH * 0.45 : 0
  const halfHeight = Math.min(
    42,
    Math.max(minHalfH, Math.round(minHalfH + lineBreakPenalty + Math.min(glyphs, 56) / 52))
  )

  return { halfWidth, halfHeight }
}
