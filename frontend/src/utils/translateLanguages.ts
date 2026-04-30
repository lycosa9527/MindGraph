export interface TranslateLanguage {
  code: string
  label: string
}

/** All languages supported by qwen3-livetranslate-flash-realtime as translation targets. */
export const TRANSLATE_LANGUAGES: TranslateLanguage[] = [
  { code: 'auto', label: 'Auto (自动)' },
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
