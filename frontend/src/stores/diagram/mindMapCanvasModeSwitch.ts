import { DEFAULT_CENTER_X } from '@/composables/diagrams/layoutConfig'
import { syncMindMapConnectionStrokeColorsForCanvasMode } from '@/config/mindMapGeometry'
import type { MindMapCanvasMode } from '@/stores/ui'
import type {
  DiagramData,
  DiagramNode,
  MindMapCanvasStyleBuckets,
  MindMapCanvasStylesByPath,
  NodeStyle,
} from '@/types'
import { loadMindMapSpec, nodesAndConnectionsToMindMapSpec } from '../specLoader'
import {
  pruneMindMapCollapsedPaths,
  remapMindMapCollapsedPathsAfterReload,
  setMindMapCollapsedPaths,
} from './mindMapCollapse'
import { emitEvent, getMindMapCurveExtents } from './events'
import {
  applyMindMapStylesByPath,
  collectMindMapStylesByPath,
} from './mindMapStylePreservation'
import type { DiagramContext } from './types'

function isMindMapType(type: string | null | undefined): boolean {
  return type === 'mindmap' || type === 'mind_map'
}

function ensureMindMapCanvasBuckets(data: DiagramData): MindMapCanvasStyleBuckets {
  if (!data._mindmap_canvas) {
    data._mindmap_canvas = {}
  }
  return data._mindmap_canvas
}

function stylesMapToRecord(map: Map<string, NodeStyle>): MindMapCanvasStylesByPath {
  return Object.fromEntries(map)
}

function stylesRecordToMap(record: MindMapCanvasStylesByPath | undefined): Map<string, NodeStyle> {
  if (!record) return new Map()
  return new Map(Object.entries(record))
}

/** Strip v2-only fields before persisting classic canvas styles. */
export function sanitizeLegacyNodeStyle(style: NodeStyle): NodeStyle {
  const cleaned = { ...style }
  delete cleaned.nodeShape
  delete cleaned.backgroundColor
  delete cleaned.borderColor
  return cleaned
}

function sanitizeLegacyStylesByPath(
  styles: MindMapCanvasStylesByPath
): MindMapCanvasStylesByPath {
  const out: MindMapCanvasStylesByPath = {}
  for (const [pathKey, style] of Object.entries(styles)) {
    out[pathKey] = sanitizeLegacyNodeStyle(style)
  }
  return out
}

/** Strip v2-only fields from a persisted _node_styles map (legacy canvas load). */
export function sanitizeLegacyNodeStylesRecord(
  record: Record<string, NodeStyle>
): Record<string, NodeStyle> {
  const out: Record<string, NodeStyle> = {}
  for (const [nodeId, style] of Object.entries(record)) {
    out[nodeId] = sanitizeLegacyNodeStyle(style)
  }
  return out
}

function hasMindMapNodes(data: DiagramData): boolean {
  return Boolean(data.nodes?.length)
}

/** Persist live diagram styles into the bucket for the given canvas mode. */
export function snapshotMindMapCanvasBucket(
  data: DiagramData,
  mode: MindMapCanvasMode
): void {
  if (!hasMindMapNodes(data)) return

  const connections = data.connections ?? []
  const buckets = ensureMindMapCanvasBuckets(data)
  const stylesByPath = collectMindMapStylesByPath(
    data.nodes,
    connections,
    data._node_styles
  )
  const stylesRecord =
    mode === 'legacy'
      ? sanitizeLegacyStylesByPath(stylesMapToRecord(stylesByPath))
      : stylesMapToRecord(stylesByPath)

  if (mode === 'legacy') {
    buckets.legacy = { node_styles_by_path: stylesRecord }
    return
  }

  buckets.v2 = {
    node_styles_by_path: stylesMapToRecord(stylesByPath),
    theme: data._mindmap_theme,
    collapsed_paths: data._collapsed_paths?.length ? [...data._collapsed_paths] : undefined,
  }
}

function retainMeasuredDimensions(ctx: DiagramContext, newNodes: DiagramNode[]): void {
  const surviving = new Set(newNodes.map((node) => node.id))

  const widths = ctx.mindMapNodeWidths.value
  for (const id of Object.keys(widths)) {
    if (!surviving.has(id)) delete widths[id]
  }

  const heights = ctx.mindMapNodeHeights.value
  for (const id of Object.keys(heights)) {
    if (!surviving.has(id)) delete heights[id]
  }
}

function stylesByPathForMode(
  data: DiagramData,
  mode: MindMapCanvasMode
): Map<string, NodeStyle> {
  const buckets = data._mindmap_canvas
  if (mode === 'v2') {
    return stylesRecordToMap(buckets?.v2?.node_styles_by_path)
  }
  const legacy = buckets?.legacy?.node_styles_by_path
  return stylesRecordToMap(legacy ? sanitizeLegacyStylesByPath(legacy) : undefined)
}

/**
 * Apply saved per-mode buckets after load (or when UI mode differs from inline _node_styles).
 */
export function hydrateMindMapCanvasStylesOnLoad(
  data: DiagramData,
  mode: MindMapCanvasMode
): void {
  if (!hasMindMapNodes(data)) return

  const connections = data.connections ?? []
  const bucketStyles = stylesByPathForMode(data, mode)

  if (bucketStyles.size > 0) {
    const themeId =
      mode === 'v2' ? (data._mindmap_canvas?.v2?.theme ?? data._mindmap_theme) : undefined
    data._node_styles = applyMindMapStylesByPath(
      data.nodes,
      connections,
      bucketStyles,
      themeId
    )
    if (mode === 'legacy') {
      for (const node of data.nodes) {
        if (node.style) {
          node.style = sanitizeLegacyNodeStyle(node.style)
        }
      }
      if (data._node_styles) {
        data._node_styles = sanitizeLegacyNodeStylesRecord(data._node_styles)
      }
    }
  } else if (mode === 'legacy' && data._node_styles) {
    data._node_styles = sanitizeLegacyNodeStylesRecord(data._node_styles)
    for (const node of data.nodes) {
      if (node.style?.nodeShape) {
        node.style = sanitizeLegacyNodeStyle(node.style)
      }
    }
  }

  if (mode === 'v2') {
    const theme = data._mindmap_canvas?.v2?.theme ?? data._mindmap_theme
    if (theme) {
      data._mindmap_theme = theme
    }
    const collapsed = data._mindmap_canvas?.v2?.collapsed_paths ?? data._collapsed_paths
    if (collapsed?.length) {
      setMindMapCollapsedPaths(data as Record<string, unknown>, collapsed)
    }
  } else {
    delete data._mindmap_theme
    setMindMapCollapsedPaths(data as Record<string, unknown>, [])
  }

  if (connections.length > 0) {
    syncMindMapConnectionStrokeColorsForCanvasMode(connections, data.nodes, mode)
  }
}

/**
 * Full canvas-mode reconciliation: snapshot outgoing mode, reload tree for new handles/layout,
 * restore target mode bucket, sync connection colors.
 */
export function reconcileMindMapCanvasModeSwitch(
  ctx: DiagramContext,
  previousMode: MindMapCanvasMode,
  newMode: MindMapCanvasMode
): boolean {
  if (previousMode === newMode) return false
  if (!isMindMapType(ctx.type.value)) return false
  if (!ctx.data.value?.nodes?.length) return false

  const data = ctx.data.value
  const oldNodes = data.nodes
  const oldConnections = data.connections ?? []

  snapshotMindMapCanvasBucket(data, previousMode)

  const spec = nodesAndConnectionsToMindMapSpec(oldNodes, oldConnections)
  const result = loadMindMapSpec({
    topic: spec.topic,
    leftBranches: spec.leftBranches,
    rightBranches: spec.rightBranches,
    preserveLeftRight: true,
  })

  const stylesByPath = stylesByPathForMode(data, newMode)
  const v2Bucket = data._mindmap_canvas?.v2

  let themeId: string | null | undefined
  if (newMode === 'v2') {
    themeId = v2Bucket?.theme ?? data._mindmap_theme
    if (themeId) {
      data._mindmap_theme = themeId
    }
  } else {
    delete data._mindmap_theme
  }

  const mergedNodeStyles = applyMindMapStylesByPath(
    result.nodes,
    result.connections,
    stylesByPath,
    themeId
  )

  if (newMode === 'legacy') {
    for (const node of result.nodes) {
      if (node.style) {
        node.style = sanitizeLegacyNodeStyle(node.style)
      }
    }
    for (const [nodeId, style] of Object.entries(mergedNodeStyles)) {
      mergedNodeStyles[nodeId] = sanitizeLegacyNodeStyle(style)
    }
  }

  retainMeasuredDimensions(ctx, result.nodes)

  data.nodes = result.nodes
  data.connections = result.connections
  data._node_styles = mergedNodeStyles

  if (newMode === 'v2') {
    const collapsedSeed = v2Bucket?.collapsed_paths ?? data._collapsed_paths ?? []
    const remapped = remapMindMapCollapsedPathsAfterReload(
      oldNodes,
      oldConnections,
      result.nodes,
      result.connections,
      collapsedSeed
    )
    const pruned = pruneMindMapCollapsedPaths(result.nodes, result.connections, remapped)
    setMindMapCollapsedPaths(data as Record<string, unknown>, pruned)
  } else {
    setMindMapCollapsedPaths(data as Record<string, unknown>, [])
  }

  snapshotMindMapCanvasBucket(data, newMode)

  syncMindMapConnectionStrokeColorsForCanvasMode(
    data.connections ?? [],
    data.nodes,
    newMode
  )

  ctx.mindMapRecalcTrigger.value += 1
  if (result.nodes.length > 0) {
    const topicNode = result.nodes.find((node) => node.id === 'topic')
    const topicW =
      (topicNode?.data?.estimatedWidth as number | undefined) ??
      (topicNode?.style?.width as number | undefined) ??
      120
    const centerX =
      topicNode?.position != null ? topicNode.position.x + topicW / 2 : DEFAULT_CENTER_X
    ctx.mindMapCurveExtentBaseline.value = getMindMapCurveExtents(result.nodes, centerX)
  }

  if (ctx.pushHistory) {
    ctx.pushHistory('Switch mind map canvas mode')
  }
  emitEvent('diagram:style_changed', { preset: true })
  return true
}
