import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'
import { isOfficeEmbedDesktop } from '@/utils/officeEmbed'

export const TRAINING_RAIL_PAGE_SIZE = 50
export const TRAINING_RAIL_WINDOW = 50

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

export function windowedRosterRows<T>(rows: T[], windowSize = TRAINING_RAIL_WINDOW): T[] {
  return rows.length > windowSize ? rows.slice(0, windowSize) : rows
}
