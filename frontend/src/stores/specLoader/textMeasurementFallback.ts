/**
 * Non-DOM text width estimates (SSR, tests, zero-width fallbacks).
 * Per-code-point em-width factors approximate mixed-script labels without font metrics.
 *
 * Keep em-width rules aligned with `utils/text_width_estimate.py` (`_EM_RANGE_TABLE`).
 */

function emWidthForCodePoint(codePoint: number): number {
  if (codePoint <= 0x20) {
    return codePoint === 0x20 ? 0.28 : 0
  }
  if (codePoint >= 0x300 && codePoint <= 0x36f) return 0
  if (codePoint >= 0x1ab0 && codePoint <= 0x1aff) return 0
  if (codePoint >= 0x1dc0 && codePoint <= 0x1dff) return 0
  if (codePoint >= 0x20d0 && codePoint <= 0x20ff) return 0
  if (codePoint >= 0xfe00 && codePoint <= 0xfe0f) return 0
  if (codePoint >= 0x4e00 && codePoint <= 0x9fff) return 1.0
  if (codePoint >= 0x3400 && codePoint <= 0x4dbf) return 1.0
  if (codePoint >= 0xf900 && codePoint <= 0xfaff) return 1.0
  if (codePoint >= 0x20000 && codePoint <= 0x2ceaf) return 1.0
  if (codePoint >= 0x3040 && codePoint <= 0x309f) return 0.95
  if (codePoint >= 0x30a0 && codePoint <= 0x30ff) return 0.95
  if (codePoint >= 0x31f0 && codePoint <= 0x31ff) return 0.95
  if (codePoint >= 0xac00 && codePoint <= 0xd7af) return 0.95
  if (codePoint >= 0x1100 && codePoint <= 0x11ff) return 0.95
  if (codePoint >= 0x3130 && codePoint <= 0x318f) return 0.95
  if (codePoint >= 0x0600 && codePoint <= 0x06ff) return 0.5
  if (codePoint >= 0x0750 && codePoint <= 0x077f) return 0.5
  if (codePoint >= 0x08a0 && codePoint <= 0x08ff) return 0.5
  if (codePoint >= 0xfb50 && codePoint <= 0xfdff) return 0.5
  if (codePoint >= 0xfe70 && codePoint <= 0xfeff) return 0.5
  if (codePoint >= 0x0590 && codePoint <= 0x05ff) return 0.52
  if (codePoint >= 0x0e00 && codePoint <= 0x0e7f) return 0.55
  if (codePoint >= 0x0900 && codePoint <= 0x097f) return 0.58
  if (codePoint >= 0x0980 && codePoint <= 0x09ff) return 0.58
  if (codePoint >= 0x0a00 && codePoint <= 0x0a7f) return 0.58
  if (codePoint >= 0x0a80 && codePoint <= 0x0aff) return 0.58
  if (codePoint >= 0x0b00 && codePoint <= 0x0b7f) return 0.58
  if (codePoint >= 0x0b80 && codePoint <= 0x0bff) return 0.58
  if (codePoint >= 0x0c00 && codePoint <= 0x0c7f) return 0.58
  if (codePoint >= 0x0c80 && codePoint <= 0x0cff) return 0.58
  if (codePoint >= 0x0d00 && codePoint <= 0x0d7f) return 0.58
  if (codePoint >= 0x0d80 && codePoint <= 0x0dff) return 0.58
  if (codePoint >= 0x0e80 && codePoint <= 0x0eff) return 0.55
  if (codePoint >= 0x0f00 && codePoint <= 0x0fff) return 0.55
  if (codePoint >= 0x1000 && codePoint <= 0x109f) return 0.55
  if (codePoint >= 0x1780 && codePoint <= 0x17ff) return 0.55
  if (codePoint >= 0x10a0 && codePoint <= 0x10ff) return 0.52
  if (codePoint >= 0x2d80 && codePoint <= 0x2ddf) return 0.55
  if (codePoint >= 0xa000 && codePoint <= 0xa48f) return 0.95
  if (codePoint >= 0x4dc0 && codePoint <= 0x4dff) return 1.0
  if (codePoint >= 0xff01 && codePoint <= 0xff5e) return 0.55
  if (codePoint >= 0xff10 && codePoint <= 0xff19) return 0.55
  if (codePoint >= 0x30 && codePoint <= 0x39) return 0.55
  if (codePoint >= 0x41 && codePoint <= 0x5a) return 0.58
  if (codePoint >= 0x61 && codePoint <= 0x7a) return 0.55
  if (codePoint >= 0xc0 && codePoint <= 0x24f) return 0.55
  if (codePoint >= 0x370 && codePoint <= 0x3ff) return 0.55
  if (codePoint >= 0x400 && codePoint <= 0x4ff) return 0.58
  if (codePoint >= 0x500 && codePoint <= 0x52f) return 0.58
  if (codePoint >= 0x1e00 && codePoint <= 0x1eff) return 0.55
  if (codePoint >= 0x2c60 && codePoint <= 0x2c7f) return 0.55
  return 0.62
}

/**
 * Estimated text width in px (no DOM). Bold uses a slight advance bump.
 */
export function estimateTextWidthFallbackPx(
  text: string,
  fontSize: number,
  options?: { isTopic?: boolean }
): number {
  const t = (text || '').trim() || ' '
  let em = 0
  for (const c of t) {
    const cp = c.codePointAt(0) ?? 0
    em += emWidthForCodePoint(cp)
  }
  const bold = options?.isTopic ? 1.04 : 1.0
  return Math.max(fontSize * 0.35, em * fontSize * bold)
}

const LATIN_BASELINE_EM = 0.55
const MAX_SCRIPT_SCALE = 1.5
const SOUTHEAST_ASIAN_MIN_SCALE = 1.3

function isSoutheastAsianChar(cp: number): boolean {
  if (cp >= 0x0e00 && cp <= 0x0e7f) return true
  if (cp >= 0x0e80 && cp <= 0x0eff) return true
  if (cp >= 0x1780 && cp <= 0x17ff) return true
  if (cp >= 0x1000 && cp <= 0x109f) return true
  return false
}

/**
 * Adapt maxWidth so that visually similar line lengths are produced regardless of script.
 *
 * Latin characters average ~0.55 em, CJK ~1.0 em.  A fixed 150 px maxWidth fits ~17 Latin
 * chars per line but only ~9 CJK chars.  This function scales the base width up for
 * wide-character text (capped at 1.5×) so both scripts get a comfortable column width.
 *
 * Pure Latin  → scale 1.0  (e.g. 150 → 150)
 * Pure CJK   → scale ~1.5 (e.g. 150 → 225)
 * Southeast Asian (Thai/Lao/Khmer/Myanmar) → min scale 1.3
 * Mixed      → proportional interpolation
 */
export function computeScriptAwareMaxWidth(text: string, baseMaxWidthPx: number): number {
  const t = (text || '').trim()
  if (!t.length) return baseMaxWidthPx
  let totalEm = 0
  let glyphCount = 0
  let seaCount = 0
  for (const c of t) {
    const cp = c.codePointAt(0) ?? 0
    const w = emWidthForCodePoint(cp)
    if (w > 0) {
      totalEm += w
      glyphCount++
      if (isSoutheastAsianChar(cp)) {
        seaCount++
      }
    }
  }
  if (glyphCount === 0) return baseMaxWidthPx
  const avgEm = totalEm / glyphCount
  let scale = Math.min(MAX_SCRIPT_SCALE, Math.max(1.0, avgEm / LATIN_BASELINE_EM))

  if (seaCount / glyphCount > 0.3) {
    scale = Math.max(scale, SOUTHEAST_ASIAN_MIN_SCALE)
  }

  return Math.round(baseMaxWidthPx * scale)
}
