/**
 * Admin org scope — selected org, effective org for school-scoped views, org list for pickers.
 */
import { computed, watch } from 'vue'

import { storeToRefs } from 'pinia'

import {
  getCurrentUserOrganizationId,
  resolveDefaultOrganizationId,
  userHasOrgOnlyPanelScope,
} from '@/composables/admin/useCurrentUserOrganizationId'
import { useAdminOrganizations } from '@/composables/queries'
import { fallbackCapabilitiesForRole } from '@/utils/adminCapabilities'
import { useAdminPanelStore, useAuthStore } from '@/stores'

export function useAdminOrgScope() {
  const authStore = useAuthStore()
  const adminPanel = useAdminPanelStore()
  const { selectedOrgId } = storeToRefs(adminPanel)

  const canPickOrganization = computed(() => {
    const caps =
      authStore.adminCapabilitiesPayload?.capabilities ??
      fallbackCapabilitiesForRole(authStore.userRole)
    return caps.includes('scope.global')
  })

  const isOrgLocked = computed(() => userHasOrgOnlyPanelScope())

  const organizationsQuery = useAdminOrganizations({
    enabled: computed(() => canPickOrganization.value),
  })

  const organizations = computed(() => organizationsQuery.data.value ?? [])

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

  function ensureDefaultOrgSelection(): void {
    if (organizations.value.length > 0 && selectedOrgId.value == null) {
      selectedOrgId.value = resolveDefaultOrganizationId(organizations.value)
    }
  }

  async function refetchOrganizations(): Promise<void> {
    if (!canPickOrganization.value) {
      return
    }
    await organizationsQuery.refetch()
    ensureDefaultOrgSelection()
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

  watch(organizations, () => {
    ensureDefaultOrgSelection()
  })

  return {
    organizations,
    organizationsQuery,
    selectedOrgId,
    effectiveOrgId,
    effectiveOrgName,
    showPicker,
    canPickOrganization,
    isOrgLocked,
    refetchOrganizations,
    syncSelectedOrgFromUser,
  }
}
