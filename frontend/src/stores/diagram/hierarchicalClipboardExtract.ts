import {
  findBranchByNodeId,
  nodesAndConnectionsToMindMapSpec,
} from '@/stores/specLoader/mindMap'
import type { Connection, DiagramData, DiagramNode, DiagramType } from '@/types'
import { deepCloneMindMapBranch } from '@/utils/mindMapSubgraphMerge'

import type {
  BraceMapClipboardNode,
  FlowMapClipboardPayload,
  HierarchicalClipboard,
  HierarchicalClipboardPayload,
  TreeMapClipboardPayload,
} from './hierarchicalClipboardTypes'

const PROTECTED_CUT_IDS = new Set([
  'topic',
  'tree-topic',
  'flow-topic',
  'brace-whole',
  'dimension-label',
  'event',
])

export function isProtectedClipboardNode(nodeId: string): boolean {
  return PROTECTED_CUT_IDS.has(nodeId)
}

function filterTopLevelNodeIds(
  nodeIds: string[],
  descendantOf: (rootId: string, candidateId: string) => boolean
): string[] {
  const unique = [...new Set(nodeIds)]
  return unique.filter((id) => !unique.some((other) => other !== id && descendantOf(other, id)))
}

function buildChildrenMap(connections: Connection[]): Map<string, string[]> {
  const map = new Map<string, string[]>()
  connections.forEach((c) => {
    if (!map.has(c.source)) map.set(c.source, [])
    const list = map.get(c.source)
    if (list) list.push(c.target)
  })
  return map
}

function extractMindMapBranches(
  data: DiagramData,
  nodeIds: string[]
): HierarchicalClipboardPayload | null {
  const connections = data.connections ?? []
  const spec = nodesAndConnectionsToMindMapSpec(data.nodes, connections)
  const childrenMap = buildChildrenMap(connections)

  function isDescendant(rootId: string, candidateId: string): boolean {
    const visited = new Set<string>()
    function walk(id: string): boolean {
      if (id === candidateId) return true
      for (const childId of childrenMap.get(id) ?? []) {
        if (visited.has(childId)) continue
        visited.add(childId)
        if (walk(childId)) return true
      }
      return false
    }
    return walk(rootId)
  }

  const branchIds = filterTopLevelNodeIds(
    nodeIds.filter((id) => id.startsWith('branch-')),
    isDescendant
  )
  if (branchIds.length === 0) return null

  const branches = branchIds
    .map((nodeId) => {
      const found = findBranchByNodeId(
        spec.rightBranches,
        spec.leftBranches,
        nodeId,
        connections
      )
      return found ? deepCloneMindMapBranch(found.branch) : null
    })
    .filter((b): b is NonNullable<typeof b> => b !== null)

  if (branches.length === 0) return null
  return { kind: 'mindmap_branches', branches }
}

function buildTreeMapSpecFromData(data: DiagramData): Record<string, unknown> | null {
  const nodes = data.nodes
  const rootNode = nodes.find((n) => n.id === 'tree-topic')
  if (!rootNode) return null

  const categoryNodes = nodes
    .filter((n) => /^tree-cat-\d+$/.test(n.id ?? ''))
    .sort(
      (a, b) =>
        parseInt((a.id ?? '0').replace('tree-cat-', ''), 10) -
        parseInt((b.id ?? '0').replace('tree-cat-', ''), 10)
    )

  const categories = categoryNodes.map((cat) => {
    const idMatch = (cat.id ?? '').match(/^tree-cat-(\d+)$/)
    const categoryNum = idMatch ? parseInt(idMatch[1], 10) : -1
    const leaves = nodes
      .filter((n) => {
        const m = (n.id ?? '').match(/^tree-leaf-(\d+)-(\d+)$/)
        return m && parseInt(m[1], 10) === categoryNum
      })
      .sort(
        (a, b) =>
          parseInt((a.id ?? '0').split('-').pop() ?? '0', 10) -
          parseInt((b.id ?? '0').split('-').pop() ?? '0', 10)
      )
    return {
      id: cat.id,
      text: cat.text,
      children: leaves.map((l) => ({ id: l.id, text: l.text })),
    }
  })

  return {
    root: { id: 'tree-topic', text: rootNode.text, children: categories },
    dimension: (data as Record<string, unknown>).dimension,
    alternative_dimensions: (data as Record<string, unknown>).alternative_dimensions,
  }
}

function extractTreeMapPayload(
  data: DiagramData,
  nodeIds: string[],
  getTreeMapDescendantIds: (nodeId: string) => Set<string>
): HierarchicalClipboardPayload | null {
  const spec = buildTreeMapSpecFromData(data)
  if (!spec) return null

  const topIds = filterTopLevelNodeIds(nodeIds, (root, cand) =>
    getTreeMapDescendantIds(root).has(cand)
  )
  const nodeId = topIds.find((id) => /^tree-cat-\d+$/.test(id) || /^tree-leaf-\d+-\d+$/.test(id))
  if (!nodeId) return null

  const root = spec.root as {
    children?: Array<{ id?: string; text: string; children?: Array<{ id?: string; text: string }> }>
  }
  const categories = root.children ?? []

  if (/^tree-cat-\d+$/.test(nodeId)) {
    const cat = categories.find((c) => c.id === nodeId)
    if (!cat) return null
    const payload: TreeMapClipboardPayload = {
      kind: 'category',
      text: cat.text,
      leaves: (cat.children ?? []).map((leaf) => ({ text: leaf.text })),
    }
    return { kind: 'tree_map', payload }
  }

  const leafMatch = nodeId.match(/^tree-leaf-(\d+)-(\d+)$/)
  if (!leafMatch) return null
  const catIdx = parseInt(leafMatch[1], 10)
  const leafIdx = parseInt(leafMatch[2], 10)
  const cat = categories[catIdx]
  const leaf = cat?.children?.[leafIdx]
  if (!leaf) return null
  const payload: TreeMapClipboardPayload = { kind: 'leaf', text: leaf.text }
  return { kind: 'tree_map', payload }
}

function extractBraceSubtree(
  nodeId: string,
  nodes: DiagramNode[],
  connections: Connection[]
): BraceMapClipboardNode | null {
  const node = nodes.find((n) => n.id === nodeId)
  if (!node) return null

  const childrenMap = buildChildrenMap(connections)
  function build(id: string): BraceMapClipboardNode | null {
    const current = nodes.find((n) => n.id === id)
    if (!current) return null
    const childIds = childrenMap.get(id) ?? []
    const children = childIds
      .map((childId) => build(childId))
      .filter((c): c is BraceMapClipboardNode => c !== null)
    return { text: current.text, children }
  }
  return build(nodeId)
}

function extractBraceMapPayload(
  data: DiagramData,
  nodeIds: string[],
  getDescendantIds: (rootId: string) => Set<string>
): HierarchicalClipboardPayload | null {
  const topIds = filterTopLevelNodeIds(
    nodeIds.filter((id) => id.startsWith('brace-part-') || id.startsWith('brace-subpart-')),
    (root, cand) => getDescendantIds(root).has(cand)
  )
  const nodeId = topIds[0]
  if (!nodeId) return null
  const subtree = extractBraceSubtree(nodeId, data.nodes, data.connections ?? [])
  if (!subtree) return null
  return { kind: 'brace_map', subtree }
}

function extractFlowMapPayload(
  data: DiagramData,
  nodeIds: string[]
): HierarchicalClipboardPayload | null {
  const nodeId = nodeIds.find(
    (id) => id.startsWith('flow-step-') || id.startsWith('flow-substep-')
  )
  if (!nodeId) return null

  const stepNodes = data.nodes.filter((n) => n.type === 'flow')
  const substepNodes = data.nodes.filter((n) => n.type === 'flowSubstep')

  if (nodeId.startsWith('flow-step-')) {
    const stepMatch = nodeId.match(/flow-step-(\d+)/)
    if (!stepMatch) return null
    const stepIndex = parseInt(stepMatch[1], 10)
    const stepNode = stepNodes[stepIndex]
    if (!stepNode) return null
    const substeps = substepNodes
      .filter((n) => n.id?.startsWith(`flow-substep-${stepIndex}-`))
      .map((n) => n.text)
    const payload: FlowMapClipboardPayload = {
      kind: 'step',
      step: stepNode.text,
      substeps,
    }
    return { kind: 'flow_map', payload }
  }

  const node = data.nodes.find((n) => n.id === nodeId)
  if (!node) return null
  const payload: FlowMapClipboardPayload = { kind: 'substep', text: node.text }
  return { kind: 'flow_map', payload }
}

function extractFlatNodes(data: DiagramData, nodeIds: string[]): HierarchicalClipboardPayload | null {
  const nodesToCopy = data.nodes.filter((n) => nodeIds.includes(n.id))
  if (nodesToCopy.length === 0) return null
  const nodes = nodesToCopy.map((node) => ({
    ...JSON.parse(JSON.stringify(node)),
    id: `copy-${node.id}-${Date.now()}`,
  }))
  return { kind: 'flat_nodes', nodes }
}

export function extractHierarchicalClipboard(options: {
  diagramType: DiagramType
  data: DiagramData
  nodeIds: string[]
  getMindMapDescendantIds: (nodeId: string) => Set<string>
  getTreeMapDescendantIds: (nodeId: string) => Set<string>
}): HierarchicalClipboard | null {
  const { diagramType, data, nodeIds } = options
  const actionable = nodeIds.filter((id) => !isProtectedClipboardNode(id))
  if (actionable.length === 0) return null

  let payload: HierarchicalClipboardPayload | null = null

  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    payload = extractMindMapBranches(data, actionable)
  } else if (diagramType === 'tree_map') {
    payload = extractTreeMapPayload(data, actionable, options.getTreeMapDescendantIds)
  } else if (diagramType === 'brace_map') {
    const childrenMap = buildChildrenMap(data.connections ?? [])
    const collect = (rootId: string): Set<string> => {
      const set = new Set<string>([rootId])
      for (const childId of childrenMap.get(rootId) ?? []) {
        for (const id of collect(childId)) set.add(id)
      }
      return set
    }
    payload = extractBraceMapPayload(data, actionable, collect)
  } else if (diagramType === 'flow_map') {
    payload = extractFlowMapPayload(data, actionable)
  }

  if (!payload) {
    payload = extractFlatNodes(data, actionable)
  }
  if (!payload) return null

  return {
    sourceDiagramType: diagramType,
    payload,
    sourceNodeIds: actionable,
  }
}
