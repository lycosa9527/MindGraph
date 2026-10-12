/**
 * Overseas accounts cannot use Simplified Chinese.
 * AI requests that ask for it, or that include Simplified glyphs, show one notice.
 */
import { Converter } from 'opencc-js'

import { notify } from '@/composables/core/notifications'

const NOTICE_EN = 'We do not support Simplified Chinese for overseas users at this point.'
const NOTICE_ZH = '海外用户暂不支持简体中文。'
const NOTICE_ZH_TW = '海外用戶暫不支援簡體中文。'

const SIMPLIFIED_TO_TRADITIONAL = Converter({ from: 'cn', to: 'tw' })

const AI_REQUEST_MARKERS = [
  '/generate_graph',
  '/generate_multi_',
  '/generate_from_web_content',
  '/generate_mindmap_from_',
  '/thinking_mode/',
  '/canvas/translate',
  '/canvas/generate_mindmap',
  '/concept_map',
  '/mind-classroom',
  '/mind_classroom',
  '/zhihui',
  '/generate-text-to-image',
  '/showcase/ai',
]

let lastNoticeAt = 0

export function simplifiedChineseUnsupportedMessage(uiLanguage: string): string {
  const code = uiLanguage.trim().toLowerCase()
  if (code === 'zh-tw' || code.startsWith('zh-hant') || code === 'zh-hk' || code === 'zh-mo') {
    return NOTICE_ZH_TW
  }
  if (code === 'zh' || code.startsWith('zh-hans') || code === 'zh-cn') {
    return NOTICE_ZH
  }
  return NOTICE_EN
}

export function textHasSimplifiedChinese(text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) {
    return false
  }
  return SIMPLIFIED_TO_TRADITIONAL(trimmed) !== trimmed
}

function isTraditionalUiCode(code: string): boolean {
  const lower = code.trim().toLowerCase()
  return (
    lower === 'zh-tw' ||
    lower.startsWith('zh-hant') ||
    lower === 'zh-hk' ||
    lower === 'zh-mo'
  )
}

function treeHasSimplifiedChinese(value: unknown, budget: { left: number }): boolean {
  if (budget.left <= 0) {
    return false
  }
  if (typeof value === 'string') {
    budget.left -= value.length
    return textHasSimplifiedChinese(value.slice(0, 8000))
  }
  if (Array.isArray(value)) {
    return value.some((item) => treeHasSimplifiedChinese(item, budget))
  }
  if (value !== null && typeof value === 'object') {
    return Object.values(value as Record<string, unknown>).some((item) =>
      treeHasSimplifiedChinese(item, budget)
    )
  }
  return false
}

function payloadRequestsSimplifiedChinese(parsed: unknown): boolean {
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return treeHasSimplifiedChinese(parsed, { left: 20000 })
  }
  const record = parsed as Record<string, unknown>
  const uiLocale = typeof record.ui_locale === 'string' ? record.ui_locale : ''
  const language = typeof record.language === 'string' ? record.language.trim().toLowerCase() : ''
  if (language === 'zh' && !isTraditionalUiCode(uiLocale)) {
    return true
  }
  const target = typeof record.target_language === 'string' ? record.target_language.trim().toLowerCase() : ''
  if (target === 'zh' && !isTraditionalUiCode(uiLocale)) {
    return true
  }
  return treeHasSimplifiedChinese(parsed, { left: 20000 })
}

export function notifySimplifiedChineseUnsupported(uiLanguage: string): void {
  const now = Date.now()
  if (now - lastNoticeAt < 12000) {
    return
  }
  lastNoticeAt = now
  notify.warning(simplifiedChineseUnsupportedMessage(uiLanguage), 6000)
}

export function notifyIfAiRequestUsesSimplifiedChinese(
  url: string,
  options: RequestInit,
  policy: { allowSimplifiedChinese: boolean; uiLanguage: string }
): void {
  if (policy.allowSimplifiedChinese) {
    return
  }
  if (!AI_REQUEST_MARKERS.some((marker) => url.includes(marker))) {
    return
  }
  const body = options.body
  if (typeof body !== 'string' || body.length === 0 || body.length > 400000) {
    return
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(body) as unknown
  } catch {
    return
  }
  if (payloadRequestsSimplifiedChinese(parsed)) {
    notifySimplifiedChineseUnsupported(policy.uiLanguage)
  }
}

/** Test hook: the notice debounce must not leak between cases. */
export function resetSimplifiedChineseNoticeForTests(): void {
  lastNoticeAt = 0
}
