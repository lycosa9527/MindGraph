/**
 * /privacy locale — browser default with manual zh/en override via segmented control.
 */
import { computed, ref } from 'vue'

import {
  browserExtensionPrivacyForUiCode,
  softwareAgreementForUiCode,
} from '@/content/authSoftwareAgreement'
import {
  detectPrivacyPageUiCode,
  privacyPageChrome,
  privacyPageUpdatedLabel,
  type PrivacyPageUiCode,
} from '@/utils/privacyPageLocale'

/** Shared ref so App.vue can sync document.title when the user toggles language. */
export const privacyPageUiCode = ref<PrivacyPageUiCode>(detectPrivacyPageUiCode())

export const PRIVACY_PAGE_LANGUAGE_OPTIONS: Array<{
  label: string
  value: PrivacyPageUiCode
}> = [
  { label: '中文', value: 'zh' },
  { label: 'English', value: 'en' },
]

export function usePrivacyPageLocale() {
  const chrome = computed(() => privacyPageChrome(privacyPageUiCode.value))
  const agreement = computed(() => softwareAgreementForUiCode(privacyPageUiCode.value))
  const extensionSections = computed(() =>
    browserExtensionPrivacyForUiCode(privacyPageUiCode.value)
  )
  const updatedLabel = computed(() =>
    privacyPageUpdatedLabel(privacyPageUiCode.value, agreement.value.updated)
  )

  function syncFromBrowser(): void {
    privacyPageUiCode.value = detectPrivacyPageUiCode()
  }

  return {
    privacyPageUiCode,
    chrome,
    agreement,
    extensionSections,
    updatedLabel,
    syncFromBrowser,
  }
}
