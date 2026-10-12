import { describe, expect, it } from 'vitest'

import {
  LIVE_TRANSLATE_LANGUAGES,
  canvasTranslateTargetForUiLocale,
} from '@/utils/translateLanguages'

/** DashScope qwen3.8-livetranslate-flash-realtime target codes, doc order. */
const QWEN38_LIVE_TRANSLATE_CODES = [
  'zh',
  'en',
  'ar',
  'de',
  'fr',
  'es',
  'pt',
  'id',
  'it',
  'ko',
  'ru',
  'th',
  'vi',
  'ja',
  'tr',
  'hi',
  'ms',
  'nl',
  'ur',
  'nb',
  'sv',
  'da',
  'he',
  'fi',
  'pl',
  'is',
  'cs',
  'fil',
  'fa',
  'yue',
  'el',
  'af',
  'ast',
  'be',
  'bg',
  'bn',
  'bs',
  'ca',
  'ceb',
  'et',
  'gl',
  'gu',
  'hr',
  'hu',
  'jv',
  'kk',
  'kn',
  'ky',
  'lv',
  'mk',
  'ml',
  'mr',
  'pa',
  'ro',
  'sk',
  'sl',
  'sw',
  'tg',
  'az',
  'uk',
]

describe('LIVE_TRANSLATE_LANGUAGES', () => {
  it('lists every qwen3.8 live-translate target once', () => {
    const codes = LIVE_TRANSLATE_LANGUAGES.map((entry) => entry.code)
    expect(codes).toHaveLength(60)
    expect(new Set(codes)).toEqual(new Set(QWEN38_LIVE_TRANSLATE_CODES))
  })
})

describe('canvasTranslateTargetForUiLocale', () => {
  it('keeps diagram translation on the original allowlist', () => {
    expect(canvasTranslateTargetForUiLocale('pl')).toBe('en')
    expect(canvasTranslateTargetForUiLocale('zh-tw')).toBe('zh')
    expect(canvasTranslateTargetForUiLocale('fr-FR')).toBe('fr')
  })
})
