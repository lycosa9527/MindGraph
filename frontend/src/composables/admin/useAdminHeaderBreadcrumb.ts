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
import {
  defaultFeatureDevSubtab,
  featureDevSubtabLabelKey,
  resolveFeatureDevSubtab,
} from '@/composables/admin/adminFeatureDevNav'
import {
  defaultSettingsSubtab,
  isSettingsSubtab,
  settingsSubtabLabelKey,
} from '@/composables/admin/adminSettingsNav'
import { resolveShowcaseSubtab, showcaseSubtabLabelKey } from '@/composables/admin/adminShowcaseNav'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useAdminOrganizations } from '@/composables/queries'
import { useAdminPanelStore, useAuthStore } from '@/stores'
import { getRolePillStyle } from '@/utils/userRoleDisplay'

export interface AdminHeaderBreadcrumbSegment {
  /** Static chrome. Render with bilingual labels. */
  labelKey?: string
  /** Dynamic text (organization name, unknown role). Primary locale only. */
  label?: string
}

export function useAdminHeaderBreadcrumb(options: {
  activeTab: Ref<string>
  route: RouteLocationNormalizedLoaded
  tabs: ComputedRef<ReadonlyArray<{ name: string; labelKey: string }>>
  hasGlobalScope: Ref<boolean> | ComputedRef<boolean>
}) {
  const authStore = useAuthStore()
  const adminPanel = useAdminPanelStore()
  const { featureSmartResponse, featureTeacherUsage, featureKittyAgent, featureMindmateExport } =
    useFeatureFlags()
  const { effectiveOrgId, canViewSettingsSubtab } = useAdminAccess()
  const orgsQuery = useAdminOrganizations({
    enabled: computed(() => options.activeTab.value === 'users'),
  })
  const organizations = computed(() => orgsQuery.data.value ?? [])

  watch(
    () => options.activeTab.value,
    (tab) => {
      if (tab === 'users') {
        void orgsQuery.refetch()
      }
    },
    { immediate: true }
  )

  const usersTabOrgId = computed((): number | null => {
    const scoped = adminPanel.usersToolbar?.scopedOrgId
    if (scoped != null && Number.isFinite(scoped)) {
      return scoped
    }
    const filterVal = adminPanel.usersToolbar?.orgFilter
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
    const tabSegment: AdminHeaderBreadcrumbSegment = { labelKey: tab?.labelKey ?? 'admin.title' }

    if (options.activeTab.value === 'users') {
      const schoolName = usersTabOrgName.value
      if (schoolName) {
        return [tabSegment, { label: schoolName }]
      }
      return [tabSegment]
    }

    if (options.activeTab.value === 'data_center') {
      const raw = options.route.query.view
      const viewKey =
        typeof raw === 'string' && isDataCenterView(raw)
          ? raw
          : defaultDataCenterView(options.hasGlobalScope.value)
      const view = DATA_CENTER_VIEWS.find((item) => item.name === viewKey)
      if (view) {
        return [tabSegment, { labelKey: view.labelKey }]
      }
    }

    if (options.activeTab.value === 'feature_dev') {
      const featureDevVisibility = {
        canViewSettingsSubtab,
        featureSmartResponse: featureSmartResponse.value,
        featureTeacherUsage: featureTeacherUsage.value,
        featureKittyAgent: featureKittyAgent.value,
        featureMindmateExport: featureMindmateExport.value,
      }
      const subtabName =
        resolveFeatureDevSubtab(options.route.query.subtab as string, featureDevVisibility) ??
        defaultFeatureDevSubtab(featureDevVisibility)
      const subtabLabelKey = subtabName ? featureDevSubtabLabelKey(subtabName) : null
      if (subtabLabelKey) {
        return [tabSegment, { labelKey: subtabLabelKey }]
      }
    }

    if (options.activeTab.value === 'settings') {
      const raw = options.route.query.subtab
      const subtabName =
        typeof raw === 'string' && isSettingsSubtab(raw) ? raw : defaultSettingsSubtab()
      const subtabLabelKey = settingsSubtabLabelKey(subtabName)
      if (subtabLabelKey) {
        if (subtabName === 'roles') {
          const activeRole = adminPanel.rolesToolbar?.activeRoleTab
          const roleStyle = activeRole ? getRolePillStyle(activeRole) : null
          if (roleStyle) {
            return [tabSegment, { labelKey: subtabLabelKey }, { labelKey: roleStyle.labelKey }]
          }
          if (activeRole) {
            return [tabSegment, { labelKey: subtabLabelKey }, { label: activeRole }]
          }
        }
        return [tabSegment, { labelKey: subtabLabelKey }]
      }
    }

    if (options.activeTab.value === 'showcase') {
      const subtabName = resolveShowcaseSubtab(options.route.query.subtab)
      return [tabSegment, { labelKey: showcaseSubtabLabelKey(subtabName) }]
    }

    return [tabSegment]
  })
}
