/**
 * Admin school selection for the school dashboard (shared page + management header).
 */
import { computed, ref } from 'vue'

import {
  getCurrentUserOrganizationId,
  resolveDefaultOrganizationId,
  userHasOrgOnlyPanelScope,
} from '@/composables/admin/useCurrentUserOrganizationId'
import { fallbackCapabilitiesForRole } from '@/utils/adminCapabilities'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'

export interface SchoolDashboardOrganization {
  id: number
  name: string
  code: string
}

const organizations = ref<SchoolDashboardOrganization[]>([])
const selectedOrgId = ref<number | null>(null)

export function useSchoolDashboardOrgPicker() {
  const authStore = useAuthStore()

  const canPickOrganization = computed(() => {
    const caps =
      authStore.adminCapabilitiesPayload?.capabilities ??
      fallbackCapabilitiesForRole(authStore.userRole)
    return caps.includes('scope.global')
  })

  const isOrgLocked = computed(() => userHasOrgOnlyPanelScope())

  const effectiveOrgId = computed(() => {
    if (isOrgLocked.value) {
      return getCurrentUserOrganizationId()
    }
    if (canPickOrganization.value && selectedOrgId.value != null) {
      return selectedOrgId.value
    }
    return getCurrentUserOrganizationId()
  })

  const showPicker = computed(
    () => canPickOrganization.value && organizations.value.length > 0
  )

  const effectiveOrgName = computed(() => {
    const orgId = effectiveOrgId.value
    if (orgId == null) {
      return ''
    }
    const fromList = organizations.value.find((org) => org.id === orgId)?.name
    if (fromList) {
      return fromList
    }
    const userSchoolId = authStore.user?.schoolId
    if (userSchoolId != null && String(userSchoolId) === String(orgId)) {
      return (authStore.user?.schoolName ?? '').trim()
    }
    return ''
  })

  async function loadOrganizations(): Promise<void> {
    if (!canPickOrganization.value) {
      return
    }
    const res = await apiRequest('/api/auth/admin/organizations')
    if (!res.ok) {
      return
    }
    const data = await res.json()
    organizations.value = data.map((org: SchoolDashboardOrganization) => ({
      id: org.id,
      name: org.name,
      code: org.code,
    }))
    if (organizations.value.length > 0 && selectedOrgId.value == null) {
      selectedOrgId.value = resolveDefaultOrganizationId(organizations.value)
    }
  }

  function syncSelectedOrgFromUser(): void {
    const userOrg = getCurrentUserOrganizationId()
    if (userOrg == null) {
      return
    }
    if (isOrgLocked.value) {
      selectedOrgId.value = userOrg
      return
    }
    if (canPickOrganization.value && selectedOrgId.value == null) {
      if (
        organizations.value.length === 0 ||
        organizations.value.some((org) => org.id === userOrg)
      ) {
        selectedOrgId.value = userOrg
      }
    }
  }

  return {
    organizations,
    selectedOrgId,
    effectiveOrgId,
    effectiveOrgName,
    showPicker,
    canPickOrganization,
    isOrgLocked,
    loadOrganizations,
    syncSelectedOrgFromUser,
  }
}
