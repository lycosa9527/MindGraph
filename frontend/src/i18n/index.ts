import { createI18n } from 'vue-i18n'

import enMessages from '@/locales/messages/en'
import zhMessages from '@/locales/messages/zh'

import type { LocaleCode } from './locales'
import { htmlLangForUiCode } from './locales'

export type { LocaleCode } from './locales'
export { intlLocaleForUiCode } from './locales'
export type { MessageSchema } from './messageSchema'
export { loadElementPlusLocale } from './elementPlusLocale'

/** vue-i18n instance — boot locale is `zh`, English is the fallback. */
export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: 'zh',
  fallbackLocale: 'en',
  messages: {
    zh: zhMessages as Record<string, string>,
    en: enMessages as Record<string, string>,
  },
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
})

/** Locale bundles registered so far — avoids redundant network fetches on repeat switches. */
const loadedLocales = new Set<LocaleCode>(['zh', 'en'])

/**
 * Lazy-loads a locale message bundle on first use and registers it with vue-i18n.
 * All locales other than the two boot locales (zh, en) are fetched on demand,
 * keeping them out of the main JS chunk.
 */
export async function loadLocaleMessages(locale: LocaleCode): Promise<void> {
  if (loadedLocales.has(locale)) return
  const mod = await import(`../locales/messages/${locale}.ts`)
  i18n.global.setLocaleMessage(locale, mod.default as Record<string, string>)
  loadedLocales.add(locale)
}

export function setI18nLocale(locale: LocaleCode): void {
  const loc = i18n.global.locale as { value: LocaleCode }
  loc.value = locale
}

/** BCP 47–friendly value for the document element. */
export function htmlLangForLocale(locale: LocaleCode): string {
  return htmlLangForUiCode(locale)
}
