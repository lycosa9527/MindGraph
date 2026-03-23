/**
 * Vue I18n — zh / en / az message bundles (merged namespace files per locale).
 */
import { createI18n } from 'vue-i18n'

import azMessages from '@/locales/messages/az'
import enMessages from '@/locales/messages/en'
import zhMessages from '@/locales/messages/zh'

import type { LocaleCode } from './locales'
import { htmlLangForUiCode } from './locales'

export type { LocaleCode } from './locales'
export { intlLocaleForUiCode } from './locales'
export type { MessageSchema } from './messageSchema'
export { loadElementPlusLocale } from './elementPlusLocale'

/** Typed keys for `t()` — use `import type { MessageSchema } from '@/i18n/messageSchema'`. */
export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: 'zh',
  fallbackLocale: 'en',
  messages: {
    zh: zhMessages as Record<string, string>,
    en: enMessages as Record<string, string>,
    az: azMessages as Record<string, string>,
  },
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
})

const loadedLocales = new Set<LocaleCode>(['zh', 'en', 'az'])

/**
 * Loads a UI locale message module when adding new languages beyond the bundled set.
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
