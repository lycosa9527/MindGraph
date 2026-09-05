import type { TrainingSnapshot } from '@/types/training'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'
import { isOfficeEmbedDesktop } from '@/utils/officeEmbed'

export const TRAINING_RAIL_PAGE_SIZE = 50
export const TRAINING_RAIL_WINDOW = 50

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
