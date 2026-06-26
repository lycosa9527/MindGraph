import {
  getMindMapDiagramStyleById,
  mindMapDiagramStyleUsesLayeredBranchColors,
  mindMapNodeShapeFromPreset,
  resolveMindMapDiagramStyleId,
} from '@/config/mindMapDiagramStyles'
import {
  isRainbowMindMapTheme,
  mindMapRainbowColorsForNode,
  MIND_MAP_RAINBOW_TOPIC_COLORS,
  syncRainbowMindMapConnectionColors,
} from '@/config/mindMapVibrantThemes'
import {
  syncLegacyMindMapConnectionStrokeColors,
  syncMindMapConnectionStrokeColors,
  syncMindMapConnectionStrokeColorsForCanvasMode,
} from '@/config/mindMapGeometry'
import {
  getMindMapThemeById,
  mindMapStyleFromTheme,
  resolveMindMapThemeId,
  type MindMapThemeId,
} from '@/config/mindMapThemes'
import type { Connection, DiagramNode, DiagramType, NodeStyle } from '@/types'
import { readEffectiveMindMapCanvasMode, readMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'

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

/** Inherit shape from an earlier sibling on the same parent row (e.g. new child matches siblings). */
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

/**
 * Resolve nodeShape after a tree reload.
 * Never inherit the parent's shape — L1 rounded must not overwrite L2 underline in classic.
 * Also heals shapes that were wrongly parent-inherited on a prior reload.
 */
function resolveMindMapRestoredNodeShape(
  node: DiagramNode,
  pathKey: string,
  preserved: NodeStyle | undefined,
  stylesByPath: Map<string, NodeStyle>,
  nodes: DiagramNode[],
  connections: Connection[],
  diagramStyle: ReturnType<typeof getMindMapDiagramStyleById>
): NodeStyle['nodeShape'] {
  const presetShape = mindMapNodeShapeFromPreset(node, diagramStyle)
  const fromPreserved = preserved?.nodeShape
  if (!fromPreserved) {
    return (
      resolvePriorSiblingNodeShape(pathKey, stylesByPath) ??
      presetShape
    )
  }

  const parentShape = resolveParentNodeShape(pathKey, stylesByPath, nodes, connections)
  if (parentShape && fromPreserved === parentShape && fromPreserved !== presetShape) {
    return presetShape
  }
  return fromPreserved
}

export function applyMindMapStylesByPath(
  nodes: DiagramNode[],
  connections: Connection[],
  stylesByPath: Map<string, NodeStyle>,
  themeId?: MindMapThemeId | string | null,
  diagramStyleId?: string | null
): Record<string, NodeStyle> {
  const v2Visuals = readMindMapV2VisualDesignActive()
  const defaultTheme = getMindMapThemeById(resolveMindMapThemeId(themeId))
  const diagramStyle = getMindMapDiagramStyleById(resolveMindMapDiagramStyleId(diagramStyleId))
  const nodeStyles: Record<string, NodeStyle> = {}
  for (const node of nodes) {
    const key = mindMapNodePathKey(node.id, connections)
    if (!key) continue
    const preserved = stylesByPath.get(key)
    const nodeShape = resolveMindMapRestoredNodeShape(
      node,
      key,
      preserved,
      stylesByPath,
      nodes,
      connections,
      diagramStyle
    )

    if (preserved) {
      const merged = { ...preserved, nodeShape }
      node.style = { ...(node.style || {}), ...merged }
      nodeStyles[node.id] = { ...merged }
    } else {
      let themeDefaults = {
        ...mindMapStyleFromTheme(node, defaultTheme, diagramStyleId),
        nodeShape,
      }
      if (isRainbowMindMapTheme(themeId)) {
        if (node.id === 'topic' || node.type === 'topic' || node.type === 'center') {
          themeDefaults = {
            ...themeDefaults,
            backgroundColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
            textColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
            borderColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
          }
        } else {
          const branchColors = mindMapRainbowColorsForNode(node.id, connections)
          if (branchColors) {
            themeDefaults = {
              ...themeDefaults,
              backgroundColor: branchColors.backgroundColor,
              textColor: branchColors.textColor,
              borderColor: branchColors.borderColor,
            }
          }
        }
      }
      node.style = { ...themeDefaults, ...(node.style || {}) }
      nodeStyles[node.id] = { ...node.style }
    }
  }
  if (isRainbowMindMapTheme(themeId)) {
    syncRainbowMindMapConnectionColors(connections, nodes)
  } else if (v2Visuals) {
    const layered = mindMapDiagramStyleUsesLayeredBranchColors(diagramStyleId)
    const topicBorder =
      nodes.find((n) => n.id === 'topic')?.style?.borderColor ??
      stylesByPath.get('topic')?.borderColor
    const branchAccent =
      defaultTheme.borderColor ??
      nodes.find((n) => n.id.startsWith('branch-'))?.style?.borderColor
    const strokeColor = layered && branchAccent ? branchAccent : topicBorder
    if (strokeColor) {
      syncMindMapConnectionStrokeColors(connections, strokeColor)
    }
  } else {
    syncLegacyMindMapConnectionStrokeColors(connections, nodes)
  }
  return nodeStyles
}

/** Reconcile persisted connection stroke colors when canvas mode changes or diagram reloads. */
export function resyncMindMapConnectionStrokeColorsForActiveMode(
  diagramType: DiagramType | null,
  nodes: DiagramNode[] | undefined,
  connections: Connection[] | undefined
): boolean {
  if (!nodes?.length || !connections?.length) return false
  if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return false
  syncMindMapConnectionStrokeColorsForCanvasMode(
    connections,
    nodes,
    readEffectiveMindMapCanvasMode()
  )
  return true
}

/** Preserve visual styles when mind-map tree is rebuilt (add/remove/reload). */
export function mergeMindMapReloadStyles(
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[],
  existingNodeStyles?: Record<string, NodeStyle>,
  themeId?: MindMapThemeId | string | null,
  diagramStyleId?: string | null
): Record<string, NodeStyle> {
  const stylesByPath = collectMindMapStylesByPath(
    oldNodes,
    oldConnections,
    existingNodeStyles
  )
  return applyMindMapStylesByPath(
    newNodes,
    newConnections,
    stylesByPath,
    themeId,
    diagramStyleId
  )
}
