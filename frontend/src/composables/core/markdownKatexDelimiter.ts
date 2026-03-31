/**
 * Helpers for @vscode/markdown-it-katex delimiter rules (same as microsoft/vscode-markdown-it-katex
 * isValidInlineDelim): opening `$` / `$$` must not immediately follow an ASCII letter, digit, or _.
 *
 * MathLive `\placeholder{...}` is not valid KaTeX; empty placeholders render as red errors.
 * We map empty blanks to a square (like MathLive’s placeholder box) and unwrap non-empty bodies.
 */

/** KaTeX `\square` — hollow square, closest to MathLive’s placeholder appearance. */
const KATEX_EMPTY_PLACEHOLDER = '\\square'

/**
 * Replace MathLive `\placeholder{...}` with KaTeX-safe output before markdown-it-katex runs.
 * - Empty (or whitespace-only) body → `\square` for student fill-ins (aligned with MathLive’s box).
 * - Non-empty body → unwrap (show teacher / prefilled LaTeX as normal math).
 */
export function replaceMathLivePlaceholdersForKatex(text: string): string {
  if (!text.includes('\\placeholder')) {
    return text
  }
  const token = '\\placeholder'
  let out = text
  let idx = 0
  while ((idx = out.indexOf(token, idx)) !== -1) {
    let pos = idx + token.length
    while (pos < out.length && /\s/.test(out[pos])) {
      pos += 1
    }
    if (out[pos] !== '{') {
      idx += token.length
      continue
    }
    let depth = 1
    const start = pos + 1
    let i = start
    while (i < out.length && depth > 0) {
      const c = out[i]
      if (c === '{') {
        depth += 1
      } else if (c === '}') {
        depth -= 1
      }
      i += 1
    }
    if (depth !== 0) {
      idx += token.length
      continue
    }
    const inner = out.slice(start, i - 1)
    const replacement = inner.trim() === '' ? KATEX_EMPTY_PLACEHOLDER : inner
    out = out.slice(0, idx) + replacement + out.slice(i)
    idx += replacement.length
  }
  return out
}

export function normalizeKatexDelimitersForMarkdownIt(text: string): string {
  if (!text) return text
  let s = text
  s = s.replace(/([A-Za-z0-9_])(\$\$)/g, '$1 $2')
  s = s.replace(/([A-Za-z0-9_])(\$(?!\$))/g, '$1 $2')
  return s
}

/**
 * When appending an inline math snippet (`$...$`) to text ending in ASCII letter/digit/_,
 * insert a space so markdown-it-katex parses math.
 */
export function joinLabelAndMathSnippet(prefix: string, mathSnippet: string): string {
  const gap =
    /[A-Za-z0-9_]$/.test(prefix) && mathSnippet.startsWith('$') && !prefix.endsWith(' ') ? ' ' : ''
  return prefix + gap + mathSnippet
}
