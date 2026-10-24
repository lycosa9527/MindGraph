/**
 * Format school-activity snapshot timestamps in Beijing wall clock.
 */
import { beijingWallClock, parseApiInstant } from '@/utils/beijingClock'

export function beijingCalendarParts(now: Date = new Date()): { year: number; month: number } {
  const wall = beijingWallClock(now)
  return { year: Number(wall.year), month: Number(wall.month) }
}

export function beijingCalendarYear(now: Date = new Date()): number {
  return beijingCalendarParts(now).year
}

export function formatBeijingSnapshotTime(isoUtc: string): string {
  const parsed = parseApiInstant(isoUtc)
  if (!parsed) {
    return isoUtc
  }
  const wall = beijingWallClock(parsed)
  return `${wall.year}-${wall.month}-${wall.day} ${wall.hour}:${wall.minute}`
}
