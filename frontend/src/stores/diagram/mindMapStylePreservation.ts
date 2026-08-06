import {
  getMindMapDiagramStyleById,
  mindMapDiagramStyleUsesLayeredBranchColors,
  mindMapNodeShapeFromPreset,
  resolveMindMapDiagramStyleId,
} from '@/config/mindMapDiagramStyles'
import {
  mindMapBranchDepth,
  syncLegacyMindMapConnectionStrokeColors,
  syncMindMapConnectionStrokeColors,
  syncMindMapConnectionStrokeColorsForCanvasMode,
} from '@/config/mindMapGeometry'
import {
  type MindMapThemeId,
  getMindMapThemeById,
  mindMapStyleFromTheme,
  resolveMindMapThemeId,
} from '@/config/mindMapThemes'
import {
  MIND_MAP_RAINBOW_TOPIC_COLORS,
  isRainbowMindMapTheme,
  mindMapRainbowColorsForNode,
  syncRainbowMindMapConnectionColors,
} from '@/config/mindMapVibrantThemes'
import type { MindMapCanvasMode } from '@/stores/ui'
import type { Connection, DiagramNode, DiagramType, NodeStyle } from '@/types'
import { readEffectiveMindMapCanvasMode } from '@/utils/mindMapCanvasMode'

/** Injected to avoid a circular import with mindMapCollapse remap helpers. */
export type MindMapNodeIdRemapper = (
  oldId: string,
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[]
) => string | null

function branchGlobalIndex(nodeId: string): number {
  return parseInt(nodeId.split('-')[3] ?? '0', 10)
}

/**
 * Sort by layout global index in the id suffix.
 * Prefer {@link buildMindMapChildrenMapByConnectionOrder} for sibling order —
 * connection array order is the SoT for insert/path keys/layout.
 */
export function sortMindMapNodeIdsByGlobalIndex(a: string, b: string): number {
  return branchGlobalIndex(a) - branchGlobalIndex(b)
}

/** Children grouped by parent in connection-list order (no global-index sort). */
export function buildMindMapChildrenMapByConnectionOrder(
  connections: Connection[]
): Map<string, string[]> {
  const map = new Map<string, string[]>()
  for (const c of connections) {
    const kids = map.get(c.source)
    if (kids) kids.push(c.target)
    else map.set(c.source, [c.target])
  }
  return map
}

function buildChildrenMap(connections: Connection[]): Map<string, string[]> {
  return buildMindMapChildrenMapByConnectionOrder(connections)
}

/** Stable tree path (side + sibling indices) — survives node id regeneration on reload. */
export function mindMapNodePathKey(nodeId: string, connections: Connection[]): string | null {
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

/**
 * Same-parent sibling styles, nearest earlier first then later
 * (so insert-above / index-0 still matches a neighbor).
 */
function siblingStylesNearestFirst(
  pathKey: string,
  stylesByPath: Map<string, NodeStyle>
): NodeStyle[] {
  const parentKey = parentPathKey(pathKey)
  if (!parentKey) return []
  const idx = parseInt(pathKey.slice(pathKey.lastIndexOf('/') + 1), 10)
  if (!Number.isFinite(idx) || idx < 0) return []
  const prefix = `${parentKey}/`
  const before: { i: number; style: NodeStyle }[] = []
  const after: { i: number; style: NodeStyle }[] = []
  for (const [key, style] of stylesByPath) {
    if (!key.startsWith(prefix)) continue
    const rest = key.slice(prefix.length)
    if (rest.includes('/')) continue
    const i = parseInt(rest, 10)
    if (!Number.isFinite(i) || i === idx) continue
    if (!style || Object.keys(style).length === 0) continue
    if (i < idx) before.push({ i, style })
    else after.push({ i, style })
  }
  before.sort((a, b) => b.i - a.i)
  after.sort((a, b) => a.i - b.i)
  return [...before, ...after].map((entry) => entry.style)
}

/** Inherit shape from a same-parent sibling (prefer earlier index, then later). */
function resolveSiblingNodeShape(
  pathKey: string,
  stylesByPath: Map<string, NodeStyle>
): NodeStyle['nodeShape'] | undefined {
  for (const style of siblingStylesNearestFirst(pathKey, stylesByPath)) {
    if (style.nodeShape) return style.nodeShape
  }
  return undefined
}

/** Full visual style from a same-parent sibling (prefer earlier index, then later). */
function resolveSiblingStyle(
  pathKey: string,
  stylesByPath: Map<string, NodeStyle>
): NodeStyle | undefined {
  const styles = siblingStylesNearestFirst(pathKey, stylesByPath)
  return styles[0]
}

/**
 * Colors + typography copied from a sibling for a new node at the same depth.
 * Shape is resolved separately (depth preset / sibling shape / heal rules).
 */
function visualStyleFromSibling(sibling: NodeStyle): Partial<NodeStyle> {
  const next: Partial<NodeStyle> = {}
  if (sibling.backgroundColor) next.backgroundColor = sibling.backgroundColor
  if (sibling.borderColor) next.borderColor = sibling.borderColor
  if (sibling.textColor) next.textColor = sibling.textColor
  if (sibling.borderWidth !== undefined) next.borderWidth = sibling.borderWidth
  if (sibling.borderStyle) next.borderStyle = sibling.borderStyle
  if (sibling.fontFamily) next.fontFamily = sibling.fontFamily
  if (sibling.fontSize !== undefined) next.fontSize = sibling.fontSize
  if (sibling.fontWeight) next.fontWeight = sibling.fontWeight
  if (sibling.fontStyle) next.fontStyle = sibling.fontStyle
  if (sibling.textDecoration) next.textDecoration = sibling.textDecoration
  return next
}

/**
 * Resolve nodeShape after a tree reload.
 * Never inherit the parent's shape — L1 rounded must not overwrite L2 underline in classic.
 * Also heals shapes that were wrongly parent-inherited on a prior reload.
 * When depth changes (drag-reparent), use the diagram-style preset for the new depth.
 */
function resolveMindMapRestoredNodeShape(
  node: DiagramNode,
  pathKey: string,
  preserved: NodeStyle | undefined,
  stylesByPath: Map<string, NodeStyle>,
  nodes: DiagramNode[],
  connections: Connection[],
  diagramStyle: ReturnType<typeof getMindMapDiagramStyleById>,
  previousDepth?: number
): NodeStyle['nodeShape'] {
  const presetShape = mindMapNodeShapeFromPreset(node, diagramStyle)
  if (
    previousDepth !== undefined &&
    node.id.startsWith('branch-') &&
    previousDepth !== mindMapBranchDepth(node.id)
  ) {
    return presetShape
  }

  const fromPreserved = preserved?.nodeShape
  if (!fromPreserved) {
    return resolveSiblingNodeShape(pathKey, stylesByPath) ?? presetShape
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
  diagramStyleId?: string | null,
  previousDepthByPath?: Map<string, number>,
  canvasMode: MindMapCanvasMode = readEffectiveMindMapCanvasMode()
): Record<string, NodeStyle> {
  const v2Visuals = canvasMode === 'v2'
  const nodeStyles: Record<string, NodeStyle> = {}

  // Classic: restore sanitized path styles only — never seed v2 theme defaults.
  if (!v2Visuals) {
    for (const node of nodes) {
      const key = mindMapNodePathKey(node.id, connections)
      if (!key) continue
      const preserved = stylesByPath.get(key)
      if (preserved) {
        const merged = { ...preserved }
        delete merged.nodeShape
        node.style = { ...(node.style || {}), ...merged }
        nodeStyles[node.id] = { ...merged }
      }
    }
    syncLegacyMindMapConnectionStrokeColors(connections, nodes)
    return nodeStyles
  }

  const defaultTheme = getMindMapThemeById(resolveMindMapThemeId(themeId))
  const diagramStyle = getMindMapDiagramStyleById(resolveMindMapDiagramStyleId(diagramStyleId))
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
      diagramStyle,
      previousDepthByPath?.get(key)
    )

    if (preserved) {
      const merged = { ...preserved, nodeShape }
      node.style = { ...(node.style || {}), ...merged }
      nodeStyles[node.id] = { ...merged }
    } else {
      // Single SoT with in-place insert — theme / rainbow / same-row sibling match.
      const themeDefaults = buildMindMapStyleForNewBranchNode(node, connections, {
        themeId,
        diagramStyleId,
        siblingStyle: resolveSiblingStyle(key, stylesByPath),
        nodeShape,
      })
      // themeDefaults last so resolution wins over loader stub `style: { nodeShape }`.
      node.style = { ...(node.style || {}), ...themeDefaults }
      nodeStyles[node.id] = { ...node.style }
    }
  }
  if (isRainbowMindMapTheme(themeId)) {
    syncRainbowMindMapConnectionColors(connections, nodes)
  } else {
    const layered = mindMapDiagramStyleUsesLayeredBranchColors(diagramStyleId)
    const topicBorder =
      nodes.find((n) => n.id === 'topic')?.style?.borderColor ??
      stylesByPath.get('topic')?.borderColor
    const branchAccent =
      defaultTheme.borderColor ?? nodes.find((n) => n.id.startsWith('branch-'))?.style?.borderColor
    const strokeColor = layered && branchAccent ? branchAccent : topicBorder
    if (strokeColor) {
      syncMindMapConnectionStrokeColors(connections, strokeColor)
    }
  }
  return nodeStyles
}

/**
 * Resolve a same-parent sibling style from live graph state (v2 in-place insert).
 * Delegates to the path-keyed nearest-sibling SoT so Enter and reload cannot drift.
 * Topic L1 same-side is inherent in path keys (`r/…` vs `l/…`).
 */
export function resolveMindMapLiveSiblingStyle(
  nodeId: string,
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStylesRecord?: Record<string, NodeStyle>
): NodeStyle | undefined {
  const pathKey = mindMapNodePathKey(nodeId, connections)
  if (!pathKey) return undefined
  const stylesByPath = collectMindMapStylesByPath(nodes, connections, nodeStylesRecord)
  return resolveSiblingStyle(pathKey, stylesByPath)
}

/**
 * Single SoT for a newly added branch node (in-place Enter + reload new path).
 * Theme / diagram-style defaults; rainbow keeps per-L1 accents; non-rainbow matches
 * same-row sibling fill/border/text when present.
 */
export function buildMindMapStyleForNewBranchNode(
  node: Pick<DiagramNode, 'id' | 'type'>,
  connections: Connection[],
  options: {
    themeId?: MindMapThemeId | string | null
    diagramStyleId?: string | null
    siblingStyle?: NodeStyle
    /** Reload heal/depth resolution — wins over sibling/preset when set. */
    nodeShape?: NodeStyle['nodeShape']
  }
): NodeStyle {
  const theme = getMindMapThemeById(resolveMindMapThemeId(options.themeId))
  const diagramStyle = getMindMapDiagramStyleById(
    resolveMindMapDiagramStyleId(options.diagramStyleId)
  )
  const presetShape = mindMapNodeShapeFromPreset(node, diagramStyle)
  const nodeShape = options.nodeShape ?? options.siblingStyle?.nodeShape ?? presetShape

  let style: NodeStyle = {
    ...mindMapStyleFromTheme(node, theme, options.diagramStyleId),
    nodeShape,
  }

  if (isRainbowMindMapTheme(options.themeId)) {
    if (node.id === 'topic' || node.type === 'topic' || node.type === 'center') {
      return {
        ...style,
        backgroundColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
        textColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
        borderColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
      }
    }
    const branchColors = mindMapRainbowColorsForNode(node.id, connections)
    if (!branchColors) return style
    return {
      ...style,
      backgroundColor: branchColors.backgroundColor,
      textColor: branchColors.textColor,
      borderColor: branchColors.borderColor,
    }
  }

  if (options.siblingStyle) {
    return {
      ...style,
      ...visualStyleFromSibling(options.siblingStyle),
      nodeShape,
    }
  }
  return style
}

/** Reconcile persisted connection stroke colors when canvas mode changes or diagram reloads. */
export function resyncMindMapConnectionStrokeColorsForActiveMode(
  diagramType: DiagramType | null,
  nodes: DiagramNode[] | undefined,
  connections: Connection[] | undefined,
  canvasMode: MindMapCanvasMode = readEffectiveMindMapCanvasMode()
): boolean {
  if (!nodes?.length || !connections?.length) return false
  if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return false
  syncMindMapConnectionStrokeColorsForCanvasMode(connections, nodes, canvasMode)
  return true
}

/**
 * Preserve visual styles when mind-map tree is rebuilt (add/remove/move/reload).
 * When `remapNodeId` is provided, styles follow content identity (same as measured dims),
 * and nodeShape updates to the diagram-style preset when depth changes.
 * Without a remapper, styles stay path-slot keyed (used by canvas-mode buckets).
 */
export function mergeMindMapReloadStyles(
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[],
  existingNodeStyles?: Record<string, NodeStyle>,
  themeId?: MindMapThemeId | string | null,
  diagramStyleId?: string | null,
  remapNodeId?: MindMapNodeIdRemapper,
  canvasMode: MindMapCanvasMode = readEffectiveMindMapCanvasMode()
): Record<string, NodeStyle> {
  if (!remapNodeId) {
    const stylesByPath = collectMindMapStylesByPath(oldNodes, oldConnections, existingNodeStyles)
    return applyMindMapStylesByPath(
      newNodes,
      newConnections,
      stylesByPath,
      themeId,
      diagramStyleId,
      undefined,
      canvasMode
    )
  }

  const stylesByPath = new Map<string, NodeStyle>()
  const previousDepthByPath = new Map<string, number>()

  for (const oldNode of oldNodes) {
    const merged = mergeNodeStyle(oldNode, existingNodeStyles)
    if (!merged || Object.keys(merged).length === 0) continue

    const newId = remapNodeId(oldNode.id, oldNodes, oldConnections, newNodes, newConnections)
    if (!newId) continue

    const newPath = mindMapNodePathKey(newId, newConnections)
    if (!newPath) continue

    stylesByPath.set(newPath, merged)
    if (oldNode.id.startsWith('branch-')) {
      previousDepthByPath.set(newPath, mindMapBranchDepth(oldNode.id))
    }
  }

  return applyMindMapStylesByPath(
    newNodes,
    newConnections,
    stylesByPath,
    themeId,
    diagramStyleId,
    previousDepthByPath,
    canvasMode
  )
}
