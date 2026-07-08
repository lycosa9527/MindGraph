/**
 * Visible management panel tabs (capability + feature gated).
 */
import { computed, onMounted } from 'vue'

import { ADMIN_PANEL_TAB_CONFIG } from '@/composables/admin/adminPanelTabs'
import { hasVisibleFeatureDevNav } from '@/composables/admin/adminFeatureDevNav'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useLanguage } from '@/composables/core/useLanguage'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'

export function useAdminPanelTabs(options?: { loadOnMount?: boolean }) {
  const { t } = useLanguage()
  const {
    featureMarkets,
    featureSmartResponse,
    featureTeacherUsage,
    featureKittyAgent,
    featureMindmateExport,
  } = useFeatureFlags()
  const { can, canViewTab, canViewSettingsSubtab, loadCapabilities } = useAdminAccess()

  const tabs = computed(() => {
    let visible = ADMIN_PANEL_TAB_CONFIG.filter((tab) => canViewTab(tab.name))
    if (!featureMarkets.value) {
      visible = visible.filter((tab) => tab.name !== 'billing')
    }
    // Case Square admin is capability-gated only (not hidden when FEATURE_CASE_SQUARE is off).
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
