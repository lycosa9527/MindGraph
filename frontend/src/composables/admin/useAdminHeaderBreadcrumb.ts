/**
 * Management panel header breadcrumb (parent tab / nested view or sub-tab).
 */
import type { ComputedRef, Ref } from 'vue'
import { computed, watch } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'

import {
  DATA_CENTER_VIEWS,
  defaultDataCenterView,
  isDataCenterView,
} from '@/composables/admin/adminDataCenterViews'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useAdminOrganizationsList } from '@/composables/admin/useAdminOrganizationsList'
import { useAdminUsersHeaderToolbarModel } from '@/composables/admin/useAdminUsersHeaderToolbar'
import { ADMIN_SETTINGS_SUBTAB_CONFIG } from '@/composables/admin/adminSettingsSubtabs'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'

export interface AdminHeaderBreadcrumbSegment {
  label: string
}

export function useAdminHeaderBreadcrumb(options: {
  activeTab: Ref<string>
  route: RouteLocationNormalizedLoaded
  tabs: ComputedRef<ReadonlyArray<{ name: string; label: string }>>
  hasGlobalScope: Ref<boolean> | ComputedRef<boolean>
}) {
  const { t } = useLanguage()
  const authStore = useAuthStore()
  const toolbarModel = useAdminUsersHeaderToolbarModel()
  const { effectiveOrgId } = useAdminAccess()
  const { organizations, loadOrganizations } = useAdminOrganizationsList()

  watch(
    () => options.activeTab.value,
    (tab) => {
      if (tab === 'users') {
        void loadOrganizations()
      }
    },
    { immediate: true }
  )

  const usersTabOrgId = computed((): number | null => {
    const scoped = toolbarModel.value?.scopedOrgId?.value
    if (scoped != null && Number.isFinite(scoped)) {
      return scoped
    }
    const filterRef = toolbarModel.value?.orgFilter
    const filterVal = filterRef?.value
    if (filterVal !== undefined && filterVal !== '') {
      return Number(filterVal)
    }
    return effectiveOrgId.value
  })

  const usersTabOrgName = computed((): string | null => {
    const orgId = usersTabOrgId.value
    if (orgId == null || !Number.isFinite(orgId)) {
      return null
    }
    const fromList = organizations.value.find((org) => org.id === orgId)?.name
    if (fromList) {
      return fromList
    }
    const schoolId = authStore.user?.schoolId
    if (schoolId != null && Number(schoolId) === orgId) {
      const label = authStore.user?.schoolName
      return typeof label === 'string' && label.trim() ? label : null
    }
    return null
  })

  return computed((): AdminHeaderBreadcrumbSegment[] => {
    const tab = options.tabs.value.find((item) => item.name === options.activeTab.value)
    const tabLabel = tab?.label ?? t('admin.title')

    if (options.activeTab.value === 'users') {
      const schoolName = usersTabOrgName.value
      if (schoolName) {
        return [{ label: tabLabel }, { label: schoolName }]
      }
      return [{ label: tabLabel }]
    }

    if (options.activeTab.value === 'data_center') {
      const raw = options.route.query.view
      const viewKey =
        typeof raw === 'string' && isDataCenterView(raw)
          ? raw
          : defaultDataCenterView(options.hasGlobalScope.value)
      const view = DATA_CENTER_VIEWS.find((item) => item.name === viewKey)
      const childLabel = view ? t(view.labelKey) : null
      if (childLabel) {
        return [{ label: tabLabel }, { label: childLabel }]
      }
    }

    if (options.activeTab.value === 'settings') {
      const raw = options.route.query.subtab
      const subtabName = typeof raw === 'string' ? raw : 'features'
      const match = ADMIN_SETTINGS_SUBTAB_CONFIG.find((item) => item.name === subtabName)
      const childLabel = match ? t(match.labelKey) : null
      if (childLabel) {
        return [{ label: tabLabel }, { label: childLabel }]
      }
    }

    return [{ label: tabLabel }]
  })
}
