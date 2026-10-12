export interface TranslateLanguage {
  code: string
  label: string
}

/**
 * Translation targets for qwen3.8-livetranslate-flash-realtime.
 * Subtitles request text only, so both audio+text and text-only codes are valid.
 * Order matches the DashScope realtime translation language table (en, zh first).
 */
export const LIVE_TRANSLATE_LANGUAGES: TranslateLanguage[] = [
  { code: 'en', label: 'English (英语)' },
  { code: 'zh', label: '中文' },
  { code: 'ar', label: 'العربية (阿拉伯语)' },
  { code: 'de', label: 'Deutsch (德语)' },
  { code: 'fr', label: 'Français (法语)' },
  { code: 'es', label: 'Español (西班牙语)' },
  { code: 'pt', label: 'Português (葡语)' },
  { code: 'id', label: 'Indonesia (印尼语)' },
  { code: 'it', label: 'Italiano (意大利语)' },
  { code: 'ko', label: '한국어 (韩语)' },
  { code: 'ru', label: 'Русский (俄语)' },
  { code: 'th', label: 'ภาษาไทย (泰语)' },
  { code: 'vi', label: 'Tiếng Việt (越南语)' },
  { code: 'ja', label: '日本語 (日语)' },
  { code: 'tr', label: 'Türkçe (土耳其语)' },
  { code: 'hi', label: 'हिन्दी (印地语)' },
  { code: 'ms', label: 'Bahasa Melayu (马来语)' },
  { code: 'nl', label: 'Nederlands (荷兰语)' },
  { code: 'ur', label: 'اردو (乌尔都语)' },
  { code: 'nb', label: 'Norsk bokmål (挪威语)' },
  { code: 'sv', label: 'Svenska (瑞典语)' },
  { code: 'da', label: 'Dansk (丹麦语)' },
  { code: 'he', label: 'עברית (希伯来语)' },
  { code: 'fi', label: 'Suomi (芬兰语)' },
  { code: 'pl', label: 'Polski (波兰语)' },
  { code: 'is', label: 'Íslenska (冰岛语)' },
  { code: 'cs', label: 'Čeština (捷克语)' },
  { code: 'fil', label: 'Filipino (菲律宾语)' },
  { code: 'fa', label: 'فارسی (波斯语)' },
  { code: 'yue', label: '粤语' },
  { code: 'el', label: 'Ελληνικά (希腊语)' },
  { code: 'af', label: 'Afrikaans (南非荷兰语)' },
  { code: 'ast', label: 'Asturianu (阿斯图里亚斯语)' },
  { code: 'be', label: 'Беларуская (白俄罗斯语)' },
  { code: 'bg', label: 'Български (保加利亚语)' },
  { code: 'bn', label: 'বাংলা (孟加拉语)' },
  { code: 'bs', label: 'Bosanski (波斯尼亚语)' },
  { code: 'ca', label: 'Català (加泰罗尼亚语)' },
  { code: 'ceb', label: 'Cebuano (宿务语)' },
  { code: 'et', label: 'Eesti (爱沙尼亚语)' },
  { code: 'gl', label: 'Galego (加利西亚语)' },
  { code: 'gu', label: 'ગુજરાતી (古吉拉特语)' },
  { code: 'hr', label: 'Hrvatski (克罗地亚语)' },
  { code: 'hu', label: 'Magyar (匈牙利语)' },
  { code: 'jv', label: 'Basa Jawa (爪哇语)' },
  { code: 'kk', label: 'Қазақша (哈萨克语)' },
  { code: 'kn', label: 'ಕನ್ನಡ (卡纳达语)' },
  { code: 'ky', label: 'Кыргызча (柯尔克孜语)' },
  { code: 'lv', label: 'Latviešu (拉脱维亚语)' },
  { code: 'mk', label: 'Македонски (马其顿语)' },
  { code: 'ml', label: 'മലയാളം (马拉雅拉姆语)' },
  { code: 'mr', label: 'मराठी (马拉地语)' },
  { code: 'pa', label: 'ਪੰਜਾਬੀ (旁遮普语)' },
  { code: 'ro', label: 'Română (罗马尼亚语)' },
  { code: 'sk', label: 'Slovenčina (斯洛伐克语)' },
  { code: 'sl', label: 'Slovenščina (斯洛文尼亚语)' },
  { code: 'sw', label: 'Kiswahili (斯瓦希里语)' },
  { code: 'tg', label: 'Тоҷикӣ (塔吉克语)' },
  { code: 'az', label: 'Azərbaycan (阿塞拜疆语)' },
  { code: 'uk', label: 'Українська (乌克兰语)' },
]

/**
 * Diagram-label targets accepted by `/api/canvas/translate_*`.
 * That API allowlist is separate from live subtitle languages.
 */
const CANVAS_TRANSLATE_TARGET_CODES = new Set([
  'en',
  'zh',
  'yue',
  'ja',
  'ko',
  'fr',
  'de',
  'es',
  'pt',
  'it',
  'ru',
  'ar',
  'hi',
  'id',
  'vi',
  'th',
  'el',
  'tr',
])

/**
 * Map MindGraph UI locale to `target_language` for `/api/canvas/translate_*` endpoints.
 * Only the diagram-translate allowlist is accepted; other locales fall back to `en`.
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
