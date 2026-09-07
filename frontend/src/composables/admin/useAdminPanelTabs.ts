/**
 * Visible management panel tabs (capability + feature gated).
 */
import { computed, onMounted } from 'vue'

import { hasVisibleFeatureDevNav } from '@/composables/admin/adminFeatureDevNav'
import { ADMIN_PANEL_TAB_CONFIG } from '@/composables/admin/adminPanelTabs'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useLanguage } from '@/composables/core/useLanguage'

export function useAdminPanelTabs(options?: { loadOnMount?: boolean }) {
  const { t } = useLanguage()
  const {
    featureMarkets,
    featureSmartResponse,
    featureTeacherUsage,
    featureKittyAgent,
    featureMindmateExport,
    featureVod,
  } = useFeatureFlags()
  const { can, canViewTab, canViewSettingsSubtab, loadCapabilities } = useAdminAccess()

  const tabs = computed(() => {
    let visible = ADMIN_PANEL_TAB_CONFIG.filter((tab) => canViewTab(tab.name))
    if (!featureMarkets.value) {
      visible = visible.filter((tab) => tab.name !== 'billing')
    }
    // Showcase admin is capability-gated only (not hidden when FEATURE_SHOWCASE is off).
    if (!featureVod.value) {
      visible = visible.filter((tab) => tab.name !== 'vod')
    }
    if (!can('tab.billing.view')) {
      visible = visible.filter((tab) => tab.name !== 'billing')
    }
    const featureDevVisible = hasVisibleFeatureDevNav({
      canViewSettingsSubtab,
      featureSmartResponse: featureSmartResponse.value,
      featureTeacherUsage: featureTeacherUsage.value,
      featureKittyAgent: featureKittyAgent.value,
      featureMindmateExport: featureMindmateExport.value,
    })
    if (!featureDevVisible) {
      visible = visible.filter((tab) => tab.name !== 'feature_dev')
    }
    return visible.map((tab) => ({ ...tab, label: t(tab.labelKey) }))
  })

  if (options?.loadOnMount !== false) {
    onMounted(() => {
      void loadCapabilities()
    })
  }

  return {
    tabs,
    loadCapabilities,
  }
}
