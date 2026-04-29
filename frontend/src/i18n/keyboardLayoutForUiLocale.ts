/**
 * Maps MindGraph UI locale (`LocaleCode`) to simple-keyboard-layouts preset modules.
 *
 * ## Tier-27 interface picker → virtual keyboard (same order as {@link INTERFACE_LANGUAGE_PICKER_CODES})
 *
 * | UI code | Preset | Notes |
 * |---------|--------|--------|
 * | zh-tw | chinese | Pinyin row + candidates |
 * | zh | chinese | Same |
 * | en | english | US QWERTY |
 * | es | spanish | |
 * | az | turkish | Closest Latin-Turkic in pack (no AZ) |
 * | th | thai | |
 * | fr | french | AZERTY |
 * | de | german | QWERTZ |
 * | sq | english | No Albanian layout in pack |
 * | ja | japanese | Kana rows |
 * | ko | korean | Jamo + candidates |
 * | pt | brazilian | ABNT-style (only PT preset in pack; QWERTY + ç, ´) |
 * | ru | russian | |
 * | ar | arabic | |
 * | fa | farsi | |
 * | uz | english | Latin Uzbek; uyghur preset is Arabic script |
 * | nl | english | NL uses US-style QWERTY; no NL pack layout |
 * | it | italian | |
 * | hi | hindi | Devanagari |
 * | id | english | Latin / QWERTY |
 * | tl | english | Latin / QWERTY |
 * | vi | english | No Telex/VNI in pack |
 * | tr | turkish | |
 * | pl | polish | |
 * | uk | ukrainian | |
 * | ms | english | Latin / QWERTY |
 * | af | english | Latin / QWERTY |
 *
 * All layout modules under `simple-keyboard-layouts/build/layouts/*.js` are in {@link PRESET_LOADERS}.
 */
import type { KeyboardLayoutObject } from 'simple-keyboard/build/interfaces'

import {
  INTERFACE_LANGUAGE_PICKER_CODES,
  type InterfaceLanguagePickerCode,
  isInterfaceLanguagePickerLocale,
} from '@/i18n/locales'
import type { LocaleCode } from '@/i18n/supportedUiLocales'

export type SimpleKeyboardLayoutModule = {
  default: {
    layout: KeyboardLayoutObject
    /** Pinyin/jamo → candidate characters map; present on zh, ko layouts. */
    layoutCandidates?: Record<string, string>
  }
}

const PRESET_LOADERS = {
  arabic: () => import('simple-keyboard-layouts/build/layouts/arabic.js'),
  armenianEastern: () => import('simple-keyboard-layouts/build/layouts/armenianEastern.js'),
  armenianWestern: () => import('simple-keyboard-layouts/build/layouts/armenianWestern.js'),
  assamese: () => import('simple-keyboard-layouts/build/layouts/assamese.js'),
  balochi: () => import('simple-keyboard-layouts/build/layouts/balochi.js'),
  belarusian: () => import('simple-keyboard-layouts/build/layouts/belarusian.js'),
  bengali: () => import('simple-keyboard-layouts/build/layouts/bengali.js'),
  brazilian: () => import('simple-keyboard-layouts/build/layouts/brazilian.js'),
  burmese: () => import('simple-keyboard-layouts/build/layouts/burmese.js'),
  chinese: () => import('simple-keyboard-layouts/build/layouts/chinese.js'),
  czech: () => import('simple-keyboard-layouts/build/layouts/czech.js'),
  english: () => import('simple-keyboard-layouts/build/layouts/english.js'),
  farsi: () => import('simple-keyboard-layouts/build/layouts/farsi.js'),
  french: () => import('simple-keyboard-layouts/build/layouts/french.js'),
  georgian: () => import('simple-keyboard-layouts/build/layouts/georgian.js'),
  german: () => import('simple-keyboard-layouts/build/layouts/german.js'),
  gilaki: () => import('simple-keyboard-layouts/build/layouts/gilaki.js'),
  greek: () => import('simple-keyboard-layouts/build/layouts/greek.js'),
  hebrew: () => import('simple-keyboard-layouts/build/layouts/hebrew.js'),
  hindi: () => import('simple-keyboard-layouts/build/layouts/hindi.js'),
  hungarian: () => import('simple-keyboard-layouts/build/layouts/hungarian.js'),
  italian: () => import('simple-keyboard-layouts/build/layouts/italian.js'),
  japanese: () => import('simple-keyboard-layouts/build/layouts/japanese.js'),
  kannada: () => import('simple-keyboard-layouts/build/layouts/kannada.js'),
  korean: () => import('simple-keyboard-layouts/build/layouts/korean.js'),
  kurdish: () => import('simple-keyboard-layouts/build/layouts/kurdish.js'),
  macedonian: () => import('simple-keyboard-layouts/build/layouts/macedonian.js'),
  malayalam: () => import('simple-keyboard-layouts/build/layouts/malayalam.js'),
  nigerian: () => import('simple-keyboard-layouts/build/layouts/nigerian.js'),
  nko: () => import('simple-keyboard-layouts/build/layouts/nko.js'),
  norwegian: () => import('simple-keyboard-layouts/build/layouts/norwegian.js'),
  odia: () => import('simple-keyboard-layouts/build/layouts/odia.js'),
  polish: () => import('simple-keyboard-layouts/build/layouts/polish.js'),
  punjabi: () => import('simple-keyboard-layouts/build/layouts/punjabi.js'),
  russian: () => import('simple-keyboard-layouts/build/layouts/russian.js'),
  russianOld: () => import('simple-keyboard-layouts/build/layouts/russianOld.js'),
  sindhi: () => import('simple-keyboard-layouts/build/layouts/sindhi.js'),
  spanish: () => import('simple-keyboard-layouts/build/layouts/spanish.js'),
  swedish: () => import('simple-keyboard-layouts/build/layouts/swedish.js'),
  telugu: () => import('simple-keyboard-layouts/build/layouts/telugu.js'),
  thai: () => import('simple-keyboard-layouts/build/layouts/thai.js'),
  turkish: () => import('simple-keyboard-layouts/build/layouts/turkish.js'),
  ukrainian: () => import('simple-keyboard-layouts/build/layouts/ukrainian.js'),
  urdu: () => import('simple-keyboard-layouts/build/layouts/urdu.js'),
  urduStandard: () => import('simple-keyboard-layouts/build/layouts/urduStandard.js'),
  uyghur: () => import('simple-keyboard-layouts/build/layouts/uyghur.js'),
} as const satisfies Record<string, () => Promise<SimpleKeyboardLayoutModule>>

export type LayoutPresetName = keyof typeof PRESET_LOADERS

/** Every preset shipped in `simple-keyboard-layouts` (for smoke tests). */
export const ALL_LAYOUT_PRESET_NAMES = Object.keys(PRESET_LOADERS) as LayoutPresetName[]

/**
 * Virtual keyboard preset for each Settings → Interface language entry (27).
 * Key order matches {@link INTERFACE_LANGUAGE_PICKER_CODES}.
 */
export const PICKER_VIRTUAL_KEYBOARD_PRESET_BY_UI_LOCALE = {
  'zh-tw': 'chinese',
  zh: 'chinese',
  en: 'english',
  es: 'spanish',
  az: 'turkish',
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
} as const satisfies Record<InterfaceLanguagePickerCode, LayoutPresetName>

if (
  INTERFACE_LANGUAGE_PICKER_CODES.length !==
  Object.keys(PICKER_VIRTUAL_KEYBOARD_PRESET_BY_UI_LOCALE).length
) {
  throw new Error(
    'keyboardLayoutForUiLocale: picker virtual-keyboard map key count !== INTERFACE_LANGUAGE_PICKER_CODES'
  )
}
for (const code of INTERFACE_LANGUAGE_PICKER_CODES) {
  if (!(code in PICKER_VIRTUAL_KEYBOARD_PRESET_BY_UI_LOCALE)) {
    throw new Error(
      `keyboardLayoutForUiLocale: missing PICKER_VIRTUAL_KEYBOARD_PRESET_BY_UI_LOCALE entry for ${code}`
    )
  }
}

/**
 * Registry locales not in the picker: map to the closest pack layout. Omitted → `english`.
 */
const EXTENDED_UI_LOCALE_TO_PRESET: Partial<Record<LocaleCode, LayoutPresetName>> = {
  bg: 'russian',
  bn: 'bengali',
  ca: 'spanish',
  cs: 'czech',
  da: 'norwegian',
  el: 'greek',
  es: 'spanish',
  fi: 'swedish',
  ha: 'nigerian',
  he: 'hebrew',
  hu: 'hungarian',
  hy: 'armenianEastern',
  ka: 'georgian',
  kk: 'russian',
  ky: 'russian',
  mk: 'macedonian',
  ml: 'malayalam',
  mn: 'russian',
  my: 'burmese',
  ne: 'hindi',
  no: 'norwegian',
  sk: 'czech',
  sr: 'russian',
  sv: 'swedish',
  tg: 'russian',
  tk: 'turkish',
  ur: 'urdu',
  ug: 'uyghur',
}

export function getLayoutPresetKeyForUiLocale(code: LocaleCode): LayoutPresetName {
  if (isInterfaceLanguagePickerLocale(code)) {
    return PICKER_VIRTUAL_KEYBOARD_PRESET_BY_UI_LOCALE[code as InterfaceLanguagePickerCode]
  }
  return EXTENDED_UI_LOCALE_TO_PRESET[code] ?? 'english'
}

export async function loadLayoutForPreset(
  preset: LayoutPresetName
): Promise<SimpleKeyboardLayoutModule['default']> {
  const mod = await PRESET_LOADERS[preset]()
  return mod.default
}
