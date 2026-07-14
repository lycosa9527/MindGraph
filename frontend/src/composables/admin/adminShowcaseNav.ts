/**
 * Showcase admin panel navigation.
 */
export const SHOWCASE_SUBTABS = [
  'dashboard',
  'published',
  'moderation',
  'publish',
  'fields',
  'permissions',
] as const

export type ShowcaseSubtab = (typeof SHOWCASE_SUBTABS)[number]

export const SHOWCASE_QUEUES = ['pending', 'rejected'] as const
export type ShowcaseQueue = (typeof SHOWCASE_QUEUES)[number]

export function isShowcaseSubtab(value: string): value is ShowcaseSubtab {
  return (SHOWCASE_SUBTABS as readonly string[]).includes(value)
}

export function isShowcaseQueue(value: string): value is ShowcaseQueue {
  return (SHOWCASE_QUEUES as readonly string[]).includes(value)
}

export function defaultShowcaseSubtab(): ShowcaseSubtab {
  return 'dashboard'
}

export function defaultShowcaseQueue(): ShowcaseQueue {
  return 'pending'
}

export function showcaseSubtabLabelKey(subtab: ShowcaseSubtab): string {
  const map: Record<ShowcaseSubtab, string> = {
    dashboard: 'admin.showcase.subtab.dashboard',
    published: 'admin.showcase.subtab.published',
    moderation: 'admin.showcase.subtab.moderation',
    publish: 'admin.showcase.subtab.publish',
    fields: 'admin.showcase.subtab.fields',
    permissions: 'admin.showcase.subtab.permissions',
  }
  return map[subtab]
}

export function showcaseQueueLabelKey(queue: ShowcaseQueue): string {
  const map: Record<ShowcaseQueue, string> = {
    pending: 'admin.showcase.subtab.pending',
    rejected: 'admin.showcase.subtab.rejected',
  }
  return map[queue]
}

export function resolveShowcaseSubtab(raw: unknown): ShowcaseSubtab {
  if (typeof raw === 'string' && isShowcaseSubtab(raw)) {
    return raw
  }
  return defaultShowcaseSubtab()
}

export function resolveShowcaseQueue(raw: unknown): ShowcaseQueue {
  if (typeof raw === 'string' && isShowcaseQueue(raw)) {
    return raw
  }
  return defaultShowcaseQueue()
}

export const SHOWCASE_STAFF_PERMISSIONS = [
  'showcase.dashboard.view',
  'showcase.review',
  'showcase.delete',
  'showcase.recommend',
  'showcase.publish_proxy',
  'showcase.fields.manage',
] as const

export type ShowcaseStaffPermission = (typeof SHOWCASE_STAFF_PERMISSIONS)[number]

export function showcaseStaffPermissionLabelKey(perm: ShowcaseStaffPermission): string {
  return `admin.showcase.perm.${perm.replace(/\./g, '_')}`
}
