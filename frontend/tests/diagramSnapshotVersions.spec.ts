import { describe, expect, it } from 'vitest'

import {
  CURRENT_DIAGRAM_VERSION,
  activeSnapshotVersionAfterDelete,
  canMutateDiagramSnapshots,
  canProceedAfterVersionJumpPersist,
  formatSnapshotCreatedAt,
  newestSnapshotIdentity,
  shouldPersistBeforeVersionJump,
  snapshotDisplayLabel,
  snapshotsNewestFirst,
} from '@/composables/editor/diagramSnapshotVersions'
import type { SnapshotMetadata } from '@/composables/editor/useSnapshotHistory'

function snap(version: number): SnapshotMetadata {
  return { id: version, version_number: version, created_at: `2026-01-0${version}T00:00:00Z` }
}

describe('diagramSnapshotVersions', () => {
  it('keeps newest snapshots first so oldest stay at the bottom', () => {
    expect(
      snapshotsNewestFirst([snap(1), snap(3), snap(2)]).map((row) => row.version_number)
    ).toEqual([3, 2, 1])
  })

  it('persists only when the canvas fingerprint is ahead of the last save', () => {
    expect(shouldPersistBeforeVersionJump({ canvasAheadOfLastSave: true })).toBe(true)
    expect(shouldPersistBeforeVersionJump({ canvasAheadOfLastSave: false })).toBe(false)
  })

  it('blocks collab guests and unknown owners from mutating snapshots', () => {
    expect(
      canMutateDiagramSnapshots({ collabSessionActive: false, isDiagramOwner: undefined })
    ).toBe(true)
    expect(canMutateDiagramSnapshots({ collabSessionActive: true, isDiagramOwner: true })).toBe(
      true
    )
    expect(canMutateDiagramSnapshots({ collabSessionActive: true, isDiagramOwner: false })).toBe(
      false
    )
    expect(
      canMutateDiagramSnapshots({ collabSessionActive: true, isDiagramOwner: undefined })
    ).toBe(false)
  })

  it('lets a failed persist continue only when collab owns durability', () => {
    expect(canProceedAfterVersionJumpPersist({ saved: true, reason: 'success' }, false)).toBe(true)
    expect(
      canProceedAfterVersionJumpPersist({ saved: false, reason: 'skipped_guards' }, true)
    ).toBe(true)
    expect(
      canProceedAfterVersionJumpPersist({ saved: false, reason: 'skipped_guards' }, false)
    ).toBe(false)
    expect(canProceedAfterVersionJumpPersist({ saved: false, reason: 'error' }, true)).toBe(false)
  })

  it('treats naive backend timestamps as UTC', () => {
    const label = formatSnapshotCreatedAt('2026-03-24T10:00:00', 'en-US')
    expect(label).toContain('2026')
    expect(formatSnapshotCreatedAt('', 'en')).toBe('')
    expect(formatSnapshotCreatedAt('not-a-date', 'en')).toBe('')
  })

  it('uses 0 as the current-version restore sentinel', () => {
    expect(CURRENT_DIAGRAM_VERSION).toBe(0)
  })

  it('identifies the newest snapshot even when the list stays at the cap', () => {
    const before = [snap(1), snap(2)]
    const afterCap = [{ id: 99, version_number: 2, created_at: '2026-01-09T00:00:00Z' }, snap(1)]
    expect(newestSnapshotIdentity(before)).toBe('2:2026-01-02T00:00:00Z')
    expect(newestSnapshotIdentity(afterCap)).toBe('99:2026-01-09T00:00:00Z')
    expect(newestSnapshotIdentity([])).toBe('')
  })

  it('prefers a trimmed title over the Snapshot {n} fallback', () => {
    expect(snapshotDisplayLabel({ version_number: 2, title: '  Draft  ' }, 'Snapshot 2')).toBe(
      'Draft'
    )
    expect(snapshotDisplayLabel({ version_number: 2, title: '   ' }, 'Snapshot 2')).toBe(
      'Snapshot 2'
    )
    expect(snapshotDisplayLabel({ version_number: 2, title: null }, 'Snapshot 2')).toBe(
      'Snapshot 2'
    )
  })

  it('remaps the active snapshot after a delete renumbers versions', () => {
    const before = [
      { id: 10, version_number: 1, created_at: 'a' },
      { id: 20, version_number: 2, created_at: 'b' },
      { id: 30, version_number: 3, created_at: 'c' },
    ]
    const afterDeleteOldest = [
      { id: 20, version_number: 1, created_at: 'b' },
      { id: 30, version_number: 2, created_at: 'c' },
    ]
    expect(activeSnapshotVersionAfterDelete(3, before, afterDeleteOldest)).toBe(2)
    expect(activeSnapshotVersionAfterDelete(1, before, afterDeleteOldest)).toBeNull()
    expect(activeSnapshotVersionAfterDelete(null, before, afterDeleteOldest)).toBeNull()
  })
})
