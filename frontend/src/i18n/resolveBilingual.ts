/**
 * Resolve a message key for bilingual UI chrome.
 * Primary is the active interface locale; secondary is the presenter locale.
 */
import { translateForUiLocale } from '@/i18n/translateForUiLocale'
import type { Language } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'

export interface BilingualCopy {
  primary: string
  secondary: string | null
}

export function resolveBilingual(key: string, params?: Record<string, unknown>): BilingualCopy {
  const uiStore = useUIStore()
  const primaryLocale = uiStore.language as Language
  const primary = translateForUiLocale(key, primaryLocale, params)
  if (!uiStore.bilingualUiEnabled) {
    return { primary, secondary: null }
  }
  const presenter = uiStore.presenterUiLocale as Language
  if (presenter === primaryLocale) {
    return { primary, secondary: null }
  }
  return {
    primary,
    secondary: translateForUiLocale(key, presenter, params),
  }
}
