/**
 * Map MindGraph UI language (Pinia `uiStore.language`, same as `useLanguage().currentLanguage`)
 * to MathLive's built-in locale ids.
 * @see https://mathlive.io/mathfield/guides/customizing/#localization
 * MathLive ships: en, ar, de, el, es, fr, he, it, ja, ko, pl, pt, uk, zh-cn, zh-tw (bundled in mathlive).
 */
const MATHLIVE_LOCALES = new Set([
  'en',
  'ar',
  'de',
  'el',
  'es',
  'fr',
  'he',
  'it',
  'ja',
  'ko',
  'pl',
  'pt',
  'uk',
  'zh-cn',
  'zh-tw',
])

export function mapUiLocaleToMathLiveLocale(uiLocale: string): string {
  const normalized = uiLocale.trim().toLowerCase().replace(/_/g, '-')
  if (normalized === 'zh' || normalized === 'zh-hans' || normalized === 'zh-cn') {
    return 'zh-cn'
  }
  if (normalized === 'zh-tw' || normalized === 'zh-hant') {
    return 'zh-tw'
  }
  if (MATHLIVE_LOCALES.has(normalized)) {
    return normalized
  }
  const primary = normalized.split('-')[0]
  if (primary === 'zh') {
    return 'zh-cn'
  }
  if (MATHLIVE_LOCALES.has(primary)) {
    return primary
  }
  return 'en'
}
