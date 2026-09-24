import { ref } from 'vue'

import { createI18n } from 'vue-i18n'

import enMessages from '@/locales/messages/en'

import { notifyLocaleLoaded } from './localeLabelCache'
import type { LocaleCode } from './locales'
import { htmlLangForUiCode } from './locales'

export type { LocaleCode } from './locales'
export { intlLocaleForUiCode } from './locales'
export type { MessageSchema } from './messageSchema'
export { loadElementPlusLocale } from './elementPlusLocale'

/** Always bundled — fallback for all UI locales. */
export const EAGER_LOCALES = ['en'] as const satisfies readonly LocaleCode[]

const loadedLocales = new Set<LocaleCode>(EAGER_LOCALES)
const inFlightLoads = new Map<LocaleCode, Promise<void>>()

/**
 * Bumped when a lazy catalog is registered. `isLocaleLoaded` is a plain Set, so
 * Vue computeds that translate before the chunk arrives must read this ref or
 * they keep the English fallback after the real strings land.
 */
export const localeCatalogRevision = ref(0)

type LocaleModule = { default: Record<string, string> }

/**
 * One lazy chunk per `messages/<code>.ts`. Vite builds the map from files on disk,
 * so adding a locale cannot drift from a generated loader table.
 */
const lazyLocaleModules = import.meta.glob<LocaleModule>(
  ['../locales/messages/*.ts', '!../locales/messages/en.ts'],
  { eager: false }
)

export function lazyLocaleModuleKey(locale: LocaleCode): string {
  return `../locales/messages/${locale}.ts`
}

export function hasLazyLocaleBundle(locale: LocaleCode): boolean {
  if (locale === 'en') {
    return true
  }
  return lazyLocaleModules[lazyLocaleModuleKey(locale)] != null
}

export function isLocaleLoaded(locale: LocaleCode): boolean {
  return loadedLocales.has(locale)
}

/** Typed keys for `t()` — use `import type { MessageSchema } from '@/i18n/messageSchema'`. */
export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  // Match eager messages; lazy locales are applied via syncI18nLocale / bootstrap.
  locale: 'en',
  fallbackLocale: 'en',
  messages: {
    en: enMessages as Record<string, string>,
  },
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
})

function localeHasMessages(locale: LocaleCode): boolean {
  const bag = i18n.global.getLocaleMessage(locale) as Record<string, unknown> | undefined
  if (!bag) {
    return false
  }
  return Object.keys(bag).length > 0
}

/**
 * Load UI strings for a locale when not already eager-loaded.
 * Callers await this before `setI18nLocale` so bootstrap order stays stable.
 * Reloads if the locale was marked loaded but the message bag is empty (HMR desync).
 */
export async function loadLocaleMessages(locale: LocaleCode): Promise<void> {
  if (isLocaleLoaded(locale) && localeHasMessages(locale)) {
    return
  }
  if (isLocaleLoaded(locale) && !localeHasMessages(locale)) {
    loadedLocales.delete(locale)
  }

  const pending = inFlightLoads.get(locale)
  if (pending) {
    await pending
    return
  }

  const loadPromise = (async () => {
    const loader = lazyLocaleModules[lazyLocaleModuleKey(locale)]
    if (!loader) {
      console.warn(`[i18n] No message bundle for locale: ${locale}; using English fallback`)
      loadedLocales.add(locale)
      notifyLocaleLoaded()
      return
    }
    const mod = await loader()
    i18n.global.setLocaleMessage(locale, mod.default as Record<string, string>)
    loadedLocales.add(locale)
    localeCatalogRevision.value += 1
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

/** Load messages (if needed) and set the active vue-i18n locale. */
export async function syncI18nLocale(locale: LocaleCode): Promise<void> {
  await loadLocaleMessages(locale)
  setI18nLocale(locale)
}

/** BCP 47–friendly value for the document element. */
export function htmlLangForLocale(locale: LocaleCode): string {
  return htmlLangForUiCode(locale)
}
