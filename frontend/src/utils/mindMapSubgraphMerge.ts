import {
  distributeBranchesClockwise,
  findBranchByNodeId,
  nodesAndConnectionsToMindMapSpec,
} from '@/stores/specLoader/mindMap'
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import { isEditablePlaceholderLabel } from '@/stores/diagram/diagramDefaultLabels'
import type { Connection, DiagramNode } from '@/types'
import {
  isMindMapSubgraphDebugEnabled,
  mindMapSubgraphDebug,
  mindMapSubgraphDebugError,
} from '@/utils/mindMapSubgraphDebug'

export type MindMapBranchSpec = {
  text: string
  children?: MindMapBranchSpec[]
  /** Stable identity across positional id rebuilds (duplicate labels safe). */
  uid?: string
}

function isMindMapPlaceholderChildLabel(text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return true
  if (isPlaceholderText(trimmed)) return true
  if (isEditablePlaceholderLabel(trimmed)) return true
  if (/^输入文本/.test(trimmed) || /^輸入文本/.test(trimmed)) return true
  if (/^Enter\s+text/i.test(trimmed)) return true
  return false
}

function mergeChildrenReplacingPlaceholders(
  existingChildren: MindMapBranchSpec[],
  generatedBranches: MindMapBranchSpec[]
): MindMapBranchSpec[] {
  const merged: MindMapBranchSpec[] = []
  let generatedIndex = 0

  for (const child of existingChildren) {
    if (isMindMapPlaceholderChildLabel(child.text)) {
      if (generatedIndex < generatedBranches.length) {
        merged.push(deepCloneBranch(generatedBranches[generatedIndex]))
        generatedIndex += 1
      }
      continue
    }
    merged.push(deepCloneBranch(child))
  }

  while (generatedIndex < generatedBranches.length) {
    merged.push(deepCloneBranch(generatedBranches[generatedIndex]))
    generatedIndex += 1
  }

  return merged
}

function deepCloneBranch(branch: MindMapBranchSpec): MindMapBranchSpec {
  return {
    text: branch.text,
    uid: branch.uid,
    children: branch.children?.map(deepCloneBranch),
  }
}

export function deepCloneMindMapBranch(branch: MindMapBranchSpec): MindMapBranchSpec {
  return deepCloneBranch(branch)
}

export function normalizeGeneratedBranch(item: unknown): MindMapBranchSpec | null {
  if (!item || typeof item !== 'object') return null
  const rec = item as Record<string, unknown>
  const text = String(rec.text ?? rec.label ?? '').trim()
  if (!text) return null
  const rawChildren = Array.isArray(rec.children) ? rec.children : []
  const children = rawChildren
    .map(normalizeGeneratedBranch)
    .filter((c): c is MindMapBranchSpec => c !== null)
  const uid = typeof rec.uid === 'string' && rec.uid.trim() ? rec.uid.trim() : undefined
  return {
    text,
    uid,
    children: children.length > 0 ? children : undefined,
  }
}

export function extractBranchesFromGeneratedSpec(spec: Record<string, unknown>): MindMapBranchSpec[] {
  if (isMindMapSubgraphDebugEnabled()) {
    mindMapSubgraphDebug('extract', 'spec shape for extraction', {
      keys: Object.keys(spec),
      hasChildrenArray: Array.isArray(spec.children),
      childrenLength: Array.isArray(spec.children) ? spec.children.length : 0,
      hasLeftBranches: Array.isArray(spec.leftBranches) || Array.isArray(spec.left),
      hasRightBranches: Array.isArray(spec.rightBranches) || Array.isArray(spec.right),
      topic: spec.topic,
    })
  }
  if (Array.isArray(spec.children)) {
    const fromChildren = spec.children
      .map(normalizeGeneratedBranch)
      .filter((b): b is MindMapBranchSpec => b !== null)
    if (isMindMapSubgraphDebugEnabled()) {
      mindMapSubgraphDebug('extract', 'parsed from spec.children', {
        count: fromChildren.length,
        texts: fromChildren.map((b) => b.text),
      })
    }
    return fromChildren
  }
  const left = (spec.leftBranches as unknown[]) ?? (spec.left as unknown[]) ?? []
  const right = (spec.rightBranches as unknown[]) ?? (spec.right as unknown[]) ?? []
  const combined = [...left, ...right]
  if (combined.length > 0) {
    const fromSides = combined
      .map(normalizeGeneratedBranch)
      .filter((b): b is MindMapBranchSpec => b !== null)
    if (isMindMapSubgraphDebugEnabled()) {
      mindMapSubgraphDebug('extract', 'parsed from left/right branches', {
        count: fromSides.length,
        texts: fromSides.map((b) => b.text),
      })
    }
    return fromSides
  }
  if (isMindMapSubgraphDebugEnabled()) {
    mindMapSubgraphDebugError('extractBranchesFromGeneratedSpec: no children found', { spec })
  }
  return []
}

/** Keep only one level of generated nodes — drop any nested grandchildren from the LLM. */
export function toDirectChildrenOnly(branches: MindMapBranchSpec[]): MindMapBranchSpec[] {
  const result: MindMapBranchSpec[] = []
  for (const branch of branches) {
    const text = branch.text.trim()
    if (!text) continue
    result.push({ text })
  }
  return result
}

export type MindMapSpecSnapshot = ReturnType<typeof nodesAndConnectionsToMindMapSpec>

export function mergeGeneratedBranchesIntoSpec(
  current: MindMapSpecSnapshot,
  anchorNodeId: string,
  generatedBranches: MindMapBranchSpec[],
  connections: Connection[]
): MindMapSpecSnapshot | null {
  if (generatedBranches.length === 0) return null

  const spec: MindMapSpecSnapshot = {
    topic: current.topic,
    leftBranches: current.leftBranches.map(deepCloneBranch),
    rightBranches: current.rightBranches.map(deepCloneBranch),
  }

  if (anchorNodeId === 'topic') {
    const distributed = distributeBranchesClockwise(generatedBranches)
    spec.rightBranches.push(...distributed.rightBranches.map(deepCloneBranch))
    spec.leftBranches.push(...distributed.leftBranches.map(deepCloneBranch))
    return spec
  }

  const found = findBranchByNodeId(
    spec.rightBranches,
    spec.leftBranches,
    anchorNodeId,
    connections
  )
  if (!found) {
    if (isMindMapSubgraphDebugEnabled()) {
      mindMapSubgraphDebugError('mergeGeneratedBranchesIntoSpec: anchor not found', {
        anchorNodeId,
        topLevelRight: spec.rightBranches.map((b) => b.text),
        topLevelLeft: spec.leftBranches.map((b) => b.text),
        generatedCount: generatedBranches.length,
      })
    }
    return null
  }

  if (isMindMapSubgraphDebugEnabled()) {
    mindMapSubgraphDebug('merge', 'anchor resolved', {
      anchorNodeId,
      branchText: found.branch.text,
      existingChildren: found.branch.children?.map((c) => c.text) ?? [],
      incomingGenerated: generatedBranches.map((b) => b.text),
    })
  }

  if (!found.branch.children) {
    found.branch.children = []
  }
  found.branch.children = mergeChildrenReplacingPlaceholders(
    found.branch.children,
    generatedBranches
  )
  if (isMindMapSubgraphDebugEnabled()) {
    mindMapSubgraphDebug('merge', 'children after merge', {
      anchorNodeId,
      mergedChildren: found.branch.children.map((c) => c.text),
    })
  }
  return spec
}

export function buildMindMapSpecFromDiagram(
  nodes: DiagramNode[],
  connections: Connection[]
): MindMapSpecSnapshot {
  return nodesAndConnectionsToMindMapSpec(nodes, connections)
}

/** Direct child node ids under an anchor that still carry placeholder labels. */
export function collectMindMapPlaceholderChildIds(
  nodes: DiagramNode[],
  connections: Connection[],
  anchorNodeId: string
): string[] {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  return connections
    .filter((c) => c.source === anchorNodeId)
    .map((c) => c.target)
    .filter((id) => {
      const label = nodeMap.get(id)?.text ?? ''
      return isMindMapPlaceholderChildLabel(label)
    })
}
