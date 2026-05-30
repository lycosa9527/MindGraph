/**
 * Admin school selection for the school dashboard (shared page + management header).
 */
import { computed, ref } from 'vue'

import {
  getCurrentUserOrganizationId,
  resolveDefaultOrganizationId,
  userHasOrgOnlyPanelScope,
} from '@/composables/admin/useCurrentUserOrganizationId'
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

  const isSuperAdminPicker = computed(() => authStore.isSuperAdmin)

  const isOrgLocked = computed(() => userHasOrgOnlyPanelScope())

  const effectiveOrgId = computed(() => {
    if (isOrgLocked.value) {
      return getCurrentUserOrganizationId()
    }
    if (isSuperAdminPicker.value && selectedOrgId.value != null) {
      return selectedOrgId.value
    }
    return getCurrentUserOrganizationId()
  })

  const showPicker = computed(
    () => isSuperAdminPicker.value && organizations.value.length > 0
  )

  async function loadOrganizations(): Promise<void> {
    if (!isSuperAdminPicker.value) {
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
    if (isSuperAdminPicker.value && selectedOrgId.value == null) {
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
    showPicker,
    isOrgLocked,
    loadOrganizations,
    syncSelectedOrgFromUser,
  }
}
