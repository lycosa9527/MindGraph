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
  formulaAnchorY: number | null
  liveUnderlineY: number | null
  underlineMisalignPx: number | null
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

function buildNodeRows(options: MindMapConnectorDebugDumpOptions): MindMapConnectorDebugNodeRow[] {
  const specById = new Map(options.diagramNodes.map((node) => [node.id, node]))
  const flowById = new Map(options.flowNodes.map((node) => [node.id, node]))

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
    const underlineMisalignPx =
      formulaAnchorY != null && liveUnderlineY != null
        ? round1(liveUnderlineY - formulaAnchorY)
        : null

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
      liveUnderlineY: liveUnderlineY != null ? round1(liveUnderlineY) : null,
      underlineMisalignPx,
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
      y: edge.sourceY ?? sourceNode?.position?.y ?? 0,
    }
    const targetFallback = {
      x: edge.targetX ?? targetNode?.position?.x ?? 0,
      y: edge.targetY ?? targetNode?.position?.y ?? 0,
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
      row.underlineMisalignPx != null &&
      Math.abs(row.underlineMisalignPx) > 1
  )

  console.groupCollapsed(
    `[MindMap connector debug] recalc=${options.recalcGeneration} nodes=${nodeRows.length} edges=${edgeRows.length} level=${dump.level}`
  )
  console.table(nodeRows)
  console.table(edgeRows)
  if (misaligned.length === 0) {
    console.info('[MindMap OK] No underline misalignment > 1px in settled dump.')
  } else {
    console.warn(
      `[MindMap WARN] ${misaligned.length} underline node(s) misaligned > 1px — inspect with mindMapConnectorDebug.inspect(nodeId)`
    )
  }
  console.info(
    'Levels: localStorage mindgraph.debugMindMapConnectors = "0" | "1" | "verbose" (or window.mindMapConnectorDebug.enableVerbose())'
  )
  console.info(
    'Inspect: mindMapConnectorDebug.inspect("branch-r-2-1") or .inspect() for all underline rows.'
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
  console.info(`recalc=${lastSettledDump.recalcGeneration} — node position / anchor rows`)
  console.table(rows)
}

declare global {
  interface Window {
    mindMapConnectorDebug?: {
      inspect: (nodeId?: string) => void
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
    enableVerbose: () => setMindMapConnectorDebugLevel('verbose'),
    enableBasic: () => setMindMapConnectorDebugLevel('basic'),
    disable: () => setMindMapConnectorDebugLevel('off'),
    getLevel: getMindMapConnectorDebugLevel,
  }
}
