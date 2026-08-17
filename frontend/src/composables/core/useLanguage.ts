/**
 * Language composable — wraps vue-i18n + Pinia UI/prompt locale.
 */
import { computed } from 'vue'

import { i18n } from '@/i18n'
import type { MessageSchema } from '@/i18n/messageSchema'
import type { Language, PromptLanguage } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'
import { safeI18nTranslate } from '@/utils/safeI18nTranslate'

type MessageKey = keyof MessageSchema

/** Dimension label translations (English → Chinese) for brace/tree map classification */
export const DIMENSION_TRANSLATIONS: Record<string, string> = {
  'Physical Characteristics': '物理特征',
  Parts: '组成部分',
  Components: '组件',
  Structure: '结构',
  Attributes: '属性',
  Properties: '属性',
  Types: '类型',
  Kinds: '种类',
  Categories: '类别',
  Characteristics: '特征',
  Features: '特点',
  Elements: '要素',
  Aspects: '方面',
  Factors: '因素',
}

export function translateDimension(value: string, toChinese: boolean): string {
  if (!toChinese || !value?.trim()) return value
  const trimmed = value.trim()
  return DIMENSION_TRANSLATIONS[trimmed] ?? trimmed
}

function globalTranslate(key: string, named?: Record<string, unknown>): string {
  if (named) {
    return String(i18n.global.t(key, named))
  }
  return String(i18n.global.t(key))
}

export function useLanguage() {
  // Use the i18n singleton — ``useI18n()`` throws MUST_BE_CALL_SETUP_TOP
  // (production ``SyntaxError: 26``) from event handlers / dialog remounts.
  const uiStore = useUIStore()

  const currentLanguage = computed(() => uiStore.language)
  /**
   * Locale booleans — prefer `t()` for user-visible strings.
   * Use only for non-display logic (e.g. which API field or script to prefer).
   */
  const isZh = computed(() => uiStore.language === 'zh')
  const isEn = computed(() => uiStore.language === 'en')
  const isAz = computed(() => uiStore.language === 'az')
  const promptLanguage = computed<PromptLanguage>(() => uiStore.promptLanguage)

  function t(key: MessageKey, fallback?: string): string
  function t(key: MessageKey, named: Record<string, unknown>): string
  function t(key: string, fallback?: string): string
  function t(key: string, named: Record<string, unknown>): string
  function t(key: string, second?: string | Record<string, unknown>): string {
    return safeI18nTranslate(globalTranslate, key, second)
  }

  function setLanguage(lang: Language): void {
    uiStore.setLanguage(lang)
  }

  function setPromptLanguage(lang: PromptLanguage): void {
    uiStore.setPromptLanguage(lang)
  }

  function toggleLanguage(): void {
    uiStore.toggleLanguage()
  }

  function getNotification(key: string, ...args: unknown[]): string {
    let message = t(`notification.${key}`)

    args.forEach((arg, index) => {
      message = message.replace(`{${index}}`, String(arg))
    })

    return message
  }

  return {
    currentLanguage,
    isZh,
    isEn,
    isAz,
    promptLanguage,
    t,
    setLanguage,
    setPromptLanguage,
    toggleLanguage,
    getNotification,
  }
}

/** `t` from `useLanguage()` (strict keys + string fallbacks), for deps typing */
export type UseLanguageTranslate = ReturnType<typeof useLanguage>['t']
