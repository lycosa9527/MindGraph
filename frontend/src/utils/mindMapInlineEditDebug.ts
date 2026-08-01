/**
 * Opt-in post-add / inline-edit stage tracer.
 *
 * Enable:
 *   localStorage.setItem('mindgraph.debugMindMapInlineEdit', '1')
 *   // or in DEV: window.mindMapInlineEditDebug.enable()
 * then reload and press Enter / Tab.
 *
 * Console prefix: [MindMapInlineEdit]
 */
const STORAGE_KEY = 'mindgraph.debugMindMapInlineEdit'
const LOG_PREFIX = '[MindMapInlineEdit]'

export type MindMapInlineEditStage =
  | 'pending:arm'
  | 'pending:tryFocus'
  | 'pending:host-missing'
  | 'pending:host-found'
  | 'pending:edit_requested'
  | 'pending:awaiting-input'
  | 'pending:focus-stable'
  | 'pending:cleared'
  | 'pending:open-phase-done'
  | 'pending:cancel'
  | 'pending:max-attempts'
  | 'pending:selection-drift'
  | 'branch:pending-seen'
  | 'branch:session-open'
  | 'branch:session-skip'
  | 'edit:startEditing'
  | 'edit:start-blocked'
  | 'edit:opening'
  | 'edit:closed'
  | 'edit:blur-grace'
  | 'edit:watch-kill'
  | 'edit:unmount-closed'
  | 'edit:requested-handled'
  | 'edit:refocus'
  | 'writeback:repoke'
  | 'writeback:repoke-skip'
  | 'enter-guard:zombie-heal'

export type MindMapInlineEditStagePayload = {
  nodeId?: string | null
  pendingId?: string | null
  editingId?: string | null
  generation?: number
  attempt?: number
  reason?: string
  source?: string
  hasHost?: boolean
  hasInput?: boolean
  focused?: boolean
  localIsEditing?: boolean
  propsIsEditing?: boolean
  [key: string]: unknown
}

type StageRecord = {
  stage: MindMapInlineEditStage
  at: number
  payload: MindMapInlineEditStagePayload
}

const recentStages: StageRecord[] = []
const MAX_RECENT = 80

function nowMs(): number {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now()
  }
  return Date.now()
}

export function isMindMapInlineEditDebugEnabled(): boolean {
  if (typeof localStorage === 'undefined') return false
  return localStorage.getItem(STORAGE_KEY) === '1'
}

export function setMindMapInlineEditDebugEnabled(enabled: boolean): void {
  if (typeof localStorage === 'undefined') return
  if (enabled) localStorage.setItem(STORAGE_KEY, '1')
  else localStorage.setItem(STORAGE_KEY, '0')
}

export function markMindMapInlineEditStage(
  stage: MindMapInlineEditStage,
  payload: MindMapInlineEditStagePayload = {}
): void {
  const record: StageRecord = {
    stage,
    at: nowMs(),
    payload: { ...payload },
  }
  recentStages.push(record)
  if (recentStages.length > MAX_RECENT) {
    recentStages.splice(0, recentStages.length - MAX_RECENT)
  }
  if (!isMindMapInlineEditDebugEnabled()) return

  const t = Math.round(record.at * 10) / 10
  const node = payload.nodeId ?? payload.pendingId ?? payload.editingId ?? '-'
  const detail = payload.source ?? payload.reason
  const label = detail ? `${stage} (${detail})` : stage
  console.info(`${LOG_PREFIX} ${label}`, {
    t,
    node,
    ...payload,
  })
}

export function inspectMindMapInlineEditDebug(): void {
  console.info(`${LOG_PREFIX} inspect`, {
    enabled: isMindMapInlineEditDebugEnabled(),
    recent: recentStages.slice(-40),
  })
}

export function getMindMapInlineEditDebugRecent(): readonly StageRecord[] {
  return recentStages
}

declare global {
  interface Window {
    mindMapInlineEditDebug?: {
      enable: () => void
      disable: () => void
      inspect: () => void
      recent: () => readonly StageRecord[]
    }
  }
}

if (typeof window !== 'undefined' && import.meta.env.DEV) {
  window.mindMapInlineEditDebug = {
    enable: () => {
      setMindMapInlineEditDebugEnabled(true)
      console.info(`${LOG_PREFIX} enabled — reload not required; next Enter/Tab will log stages`)
    },
    disable: () => {
      setMindMapInlineEditDebugEnabled(false)
      console.info(`${LOG_PREFIX} disabled`)
    },
    inspect: inspectMindMapInlineEditDebug,
    recent: getMindMapInlineEditDebugRecent,
  }
}
