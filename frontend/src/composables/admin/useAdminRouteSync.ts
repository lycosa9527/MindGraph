/**
 * Sync admin panel store with route query (tab, subtab, view, organization_id).
 */
import { watch, type Ref } from 'vue'

import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import {
  defaultDataCenterView,
  isDataCenterView,
} from '@/composables/admin/adminDataCenterViews'
import { LEGACY_FEATURE_DEV_SETTINGS_SUBTABS } from '@/composables/admin/adminFeatureDevNav'
import {
  defaultShowcaseSubtab,
  isShowcaseSubtab,
  resolveShowcaseSubtab,
  showcaseSubtabLabelKey,
} from '@/composables/admin/adminShowcaseNav'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { eventBus } from '@/composables/core/useEventBus'
import { useAdminPanelStore, useAuthStore } from '@/stores'

function parseRouteOrgId(raw: unknown): number | null {
  if (typeof raw === 'string' && raw.trim()) {
    const parsed = Number(raw)
    if (!Number.isNaN(parsed) && parsed > 0) {
      return parsed
    }
  }
  return null
}

export interface UseAdminRouteSyncOptions {
  tabs: Ref<ReadonlyArray<{ name: string }>>
}

export function useAdminRouteSync(options: UseAdminRouteSyncOptions) {
  const route = useRoute()
  const router = useRouter()
  const authStore = useAuthStore()
  const { can } = useAdminAccess()
  const adminPanel = useAdminPanelStore()
  const { activeTab, activeSubtab, activeDataCenterView, selectedOrgId } =
    storeToRefs(adminPanel)

  activeTab.value = (route.query.tab as string) || 'data_center'
  activeSubtab.value = typeof route.query.subtab === 'string' ? route.query.subtab : null
  activeDataCenterView.value =
    typeof route.query.view === 'string' ? route.query.view : null
  selectedOrgId.value = parseRouteOrgId(route.query.organization_id)

  function emitTabActivated(): void {
    eventBus.emit('admin:tab_activated', {
      tab: activeTab.value,
      ...(activeSubtab.value ? { subtab: activeSubtab.value } : {}),
      ...(activeDataCenterView.value ? { view: activeDataCenterView.value } : {}),
    })
  }

  watch(
    () => route.query.tab,
    (tab) => {
      if (tab && typeof tab === 'string' && tab !== activeTab.value) {
        activeTab.value = tab
      }
    }
  )

  watch(
    () => route.query.subtab,
    (subtab) => {
      const next = typeof subtab === 'string' ? subtab : null
      if (next !== activeSubtab.value) {
        activeSubtab.value = next
      }
    }
  )

  watch(
    () => route.query.view,
    (view) => {
      const next = typeof view === 'string' ? view : null
      if (next !== activeDataCenterView.value) {
        activeDataCenterView.value = next
      }
    }
  )

  watch(
    () => [route.query.tab, route.query.subtab] as const,
    ([tab, subtab]) => {
      if (
        tab === 'settings' &&
        typeof subtab === 'string' &&
        LEGACY_FEATURE_DEV_SETTINGS_SUBTABS.includes(subtab)
      ) {
        void router.replace({
          query: { ...route.query, tab: 'feature_dev', subtab },
        })
        return
      }
      if (tab === 'feature_dev' && subtab === 'features') {
        void router.replace({
          query: { ...route.query, tab: 'settings', subtab: 'features' },
        })
      }
    },
    { immediate: true }
  )

  watch(activeTab, (tab) => {
    const current = route.query.tab as string
    const query: Record<string, string | string[]> = { ...route.query, tab }
    if (tab !== 'settings' && tab !== 'feature_dev' && tab !== 'showcase') {
      delete query.subtab
      delete query.role_tab
      activeSubtab.value = null
    }
    if (tab === 'showcase') {
      const rawSubtab = query.subtab
      const resolved =
        typeof rawSubtab === 'string' && isShowcaseSubtab(rawSubtab)
          ? rawSubtab
          : defaultShowcaseSubtab()
      query.subtab = resolved
      activeSubtab.value = resolved
    }
    if (tab !== 'data_center') {
      delete query.view
      activeDataCenterView.value = null
    } else if (typeof query.view !== 'string' || !isDataCenterView(query.view)) {
      const defaultView = defaultDataCenterView(
        can('scope.global') && can('tab.data_center.view')
      )
      query.view = defaultView
      activeDataCenterView.value = defaultView
    }
    if (tab !== current || route.query.view !== query.view) {
      void router.replace({ query })
    }
    emitTabActivated()
  })

  watch(
    () => options.tabs.value.map((tab) => tab.name),
    (names) => {
      if (names.length === 0) {
        return
      }
      if (!names.includes(activeTab.value)) {
        activeTab.value = names[0]
        void router.replace({ query: { ...route.query, tab: names[0] } })
      }
    },
    { immediate: true }
  )

  watch(
    () => route.query.organization_id,
    () => {
      const parsed = parseRouteOrgId(route.query.organization_id)
      if (parsed !== selectedOrgId.value) {
        selectedOrgId.value = parsed
      }
    }
  )

  watch(selectedOrgId, (orgId, previousOrgId) => {
    if (orgId !== previousOrgId) {
      eventBus.emit('admin:org_selected', { orgId })
    }

    if (!authStore.isSuperAdmin) {
      return
    }

    const current = route.query.organization_id
    const next = orgId == null ? undefined : String(orgId)
    const currentNorm =
      typeof current === 'string' && current.trim() ? current : undefined
    if (next === currentNorm) {
      return
    }

    const query = { ...route.query }
    if (next == null) {
      delete query.organization_id
    } else {
      query.organization_id = next
    }
    void router.replace({ query })
  })

  emitTabActivated()

  return {
    activeTab,
    activeSubtab,
    activeDataCenterView,
    selectedOrgId,
  }
}
