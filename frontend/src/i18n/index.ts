import { createI18n } from 'vue-i18n'

import enMessages from '@/locales/messages/en'

import { isLocaleEnCopy, lazyLocaleLoaders } from './lazyLocaleLoaders'
import type { LocaleCode } from './locales'
import { htmlLangForUiCode } from './locales'
import { notifyLocaleLoaded } from './localeLabelCache'

export type { LocaleCode } from './locales'
export { intlLocaleForUiCode } from './locales'
export type { MessageSchema } from './messageSchema'
export { loadElementPlusLocale } from './elementPlusLocale'

/** Always bundled — fallback for all UI locales. */
export const EAGER_LOCALES = ['en'] as const satisfies readonly LocaleCode[]

const loadedLocales = new Set<LocaleCode>(EAGER_LOCALES)
const inFlightLoads = new Map<LocaleCode, Promise<void>>()

export function isLocaleLoaded(locale: LocaleCode): boolean {
  return loadedLocales.has(locale)
}

/** Typed keys for `t()` — use `import type { MessageSchema } from '@/i18n/messageSchema'`. */
export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: 'zh',
  fallbackLocale: 'en',
  messages: {
    en: enMessages as Record<string, string>,
  },
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
})

/**
 * Load UI strings for a locale when not already eager-loaded.
 * Callers await this before `setI18nLocale` so bootstrap order stays stable.
 */
export async function loadLocaleMessages(locale: LocaleCode): Promise<void> {
  if (isLocaleLoaded(locale)) {
    return
  }

  const pending = inFlightLoads.get(locale)
  if (pending) {
    await pending
    return
  }

  const loadPromise = (async () => {
    if (isLocaleEnCopy(locale)) {
      i18n.global.setLocaleMessage(locale, enMessages as Record<string, string>)
      loadedLocales.add(locale)
      notifyLocaleLoaded()
      return
    }
    const loader = lazyLocaleLoaders[locale]
    if (!loader) {
      throw new Error(`No message bundle loader for locale: ${locale}`)
    }
    const mod = await loader()
    i18n.global.setLocaleMessage(locale, mod.default)
    loadedLocales.add(locale)
    notifyLocaleLoaded()
  })()

  inFlightLoads.set(locale, loadPromise)
  try {
    await loadPromise
  } finally {
    inFlightLoads.delete(locale)
  }
}

export function setI18nLocale(locale: LocaleCode): void {
  const loc = i18n.global.locale as { value: LocaleCode }
  loc.value = locale
}

/** BCP 47–friendly value for the document element. */
export function htmlLangForLocale(locale: LocaleCode): string {
  return htmlLangForUiCode(locale)
}
