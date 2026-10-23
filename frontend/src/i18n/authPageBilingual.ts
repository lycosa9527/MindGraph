/**
 * `/auth` language pair, independent of the signed-in bilingual setting.
 * Simplified and Traditional Chinese stay a single line.
 * Every other browser locale keeps that language on top and Simplified Chinese underneath.
 */
import type { LocaleCode } from '@/i18n/locales'

const CHINESE_UI_LOCALES = new Set<LocaleCode>(['zh', 'zh-tw'])

export function authPageSecondaryLocale(primary: LocaleCode): LocaleCode | null {
  if (CHINESE_UI_LOCALES.has(primary)) {
    return null
  }
  return 'zh'
}
