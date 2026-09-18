/**
 * Bilingual UI chrome prefs — localStorage keys and presenter default.
 */
import type { LocaleCode } from '@/i18n/locales'

export const BILINGUAL_UI_KEY = 'mindgraph_bilingual_ui'
export const PRESENTER_UI_LOCALE_KEY = 'mindgraph_presenter_ui_locale'

export function defaultPresenterUiLocale(allowZh: boolean): LocaleCode {
  return allowZh ? 'zh' : 'en'
}
