/**
 * Opt-in sibling-insert tracing.
 * localStorage mindgraph.debugMindMapSibling = '1'
 * or window.mindMapSiblingDebug.enable() in DEV.
 */
const STORAGE_KEY = 'mindgraph.debugMindMapSibling'

export type MindMapSiblingInsertFailure = {
  reason: string
  details: Record<string, unknown>
  at: number
}

let lastFailure: MindMapSiblingInsertFailure | null = null
let lastAttempt: Record<string, unknown> | null = null

export function isMindMapSiblingDebugEnabled(): boolean {
  if (typeof localStorage === 'undefined') return false
  return localStorage.getItem(STORAGE_KEY) === '1'
}

export function setMindMapSiblingDebugEnabled(enabled: boolean): void {
  if (typeof localStorage === 'undefined') return
  if (enabled) localStorage.setItem(STORAGE_KEY, '1')
  else localStorage.setItem(STORAGE_KEY, '0')
}

export function getLastMindMapSiblingInsertFailure(): MindMapSiblingInsertFailure | null {
  return lastFailure
}

export function getLastMindMapSiblingInsertAttempt(): Record<string, unknown> | null {
  return lastAttempt
}

export function recordMindMapSiblingInsertAttempt(details: Record<string, unknown>): void {
  lastAttempt = { ...details, at: Date.now() }
  lastFailure = null
  if (!isMindMapSiblingDebugEnabled()) return
  console.info('[MindMap sibling debug] attempt', lastAttempt)
}

export function recordMindMapSiblingInsertFailure(
  reason: string,
  details: Record<string, unknown> = {}
): null {
  lastFailure = { reason, details, at: Date.now() }
  if (isMindMapSiblingDebugEnabled()) {
    console.warn('[MindMap sibling debug] FAIL', reason, details)
  }
  return null
}

export function recordMindMapSiblingInsertSuccess(details: Record<string, unknown>): void {
  lastFailure = null
  if (!isMindMapSiblingDebugEnabled()) return
  console.info('[MindMap sibling debug] OK', details)
}

export function inspectMindMapSiblingDebug(): void {
  console.info('[MindMap sibling debug]', {
    enabled: isMindMapSiblingDebugEnabled(),
    lastAttempt,
    lastFailure,
  })
}

declare global {
  interface Window {
    mindMapSiblingDebug?: {
      enable: () => void
      disable: () => void
      inspect: () => void
      getLastFailure: () => MindMapSiblingInsertFailure | null
    }
  }
}

if (typeof window !== 'undefined' && import.meta.env.DEV) {
  window.mindMapSiblingDebug = {
    enable: () => setMindMapSiblingDebugEnabled(true),
    disable: () => setMindMapSiblingDebugEnabled(false),
    inspect: inspectMindMapSiblingDebug,
    getLastFailure: getLastMindMapSiblingInsertFailure,
  }
}
