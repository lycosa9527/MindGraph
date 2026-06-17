import { syncMindMapConnectionStrokeColors } from '@/config/mindMapGeometry'
import {
  getMindMapThemeById,
  mindMapStyleFromTheme,
  resolveMindMapThemeId,
  type MindMapThemeId,
} from '@/config/mindMapThemes'
import type { Connection, DiagramNode, NodeStyle } from '@/types'

function branchGlobalIndex(nodeId: string): number {
  return parseInt(nodeId.split('-')[3] ?? '0', 10)
}

/** Sort mind-map node ids by layout global index (matches path-key sibling order). */
export function sortMindMapNodeIdsByGlobalIndex(a: string, b: string): number {
  return branchGlobalIndex(a) - branchGlobalIndex(b)
}

function buildChildrenMap(connections: Connection[]): Map<string, string[]> {
  const map = new Map<string, string[]>()
  for (const c of connections) {
    if (!map.has(c.source)) map.set(c.source, [])
    map.get(c.source)!.push(c.target)
  }
  for (const children of map.values()) {
    children.sort(sortMindMapNodeIdsByGlobalIndex)
  }
  return map
}

/** Stable tree path (side + sibling indices) — survives node id regeneration on reload. */
export function mindMapNodePathKey(
  nodeId: string,
  connections: Connection[]
): string | null {
  if (nodeId === 'topic') return 'topic'
  if (!nodeId.startsWith('branch-')) return null

  const side = nodeId.startsWith('branch-l-') ? 'l' : 'r'
  const parentMap = new Map<string, string>()
  connections.forEach((c) => parentMap.set(c.target, c.source))
  const childMap = buildChildrenMap(connections)

  const indices: number[] = []
  let current: string | undefined = nodeId
  while (current && current !== 'topic') {
    const parent = parentMap.get(current)
    if (!parent) return null
    const siblings = childMap.get(parent) ?? []
    const idx = siblings.indexOf(current)
    if (idx < 0) return null
    indices.unshift(idx)
    current = parent
  }

  return `${side}/${indices.join('/')}`
}

/** Resolve a stable path key to the current node id after a mind-map reload. */
export function findNodeIdByPathKey(
  nodes: DiagramNode[],
  connections: Connection[],
  pathKey: string
): string | null {
  if (pathKey === 'topic') {
    return nodes.find((n) => n.id === 'topic')?.id ?? null
  }
  for (const node of nodes) {
    if (mindMapNodePathKey(node.id, connections) === pathKey) {
      return node.id
    }
  }
  return null
}

function mergeNodeStyle(
  node: DiagramNode,
  nodeStylesRecord?: Record<string, NodeStyle>
): NodeStyle | undefined {
  const fromRecord = nodeStylesRecord?.[node.id]
  const inline = node.style
  if (!fromRecord && !inline) return undefined
  return { ...fromRecord, ...inline }
}

export function collectMindMapStylesByPath(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStylesRecord?: Record<string, NodeStyle>
): Map<string, NodeStyle> {
  const map = new Map<string, NodeStyle>()
  for (const node of nodes) {
    const key = mindMapNodePathKey(node.id, connections)
    if (!key) continue
    const merged = mergeNodeStyle(node, nodeStylesRecord)
    if (merged && Object.keys(merged).length > 0) {
      map.set(key, merged)
    }
  }
  return map
}

function parentPathKey(pathKey: string): string | null {
  if (pathKey === 'topic') return null
  const slash = pathKey.lastIndexOf('/')
  return slash >= 0 ? pathKey.slice(0, slash) : null
}

function resolveParentNodeShape(
  pathKey: string,
  stylesByPath: Map<string, NodeStyle>,
  nodes: DiagramNode[],
  connections: Connection[]
): NodeStyle['nodeShape'] | undefined {
  const parentKey = parentPathKey(pathKey)
  if (!parentKey) return undefined
  const fromStyles = stylesByPath.get(parentKey)?.nodeShape
  if (fromStyles) return fromStyles
  for (const node of nodes) {
    if (mindMapNodePathKey(node.id, connections) === parentKey) {
      return node.style?.nodeShape
    }
  }
  return undefined
}

/** Inherit shape from an earlier underline sibling on the same parent row. */
function resolvePriorSiblingNodeShape(
  pathKey: string,
  stylesByPath: Map<string, NodeStyle>
): NodeStyle['nodeShape'] | undefined {
  const parentKey = parentPathKey(pathKey)
  if (!parentKey) return undefined
  const idx = parseInt(pathKey.slice(pathKey.lastIndexOf('/') + 1), 10)
  if (!Number.isFinite(idx) || idx <= 0) return undefined
  for (let i = idx - 1; i >= 0; i--) {
    const shape = stylesByPath.get(`${parentKey}/${i}`)?.nodeShape
    if (shape) return shape
  }
  return undefined
}

export function applyMindMapStylesByPath(
  nodes: DiagramNode[],
  connections: Connection[],
  stylesByPath: Map<string, NodeStyle>,
  themeId?: MindMapThemeId | string | null
): Record<string, NodeStyle> {
  const defaultTheme = getMindMapThemeById(resolveMindMapThemeId(themeId))
  const nodeStyles: Record<string, NodeStyle> = {}
  for (const node of nodes) {
    const key = mindMapNodePathKey(node.id, connections)
    if (!key) continue
    const preserved = stylesByPath.get(key)
    if (preserved) {
      node.style = { ...(node.style || {}), ...preserved }
      nodeStyles[node.id] = { ...preserved }
    } else {
      const inheritedShape =
        resolveParentNodeShape(key, stylesByPath, nodes, connections) ??
        resolvePriorSiblingNodeShape(key, stylesByPath)
      const themeDefaults = {
        ...mindMapStyleFromTheme(node, defaultTheme),
        ...(inheritedShape ? { nodeShape: inheritedShape } : {}),
      }
      node.style = { ...themeDefaults, ...(node.style || {}) }
      nodeStyles[node.id] = { ...node.style }
    }
  }
  const topicBorder =
    nodes.find((n) => n.id === 'topic')?.style?.borderColor ??
    stylesByPath.get('topic')?.borderColor
  if (topicBorder) {
    syncMindMapConnectionStrokeColors(connections, topicBorder)
  }
  return nodeStyles
}

/** Preserve visual styles when mind-map tree is rebuilt (add/remove/reload). */
export function mergeMindMapReloadStyles(
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[],
  existingNodeStyles?: Record<string, NodeStyle>,
  themeId?: MindMapThemeId | string | null
): Record<string, NodeStyle> {
  const stylesByPath = collectMindMapStylesByPath(
    oldNodes,
    oldConnections,
    existingNodeStyles
  )
  return applyMindMapStylesByPath(newNodes, newConnections, stylesByPath, themeId)
}
