/**
 * Workshop Chat access (aligned with server `user_has_feature_access` / `can_access_workshop_chat`).
 *
 * Superadmins pass. Everyone else must belong to `workshop_chat_preview_org_ids`
 * when that list is non-empty, then `feature_org_access.feature_workshop_chat`
 * when a DB row exists.
 */
import type { FeatureOrgAccessEntry } from '@/stores/featureFlags'

function parsePositiveInt(raw: string | undefined): number | null {
  if (raw == null || raw === '') {
    return null
  }
  const n = Number(raw)
  if (Number.isNaN(n) || !Number.isInteger(n) || n <= 0) {
    return null
  }
  return n
}

function orgInPreviewList(schoolId: string | undefined, previewOrgIds: number[]): boolean {
  if (previewOrgIds.length === 0) {
    return true
  }
  const orgId = parsePositiveInt(schoolId)
  return orgId != null && previewOrgIds.includes(orgId)
}

export function userCanAccessWorkshopChat(
  isSuperAdmin: boolean,
  schoolId: string | undefined,
  userId: string | undefined,
  previewOrgIds: number[],
  accessEntry: FeatureOrgAccessEntry | undefined
): boolean {
  if (isSuperAdmin) {
    return true
  }
  if (!orgInPreviewList(schoolId, previewOrgIds)) {
    return false
  }
  if (accessEntry === undefined) {
    return previewOrgIds.length > 0
  }
  if (!accessEntry.restrict) {
    return true
  }
  const orgId = parsePositiveInt(schoolId)
  const uid = parsePositiveInt(userId)
  const okOrg = orgId != null && accessEntry.organization_ids.includes(orgId)
  const okUser = uid != null && accessEntry.user_ids.includes(uid)
  return okOrg || okUser
}
