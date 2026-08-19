/**
 * Gallery language-menu labels: native name plus Chinese, matching the caption dropdown.
 */
import {
  PROMPT_LANGUAGE_OPTIONS,
  isUiLocale,
  matchedPromptLanguageForUiLocale,
} from './locales'

const ZH_GALLERY_MENU_CODES = new Set(['zh', 'zh-tw', 'zh-hant'])

const PROMPT_CHINESE_NAME_BY_CODE = new Map(
  PROMPT_LANGUAGE_OPTIONS.map((row) => [row.code, row.chineseName])
)

/**
 * `English (英语)`. Chinese locales stay native-only (`中文`, `繁體中文`).
 */
export function formatGalleryLanguageMenuLabel(code: string, nativeLabel: string): string {
  if (ZH_GALLERY_MENU_CODES.has(code)) {
    return nativeLabel
  }
  const promptCode = isUiLocale(code) ? (matchedPromptLanguageForUiLocale(code) ?? code) : code
  const chinese = PROMPT_CHINESE_NAME_BY_CODE.get(promptCode)
  if (!chinese) {
    return nativeLabel
  }
  return `${nativeLabel} (${chinese})`
}