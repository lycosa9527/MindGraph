/**
 * Bilingual UI chrome prefs — localStorage keys and presenter default.
 */
import { INTERFACE_LANGUAGE_PICKER_CODES, type LocaleCode } from '@/i18n/locales'

export const BILINGUAL_UI_KEY = 'mindgraph_bilingual_ui'
export const PRESENTER_UI_LOCALE_KEY = 'mindgraph_presenter_ui_locale'

export function defaultPresenterUiLocale(allowZh: boolean): LocaleCode {
  return allowZh ? 'zh' : 'en'
}

/** A second interface language that is not the primary one. */
export function complementaryUiLocale(primary: LocaleCode, allowZh: boolean): LocaleCode {
  if (primary !== 'zh' && allowZh) {
    return 'zh'
  }
  if (primary !== 'en') {
    return 'en'
  }
  const other = INTERFACE_LANGUAGE_PICKER_CODES.find(
    (code) => code !== primary && (allowZh || code !== 'zh')
  )
  return other ?? 'en'
}
