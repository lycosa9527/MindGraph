import {
  ACRONYM,
  COMPOUND_SUFFIX,
  CONJUNCTION,
  GENERIC_NODE,
  GENERIC_OPERATION,
  GENERIC_PLACE,
  KO_PARTICLES,
  SMART_ADJECTIVE,
  STOP_WORD,
  fold,
} from '@/utils/toolbarLabelAbbreviationLexicon'

const WIDE_CHAR =
  /\p{Script=Thai}|\p{Script=Lao}|\p{Script=Myanmar}|\p{Script=Khmer}|\p{Script=Devanagari}|\p{Script=Bengali}|\p{Script=Gurmukhi}|\p{Script=Tamil}|\p{Script=Telugu}|\p{Script=Kannada}|\p{Script=Malayalam}|\p{Script=Sinhala}|\p{Script=Hangul}|\p{Script=Han}|\p{Script=Hiragana}|\p{Script=Katakana}/u

const HAN_CHAR = /[\u3400-\u9FFF]/

/**
 * Labels already this narrow stay whole. Wider ones keep a real word
 * from the phrase so the chip still names the command.
 */
const KEEP_VISUAL = 18

/** Join a short lead word with the next one when both still fit. */
const SHORT_LEAD = 8

type TextSegment = { segment: string; isWordLike?: boolean }

type TextSegmenter = {
  segment: (input: string) => Iterable<TextSegment>
}

/**
 * Intl.Segmenter is ES2022. The app tsconfig lib is ES2021, so the constructor
 * is read through the same cast used by concept-map pill estimates.
 */
function createSegmenter(
  locales: Intl.LocalesArgument | undefined,
  granularity: 'grapheme' | 'word'
): TextSegmenter | undefined {
  if (typeof Intl === 'undefined') return undefined
  const Seg = (
    Intl as unknown as {
      Segmenter?: new (
        locales?: Intl.LocalesArgument,
        options?: { granularity: string }
      ) => TextSegmenter
    }
  ).Segmenter
  if (typeof Seg !== 'function') return undefined
  return new Seg(locales, { granularity })
}

function graphemes(text: string): string[] {
  const segmenter = createSegmenter(undefined, 'grapheme')
  if (!segmenter) return [...text]
  return [...segmenter.segment(text)].map((part) => part.segment)
}

function isWide(grapheme: string): boolean {
  return WIDE_CHAR.test(grapheme)
}

function visualWidth(text: string): number {
  return graphemes(text).reduce((sum, grapheme) => sum + (isWide(grapheme) ? 2 : 1), 0)
}

function segmenterLocale(text: string): string | undefined {
  if (/[\u0E00-\u0E7F]/.test(text)) return 'th'
  if (/[\u3040-\u30FF]/.test(text)) return 'ja'
  if (/[\uAC00-\uD7AF]/.test(text)) return 'ko'
  if (/[\u0600-\u06FF]/.test(text)) return 'ar'
  if (/[\u0590-\u05FF]/.test(text)) return 'he'
  if (/[\u0900-\u097F]/.test(text)) return 'hi'
  if (/[\u0D80-\u0DFF]/.test(text)) return 'si'
  if (/[\u0B80-\u0BFF]/.test(text)) return 'ta'
  if (HAN_CHAR.test(text)) return 'zh'
  return undefined
}

function isSingleHan(word: string): boolean {
  const chars = graphemes(word)
  return chars.length === 1 && HAN_CHAR.test(chars[0] ?? '')
}

/** Undo segmenter splits such as 文 + 档 → 文档. */
function repairHanWords(words: string[]): string[] {
  const repaired: string[] = []
  let index = 0
  while (index < words.length) {
    const word = words[index] ?? ''
    const next = words[index + 1]
    if (next && isSingleHan(word) && isSingleHan(next)) {
      repaired.push(word + next)
      index += 2
    } else {
      repaired.push(word)
      index += 1
    }
  }
  return repaired
}

function stripKoreanParticle(word: string): string {
  if (!/[\uAC00-\uD7AF]/.test(word)) return word
  for (const particle of KO_PARTICLES) {
    if (!word.endsWith(particle)) continue
    const stem = word.slice(0, word.length - particle.length)
    if (graphemes(stem).length >= 2) return stem
  }
  return word
}

/** Keep hyphen and apostrophe compounds as one word (Nag-iisip, O'quv). */
function repairBoundForms(source: string, words: string[]): string[] {
  const repaired: string[] = []
  let index = 0
  while (index < words.length) {
    const word = words[index] ?? ''
    const next = words[index + 1]
    const sep = next ? boundSeparator(source, word, next) : ''
    const keepSplit = sep === '-' && (STOP_WORD.has(fold(word)) || isFunctionWord(next ?? ''))
    if (next && sep && !keepSplit) {
      repaired.push(`${word}${sep}${next}`)
      index += 2
    } else {
      repaired.push(word)
      index += 1
    }
  }
  return repaired
}

function boundSeparator(source: string, left: string, right: string): string {
  if (source.includes(`${left}-${right}`)) return '-'
  if (source.includes(`${left}'${right}`)) return "'"
  if (source.includes(`${left}’${right}`)) return '’'
  return ''
}

function contentWords(text: string): string[] {
  const segmenter = createSegmenter(segmenterLocale(text), 'word')
  if (!segmenter) return text.split(' ').filter((word) => word.length > 0)
  const words = [...segmenter.segment(text)]
    .filter((part) => part.isWordLike === true)
    .map((part) => stripKoreanParticle(part.segment))
  return repairBoundForms(text, repairHanWords(words))
}

function isFunctionWord(word: string): boolean {
  const key = fold(word)
  return (
    STOP_WORD.has(key) || GENERIC_OPERATION.has(key) || SMART_ADJECTIVE.has(key) || ACRONYM.has(key)
  )
}

function dropWhenOthersRemain(words: string[], skip: Set<string>): string[] {
  const kept = words.filter((word) => !skip.has(fold(word)))
  return kept.length > 0 ? kept : words
}

function contentPool(words: string[]): string[] {
  const withoutFunction = words.filter((word) => !isFunctionWord(word))
  const base = withoutFunction.length > 0 ? withoutFunction : words
  return dropWhenOthersRemain(dropWhenOthersRemain(base, GENERIC_NODE), GENERIC_PLACE)
}

function stemCompound(word: string): string {
  const lower = fold(word)
  for (const suffix of COMPOUND_SUFFIX) {
    if (!lower.endsWith(suffix)) continue
    const stem = word.slice(0, word.length - suffix.length).replace(/[-'’]+$/u, '')
    if (graphemes(stem).length >= 4) return stem
  }
  return word
}

function combineParts(source: string, left: string, right: string): string {
  const bound = boundSeparator(source, left, right)
  if (bound) return `${left}${bound}${right}`
  if (source.includes(`${left}${right}`)) return `${left}${right}`
  return `${left} ${right}`
}

function isConjunction(word: string, following: string | undefined): boolean {
  if (!CONJUNCTION.has(fold(word))) return false
  // Albanian "e" is "of" before a genitive (regjistrimit). Romance "e" is "and".
  if (fold(word) !== 'e' || !following) return true
  return !/(it|ve|ës)$/i.test(following)
}

function hasConjunctionBetween(words: string[], left: string, right: string): boolean {
  const start = words.indexOf(left)
  const end = words.indexOf(right, start + 1)
  if (start < 0 || end < 0) return false
  return words.slice(start + 1, end).some((word, index, between) => {
    return isConjunction(word, between[index + 1] ?? right)
  })
}

function pickPhrase(source: string, words: string[], pool: string[]): string {
  const first = pool[0] ?? source
  const next = pool[1]
  if (!next) return stemCompound(first)
  const combined = combineParts(source, first, next)
  const adjacent = boundSeparator(source, first, next) !== '' || source.includes(`${first}${next}`)
  const fits = visualWidth(combined) <= KEEP_VISUAL
  if (fits && (adjacent || visualWidth(first) <= SHORT_LEAD)) return combined
  if (hasConjunctionBetween(words, first, next) && visualWidth(next) <= KEEP_VISUAL) return next
  return first
}

/**
 * Short chip for a toolbar label when the full translation does not fit.
 * Keeps whole words from the label so the abbreviation still names the command.
 * Phrases drop articles and a leading "generate / make" verb. Hover shows the rest.
 */
export function abbreviateToolbarLabel(label: string): string {
  const text = label.trim().replace(/\s+/g, ' ')
  if (!text) return ''
  if (visualWidth(text) <= KEEP_VISUAL) return text

  const words = contentWords(text)
  if (words.length === 0) return text
  return pickPhrase(text, words, contentPool(words))
}

export function toolbarLabelGraphemeLength(label: string): number {
  return graphemes(label).length
}
