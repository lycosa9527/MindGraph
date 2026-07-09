import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import type { Connection, DiagramNode } from '@/types'

export interface MindMapExplainContext {
  diagramType: string
  topic: string
  topLevelBranches: string[]
  ancestorPath: string[]
  siblingBranches: string[]
  childBranches: string[]
  selectedNode: string
}

function childIds(parentId: string, connections: Connection[]): string[] {
  return connections.filter((c) => c.source === parentId).map((c) => c.target)
}

function parentIdOf(nodeId: string, connections: Connection[]): string | null {
  const link = connections.find((c) => c.target === nodeId)
  return link?.source ?? null
}

function usableLabel(text: string): string {
  const trimmed = text.trim()
  if (!trimmed || isPlaceholderText(trimmed)) return ''
  return trimmed
}

function labelsForIds(ids: string[], nodeMap: Map<string, DiagramNode>): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const id of ids) {
    const label = usableLabel(nodeMap.get(id)?.text ?? '')
    if (!label || seen.has(label)) continue
    seen.add(label)
    result.push(label)
  }
  return result
}

function buildAncestorPath(
  nodeId: string,
  connections: Connection[],
  nodeMap: Map<string, DiagramNode>
): string[] {
  const path: string[] = []
  let current = parentIdOf(nodeId, connections)
  while (current && current !== 'topic') {
    const label = usableLabel(nodeMap.get(current)?.text ?? '')
    if (label) {
      path.unshift(label)
    }
    current = parentIdOf(current, connections)
  }
  return path
}

const MAX_BRANCHES = 16

export function collectMindMapExplainContext(
  nodes: DiagramNode[],
  connections: Connection[],
  selectedNodeId: string
): MindMapExplainContext | null {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  const selected = nodeMap.get(selectedNodeId)
  if (!selected) return null

  const selectedNode = usableLabel(selected.text ?? '')
  if (!selectedNode) return null

  const topic =
    selectedNodeId === 'topic'
      ? selectedNode
      : usableLabel(nodeMap.get('topic')?.text ?? '')

  const topLevelBranches = labelsForIds(childIds('topic', connections), nodeMap).slice(
    0,
    MAX_BRANCHES
  )

  const ancestorPath =
    selectedNodeId === 'topic' ? [] : buildAncestorPath(selectedNodeId, connections, nodeMap)

  const parentId = selectedNodeId === 'topic' ? null : parentIdOf(selectedNodeId, connections)
  const siblingBranches =
    parentId === null
      ? []
      : labelsForIds(
          childIds(parentId, connections).filter((id) => id !== selectedNodeId),
          nodeMap
        ).slice(0, MAX_BRANCHES)

  const childBranches =
    selectedNodeId === 'topic'
      ? topLevelBranches
      : labelsForIds(childIds(selectedNodeId, connections), nodeMap).slice(0, MAX_BRANCHES)

  return {
    diagramType: 'mindmap',
    topic,
    topLevelBranches,
    ancestorPath,
    siblingBranches,
    childBranches,
    selectedNode,
  }
}
