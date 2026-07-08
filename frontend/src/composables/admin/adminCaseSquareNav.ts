/**
 * Case Square admin panel navigation.
 */
export const CASE_SQUARE_SUBTABS = [
  'dashboard',
  'published',
  'moderation',
  'publish',
  'fields',
  'permissions',
] as const

export type CaseSquareSubtab = (typeof CASE_SQUARE_SUBTABS)[number]

export const CASE_SQUARE_QUEUES = ['pending', 'rejected'] as const
export type CaseSquareQueue = (typeof CASE_SQUARE_QUEUES)[number]

export function isCaseSquareSubtab(value: string): value is CaseSquareSubtab {
  return (CASE_SQUARE_SUBTABS as readonly string[]).includes(value)
}

export function isCaseSquareQueue(value: string): value is CaseSquareQueue {
  return (CASE_SQUARE_QUEUES as readonly string[]).includes(value)
}

export function defaultCaseSquareSubtab(): CaseSquareSubtab {
  return 'dashboard'
}

export function defaultCaseSquareQueue(): CaseSquareQueue {
  return 'pending'
}

export function caseSquareSubtabLabelKey(subtab: CaseSquareSubtab): string {
  const map: Record<CaseSquareSubtab, string> = {
    dashboard: 'admin.caseSquare.subtab.dashboard',
    published: 'admin.caseSquare.subtab.published',
    moderation: 'admin.caseSquare.subtab.moderation',
    publish: 'admin.caseSquare.subtab.publish',
    fields: 'admin.caseSquare.subtab.fields',
    permissions: 'admin.caseSquare.subtab.permissions',
  }
  return map[subtab]
}

export function caseSquareQueueLabelKey(queue: CaseSquareQueue): string {
  const map: Record<CaseSquareQueue, string> = {
    pending: 'admin.caseSquare.subtab.pending',
    rejected: 'admin.caseSquare.subtab.rejected',
  }
  return map[queue]
}

export function resolveCaseSquareSubtab(raw: unknown): CaseSquareSubtab {
  if (typeof raw === 'string' && isCaseSquareSubtab(raw)) {
    return raw
  }
  return defaultCaseSquareSubtab()
}

export function resolveCaseSquareQueue(raw: unknown): CaseSquareQueue {
  if (typeof raw === 'string' && isCaseSquareQueue(raw)) {
    return raw
  }
  return defaultCaseSquareQueue()
}

export const CASE_SQUARE_STAFF_PERMISSIONS = [
  'case_square.dashboard.view',
  'case_square.review',
  'case_square.delete',
  'case_square.recommend',
  'case_square.publish_proxy',
  'case_square.fields.manage',
] as const

export type CaseSquareStaffPermission = (typeof CASE_SQUARE_STAFF_PERMISSIONS)[number]

export function caseSquareStaffPermissionLabelKey(perm: CaseSquareStaffPermission): string {
  return `admin.caseSquare.perm.${perm.replace(/\./g, '_')}`
}
