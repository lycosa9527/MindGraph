/**
 * Per-locale dynamic imports (generated — run: node scripts/generate-lazy-locale-loaders.js).
 * `en` is eager in i18n/index.ts. LOCALE_EN_COPY_CODES reuse those messages (no import here).
 */
import type { LocaleCode } from './locales'

type LocaleModule = { default: Record<string, string> }

/** UI locale codes that reuse eager English strings (see loadLocaleMessages in i18n/index.ts). */
export const LOCALE_EN_COPY_CODES = [
  'am',
  'bg',
  'bn',
  'bs',
  'ca',
  'cs',
  'da',
  'dv',
  'el',
  'et',
  'fi',
  'ha',
  'he',
  'hr',
  'hu',
  'hy',
  'ig',
  'ka',
  'kk',
  'km',
  'ky',
  'lo',
  'lt',
  'lv',
  'mk',
  'ml',
  'mn',
  'my',
  'ne',
  'no',
  'ps',
  'ro',
  'sk',
  'sl',
  'so',
  'sr',
  'ss',
  'st',
  'sv',
  'sw',
  'ta',
  'tg',
  'tk',
  'tn',
  'ug',
  'ur',
  'xh',
  'yo',
  'zu',
] as const satisfies readonly LocaleCode[]

const enCopySet = new Set<string>(LOCALE_EN_COPY_CODES)

export function isLocaleEnCopy(code: LocaleCode): boolean {
  return enCopySet.has(code)
}

export const lazyLocaleLoaders: Partial<Record<LocaleCode, () => Promise<LocaleModule>>> = {
  af: () => import('@/locales/messages/af'),
  ar: () => import('@/locales/messages/ar'),
  az: () => import('@/locales/messages/az'),
  de: () => import('@/locales/messages/de'),
  es: () => import('@/locales/messages/es'),
  fa: () => import('@/locales/messages/fa'),
  fr: () => import('@/locales/messages/fr'),
  hi: () => import('@/locales/messages/hi'),
  id: () => import('@/locales/messages/id'),
  it: () => import('@/locales/messages/it'),
  ja: () => import('@/locales/messages/ja'),
  ko: () => import('@/locales/messages/ko'),
  ms: () => import('@/locales/messages/ms'),
  nl: () => import('@/locales/messages/nl'),
  pl: () => import('@/locales/messages/pl'),
  pt: () => import('@/locales/messages/pt'),
  ru: () => import('@/locales/messages/ru'),
  si: () => import('@/locales/messages/si'),
  sq: () => import('@/locales/messages/sq'),
  th: () => import('@/locales/messages/th'),
  tl: () => import('@/locales/messages/tl'),
  tr: () => import('@/locales/messages/tr'),
  uk: () => import('@/locales/messages/uk'),
  uz: () => import('@/locales/messages/uz'),
  vi: () => import('@/locales/messages/vi'),
  zh: () => import('@/locales/messages/zh'),
  'zh-tw': () => import('@/locales/messages/zh-tw'),
}
