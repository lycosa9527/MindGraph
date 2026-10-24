/**
 * User-visible number and date formatting following the active UI locale (Intl).
 */
import type { LocaleCode } from '@/i18n/locales'
import { intlLocaleForUiCode } from '@/i18n/locales'
import { formatInBeijing } from '@/utils/beijingClock'

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
  return (
    formatInBeijing(isoOrDate, intlLocaleForUiCode(locale), { dateStyle }) ||
    (typeof isoOrDate === 'string' ? isoOrDate : '')
  )
}

export function formatUserDateTime(
  isoOrDate: string | Date,
  locale: LocaleCode,
  dateStyle: 'short' | 'medium' = 'short',
  timeStyle: 'short' | 'medium' = 'short'
): string {
  return (
    formatInBeijing(isoOrDate, intlLocaleForUiCode(locale), { dateStyle, timeStyle }) ||
    (typeof isoOrDate === 'string' ? isoOrDate : '')
  )
}
