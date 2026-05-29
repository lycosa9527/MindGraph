export interface TranslateLanguage {
  code: string
  label: string
}

/** All languages supported by qwen3-livetranslate-flash-realtime as translation targets. */
export const TRANSLATE_LANGUAGES: TranslateLanguage[] = [
  { code: 'en', label: 'English (英语)' },
  { code: 'zh', label: '中文' },
  { code: 'yue', label: '粤语' },
  { code: 'ja', label: '日本語 (日语)' },
  { code: 'ko', label: '한국어 (韩语)' },
  { code: 'fr', label: 'Français (法语)' },
  { code: 'de', label: 'Deutsch (德语)' },
  { code: 'es', label: 'Español (西班牙语)' },
  { code: 'pt', label: 'Português (葡语)' },
  { code: 'it', label: 'Italiano (意大利语)' },
  { code: 'ru', label: 'Русский (俄语)' },
  { code: 'ar', label: 'العربية (阿拉伯语)' },
  { code: 'hi', label: 'हिन्दी (印地语)' },
  { code: 'id', label: 'Indonesia (印尼语)' },
  { code: 'vi', label: 'Tiếng Việt (越南语)' },
  { code: 'th', label: 'ภาษาไทย (泰语)' },
  { code: 'el', label: 'Ελληνικά (希腊语)' },
  { code: 'tr', label: 'Türkçe (土耳其语)' },
]

const CANVAS_TRANSLATE_TARGET_CODES = new Set(TRANSLATE_LANGUAGES.map((entry) => entry.code))

/**
 * Map MindGraph UI locale to `target_language` for `/api/canvas/translate_*` endpoints.
 * Only languages in {@link TRANSLATE_LANGUAGES} are supported; others fall back to `en`.
 * Traditional-Chinese UI (`zh-tw`, `zh-hant`) maps to API code `zh` (see also `ui_locale` body field).
 */
export function canvasTranslateTargetForUiLocale(ui: string): string {
  const code = String(ui || '').trim()
  if (code === 'zh-tw' || code === 'zh-hant') {
    return 'zh'
  }
  if (CANVAS_TRANSLATE_TARGET_CODES.has(code)) {
    return code
  }
  const base = code.split('-')[0]
  if (base && base !== code && CANVAS_TRANSLATE_TARGET_CODES.has(base)) {
    return base
  }
  return 'en'
}
