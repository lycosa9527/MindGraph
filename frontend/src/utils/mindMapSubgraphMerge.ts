import {
  distributeBranchesClockwise,
  findBranchByNodeId,
  nodesAndConnectionsToMindMapSpec,
} from '@/stores/specLoader/mindMap'
import type { Connection, DiagramNode } from '@/types'

export type MindMapBranchSpec = {
  text: string
  children?: MindMapBranchSpec[]
}

function deepCloneBranch(branch: MindMapBranchSpec): MindMapBranchSpec {
  return {
    text: branch.text,
    children: branch.children?.map(deepCloneBranch),
  }
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
  return {
    text,
    children: children.length > 0 ? children : undefined,
  }
}

export function extractBranchesFromGeneratedSpec(spec: Record<string, unknown>): MindMapBranchSpec[] {
  if (Array.isArray(spec.children)) {
    return spec.children
      .map(normalizeGeneratedBranch)
      .filter((b): b is MindMapBranchSpec => b !== null)
  }
  const left = (spec.leftBranches as unknown[]) ?? (spec.left as unknown[]) ?? []
  const right = (spec.rightBranches as unknown[]) ?? (spec.right as unknown[]) ?? []
  const combined = [...left, ...right]
  if (combined.length > 0) {
    return combined
      .map(normalizeGeneratedBranch)
      .filter((b): b is MindMapBranchSpec => b !== null)
  }
  return []
}

export type MindMapSpecSnapshot = ReturnType<typeof nodesAndConnectionsToMindMapSpec>

export function mergeGeneratedBranchesIntoSpec(
  current: MindMapSpecSnapshot,
  anchorNodeId: string,
  generatedBranches: MindMapBranchSpec[]
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

  const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, anchorNodeId)
  if (!found) return null

  if (!found.branch.children) {
    found.branch.children = []
  }
  for (const branch of generatedBranches) {
    found.branch.children.push(deepCloneBranch(branch))
  }
  return spec
}

export function buildMindMapSpecFromDiagram(
  nodes: DiagramNode[],
  connections: Connection[]
): MindMapSpecSnapshot {
  return nodesAndConnectionsToMindMapSpec(nodes, connections)
}
