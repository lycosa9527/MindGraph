/**
 * MindBot admin access (aligned with server `user_has_feature_access` for `feature_mindbot`).
 *
 * When `feature_org_access.feature_mindbot` is absent or not restrictive, school managers
 * with `requiresAdminOrManager` may open the page. When restrictive, the manager's school
 * or user id must be granted in Postgres (`feature_access_org_grants` / `feature_access_user_grants`).
 */
import type { FeatureOrgAccessEntry } from '@/stores/featureFlags'

export function userCanAccessMindbotAdmin(
  isAdmin: boolean,
  isManager: boolean,
  schoolId: string | undefined,
  userId: string | undefined,
  accessEntry: FeatureOrgAccessEntry | undefined
): boolean {
  if (isAdmin) {
    return true
  }
  if (!isManager) {
    return false
  }
  if (accessEntry === undefined) {
    return true
  }
  if (!accessEntry.restrict) {
    return true
  }
  const oidRaw = schoolId != null && schoolId !== '' ? Number(schoolId) : NaN
  const uidRaw = userId != null && userId !== '' ? Number(userId) : NaN
  const okOrg =
    Number.isInteger(oidRaw) && oidRaw > 0 && accessEntry.organization_ids.includes(oidRaw)
  const okUser = Number.isInteger(uidRaw) && uidRaw > 0 && accessEntry.user_ids.includes(uidRaw)
  return okOrg || okUser
}
