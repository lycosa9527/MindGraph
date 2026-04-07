/**
 * Maps MindGraph UI locale (`LocaleCode`) to simple-keyboard-layouts preset modules.
 * Presets without a dedicated layout fall back to English (US QWERTY).
 */
import type { KeyboardLayoutObject } from 'simple-keyboard/build/interfaces'

import type { LocaleCode } from '@/i18n/supportedUiLocales'

/** Names of `simple-keyboard-layouts/build/layouts/<name>.js` presets we load. */
export type LayoutPresetName =
  | 'arabic'
  | 'brazilian'
  | 'chinese'
  | 'english'
  | 'farsi'
  | 'french'
  | 'german'
  | 'hindi'
  | 'italian'
  | 'japanese'
  | 'korean'
  | 'polish'
  | 'russian'
  | 'spanish'
  | 'thai'
  | 'turkish'
  | 'ukrainian'

export type SimpleKeyboardLayoutModule = {
  default: {
    layout: KeyboardLayoutObject
    /** Pinyin/jamo → candidate characters map; present on zh, ko layouts. */
    layoutCandidates?: Record<string, string>
  }
}

/**
 * Per-UI-locale layout. Any `LocaleCode` omitted here uses `english`.
 * Covers INTERFACE_LANGUAGE_PICKER_CODES plus common enabled locales; unknown codes fall back in
 * {@link getLayoutPresetKeyForUiLocale}.
 */
const UI_LOCALE_TO_PRESET: Partial<Record<LocaleCode, LayoutPresetName>> = {
  'zh-tw': 'chinese',
  zh: 'chinese',
  en: 'english',
  es: 'spanish',
  az: 'english',
  th: 'thai',
  fr: 'french',
  de: 'german',
  sq: 'english',
  ja: 'japanese',
  ko: 'korean',
  pt: 'brazilian',
  ru: 'russian',
  ar: 'arabic',
  fa: 'farsi',
  uz: 'english',
  nl: 'english',
  it: 'italian',
  hi: 'hindi',
  id: 'english',
  tl: 'english',
  vi: 'english',
  tr: 'turkish',
  pl: 'polish',
  uk: 'ukrainian',
  ms: 'english',
  af: 'english',
}

export function getLayoutPresetKeyForUiLocale(code: LocaleCode): LayoutPresetName {
  return UI_LOCALE_TO_PRESET[code] ?? 'english'
}

const PRESET_LOADERS: Record<LayoutPresetName, () => Promise<SimpleKeyboardLayoutModule>> = {
  arabic: () => import('simple-keyboard-layouts/build/layouts/arabic.js'),
  brazilian: () => import('simple-keyboard-layouts/build/layouts/brazilian.js'),
  chinese: () => import('simple-keyboard-layouts/build/layouts/chinese.js'),
  english: () => import('simple-keyboard-layouts/build/layouts/english.js'),
  farsi: () => import('simple-keyboard-layouts/build/layouts/farsi.js'),
  french: () => import('simple-keyboard-layouts/build/layouts/french.js'),
  german: () => import('simple-keyboard-layouts/build/layouts/german.js'),
  hindi: () => import('simple-keyboard-layouts/build/layouts/hindi.js'),
  italian: () => import('simple-keyboard-layouts/build/layouts/italian.js'),
  japanese: () => import('simple-keyboard-layouts/build/layouts/japanese.js'),
  korean: () => import('simple-keyboard-layouts/build/layouts/korean.js'),
  polish: () => import('simple-keyboard-layouts/build/layouts/polish.js'),
  russian: () => import('simple-keyboard-layouts/build/layouts/russian.js'),
  spanish: () => import('simple-keyboard-layouts/build/layouts/spanish.js'),
  thai: () => import('simple-keyboard-layouts/build/layouts/thai.js'),
  turkish: () => import('simple-keyboard-layouts/build/layouts/turkish.js'),
  ukrainian: () => import('simple-keyboard-layouts/build/layouts/ukrainian.js'),
}

export async function loadLayoutForPreset(
  preset: LayoutPresetName
): Promise<SimpleKeyboardLayoutModule['default']> {
  const mod = await PRESET_LOADERS[preset]()
  return mod.default
}
