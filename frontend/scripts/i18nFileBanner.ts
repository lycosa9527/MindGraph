/**
 * File-header markers for UI message modules.
 * Writers and agents must read the header before changing keys.
 */
import { INTERFACE_LANGUAGE_PICKER_CODES } from '../src/i18n/locales.ts'

export const I18N_SOURCE_MARKER = 'SOURCE — author new keys here in Simplified Chinese first.'
export const I18N_ZHTW_MARKER = 'SOURCE — generate from zh with i18n:build-zhtw (OpenCC). Do not fill from en.'
export const I18N_FILL_MARKER =
  'FILL — English of zh. Copy into other locales only for keys that do not exist yet.'
export const I18N_TRANSLATED_MARKER =
  'TRANSLATED — do not overwrite values with English. Add missing keys only (fill new keys from en).'

export const I18N_NS_FILES = [
  'common',
  'mindmate',
  'maite',
  'canvas',
  'workshop',
  'training',
  'admin',
  'knowledge',
  'learningSpace',
  'community',
  'showcase',
  'zhihui',
  'sidebar',
  'auth',
  'notification',
  'thinkingCoins',
] as const

export type I18nNsName = (typeof I18N_NS_FILES)[number]

const PICKER_SET = new Set<string>(INTERFACE_LANGUAGE_PICKER_CODES)

export function isPickerLocale(code: string): boolean {
  return PICKER_SET.has(code)
}

export function bannerMarkerForLocale(code: string): string {
  if (code === 'zh') {
    return I18N_SOURCE_MARKER
  }
  if (code === 'zh-tw') {
    return I18N_ZHTW_MARKER
  }
  if (code === 'en') {
    return I18N_FILL_MARKER
  }
  if (isPickerLocale(code)) {
    return I18N_TRANSLATED_MARKER
  }
  return I18N_FILL_MARKER
}

export function localeNamespaceBanner(locale: string, ns: string): string {
  return `/**\n * ${locale} UI — ${ns}\n * ${bannerMarkerForLocale(locale)}\n */\n`
}

export function localeIndexBanner(locale: string): string {
  return `/**\n * ${locale} UI messages — merged namespace bundles.\n * ${bannerMarkerForLocale(locale)}\n */\n`
}

export function fileHasExpectedBanner(content: string, locale: string): boolean {
  return content.includes(bannerMarkerForLocale(locale))
}

export function applyNamespaceBanner(content: string, locale: string, ns: string): string {
  const banner = localeNamespaceBanner(locale, ns)
  const stripped = content.replace(/^\/\*\*[\s\S]*?\*\/\s*/, '')
  return `${banner}\n${stripped}`
}

export function applyIndexBanner(content: string, locale: string): string {
  const banner = localeIndexBanner(locale)
  const stripped = content.replace(/^\/\*\*[\s\S]*?\*\/\s*/, '')
  return `${banner}\n${stripped}`
}
