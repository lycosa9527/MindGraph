/**
 * MindBot admin access (aligned with server `require_mindbot_admin_access` — superadmin only).
 */
import type { FeatureOrgAccessEntry } from '@/stores/featureFlags'

export function userCanAccessMindbotAdmin(
  isAdmin: boolean,
  _isManager: boolean,
  _schoolId: string | undefined,
  _userId: string | undefined,
  _accessEntry: FeatureOrgAccessEntry | undefined
): boolean {
  return isAdmin
}
