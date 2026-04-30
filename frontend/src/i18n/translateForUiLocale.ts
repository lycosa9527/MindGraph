import { i18n } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'

type GlobalTForLocale = (
  key: string,
  params: Record<string, unknown>,
  options: { locale: LocaleCode }
) => string

const globalTForLocale = i18n.global.t as GlobalTForLocale

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
  const bundle = i18n.global.getLocaleMessage(locale) as Record<string, unknown>
  if (bundle && Object.prototype.hasOwnProperty.call(bundle, key)) {
    return String(globalTForLocale(key, safeParams, { locale }))
  }
  return String(globalTForLocale(key, safeParams, { locale: 'en' }))
}
