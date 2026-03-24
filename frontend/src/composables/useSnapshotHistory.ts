/**
 * useSnapshotHistory - Manage point-in-time diagram snapshots
 *
 * Each snapshot captures the full diagram spec (without LLM results).
 * Snapshots are persisted to the backend DB with a max of 10 per diagram.
 * Module-level singleton state survives component re-mounts within a session.
 */
import { ref } from 'vue'

import { authFetch } from '@/utils/api'

export interface SnapshotMetadata {
  id: number
  version_number: number
  created_at: string
}

interface SnapshotRecallResponse {
  version_number: number
  spec: Record<string, unknown>
}

interface SnapshotListResponse {
  snapshots: SnapshotMetadata[]
}

// Singleton state — persists across component mounts within the same page session.
const snapshots = ref<SnapshotMetadata[]>([])
const isTaking = ref(false)
const activeSnapshotVersion = ref<number | null>(null)

async function loadSnapshots(diagramId: string): Promise<void> {
  try {
    const res = await authFetch(`/api/diagrams/${diagramId}/snapshots`)
    if (!res.ok) {
      console.warn('[SnapshotHistory] loadSnapshots failed:', res.status)
      return
    }
    const data: SnapshotListResponse = await res.json()
    snapshots.value = data.snapshots
  } catch (err) {
    console.warn('[SnapshotHistory] loadSnapshots error:', err)
  }
}

async function takeSnapshot(
  diagramId: string,
  spec: Record<string, unknown>
): Promise<SnapshotMetadata | null> {
  if (isTaking.value) return null
  isTaking.value = true
  try {
    const res = await authFetch(`/api/diagrams/${diagramId}/snapshots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spec }),
    })
    if (!res.ok) {
      console.warn('[SnapshotHistory] takeSnapshot failed:', res.status)
      return null
    }
    const snapshot: SnapshotMetadata = await res.json()
    // Refresh the list so the badge count is accurate (handles eviction of oldest)
    await loadSnapshots(diagramId)
    return snapshot
  } catch (err) {
    console.warn('[SnapshotHistory] takeSnapshot error:', err)
    return null
  } finally {
    isTaking.value = false
  }
}

async function recallSnapshot(
  diagramId: string,
  versionNumber: number
): Promise<Record<string, unknown> | null> {
  try {
    const res = await authFetch(
      `/api/diagrams/${diagramId}/snapshots/${versionNumber}/recall`,
      { method: 'POST' }
    )
    if (!res.ok) {
      console.warn('[SnapshotHistory] recallSnapshot failed:', res.status)
      return null
    }
    const data: SnapshotRecallResponse = await res.json()
    return data.spec
  } catch (err) {
    console.warn('[SnapshotHistory] recallSnapshot error:', err)
    return null
  }
}

async function deleteSnapshot(
  diagramId: string,
  versionNumber: number
): Promise<boolean> {
  try {
    const res = await authFetch(
      `/api/diagrams/${diagramId}/snapshots/${versionNumber}`,
      { method: 'DELETE' }
    )
    if (!res.ok) {
      console.warn('[SnapshotHistory] deleteSnapshot failed:', res.status)
      return false
    }
    const data: SnapshotListResponse = await res.json()
    snapshots.value = data.snapshots
    if (activeSnapshotVersion.value === versionNumber) {
      activeSnapshotVersion.value = null
    }
    return true
  } catch (err) {
    console.warn('[SnapshotHistory] deleteSnapshot error:', err)
    return false
  }
}

function setActiveVersion(version: number | null): void {
  activeSnapshotVersion.value = version
}

function clearSnapshots(): void {
  snapshots.value = []
  activeSnapshotVersion.value = null
}

export function useSnapshotHistory() {
  return {
    snapshots,
    isTaking,
    activeSnapshotVersion,
    loadSnapshots,
    takeSnapshot,
    recallSnapshot,
    deleteSnapshot,
    setActiveVersion,
    clearSnapshots,
  }
}
