import { i18n, isLocaleLoaded, localeCatalogRevision } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'

type GlobalTForLocale = (
  key: string,
  params: Record<string, unknown>,
  options: { locale: LocaleCode }
) => string

const globalTForLocale = i18n.global.t as GlobalTForLocale

/**
 * vue-i18n JIT compile throws SyntaxError on a literal `@` (linked-message
 * syntax). Production reports that as ``SyntaxError: 10`` (INVALID_LINKED_FORMAT).
 * Return the key so I18nText still has a string instead of crashing the render.
 */
function translateOrKey(key: string, locale: LocaleCode, params: Record<string, unknown>): string {
  try {
    return String(globalTForLocale(key, params, { locale }))
  } catch (err) {
    if (err instanceof SyntaxError) return key
    throw err
  }
}

/**
 * Translate for a specific UI locale without spamming missing-key warnings for
 * lazy-loaded bundles: if that locale is not registered yet (or lacks the key),
 * resolve via English only. Module-level helpers that iterate all locale codes
 * run before `loadLocaleMessages` for every language; this avoids intlify noise.
 */
export function translateForUiLocale(
  key: string,
  locale: LocaleCode,
  params?: Record<string, unknown>
): string {
  const safeParams = params ?? {}
  // Track lazy catalog registration so bilingual labels refresh after the chunk loads.
  void localeCatalogRevision.value
  if (!isLocaleLoaded(locale)) {
    return translateOrKey(key, 'en', safeParams)
  }
  const bundle = i18n.global.getLocaleMessage(locale) as Record<string, unknown>
  if (bundle && Object.prototype.hasOwnProperty.call(bundle, key)) {
    return translateOrKey(key, locale, safeParams)
  }
  return translateOrKey(key, 'en', safeParams)
}

/** True when the key exists in the locale catalog, or in English while that locale is still loading. */
export function uiMessageExists(key: string, locale: LocaleCode): boolean {
  void localeCatalogRevision.value
  const locales: LocaleCode[] = locale === 'en' ? ['en'] : [locale, 'en']
  for (const code of locales) {
    if (!isLocaleLoaded(code)) continue
    const bundle = i18n.global.getLocaleMessage(code) as Record<string, unknown>
    if (bundle && Object.prototype.hasOwnProperty.call(bundle, key)) return true
  }
  return false
}
