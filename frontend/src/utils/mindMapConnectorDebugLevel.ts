const STORAGE_KEY = 'mindgraph.debugMindMapConnectors'

export type MindMapConnectorDebugLevel = 'off' | 'basic' | 'verbose'

function readStoredLevel(): string | null {
  if (typeof localStorage === 'undefined') return null
  return localStorage.getItem(STORAGE_KEY)
}

/** Dev default: basic tables; set localStorage mindgraph.debugMindMapConnectors = '0' to disable. */
export function getMindMapConnectorDebugLevel(): MindMapConnectorDebugLevel {
  const raw = readStoredLevel()
  if (raw === '0') return 'off'
  if (raw === 'verbose') return 'verbose'
  if (raw === '1') return 'basic'
  if (import.meta.env.DEV) return 'basic'
  return 'off'
}

export function isMindMapConnectorDebugEnabled(): boolean {
  return getMindMapConnectorDebugLevel() !== 'off'
}

export function isMindMapConnectorVerboseDebugEnabled(): boolean {
  return getMindMapConnectorDebugLevel() === 'verbose'
}

export function setMindMapConnectorDebugLevel(level: MindMapConnectorDebugLevel): void {
  if (typeof localStorage === 'undefined') return
  if (level === 'off') {
    localStorage.setItem(STORAGE_KEY, '0')
    return
  }
  if (level === 'verbose') {
    localStorage.setItem(STORAGE_KEY, 'verbose')
    return
  }
  localStorage.setItem(STORAGE_KEY, '1')
}
