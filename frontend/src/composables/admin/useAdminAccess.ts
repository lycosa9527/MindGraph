/**

 * Admin panel access — capabilities, org scope, tab visibility.

 */

import { computed } from 'vue'



import { useRoute, useRouter } from 'vue-router'



import {

  type AdminCapability,

  fallbackCapabilitiesForRole,

  settingsSubtabRequiresCapabilities,

  tabEditCapability,

  tabRequiresCapabilities,

  canViewDataCenterTab,

  canViewFeatureDevTab,

  canViewUsersTab,

  isDataCenterTabReadOnly,

} from '@/utils/adminCapabilities'

import { useAuthStore } from '@/stores'



export function useAdminAccess() {

  const authStore = useAuthStore()

  const route = useRoute()

  const router = useRouter()



  const capabilities = computed((): AdminCapability[] => {
    const fromStore = authStore.adminCapabilitiesPayload?.capabilities
    const roleFallback = fallbackCapabilitiesForRole(authStore.userRole)

    if (fromStore?.length) {
      // Union with role fallback so new panel caps appear before backend restart.
      return [...new Set([...fromStore, ...roleFallback])] as AdminCapability[]
    }

    if (authStore.adminCapabilitiesLoaded) {
      return []
    }

    return roleFallback
  })



  const isReadOnly = computed(

    () =>

      authStore.adminCapabilitiesPayload?.read_only ??

      authStore.isPlatformBd

  )



  function canEditTab(tabKey: string): boolean {

    const editCap = tabEditCapability(tabKey)

    if (!editCap) {

      return false

    }

    return can(editCap)

  }



  function isTabReadOnly(tabKey: string): boolean {

    if (tabKey === 'invites' && canEditTab('invites')) {

      return false

    }

    if (tabKey === 'data_center') {

      return isDataCenterTabReadOnly(capabilities.value)

    }

    const editCap = tabEditCapability(tabKey)

    if (!editCap) {

      return isReadOnly.value

    }

    return !can(editCap)

  }



  const effectiveOrgId = computed((): number | null => {

    const fromApi = authStore.adminCapabilitiesPayload?.default_org_id

    if (authStore.isSchoolAdmin && fromApi != null) {

      return fromApi

    }

    if (authStore.isSchoolAdmin && authStore.user?.schoolId) {

      return Number(authStore.user.schoolId)

    }

    const queryOrg = route.query.organization_id

    if (typeof queryOrg === 'string' && queryOrg.trim()) {

      return Number(queryOrg)

    }

    return null

  })



  function can(cap: AdminCapability): boolean {

    return capabilities.value.includes(cap)

  }



  function canViewTab(tabKey: string): boolean {

    if (tabKey === 'data_center') {

      return canViewDataCenterTab(capabilities.value)

    }

    if (tabKey === 'feature_dev') {

      return canViewFeatureDevTab(capabilities.value)

    }

    if (tabKey === 'users') {

      return canViewUsersTab(capabilities.value)

    }

    const required = tabRequiresCapabilities(tabKey)

    return required.every((cap) => can(cap))

  }



  function canViewSettingsSubtab(subtab: string): boolean {

    const required = settingsSubtabRequiresCapabilities(subtab)

    return required.every((cap) => can(cap))

  }



  const visibleTabKeys = computed(() => {

    const keys = ['data_center', 'users', 'organizations', 'invites', 'billing', 'case_square', 'settings', 'feature_dev']

    return keys.filter((key) => canViewTab(key))

  })



  function adminQueryParams(): Record<string, string> {

    const orgId = effectiveOrgId.value

    if (orgId != null) {

      return { organization_id: String(orgId) }

    }

    return {}

  }



  async function loadCapabilities(): Promise<void> {

    await authStore.loadAdminCapabilities()

  }



  function ensureValidTab(activeTab: { value: string }): void {

    const names = visibleTabKeys.value

    if (names.length === 0) {

      return

    }

    if (!names.includes(activeTab.value)) {

      activeTab.value = names[0]

      void router.replace({ query: { ...route.query, tab: names[0] } })

    }

  }



  return {

    capabilities,

    capabilitiesLoaded: computed(() => authStore.adminCapabilitiesLoaded),

    isReadOnly,

    canEditTab,

    isTabReadOnly,

    effectiveOrgId,

    visibleTabKeys,

    can,

    canViewTab,

    canViewSettingsSubtab,

    adminQueryParams,

    loadCapabilities,

    ensureValidTab,

  }

}


