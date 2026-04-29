import { i18n } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'

type GlobalTForLocale = (
  key: string,
  params: Record<string, unknown>,
  options: { locale: LocaleCode }
) => string

const globalTForLocale = i18n.global.t as GlobalTForLocale

/**
 * Translate for a specific UI locale. `i18n.global.t` infers `locale` from static
 * `messages` keys (`zh`, `en`); lazy-loaded bundles still work at runtime.
 */
export function translateForUiLocale(
  key: string,
  locale: LocaleCode,
  params?: Record<string, unknown>
): string {
  return String(globalTForLocale(key, params ?? {}, { locale }))
}
