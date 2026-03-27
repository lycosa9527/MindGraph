/**
 * User-visible number and date formatting following the active UI locale (Intl).
 */
import type { LocaleCode } from '@/i18n/locales'
import { intlLocaleForUiCode } from '@/i18n/locales'

export function formatUserNumber(value: number, locale: LocaleCode): string {
  return new Intl.NumberFormat(intlLocaleForUiCode(locale)).format(value)
}

export function formatUserInteger(value: number, locale: LocaleCode): string {
  return new Intl.NumberFormat(intlLocaleForUiCode(locale), {
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatUserDate(
  isoOrDate: string | Date,
  locale: LocaleCode,
  dateStyle: 'short' | 'medium' | 'long' = 'short'
): string {
  const d = typeof isoOrDate === 'string' ? new Date(isoOrDate) : isoOrDate
  return new Intl.DateTimeFormat(intlLocaleForUiCode(locale), { dateStyle }).format(d)
}

export function formatUserDateTime(
  isoOrDate: string | Date,
  locale: LocaleCode,
  dateStyle: 'short' | 'medium' = 'short',
  timeStyle: 'short' | 'medium' = 'short'
): string {
  const d = typeof isoOrDate === 'string' ? new Date(isoOrDate) : isoOrDate
  return new Intl.DateTimeFormat(intlLocaleForUiCode(locale), {
    dateStyle,
    timeStyle,
  }).format(d)
}
