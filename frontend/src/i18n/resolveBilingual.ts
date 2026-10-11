/**
 * Resolve a message key for bilingual UI chrome.
 * Primary is the active interface locale; secondary is the presenter locale.
 * On `/auth`, the second line is Simplified Chinese. Chinese browsers stay one line.
 */
import { authPageSecondaryLocale } from '@/i18n/authPageBilingual'
import { translateForUiLocale } from '@/i18n/translateForUiLocale'
import type { Language } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'

export interface BilingualCopy {
  primary: string
  secondary: string | null
}

function presenterLocale(): Language | null {
  const uiStore = useUIStore()
  if (uiStore.authPageBilingual) {
    return authPageSecondaryLocale(uiStore.language)
  }
  if (!uiStore.bilingualUiEnabled) {
    return null
  }
  return uiStore.presenterUiLocale as Language
}

export function resolveBilingual(key: string, params?: Record<string, unknown>): BilingualCopy {
  const uiStore = useUIStore()
  const primaryLocale = uiStore.language as Language
  const primary = translateForUiLocale(key, primaryLocale, params)
  const presenter = presenterLocale()
  if (presenter === null || presenter === primaryLocale) {
    return { primary, secondary: null }
  }
  const secondary = translateForUiLocale(key, presenter, params)
  if (secondary === primary) {
    return { primary, secondary: null }
  }
  return { primary, secondary }
}
