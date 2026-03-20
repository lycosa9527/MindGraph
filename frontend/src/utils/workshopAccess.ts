/**
 * Workshop Chat access (matches server can_access_workshop_chat rules).
 */

export function userCanAccessWorkshopChat(
  isAdminOrManager: boolean,
  schoolId: string | undefined,
  previewOrgIds: number[]
): boolean {
  if (isAdminOrManager) {
    return true
  }
  if (!schoolId) {
    return false
  }
  const n = Number(schoolId)
  if (Number.isNaN(n)) {
    return false
  }
  return previewOrgIds.includes(n)
}
