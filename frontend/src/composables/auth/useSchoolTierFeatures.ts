import { computed } from 'vue'

import {
  PREMIUM_SCHOOL_TIER_FEATURES,
  type SchoolTier,
  type SchoolTierFeatures,
  mergeSchoolTierFeatures,
} from '@/constants/schoolTier'
import { useAuthStore } from '@/stores/auth'

function resolveFeatures(
  schoolId: string | undefined,
  schoolTier: SchoolTier | null | undefined,
  fromApi: SchoolTierFeatures | null | undefined
): SchoolTierFeatures {
  if (!schoolId) {
    return PREMIUM_SCHOOL_TIER_FEATURES
  }
  return mergeSchoolTierFeatures(schoolTier, fromApi)
}

export function useSchoolTierFeatures() {
  const authStore = useAuthStore()

  const schoolTier = computed(() => authStore.user?.schoolTier)
  const features = computed(() =>
    resolveFeatures(
      authStore.user?.schoolId,
      authStore.user?.schoolTier,
      authStore.user?.schoolTierFeatures
    )
  )

  const canUseOnlineCollab = computed(() => features.value.online_collab)
  const canUsePresentationTools = computed(() => features.value.presentation_tools)
  const canUseChromeExtension = computed(() => features.value.chrome_extension)
  const canUseApiToken = computed(() => features.value.api_token)

  /** Account plugin row: API token, Chrome extension, OpenClaw skill download. */
  const showAccountPlugins = computed(
    () =>
      canUseApiToken.value || canUseChromeExtension.value
  )

  return {
    schoolTier,
    features,
    canUseOnlineCollab,
    canUsePresentationTools,
    canUseChromeExtension,
    canUseApiToken,
    showAccountPlugins,
  }
}
