/**
 * Per-locale dynamic imports (generated — run: node scripts/generate-lazy-locale-loaders.js).
 * `en` is eager in i18n/index.ts. LOCALE_EN_COPY_CODES reuse those messages (no import here).
 */
import type { LocaleCode } from './locales'

type LocaleModule = { default: Record<string, string> }

/** UI locale codes that reuse eager English strings (see loadLocaleMessages in i18n/index.ts). */
export const LOCALE_EN_COPY_CODES = [] as const satisfies readonly LocaleCode[]

const enCopySet = new Set<string>(LOCALE_EN_COPY_CODES)

export function isLocaleEnCopy(code: LocaleCode): boolean {
  return enCopySet.has(code)
}

export const lazyLocaleLoaders: Partial<Record<LocaleCode, () => Promise<LocaleModule>>> = {
  af: () => import('@/locales/messages/af'),
  az: () => import('@/locales/messages/az'),
  fr: () => import('@/locales/messages/fr'),
  th: () => import('@/locales/messages/th'),
  zh: () => import('@/locales/messages/zh'),
  'zh-tw': () => import('@/locales/messages/zh-tw'),
}
