/**
 * Public site URL for user-facing links (matches server EXTERNAL_BASE_URL from .env).
 * Falls back to window.location.origin when unset (e.g. local dev).
 */
import { computed } from 'vue'

import { useFeatureFlagsStore } from '@/stores/featureFlags'

export function usePublicSiteUrl() {
  const store = useFeatureFlagsStore()
  const publicSiteUrl = computed(() => {
    const raw = store.flags?.external_base_url?.trim()
    if (raw) {
      return raw.replace(/\/$/, '')
    }
    if (typeof window !== 'undefined') {
      return window.location.origin
    }
    return ''
  })
  return { publicSiteUrl }
}
