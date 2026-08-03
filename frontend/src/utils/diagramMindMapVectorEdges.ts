/**
 * Edge path SVG for mind-map vector export (v2 orthogonal + legacy bezier).
 */
import { getBezierPath, Position } from '@vue-flow/core'

import {
  MIND_MAP_GEOMETRY,
  MINDMAP_UNDERLINE_STROKE_WIDTH,
  mindMapConnectionAnchorY,
  resolveMindMapTopicBorderColor,
  resolveMindMapTopicStemWidth,
} from '@/config/mindMapGeometry'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import type { Connection, MindGraphNodeType, NodeStyle } from '@/types'
import {
  mindMapBranchSide,
  resolveMindMapEdgeEndpoint,
} from '@/utils/mindMapEdgeEndpoints'
import {
  buildMindMapBracketBusPath,
  computeMindMapSharedTrunkX,
} from '@/utils/mindMapOrthogonalPath'
import {
  buildMindMapOrthogonalSiblingMap,
  mindMapOrthogonalSiblingGroupKey,
} from '@/utils/mindMapOrthogonalSiblings'
import { resolveMindMapOutlineWireframeEdgeStroke } from '@/utils/mindMapOutlineWireframeStyle'
import type { MindMapVectorNodeDraw } from '@/utils/diagramMindMapVectorNodes'

type NodeMap = Map<string, MindMapVectorNodeDraw>

function toFlowNode(node: MindMapVectorNodeDraw) {
  const nodeType: MindGraphNodeType =
    node.id === 'topic' || node.type === 'topic' || node.type === 'center'
      ? 'topic'
      : 'branch'
  return {
    id: node.id,
    position: { x: node.x, y: node.y },
    dimensions: { width: node.width, height: node.height },
    data: {
      label: node.text,
      nodeType,
      diagramType: 'mind_map' as const,
      style: node.style,
    },
  }
}

function topicStemWidth(topic: MindMapVectorNodeDraw, topicActualWidth?: number | null): number {
  return resolveMindMapTopicStemWidth(topicActualWidth ?? topic.width, topic.width)
}

function topicSourcePoint(
  topic: MindMapVectorNodeDraw,
  targetId: string,
  diagramStyleId: string | null | undefined,
  topicActualWidth?: number | null
): { x: number; y: number } {
  const w = topicStemWidth(topic, topicActualWidth)
  const shape = resolveMindMapNodeShape(
    { id: topic.id, type: 'topic', style: topic.style },
    diagramStyleId
  )
  const side = mindMapBranchSide(targetId)
  const baseX = side === 'left' ? topic.x : topic.x + w
  return resolveMindMapEdgeEndpoint(
    toFlowNode({ ...topic, width: w }),
    'source',
    { x: baseX, y: mindMapConnectionAnchorY(topic.y, topic.height, shape) },
    topic.style,
    { width: w, height: topic.height },
    diagramStyleId
  )
}

function endpointFor(
  node: MindMapVectorNodeDraw | undefined,
  role: 'source' | 'target',
  fallback: { x: number; y: number },
  diagramStyleId: string | null | undefined
): { x: number; y: number } {
  if (!node) return fallback
  return resolveMindMapEdgeEndpoint(
    toFlowNode(node),
    role,
    fallback,
    node.style,
    { width: node.width, height: node.height },
    diagramStyleId
  )
}

function edgeStroke(
  topic: MindMapVectorNodeDraw | undefined,
  connection: Connection,
  outlineWireframe: boolean
): { color: string; width: number; opacity: number; dash: string } {
  if (outlineWireframe) {
    return {
      color: resolveMindMapOutlineWireframeEdgeStroke(),
      width: connection.style?.strokeWidth ?? MIND_MAP_GEOMETRY.edgeStrokeWidth,
      opacity: 1,
      dash: connection.style?.strokeDasharray || 'none',
    }
  }
  return {
    color:
      connection.style?.strokeColor ||
      resolveMindMapTopicBorderColor(topic ? { style: topic.style } : null),
    width: connection.style?.strokeWidth ?? MIND_MAP_GEOMETRY.edgeStrokeWidth,
    opacity: MIND_MAP_GEOMETRY.edgeStrokeOpacity,
    dash: connection.style?.strokeDasharray || 'none',
  }
}

function renderPath(
  d: string,
  stroke: { color: string; width: number; opacity: number; dash: string }
): string {
  const dashAttr = stroke.dash !== 'none' ? ` stroke-dasharray="${stroke.dash}"` : ''
  return (
    `<path d="${d}" fill="none" stroke="${stroke.color}" stroke-width="${stroke.width}" ` +
    `stroke-opacity="${stroke.opacity}" stroke-linecap="butt" stroke-linejoin="round"${dashAttr} />`
  )
}

function renderV2Edges(
  connections: Connection[],
  nodes: NodeMap,
  diagramStyleId: string | null | undefined,
  outlineWireframe: boolean,
  topicActualWidth?: number | null
): string {
  const visible = connections.filter(
    (c) => nodes.has(c.source) && nodes.has(c.target)
  )
  const siblingMap = buildMindMapOrthogonalSiblingMap(visible)
  const topic = nodes.get('topic')
  const chunks: string[] = []
  const drawnUnderlineBars = new Set<string>()

  for (const connection of visible) {
    const source = nodes.get(connection.source)
    const target = nodes.get(connection.target)
    if (!source || !target) continue

    const fromTopic = connection.source === 'topic'
    const from = fromTopic
      ? topicSourcePoint(source, connection.target, diagramStyleId, topicActualWidth)
      : endpointFor(
          source,
          'source',
          { x: source.x + source.width, y: source.y + source.height / 2 },
          diagramStyleId
        )
    const to = endpointFor(
      target,
      'target',
      { x: target.x, y: target.y + target.height / 2 },
      diagramStyleId
    )

    const groupKey = mindMapOrthogonalSiblingGroupKey(connection.source, connection.target)
    const siblings = siblingMap.get(groupKey) ?? [connection]
    const siblingTargets = siblings
      .map((edge) => nodes.get(edge.target))
      .filter((n): n is MindMapVectorNodeDraw => Boolean(n))

    const siblingPoints = siblingTargets.map((node) =>
      endpointFor(
        node,
        'target',
        { x: node.x, y: node.y + node.height / 2 },
        diagramStyleId
      )
    )
    const siblingYs = siblingPoints.map((p) => p.y)
    const siblingXs = siblingPoints.map((p) => p.x)
    const trunkX = computeMindMapSharedTrunkX(from.x, siblingXs, to.x)

    const sorted = [...siblings].sort((a, b) => String(a.id).localeCompare(String(b.id)))
    const drawSpine = siblings.length <= 1 || sorted[0]?.id === connection.id

    const targetShape = resolveMindMapNodeShape(
      { id: target.id, type: target.type as 'branch', style: target.style },
      diagramStyleId
    )
    const d = buildMindMapBracketBusPath(from.x, from.y, to.x, to.y, trunkX, siblingYs, {
      drawSpine,
      siblingToXs: siblingXs,
      singleUnderlineChild: siblingYs.length === 1 && targetShape === 'underline',
      singleTopicSideChild: fromTopic && siblings.length === 1,
    })

    const stroke = edgeStroke(topic, connection, outlineWireframe)
    chunks.push(renderPath(d, stroke))

    if (targetShape === 'underline' && !drawnUnderlineBars.has(target.id)) {
      drawnUnderlineBars.add(target.id)
      const y = to.y
      const bar = `M ${target.x} ${y} L ${target.x + target.width} ${y}`
      chunks.push(
        renderPath(bar, {
          ...stroke,
          width: MINDMAP_UNDERLINE_STROKE_WIDTH,
        })
      )
    }
  }

  return chunks.join('')
}

function legacyHandlePositions(
  source: MindMapVectorNodeDraw,
  target: MindMapVectorNodeDraw
): { sourcePosition: Position; targetPosition: Position } {
  const sourceSide = mindMapBranchSide(source.id)
  const targetSide = mindMapBranchSide(target.id)
  if (source.id === 'topic') {
    const side = mindMapBranchSide(target.id)
    return {
      sourcePosition: side === 'left' ? Position.Left : Position.Right,
      targetPosition: side === 'left' ? Position.Right : Position.Left,
    }
  }
  if (sourceSide === 'left' || targetSide === 'left') {
    return { sourcePosition: Position.Left, targetPosition: Position.Right }
  }
  return { sourcePosition: Position.Right, targetPosition: Position.Left }
}

function renderLegacyEdges(
  connections: Connection[],
  nodes: NodeMap,
  diagramStyleId: string | null | undefined,
  outlineWireframe: boolean
): string {
  const topic = nodes.get('topic')
  const chunks: string[] = []

  for (const connection of connections) {
    const source = nodes.get(connection.source)
    const target = nodes.get(connection.target)
    if (!source || !target) continue

    const from =
      connection.source === 'topic'
        ? topicSourcePoint(source, connection.target, diagramStyleId, source.width)
        : endpointFor(
            source,
            'source',
            {
              x: mindMapBranchSide(source.id) === 'left' ? source.x : source.x + source.width,
              y: source.y + source.height / 2,
            },
            diagramStyleId
          )
    const to = endpointFor(
      target,
      'target',
      {
        x: mindMapBranchSide(target.id) === 'left' ? target.x + target.width : target.x,
        y: target.y + target.height / 2,
      },
      diagramStyleId
    )

    const { sourcePosition, targetPosition } = legacyHandlePositions(source, target)
    const [d] = getBezierPath({
      sourceX: from.x,
      sourceY: from.y,
      targetX: to.x,
      targetY: to.y,
      sourcePosition,
      targetPosition,
      curvature: 0.25,
    })
    chunks.push(renderPath(d, edgeStroke(topic, connection, outlineWireframe)))
  }

  return chunks.join('')
}

export function renderMindMapVectorEdges(options: {
  connections: Connection[]
  nodes: MindMapVectorNodeDraw[]
  canvasMode: 'legacy' | 'v2'
  diagramStyleId?: string | null
  outlineWireframe: boolean
  topicActualWidth?: number | null
}): string {
  const nodeMap: NodeMap = new Map(options.nodes.map((n) => [n.id, n]))
  if (options.canvasMode === 'legacy') {
    return renderLegacyEdges(
      options.connections,
      nodeMap,
      options.diagramStyleId,
      options.outlineWireframe
    )
  }
  return renderV2Edges(
    options.connections,
    nodeMap,
    options.diagramStyleId,
    options.outlineWireframe,
    options.topicActualWidth
  )
}

/** @internal exported for tests */
export function mindMapVectorEdgeStrokeColor(
  topicStyle: NodeStyle | undefined,
  outlineWireframe: boolean
): string {
  if (outlineWireframe) return resolveMindMapOutlineWireframeEdgeStroke()
  return resolveMindMapTopicBorderColor(topicStyle ? { style: topicStyle } : null)
}
