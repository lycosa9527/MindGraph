/**
 * Workshop Chat access (aligned with server `user_has_feature_access` / `can_access_workshop_chat`).
 *
 * Uses `feature_org_access.feature_workshop_chat` when present; otherwise falls back to
 * `workshop_chat_preview_org_ids` (legacy env preview list).
 */
import type { FeatureOrgAccessEntry } from '@/stores/featureFlags'

export function userCanAccessWorkshopChat(
  isAdminOrManager: boolean,
  schoolId: string | undefined,
  userId: string | undefined,
  previewOrgIds: number[],
  accessEntry: FeatureOrgAccessEntry | undefined,
): boolean {
  if (isAdminOrManager) {
    return true
  }
  if (accessEntry === undefined) {
    if (!schoolId) {
      return false
    }
    const n = Number(schoolId)
    if (Number.isNaN(n) || !Number.isInteger(n)) {
      return false
    }
    return previewOrgIds.includes(n)
  }
  if (!accessEntry.restrict) {
    return true
  }
  const oidRaw = schoolId != null && schoolId !== '' ? Number(schoolId) : NaN
  const uidRaw = userId != null && userId !== '' ? Number(userId) : NaN
  const okOrg =
    Number.isInteger(oidRaw) && oidRaw > 0 && accessEntry.organization_ids.includes(oidRaw)
  const okUser =
    Number.isInteger(uidRaw) && uidRaw > 0 && accessEntry.user_ids.includes(uidRaw)
  return okOrg || okUser
}
