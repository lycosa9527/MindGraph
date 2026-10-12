/**
 * Simplified/traditional glyph map from OpenCC's character table (~32 KB).
 * `import { Converter } from 'opencc-js'` also pulls the phrase dictionaries
 * (~1 MB) into the startup chunk. Glyph checks only need this table.
 */
import stCharacters from 'opencc-js/dict/STCharacters'

const SIMPLIFIED_TO_TRADITIONAL = new Map<string, string>()

for (const entry of stCharacters.split('|')) {
  const space = entry.indexOf(' ')
  if (space <= 0) {
    continue
  }
  const source = entry.slice(0, space)
  const target = entry.slice(space + 1)
  if (source.length > 0 && target.length > 0 && source !== target) {
    SIMPLIFIED_TO_TRADITIONAL.set(source, target)
  }
}

/** True when `text` contains a simplified glyph from the OpenCC character table. */
export function textHasSimplifiedChinese(text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) {
    return false
  }
  for (const char of trimmed) {
    if (SIMPLIFIED_TO_TRADITIONAL.has(char)) {
      return true
    }
  }
  return false
}

/** Character-level simplified → traditional. Shared glyphs are left unchanged. */
export function toTraditionalChinese(text: string): string {
  if (!text) {
    return text
  }
  let converted = ''
  for (const char of text) {
    converted += SIMPLIFIED_TO_TRADITIONAL.get(char) ?? char
  }
  return converted
}
