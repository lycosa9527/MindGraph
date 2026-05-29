/**
 * Visible management panel tabs (capability + feature gated).
 */
import { computed, onMounted } from 'vue'

import { ADMIN_PANEL_TAB_CONFIG } from '@/composables/admin/adminPanelTabs'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useLanguage } from '@/composables/core/useLanguage'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'

export function useAdminPanelTabs(options?: { loadOnMount?: boolean }) {
  const { t } = useLanguage()
  const { featureMarkets } = useFeatureFlags()
  const { can, canViewTab, loadCapabilities } = useAdminAccess()

  const tabs = computed(() => {
    let visible = ADMIN_PANEL_TAB_CONFIG.filter((tab) => canViewTab(tab.name))
    if (!featureMarkets.value) {
      visible = visible.filter((tab) => tab.name !== 'billing')
    }
    if (!can('tab.billing.view')) {
      visible = visible.filter((tab) => tab.name !== 'billing')
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
