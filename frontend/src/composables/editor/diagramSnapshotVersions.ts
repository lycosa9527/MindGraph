/**
 * Diagram snapshot list order, persist-before-switch, and display helpers.
 */
import type { SnapshotMetadata } from '@/composables/editor/useSnapshotHistory'

/** Sentinel used while restoring the live (non-snapshot) canvas. */
export const CURRENT_DIAGRAM_VERSION = 0

export function snapshotsNewestFirst(snapshots: readonly SnapshotMetadata[]): SnapshotMetadata[] {
  return [...snapshots].sort((left, right) => right.version_number - left.version_number)
}

/** Identity of the newest row so a take at the 10-snapshot cap still registers. */
export function newestSnapshotIdentity(snapshots: readonly SnapshotMetadata[]): string {
  if (snapshots.length === 0) {
    return ''
  }
  const newest = snapshotsNewestFirst(snapshots)[0]
  return `${newest.id}:${newest.created_at}`
}

/**
 * Persist only when the canvas fingerprint is ahead of the last save.
 * Do not use the autosave `isDirty` flag: loading a snapshot can mark dirty
 * while suppressed, and flushing that would overwrite the saved current.
 */
export function shouldPersistBeforeVersionJump(options: {
  canvasAheadOfLastSave: boolean
}): boolean {
  return options.canvasAheadOfLastSave
}

/** Hosts may mutate snapshots; collab guests (or unknown owner) must not. */
export function canMutateDiagramSnapshots(options: {
  collabSessionActive: boolean
  isDiagramOwner: boolean | undefined
}): boolean {
  if (!options.collabSessionActive) {
    return true
  }
  return options.isDiagramOwner === true
}

export function canProceedAfterVersionJumpPersist(
  result: { saved: boolean; reason?: string },
  collabOwnsPersist: boolean
): boolean {
  if (result.saved) {
    return true
  }
  return result.reason === 'skipped_guards' && collabOwnsPersist
}

/** Backend stores UTC datetimes without a timezone suffix. */
export function formatSnapshotCreatedAt(iso: string, locale: string): string {
  const trimmed = iso.trim()
  if (!trimmed) {
    return ''
  }
  const hasZone = /Z$|[+-]\d{2}:?\d{2}$/.test(trimmed)
  const parsed = new Date(hasZone ? trimmed : `${trimmed}Z`)
  if (Number.isNaN(parsed.getTime())) {
    return ''
  }
  try {
    return parsed.toLocaleString(locale)
  } catch {
    return parsed.toLocaleString()
  }
}
