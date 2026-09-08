import type { TrainingSnapshot } from '@/types/training'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'
import { isMobileRoutePath } from '@/utils/mobileRouteRedirect'
import { isOfficeEmbedDesktop } from '@/utils/officeEmbed'

export const TRAINING_RAIL_PAGE_SIZE = 50
export const TRAINING_RAIL_WINDOW = 50
/** Visible rows before the friends list scrolls. */
export const TRAINING_RAIL_VISIBLE_ROWS = 15

export function emptyTrainingSnapshot(): TrainingSnapshot {
  return {
    state: 'none',
    session_id: null,
    org_id: null,
    seq: 0,
    diagram_type: null,
    topic_options: [],
    instructor_id: null,
    instructor_name: null,
    course_id: null,
    step_index: 0,
    step_count: 0,
    step: null,
    pull_users: true,
  }
}

/** Above lesson marks (4200) and the instructor pad (4300). */
export const TRAINING_DIALOG_Z = 4500

export function isTrainingRemotePath(path: string): boolean {
  return path === '/m/training' || path.startsWith('/m/training/')
}

export function shouldHideTrainingDesktopChrome(path: string): boolean {
  return isMobileRoutePath(path) || path.startsWith('/training/builder')
}

export function shouldHoldTrainingHostOnMobile(
  path: string,
  instructorId: number | null,
  userId: number | null | undefined
): boolean {
  if (isTrainingRemotePath(path)) return true
  if (!isMobileRoutePath(path)) return false
  const mine = Number(userId)
  const host = Number(instructorId)
  return mine > 0 && host > 0 && mine === host
}

export function shouldSkipTrainingFollow(
  pathname = typeof window === 'undefined' ? '' : window.location.pathname
): boolean {
  if (isMindgraphHeadlessExportSession()) return true
  if (isOfficeEmbedDesktop()) return true
  return pathname === '/export-render'
}

export function trainingEventsUrl(orgId: number | null, isPlatformLevel: boolean): string {
  if (orgId != null && isPlatformLevel) {
    return `/api/training/events?org_id=${orgId}`
  }
  return '/api/training/events'
}

export function canOpenTrainingEvents(
  isPlatformLevel: boolean,
  orgId: number | null
): boolean {
  if (!isPlatformLevel) return true
  return orgId != null
}

export function isTrainingRailVisible(isPlatformLevel: boolean, isActive: boolean): boolean {
  return isPlatformLevel && isActive
}

export function isTrainingOwnerHeartbeat(
  isPlatformLevel: boolean,
  isActive: boolean,
  userId: number,
  instructorId: number | null
): boolean {
  if (!isPlatformLevel || !isActive || instructorId == null) return false
  return userId > 0 && userId === Number(instructorId)
}

export function windowedRosterRows<T>(rows: T[], windowSize = TRAINING_RAIL_WINDOW): T[] {
  return rows.length > windowSize ? rows.slice(0, windowSize) : rows
}
