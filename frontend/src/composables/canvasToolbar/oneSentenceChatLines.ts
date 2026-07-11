/**
 * Rotating one-sentence chat lines (welcome / generating / generate-done).
 */
import {
  poolGenerateDone,
  poolGenerating,
  poolWelcome,
  resolveOneSentenceChatLocale,
  type OneSentenceChatLocale,
} from '@/composables/canvasToolbar/oneSentenceChatPools'

const lastPicked = new Map<string, string>()

function pickFromPool(poolKey: string, lines: readonly string[]): string {
  if (lines.length === 0) {
    return ''
  }
  if (lines.length === 1) {
    return lines[0]
  }
  const previous = lastPicked.get(poolKey)
  const choices = previous ? lines.filter((line) => line !== previous) : [...lines]
  const pool = choices.length > 0 ? choices : lines
  const index = Math.floor(Math.random() * pool.length)
  const picked = pool[Math.max(0, Math.min(index, pool.length - 1))]
  lastPicked.set(poolKey, picked)
  return picked
}

function localeFromLanguage(language?: string): OneSentenceChatLocale {
  return resolveOneSentenceChatLocale(language || 'zh')
}

export function pickOneSentenceWelcome(language?: string): string {
  const locale = localeFromLanguage(language)
  return pickFromPool(`welcome:${locale}`, poolWelcome(locale))
}

export function pickOneSentenceGenerateDone(language?: string): string {
  const locale = localeFromLanguage(language)
  return pickFromPool(`generateDone:${locale}`, poolGenerateDone(locale))
}

export function pickOneSentenceGenerating(language?: string): string {
  const locale = localeFromLanguage(language)
  return pickFromPool(`generating:${locale}`, poolGenerating(locale))
}

/** Exported for tests. */
export const ONE_SENTENCE_WELCOME_MIN_COUNT = 50
