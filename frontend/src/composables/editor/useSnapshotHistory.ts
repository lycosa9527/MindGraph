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

export type SnapshotTakeResult =
  | { ok: true; snapshot: SnapshotMetadata }
  | { ok: false; status: number; message: string }

export type SnapshotRecallResult =
  | { ok: true; spec: Record<string, unknown> }
  | { ok: false; status: number; message: string }

export type SnapshotDeleteResult = { ok: true } | { ok: false; status: number; message: string }

interface SnapshotRecallResponse {
  version_number: number
  spec: Record<string, unknown>
}

interface SnapshotListResponse {
  snapshots: SnapshotMetadata[]
}

function detailToString(detail: unknown): string {
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    if (first && typeof first === 'object' && 'msg' in first) {
      return String((first as { msg: unknown }).msg)
    }
  }
  return ''
}

async function readErrorDetail(res: Response): Promise<string> {
  try {
    const text = await res.text()
    if (!text) {
      return ''
    }
    const data = JSON.parse(text) as { detail?: unknown }
    return detailToString(data.detail)
  } catch {
    return ''
  }
}

// Singleton state — persists across component mounts within the same page session.
const snapshots = ref<SnapshotMetadata[]>([])
const isTaking = ref(false)
const activeSnapshotVersion = ref<number | null>(null)

async function loadSnapshots(diagramId: string): Promise<void> {
  try {
    const res = await authFetch(`/api/diagrams/${diagramId}/snapshots`)
    if (res.status === 404) {
      snapshots.value = []
      return
    }
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
): Promise<SnapshotTakeResult | null> {
  if (isTaking.value) {
    return null
  }
  isTaking.value = true
  try {
    const res = await authFetch(`/api/diagrams/${diagramId}/snapshots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spec }),
    })
    if (!res.ok) {
      const message = await readErrorDetail(res)
      console.warn('[SnapshotHistory] takeSnapshot failed:', res.status, message)
      return { ok: false, status: res.status, message }
    }
    const snapshot: SnapshotMetadata = await res.json()
    await loadSnapshots(diagramId)
    return { ok: true, snapshot }
  } catch (err) {
    console.warn('[SnapshotHistory] takeSnapshot error:', err)
    return { ok: false, status: 0, message: '' }
  } finally {
    isTaking.value = false
  }
}

async function recallSnapshot(
  diagramId: string,
  versionNumber: number
): Promise<SnapshotRecallResult> {
  try {
    const res = await authFetch(`/api/diagrams/${diagramId}/snapshots/${versionNumber}/recall`, {
      method: 'POST',
    })
    if (!res.ok) {
      const message = await readErrorDetail(res)
      console.warn('[SnapshotHistory] recallSnapshot failed:', res.status, message)
      return { ok: false, status: res.status, message }
    }
    const data: SnapshotRecallResponse = await res.json()
    return { ok: true, spec: data.spec }
  } catch (err) {
    console.warn('[SnapshotHistory] recallSnapshot error:', err)
    return { ok: false, status: 0, message: '' }
  }
}

async function deleteSnapshot(
  diagramId: string,
  versionNumber: number
): Promise<SnapshotDeleteResult> {
  try {
    const res = await authFetch(`/api/diagrams/${diagramId}/snapshots/${versionNumber}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const message = await readErrorDetail(res)
      console.warn('[SnapshotHistory] deleteSnapshot failed:', res.status, message)
      return { ok: false, status: res.status, message }
    }
    const data: SnapshotListResponse = await res.json()
    snapshots.value = data.snapshots
    if (activeSnapshotVersion.value === versionNumber) {
      activeSnapshotVersion.value = null
    }
    return { ok: true }
  } catch (err) {
    console.warn('[SnapshotHistory] deleteSnapshot error:', err)
    return { ok: false, status: 0, message: '' }
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
