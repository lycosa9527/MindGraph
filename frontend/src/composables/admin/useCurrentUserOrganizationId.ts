/**
 * Resolve the signed-in user's primary organization for admin school pickers/filters.
 */
import { fallbackCapabilitiesForRole } from '@/utils/adminCapabilities'
import type { AdminCapability } from '@/utils/adminCapabilities'
import { useAuthStore } from '@/stores'

export function getCurrentUserOrganizationId(): number | null {
  const authStore = useAuthStore()
  const fromCapabilities = authStore.adminCapabilitiesPayload?.default_org_id
  if (fromCapabilities != null) {
    return fromCapabilities
  }
  const orgIds = authStore.adminCapabilitiesPayload?.org_ids
  if (orgIds != null && orgIds.length === 1) {
    return orgIds[0]
  }
  const schoolId = authStore.user?.schoolId
  if (schoolId != null && String(schoolId).trim() !== '') {
    const parsed = Number(schoolId)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

/** School managers (scope.org only) must not switch org in the UI — backend enforces the same. */
export function userHasOrgOnlyPanelScope(): boolean {
  const authStore = useAuthStore()
  const caps: AdminCapability[] =
    authStore.adminCapabilitiesPayload?.capabilities ??
    fallbackCapabilitiesForRole(authStore.userRole)
  return caps.includes('scope.org') && !caps.includes('scope.global')
}

export function resolveDefaultOrganizationId(
  organizations: ReadonlyArray<{ id: number }>,
  preferredId?: number | null
): number | null {
  if (organizations.length === 0) {
    return null
  }
  const preferred = preferredId ?? getCurrentUserOrganizationId()
  if (preferred != null && organizations.some((org) => org.id === preferred)) {
    return preferred
  }
  return organizations[0]?.id ?? null
}

export function resolveDefaultOrganizationFilter(
  organizations: ReadonlyArray<{ id: number }>,
  preferredId?: number | null
): number | '' {
  const id = resolveDefaultOrganizationId(organizations, preferredId)
  return id ?? ''
}
