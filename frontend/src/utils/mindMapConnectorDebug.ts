import { mindMapConnectionAnchorY } from '@/config/mindMapGeometry'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import type { DiagramNode, MindGraphNodeData, NodeStyle } from '@/types'
import type { NodeShape } from '@/utils/nodeShapeStyle'
import {
  getMindMapConnectorDebugLevel,
  isMindMapConnectorDebugEnabled,
  isMindMapConnectorVerboseDebugEnabled,
  setMindMapConnectorDebugLevel,
  type MindMapConnectorDebugLevel,
} from '@/utils/mindMapConnectorDebugLevel'
import {
  beginMindMapConnectorPipeline,
  endMindMapConnectorPipeline,
  logMindMapProcess,
  setMindMapVerboseRecalcGen,
} from '@/utils/mindMapConnectorDebugVerbose'
import { resolveMindMapEdgeEndpoint, resolveMindMapNodeStyle } from '@/utils/mindMapEdgeEndpoints'

export interface MindMapConnectorDebugDumpOptions {
  container: HTMLElement | null
  diagramNodes: DiagramNode[]
  flowNodes: Array<{
    id: string
    position?: { x: number; y: number }
    dimensions?: { width?: number; height?: number }
    data?: {
      estimatedWidth?: number
      estimatedHeight?: number
      style?: NodeStyle
    }
  }>
  edges: Array<{
    id: string
    source: string
    target: string
    sourceX?: number
    sourceY?: number
    targetX?: number
    targetY?: number
  }>
  widths: Record<string, number>
  heights: Record<string, number>
  preservedNodeStyles: Record<string, NodeStyle>
  diagramStyleId?: string
  recalcGeneration: number
  screenToFlowCoordinate: (pos: { x: number; y: number }) => { x: number; y: number }
}

export interface MindMapConnectorDebugNodeRow {
  nodeId: string
  shape: string
  specX: number | null
  specY: number | null
  layoutX: number | null
  layoutY: number | null
  deltaY: number | null
  piniaWidth: number | null
  piniaHeight: number | null
  estimateHeight: number | null
  /** mindMapConnectionAnchorY(layoutY, piniaHeight) — formula only, no Vue Flow. */
  formulaAnchorY: number | null
  /** Vue Flow handle Y from an attached edge (targetY inbound, else sourceY outbound). */
  vueFlowHandleY: number | null
  /** DOM center of the bottom-most .vue-flow__handle on this node. */
  domHandleY: number | null
  /** resolveMindMapEdgeEndpoint Y used when drawing SVG for that edge. */
  resolvedEdgeY: number | null
  /** DOM .mind-map-underline-line midline (flow coords). */
  liveUnderlineY: number | null
  /** liveUnderlineY − formulaAnchorY (positive = bar below formula) */
  formulaVsLivePx: number | null
  /** liveUnderlineY − resolvedEdgeY (positive = bar below SVG path) */
  resolvedVsLivePx: number | null
  /** liveUnderlineY − vueFlowHandleY (positive = bar below handle) */
  vueFlowVsLivePx: number | null
  /** liveUnderlineY − domHandleY (positive = bar below DOM handle) */
  domHandleVsLivePx: number | null
  /** @deprecated use formulaVsLivePx */
  underlineMisalignPx: number | null
  /** Edge sampled for handle/resolved columns (e.g. edge-branch-r-1-0-branch-r-2-1). */
  sampleEdgeId: string | null
}

export interface MindMapConnectorDebugEdgeRow {
  edgeId: string
  source: string
  target: string
  resolvedSourceX: number | null
  resolvedSourceY: number | null
  resolvedTargetX: number | null
  resolvedTargetY: number | null
  vueFlowSourceX: number | null
  vueFlowSourceY: number | null
  vueFlowTargetX: number | null
  vueFlowTargetY: number | null
  liveTargetUnderlineY: number | null
  resolvedTargetVsLivePx: number | null
  vueFlowTargetVsLivePx: number | null
}

export interface MindMapConnectorDebugDump {
  recalcGeneration: number
  level: MindMapConnectorDebugLevel
  nodeRows: MindMapConnectorDebugNodeRow[]
  edgeRows: MindMapConnectorDebugEdgeRow[]
}

let lastSettledDump: MindMapConnectorDebugDump | null = null

type DebugFlowNodeLike = {
  id: string
  position?: { x: number; y: number }
  dimensions?: { width?: number; height?: number }
  data?: MindGraphNodeData
}

function asDebugFlowNode(
  flowNode: MindMapConnectorDebugDumpOptions['flowNodes'][number] | undefined,
): DebugFlowNodeLike | undefined {
  if (!flowNode) return undefined
  return {
    id: flowNode.id,
    position: flowNode.position,
    dimensions: flowNode.dimensions,
    data: flowNode.data as MindGraphNodeData | undefined,
  }
}

function round1(value: number): number {
  return Math.round(value * 10) / 10
}

function resolveShape(
  nodeId: string,
  flowNode: MindMapConnectorDebugDumpOptions['flowNodes'][number] | undefined,
  preservedNodeStyles: Record<string, NodeStyle>,
  diagramStyleId?: string
): NodeShape {
  if (!flowNode) return 'rounded'
  return resolveMindMapNodeShape(
    {
      id: nodeId,
      type: nodeId === 'topic' ? 'topic' : 'branch',
      style: resolveMindMapNodeStyle(
        nodeId,
        flowNode.data as MindGraphNodeData | undefined,
        preservedNodeStyles,
      ),
    },
    diagramStyleId
  )
}

function resolveLayoutHeight(
  nodeId: string,
  flowNode: MindMapConnectorDebugDumpOptions['flowNodes'][number] | undefined,
  heights: Record<string, number>
): number | null {
  const fromPinia = heights[nodeId]
  if (fromPinia != null) return fromPinia
  const estimate = flowNode?.data?.estimatedHeight
  return estimate != null ? estimate : null
}

/** Read-only DOM probe for underline midline Y (does not write to Pinia). */
export function readLiveMindMapUnderlineAnchorY(
  nodeId: string,
  screenToFlowCoordinate: (pos: { x: number; y: number }) => { x: number; y: number }
): number | null {
  if (typeof document === 'undefined') return null
  const wrapper = document.querySelector(
    `.vue-flow__node[data-id="${nodeId}"]`
  ) as HTMLElement | null
  if (!wrapper) return null
  const line = wrapper.querySelector('.mind-map-underline-line') as HTMLElement | null
  if (!line) return null
  const rect = line.getBoundingClientRect()
  if (rect.height < 0.5) return null
  return screenToFlowCoordinate({
    x: rect.left,
    y: rect.top + rect.height / 2,
  }).y
}

/** Read-only DOM probe for vue-flow handle center Y (bottom-most handle on underline nodes). */
export function readLiveMindMapHandleAnchorY(
  nodeId: string,
  screenToFlowCoordinate: (pos: { x: number; y: number }) => { x: number; y: number }
): number | null {
  if (typeof document === 'undefined') return null
  const wrapper = document.querySelector(
    `.vue-flow__node[data-id="${nodeId}"]`
  ) as HTMLElement | null
  if (!wrapper) return null
  const handles = wrapper.querySelectorAll('.vue-flow__handle')
  if (handles.length === 0) return null

  let bestY: number | null = null
  handles.forEach((handle) => {
    const rect = handle.getBoundingClientRect()
    if (rect.width < 0.5 && rect.height < 0.5) return
    const y = screenToFlowCoordinate({
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    }).y
    if (bestY == null || y > bestY) {
      bestY = y
    }
  })
  return bestY
}

interface NodeEdgeAnchorSample {
  edgeId: string
  vueFlowHandleY: number
  resolvedEdgeY: number
}

function buildNodeEdgeAnchorIndex(
  options: MindMapConnectorDebugDumpOptions
): Map<string, NodeEdgeAnchorSample> {
  const flowById = new Map(options.flowNodes.map((node) => [node.id, node]))
  const index = new Map<string, NodeEdgeAnchorSample>()

  for (const edge of options.edges) {
    const targetNode = asDebugFlowNode(flowById.get(edge.target))
    const sourceNode = asDebugFlowNode(flowById.get(edge.source))
    const targetStyle = resolveMindMapNodeStyle(
      edge.target,
      targetNode?.data,
      options.preservedNodeStyles
    )
    const sourceStyle = resolveMindMapNodeStyle(
      edge.source,
      sourceNode?.data,
      options.preservedNodeStyles
    )
    const targetMeasured = {
      width: options.widths[edge.target],
      height: options.heights[edge.target],
    }
    const sourceMeasured = {
      width: options.widths[edge.source],
      height: options.heights[edge.source],
    }
    const targetFallback = {
      x: edge.targetX ?? targetNode?.position?.x ?? 0,
      y:
        edge.targetY ??
        readLiveMindMapHandleAnchorY(edge.target, options.screenToFlowCoordinate) ??
        targetNode?.position?.y ??
        0,
    }
    const sourceFallback = {
      x: edge.sourceX ?? sourceNode?.position?.x ?? 0,
      y:
        edge.sourceY ??
        readLiveMindMapHandleAnchorY(edge.source, options.screenToFlowCoordinate) ??
        sourceNode?.position?.y ??
        0,
    }
    const resolvedTarget = resolveMindMapEdgeEndpoint(
      targetNode,
      'target',
      targetFallback,
      targetStyle,
      targetMeasured,
      options.diagramStyleId
    )
    const resolvedSource = resolveMindMapEdgeEndpoint(
      sourceNode,
      'source',
      sourceFallback,
      sourceStyle,
      sourceMeasured,
      options.diagramStyleId
    )

    if (!index.has(edge.target)) {
      index.set(edge.target, {
        edgeId: edge.id,
        vueFlowHandleY:
          edge.targetY ??
          readLiveMindMapHandleAnchorY(edge.target, options.screenToFlowCoordinate) ??
          targetFallback.y,
        resolvedEdgeY: resolvedTarget.y,
      })
    }
    if (!index.has(edge.source)) {
      index.set(edge.source, {
        edgeId: edge.id,
        vueFlowHandleY:
          edge.sourceY ??
          readLiveMindMapHandleAnchorY(edge.source, options.screenToFlowCoordinate) ??
          sourceFallback.y,
        resolvedEdgeY: resolvedSource.y,
      })
    }
  }

  return index
}

function buildNodeRows(options: MindMapConnectorDebugDumpOptions): MindMapConnectorDebugNodeRow[] {
  const specById = new Map(options.diagramNodes.map((node) => [node.id, node]))
  const edgeAnchorByNode = buildNodeEdgeAnchorIndex(options)

  return options.flowNodes.map((flowNode) => {
    const nodeId = flowNode.id
    const spec = specById.get(nodeId)
    const shape = resolveShape(
      nodeId,
      flowNode,
      options.preservedNodeStyles,
      options.diagramStyleId
    )
    const layoutY = flowNode.position?.y ?? null
    const specY = spec?.position?.y ?? null
    const piniaHeight = resolveLayoutHeight(nodeId, flowNode, options.heights)
    const formulaAnchorY =
      layoutY != null && piniaHeight != null
        ? mindMapConnectionAnchorY(layoutY, piniaHeight, shape)
        : null
    const liveUnderlineY =
      shape === 'underline'
        ? readLiveMindMapUnderlineAnchorY(nodeId, options.screenToFlowCoordinate)
        : null
    const domHandleY =
      shape === 'underline'
        ? readLiveMindMapHandleAnchorY(nodeId, options.screenToFlowCoordinate)
        : null
    const edgeSample = edgeAnchorByNode.get(nodeId)
    const vueFlowHandleY = edgeSample?.vueFlowHandleY ?? null
    const resolvedEdgeY = edgeSample?.resolvedEdgeY ?? null
    const formulaVsLivePx =
      formulaAnchorY != null && liveUnderlineY != null
        ? round1(liveUnderlineY - formulaAnchorY)
        : null
    const resolvedVsLivePx =
      resolvedEdgeY != null && liveUnderlineY != null
        ? round1(liveUnderlineY - resolvedEdgeY)
        : null
    const vueFlowVsLivePx =
      vueFlowHandleY != null && liveUnderlineY != null
        ? round1(liveUnderlineY - vueFlowHandleY)
        : null
    const domHandleVsLivePx =
      domHandleY != null && liveUnderlineY != null ? round1(liveUnderlineY - domHandleY) : null

    return {
      nodeId,
      shape,
      specX: spec?.position?.x ?? null,
      specY,
      layoutX: flowNode.position?.x ?? null,
      layoutY,
      deltaY:
        specY != null && layoutY != null ? round1(layoutY - specY) : null,
      piniaWidth: options.widths[nodeId] ?? null,
      piniaHeight,
      estimateHeight: (flowNode.data?.estimatedHeight as number | undefined) ?? null,
      formulaAnchorY: formulaAnchorY != null ? round1(formulaAnchorY) : null,
      vueFlowHandleY: vueFlowHandleY != null ? round1(vueFlowHandleY) : null,
      domHandleY: domHandleY != null ? round1(domHandleY) : null,
      resolvedEdgeY: resolvedEdgeY != null ? round1(resolvedEdgeY) : null,
      liveUnderlineY: liveUnderlineY != null ? round1(liveUnderlineY) : null,
      formulaVsLivePx,
      resolvedVsLivePx,
      vueFlowVsLivePx,
      domHandleVsLivePx,
      underlineMisalignPx: formulaVsLivePx,
      sampleEdgeId: edgeSample?.edgeId ?? null,
    }
  })
}

function buildEdgeRows(options: MindMapConnectorDebugDumpOptions): MindMapConnectorDebugEdgeRow[] {
  const flowById = new Map(options.flowNodes.map((node) => [node.id, node]))

  return options.edges.map((edge) => {
    const sourceNode = asDebugFlowNode(flowById.get(edge.source))
    const targetNode = asDebugFlowNode(flowById.get(edge.target))
    const sourceStyle = resolveMindMapNodeStyle(
      edge.source,
      sourceNode?.data,
      options.preservedNodeStyles
    )
    const targetStyle = resolveMindMapNodeStyle(
      edge.target,
      targetNode?.data,
      options.preservedNodeStyles
    )
    const sourceMeasured = {
      width: options.widths[edge.source],
      height: options.heights[edge.source],
    }
    const targetMeasured = {
      width: options.widths[edge.target],
      height: options.heights[edge.target],
    }
    const sourceFallback = {
      x: edge.sourceX ?? sourceNode?.position?.x ?? 0,
      y:
        edge.sourceY ??
        readLiveMindMapHandleAnchorY(edge.source, options.screenToFlowCoordinate) ??
        sourceNode?.position?.y ??
        0,
    }
    const targetFallback = {
      x: edge.targetX ?? targetNode?.position?.x ?? 0,
      y:
        edge.targetY ??
        readLiveMindMapHandleAnchorY(edge.target, options.screenToFlowCoordinate) ??
        targetNode?.position?.y ??
        0,
    }
    const resolvedSource = resolveMindMapEdgeEndpoint(
      sourceNode,
      'source',
      sourceFallback,
      sourceStyle,
      sourceMeasured,
      options.diagramStyleId
    )
    const resolvedTarget = resolveMindMapEdgeEndpoint(
      targetNode,
      'target',
      targetFallback,
      targetStyle,
      targetMeasured,
      options.diagramStyleId
    )

    const targetShape = resolveShape(
      edge.target,
      flowById.get(edge.target),
      options.preservedNodeStyles,
      options.diagramStyleId
    )
    const liveTargetUnderlineY =
      targetShape === 'underline'
        ? readLiveMindMapUnderlineAnchorY(edge.target, options.screenToFlowCoordinate)
        : null
    const resolvedTargetVsLivePx =
      liveTargetUnderlineY != null
        ? round1(liveTargetUnderlineY - resolvedTarget.y)
        : null
    const vueFlowTargetVsLivePx =
      edge.targetY != null && liveTargetUnderlineY != null
        ? round1(liveTargetUnderlineY - edge.targetY)
        : null

    if (isMindMapConnectorVerboseDebugEnabled()) {
      logMindMapProcess('edge:resolve', {
        edgeId: edge.id,
        source: edge.source,
        target: edge.target,
        resolvedSource,
        resolvedTarget,
        vueFlowSource: sourceFallback,
        vueFlowTarget: targetFallback,
      })
    }

    return {
      edgeId: edge.id,
      source: edge.source,
      target: edge.target,
      resolvedSourceX: round1(resolvedSource.x),
      resolvedSourceY: round1(resolvedSource.y),
      resolvedTargetX: round1(resolvedTarget.x),
      resolvedTargetY: round1(resolvedTarget.y),
      vueFlowSourceX: edge.sourceX ?? null,
      vueFlowSourceY: edge.sourceY ?? null,
      vueFlowTargetX: edge.targetX ?? null,
      vueFlowTargetY: edge.targetY ?? null,
      liveTargetUnderlineY:
        liveTargetUnderlineY != null ? round1(liveTargetUnderlineY) : null,
      resolvedTargetVsLivePx,
      vueFlowTargetVsLivePx,
    }
  })
}

export function dumpMindMapConnectorDebug(options: MindMapConnectorDebugDumpOptions): void {
  if (!isMindMapConnectorDebugEnabled()) return

  if (isMindMapConnectorVerboseDebugEnabled()) {
    setMindMapVerboseRecalcGen(options.recalcGeneration)
    beginMindMapConnectorPipeline(options.recalcGeneration, 'settled dump')
  }

  const nodeRows = buildNodeRows(options)
  const edgeRows = buildEdgeRows(options)
  const dump: MindMapConnectorDebugDump = {
    recalcGeneration: options.recalcGeneration,
    level: getMindMapConnectorDebugLevel(),
    nodeRows,
    edgeRows,
  }
  lastSettledDump = dump

  const misaligned = nodeRows.filter(
    (row) =>
      row.shape === 'underline' &&
      row.resolvedVsLivePx != null &&
      Math.abs(row.resolvedVsLivePx) > 1
  )
  const underlineRows = nodeRows.filter((row) => row.shape === 'underline')

  console.groupCollapsed(
    `[MindMap connector debug] recalc=${options.recalcGeneration} nodes=${nodeRows.length} edges=${edgeRows.length} level=${dump.level}`
  )
  if (underlineRows.length > 0) {
    console.info(
      '[MindMap] Underline anchor compare — live bar vs formula / Vue Flow handle / resolved SVG Y:'
    )
    console.table(underlineRows)
  }
  console.table(nodeRows)
  console.table(edgeRows)
  if (misaligned.length === 0) {
    console.info('[MindMap OK] No underline resolvedEdgeY vs live bar misalignment > 1px.')
  } else {
    console.warn(
      `[MindMap WARN] ${misaligned.length} underline node(s) SVG Y misaligned > 1px — mindMapConnectorDebug.inspect()`
    )
  }
  console.info(
    'Columns: formulaVsLivePx = formula−live | resolvedVsLivePx = SVG−live | vueFlowVsLivePx = handle−live | domHandleVsLivePx = DOM handle−live'
  )
  console.info(
    'Levels: localStorage mindgraph.debugMindMapConnectors = "1" | "verbose" (or window.mindMapConnectorDebug.enableBasic())'
  )
  console.info(
    'Inspect: mindMapConnectorDebug.inspect("branch-r-2-1") | mindMapConnectorDebug.inspectEdges("branch-r-2-1")'
  )
  console.groupEnd()

  logMindMapProcess('debug:dump', {
    recalcGeneration: options.recalcGeneration,
    nodeCount: nodeRows.length,
    edgeCount: edgeRows.length,
    movedYCount: nodeRows.filter(
      (row) => row.deltaY != null && Math.abs(row.deltaY) >= 0.5
    ).length,
    underlineMisalignedCount: misaligned.length,
  })

  if (isMindMapConnectorVerboseDebugEnabled()) {
    endMindMapConnectorPipeline()
  }
}

export function inspectMindMapConnectorDebug(nodeId?: string): void {
  if (!lastSettledDump) {
    console.warn('[MindMap] No settled dump yet — wait for recalc or reload with debug enabled.')
    return
  }
  const rows = nodeId
    ? lastSettledDump.nodeRows.filter((row) => row.nodeId === nodeId)
    : lastSettledDump.nodeRows.filter((row) => row.shape === 'underline')
  if (rows.length === 0) {
    console.warn(`[MindMap] No debug rows for nodeId=${nodeId ?? '(underline only)'}`)
    return
  }
  console.info(`recalc=${lastSettledDump.recalcGeneration} — underline anchor compare`)
  console.table(
    rows.map((row) => ({
      nodeId: row.nodeId,
      layoutY: row.layoutY,
      piniaHeight: row.piniaHeight,
      liveUnderlineY: row.liveUnderlineY,
      formulaAnchorY: row.formulaAnchorY,
      vueFlowHandleY: row.vueFlowHandleY,
      domHandleY: row.domHandleY,
      resolvedEdgeY: row.resolvedEdgeY,
      formulaVsLivePx: row.formulaVsLivePx,
      vueFlowVsLivePx: row.vueFlowVsLivePx,
      domHandleVsLivePx: row.domHandleVsLivePx,
      resolvedVsLivePx: row.resolvedVsLivePx,
      sampleEdgeId: row.sampleEdgeId,
    }))
  )
}

export function inspectMindMapConnectorDebugEdges(nodeId?: string): void {
  if (!lastSettledDump) {
    console.warn('[MindMap] No settled dump yet — wait for recalc or reload with debug enabled.')
    return
  }
  const rows = nodeId
    ? lastSettledDump.edgeRows.filter(
        (row) => row.source === nodeId || row.target === nodeId
      )
    : lastSettledDump.edgeRows.filter((row) => row.liveTargetUnderlineY != null)
  if (rows.length === 0) {
    console.warn(`[MindMap] No edge rows for nodeId=${nodeId ?? '(underline targets)'}`)
    return
  }
  console.info(`recalc=${lastSettledDump.recalcGeneration} — edge endpoint compare`)
  console.table(rows)
}

declare global {
  interface Window {
    mindMapConnectorDebug?: {
      inspect: (nodeId?: string) => void
      inspectEdges: (nodeId?: string) => void
      enableVerbose: () => void
      enableBasic: () => void
      disable: () => void
      getLevel: () => MindMapConnectorDebugLevel
    }
  }
}

if (typeof window !== 'undefined' && import.meta.env.DEV) {
  window.mindMapConnectorDebug = {
    inspect: inspectMindMapConnectorDebug,
    inspectEdges: inspectMindMapConnectorDebugEdges,
    enableVerbose: () => setMindMapConnectorDebugLevel('verbose'),
    enableBasic: () => setMindMapConnectorDebugLevel('basic'),
    disable: () => setMindMapConnectorDebugLevel('off'),
    getLevel: getMindMapConnectorDebugLevel,
  }
}
