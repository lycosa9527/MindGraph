import type { Connection, DiagramNode } from '@/types'
import type { MindMapSubgraphContext } from '@/utils/mindMapSubgraphContext'
import { findBranchByNodeId, nodesAndConnectionsToMindMapSpec } from '@/stores/specLoader/mindMap'

type DebugBranchSpec = { text: string; children?: DebugBranchSpec[] }

const STORAGE_KEY = 'mindgraph.debugSubgraph'
const LOG_PREFIX = '[MindMapSubgraph]'

export type MindMapSubgraphDebugPhase =
  | 'start'
  | 'guard'
  | 'context'
  | 'request'
  | 'response'
  | 'extract'
  | 'merge'
  | 'paste'
  | 'done'
  | 'error'

export interface MindMapSubgraphDebugEntry {
  ts: number
  phase: MindMapSubgraphDebugPhase
  message: string
  data?: unknown
}

let activeRunId = 0
let lastRunEntries: MindMapSubgraphDebugEntry[] = []
let groupOpen = false

/** Default off; opt in with localStorage mindgraph.debugSubgraph = '1' | 'verbose'. */
export function isMindMapSubgraphDebugEnabled(): boolean {
  if (typeof localStorage !== 'undefined') {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === '1' || stored === 'verbose') return true
  }
  return false
}

export function isMindMapSubgraphVerboseDebugEnabled(): boolean {
  if (typeof localStorage !== 'undefined') {
    return localStorage.getItem(STORAGE_KEY) === 'verbose'
  }
  return false
}

export function setMindMapSubgraphDebugEnabled(enabled: boolean): void {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0')
}

export function getMindMapSubgraphDebugLastRun(): MindMapSubgraphDebugEntry[] {
  return [...lastRunEntries]
}

function pushEntry(phase: MindMapSubgraphDebugPhase, message: string, data?: unknown): void {
  lastRunEntries.push({ ts: Date.now(), phase, message, data })
}

function logToConsole(phase: MindMapSubgraphDebugPhase, message: string, data?: unknown): void {
  const label = `${LOG_PREFIX} [${phase}] ${message}`
  if (data !== undefined) {
    console.warn(label, data)
    return
  }
  console.warn(label)
}

export function mindMapSubgraphDebug(
  phase: MindMapSubgraphDebugPhase,
  message: string,
  data?: unknown
): void {
  pushEntry(phase, message, data)
  if (!isMindMapSubgraphDebugEnabled()) return
  logToConsole(phase, message, data)
}

export function mindMapSubgraphDebugError(message: string, data?: unknown): void {
  pushEntry('error', message, data)
  if (!isMindMapSubgraphDebugEnabled()) return
  if (data !== undefined) {
    console.error(`${LOG_PREFIX} [error] ${message}`, data)
    return
  }
  console.error(`${LOG_PREFIX} [error] ${message}`)
}

/** Logs a compact failure bundle when subgraph debug is enabled. */
export function mindMapSubgraphFailureDump(bundle: Record<string, unknown>): void {
  pushEntry('error', 'failure dump', bundle)
  if (!isMindMapSubgraphDebugEnabled()) return
  console.error(`${LOG_PREFIX} FAILURE`, bundle)
}

export function beginMindMapSubgraphDebugRun(anchorNodeId: string): number {
  activeRunId += 1
  lastRunEntries = []
  if (!isMindMapSubgraphDebugEnabled()) {
    pushEntry('start', `Run #${activeRunId} (logging disabled)`, { anchorNodeId })
    return activeRunId
  }
  if (groupOpen) {
    console.groupEnd()
  }
  console.group(`${LOG_PREFIX} Run #${activeRunId} — anchor ${anchorNodeId}`)
  groupOpen = true
  mindMapSubgraphDebug('start', `Run #${activeRunId}`, {
    anchorNodeId,
    verbose: isMindMapSubgraphVerboseDebugEnabled(),
    optIn: "localStorage.setItem('mindgraph.debugSubgraph','1')",
  })
  return activeRunId
}

export function endMindMapSubgraphDebugRun(success: boolean): void {
  mindMapSubgraphDebug('done', success ? 'completed OK' : 'finished with failure', {
    runId: activeRunId,
    entryCount: lastRunEntries.length,
  })
  if (groupOpen) {
    console.groupEnd()
    groupOpen = false
  }
}

export function summarizeMindMapNodesForDebug(
  nodes: DiagramNode[],
  connections: Connection[]
): Record<string, unknown> {
  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  const childrenByParent = new Map<string, string[]>()
  for (const link of connections) {
    const list = childrenByParent.get(link.source) ?? []
    list.push(link.target)
    childrenByParent.set(link.source, list)
  }

  const branchNodes = nodes
    .filter((n) => n.id.startsWith('branch-'))
    .map((n) => ({
      id: n.id,
      text: (n.text ?? '').trim(),
      parent: connections.find((c) => c.target === n.id)?.source ?? null,
      childIds: childrenByParent.get(n.id) ?? [],
    }))

  return {
    nodeCount: nodes.length,
    connectionCount: connections.length,
    topic: nodeById.get('topic')?.text ?? null,
    branchNodes,
    topicChildren: childrenByParent.get('topic') ?? [],
  }
}

export function debugMindMapSubgraphMergeLookup(
  nodes: DiagramNode[],
  connections: Connection[],
  anchorNodeId: string
): Record<string, unknown> {
  const spec = nodesAndConnectionsToMindMapSpec(nodes, connections)
  const found = findBranchByNodeId(
    spec.rightBranches,
    spec.leftBranches,
    anchorNodeId,
    connections
  )
  return {
    anchorNodeId,
    anchorText: nodes.find((n) => n.id === anchorNodeId)?.text ?? null,
    found: found
      ? {
          branchText: found.branch.text,
          indexInParent: found.indexInParent,
          existingChildCount: found.branch.children?.length ?? 0,
          existingChildTexts: found.branch.children?.map((c) => c.text) ?? [],
        }
      : null,
    specTopic: spec.topic,
    topLevelRight: spec.rightBranches.map((b) => b.text),
    topLevelLeft: spec.leftBranches.map((b) => b.text),
  }
}

export function installMindMapSubgraphDebugGlobal(): void {
  if (typeof window === 'undefined') return
  const w = window as Window & { mindMapSubgraphDebug?: Record<string, unknown> }
  if (w.mindMapSubgraphDebug) return
  w.mindMapSubgraphDebug = {
    enable: () => setMindMapSubgraphDebugEnabled(true),
    disable: () => setMindMapSubgraphDebugEnabled(false),
    verbose: () => {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, 'verbose')
      }
    },
    lastRun: () => getMindMapSubgraphDebugLastRun(),
    isEnabled: () => isMindMapSubgraphDebugEnabled(),
  }
}

if (typeof window !== 'undefined' && import.meta.env.DEV) {
  installMindMapSubgraphDebugGlobal()
}

export type MindMapSubgraphRequestDebug = {
  endpoint: string
  llm: string
  language: string
  diagramId: string | null
  prompt: string
  body: Record<string, unknown>
  context: MindMapSubgraphContext
}

export type MindMapSubgraphResponseDebug = {
  httpStatus: number
  success?: boolean
  diagramType?: string
  specKeys: string[]
  specTopic?: string
  rawSpecChildrenCount: number
  rawSpecChildTexts: string[]
  rawResult: unknown
}

export type MindMapSubgraphExtractDebug = {
  extractedCount: number
  extractedTexts: string[]
  afterDirectChildrenOnly: DebugBranchSpec[]
}
