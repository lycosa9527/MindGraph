/**
 * Pure camera-tour beats for the library demo.
 * Dwell is computed from the text and the node count of each beat.
 */
import type { Connection, DiagramNode } from '@/types'
import { buildMindMapSlides } from '@/utils/mindMapSlides'

export type DemoTourBeatKind = 'overview' | 'group'

export interface DemoTourBeat {
  kind: DemoTourBeatKind
  nodeIds: string[]
  /** Primary node that receives the focus ring. Null on the overview. */
  focusNodeId: string | null
  /** How long the group stays still after the camera arrives. */
  ms: number
}

/** Pan and zoom travel together. Hold time starts after this. */
export const DEMO_CAMERA_MS = 1100

/** Separate from the editor camera so closing the demo does not freeze that viewport. */
export const DEMO_VIEWPORT_LANE = 'library-demo'

/** Hold used when the saved spec never arrives, so the blank template is not toured. */
export const DEMO_MISSING_SPEC_MS = 2500

/** Labels are about this many pixels tall at zoom 1. */
export const DEMO_LABEL_PX_AT_ZOOM_1 = 16

/** Keeps the group clear of the lower-right note card and the lower-left pause control. */
export const DEMO_TOUR_PADDING = { top: 0.1, right: 0.32, bottom: 0.18, left: 0.1 }

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function beatMs(textLength: number, nodeCount: number, kind: DemoTourBeatKind): number {
  const text = Math.max(0, textLength)
  const count = Math.max(0, nodeCount)
  if (kind === 'overview') {
    return clamp(1800 + text * 20 + count * 60, 2500, 6000)
  }
  return clamp(1000 + text * 40 + Math.max(0, count - 1) * 320, 1400, 5500)
}

/** Cap zoom so a label stays near a comfortable on-screen size for this canvas. */
export function demoFocusMaxZoom(viewportHeight: number): number {
  const height = viewportHeight > 0 ? viewportHeight : 800
  const targetPx = clamp(height * 0.034, 20, 30)
  return targetPx / DEMO_LABEL_PX_AT_ZOOM_1
}

function textLengthOf(nodes: readonly DiagramNode[]): number {
  return nodes.reduce((sum, node) => sum + (node.text?.trim().length ?? 0), 0)
}

function beatFor(
  kind: DemoTourBeatKind,
  nodes: readonly DiagramNode[],
  focusNodeId: string | null
): DemoTourBeat {
  return {
    kind,
    nodeIds: nodes.map((node) => node.id),
    focusNodeId: kind === 'overview' ? null : focusNodeId,
    ms: beatMs(textLengthOf(nodes), nodes.length, kind),
  }
}

function byIdMap(nodes: readonly DiagramNode[]): Map<string, DiagramNode> {
  return new Map(nodes.map((node) => [node.id, node]))
}

function childMap(connections: readonly Connection[]): Map<string, string[]> {
  const map = new Map<string, string[]>()
  for (const edge of connections) {
    const list = map.get(edge.source) ?? []
    list.push(edge.target)
    map.set(edge.source, list)
  }
  return map
}

function directChildren(
  node: DiagramNode,
  nodesById: Map<string, DiagramNode>,
  connections: readonly Connection[]
): DiagramNode[] {
  const ids = new Set<string>([
    ...(childMap(connections).get(node.id) ?? []),
    ...(node.childIds ?? []),
  ])
  return [...ids]
    .map((id) => nodesById.get(id))
    .filter((child): child is DiagramNode => child != null)
}

function descendantIds(rootId: string, connections: readonly Connection[]): Set<string> {
  const map = childMap(connections)
  const result = new Set<string>([rootId])
  const stack = [rootId]
  while (stack.length > 0) {
    const current = stack.pop()
    if (!current) continue
    for (const childId of map.get(current) ?? []) {
      if (result.has(childId)) continue
      result.add(childId)
      stack.push(childId)
    }
  }
  return result
}

function centerOf(node: DiagramNode): { x: number; y: number } {
  const size = typeof node.style?.size === 'number' ? node.style.size : 0
  return {
    x: (node.position?.x ?? 0) + size / 2,
    y: (node.position?.y ?? 0) + size / 2,
  }
}

/** Screen y grows downward, so increasing atan2 is clockwise. Zero is the top. */
function clockwiseFromTop(nodes: readonly DiagramNode[], origin: DiagramNode): DiagramNode[] {
  const originPoint = centerOf(origin)
  const turn = (node: DiagramNode): number => {
    const point = centerOf(node)
    const angle = Math.atan2(point.y - originPoint.y, point.x - originPoint.x)
    return (angle + Math.PI / 2 + Math.PI * 2) % (Math.PI * 2)
  }
  return [...nodes].sort((a, b) => turn(a) - turn(b))
}

function byPosition(nodes: readonly DiagramNode[], axis: 'x' | 'y'): DiagramNode[] {
  return [...nodes].sort((a, b) => (a.position?.[axis] ?? 0) - (b.position?.[axis] ?? 0))
}

function roleOf(node: DiagramNode, key: string): string {
  const value = node.data?.[key]
  return typeof value === 'string' ? value : ''
}

function mindMapBeats(nodes: DiagramNode[], connections: Connection[]): DemoTourBeat[] {
  const nodesById = byIdMap(nodes)
  const slides = buildMindMapSlides(
    nodes,
    connections,
    (rootId) => descendantIds(rootId, connections),
    'firstLevel'
  )
  const overview = slides[0]
  if (!overview) return []
  const topic = nodesById.get(overview.branchNodeId ?? '') ?? nodes[0]
  const beats: DemoTourBeat[] = [beatFor('overview', nodes, null)]
  if (topic) beats.push(beatFor('group', [topic], topic.id))
  for (const slide of slides.slice(1)) {
    const group = slide.focusNodeIds
      .map((id) => nodesById.get(id))
      .filter((node): node is DiagramNode => node != null)
    const focus = slide.branchNodeId ?? group[0]?.id ?? null
    if (group.length > 0) beats.push(beatFor('group', group, focus))
  }
  return beats
}

function satelliteBeats(nodes: DiagramNode[]): DemoTourBeat[] {
  const origin = nodes.find((node) => node.type === 'center' || node.type === 'topic') ?? nodes[0]
  const satellites = nodes.filter(
    (node) => node.type !== 'boundary' && node.type !== 'label' && node.id !== origin?.id
  )
  const ordered = origin ? clockwiseFromTop(satellites, origin) : satellites
  return [
    beatFor('overview', nodes, null),
    ...ordered.map((node) => beatFor('group', [node], node.id)),
  ]
}

function flowBeats(nodes: DiagramNode[], connections: Connection[]): DemoTourBeat[] {
  const nodesById = byIdMap(nodes)
  const steps = byPosition(
    nodes.filter((node) => node.type === 'flow'),
    'x'
  )
  const beats: DemoTourBeat[] = [beatFor('overview', nodes, null)]
  for (const step of steps) {
    const subs = directChildren(step, nodesById, connections).filter(
      (node) => node.type === 'flowSubstep'
    )
    beats.push(beatFor('group', [step, ...subs], step.id))
  }
  return beats
}

function multiFlowBeats(nodes: DiagramNode[]): DemoTourBeat[] {
  const causes = byPosition(
    nodes.filter((node) => roleOf(node, 'multiFlowRole') === 'cause'),
    'y'
  )
  const effects = byPosition(
    nodes.filter((node) => roleOf(node, 'multiFlowRole') === 'effect'),
    'y'
  )
  return [
    beatFor('overview', nodes, null),
    ...causes.map((node) => beatFor('group', [node], node.id)),
    ...effects.map((node) => beatFor('group', [node], node.id)),
  ]
}

function descendantNodes(
  node: DiagramNode,
  nodesById: Map<string, DiagramNode>,
  connections: readonly Connection[]
): DiagramNode[] {
  const out: DiagramNode[] = []
  const seen = new Set<string>()
  const stack = directChildren(node, nodesById, connections)
  while (stack.length > 0) {
    const next = stack.shift()
    if (!next || seen.has(next.id)) continue
    seen.add(next.id)
    if (next.type === 'label') continue
    out.push(next)
    stack.push(...directChildren(next, nodesById, connections))
  }
  return out
}

function groupedChildBeats(nodes: DiagramNode[], connections: Connection[]): DemoTourBeat[] {
  const nodesById = byIdMap(nodes)
  const root =
    nodes.find((node) => node.type === 'topic' || node.type === 'whole') ??
    nodes.find((node) => node.type !== 'label')
  const beats: DemoTourBeat[] = [beatFor('overview', nodes, null)]
  if (!root) return beats
  const categories = directChildren(root, nodesById, connections).filter(
    (node) => node.type !== 'label'
  )
  for (const category of categories) {
    const items = descendantNodes(category, nodesById, connections)
    beats.push(beatFor('group', [category, ...items], category.id))
  }
  return beats
}

function doubleBubbleBeats(nodes: DiagramNode[]): DemoTourBeat[] {
  const topics = byPosition(
    nodes.filter((node) => node.type === 'topic'),
    'x'
  )
  const leftTopic = topics[0]
  const rightTopic = topics[1]
  const leftDiffs = byPosition(
    nodes.filter((node) => roleOf(node, 'doubleBubbleRole') === 'leftDiff'),
    'y'
  )
  const similarities = byPosition(
    nodes.filter((node) => roleOf(node, 'doubleBubbleRole') === 'similarity'),
    'y'
  )
  const rightDiffs = byPosition(
    nodes.filter((node) => roleOf(node, 'doubleBubbleRole') === 'rightDiff'),
    'y'
  )
  const beats: DemoTourBeat[] = [beatFor('overview', nodes, null)]
  const left = [leftTopic, ...leftDiffs].filter((node): node is DiagramNode => node != null)
  const right = [rightTopic, ...rightDiffs].filter((node): node is DiagramNode => node != null)
  if (left.length > 0) beats.push(beatFor('group', left, leftTopic?.id ?? left[0].id))
  if (similarities.length > 0) {
    beats.push(beatFor('group', similarities, similarities[0]?.id ?? null))
  }
  if (right.length > 0) beats.push(beatFor('group', right, rightTopic?.id ?? right[0].id))
  return beats
}

function bridgeBeats(nodes: DiagramNode[]): DemoTourBeat[] {
  const pairs = new Map<number, DiagramNode[]>()
  for (const node of nodes) {
    if (node.type === 'label') continue
    const index = node.data?.pairIndex
    if (typeof index !== 'number') continue
    const list = pairs.get(index) ?? []
    list.push(node)
    pairs.set(index, list)
  }
  const beats: DemoTourBeat[] = [beatFor('overview', nodes, null)]
  for (const index of [...pairs.keys()].sort((a, b) => a - b)) {
    const pair = pairs.get(index) ?? []
    const focus = pair.find((node) => node.data?.position === 'left') ?? pair[0]
    if (pair.length > 0) beats.push(beatFor('group', pair, focus?.id ?? null))
  }
  return beats
}

function conceptBeats(nodes: DiagramNode[], connections: Connection[]): DemoTourBeat[] {
  const nodesById = byIdMap(nodes)
  const topic = nodes.find((node) => node.type === 'topic') ?? nodes[0]
  const linked = topic ? directChildren(topic, nodesById, connections) : []
  const linkedIds = new Set(linked.map((node) => node.id))
  const rest = nodes.filter(
    (node) => node.id !== topic?.id && node.type !== 'label' && !linkedIds.has(node.id)
  )
  const concepts = [...linked, ...byPosition(rest, 'x')].filter((node) => node.type !== 'label')
  const beats: DemoTourBeat[] = [beatFor('overview', nodes, null)]
  if (topic && topic.type !== 'label') beats.push(beatFor('group', [topic], topic.id))
  for (const concept of concepts) {
    if (concept.id === topic?.id) continue
    beats.push(beatFor('group', [concept], concept.id))
  }
  return beats
}

function normalizeType(diagramType: string): string {
  if (diagramType === 'mind_map') return 'mindmap'
  return diagramType
}

export function buildDemoTour(
  diagramType: string,
  nodes: DiagramNode[],
  connections: Connection[]
): DemoTourBeat[] {
  if (nodes.length === 0) return []
  switch (normalizeType(diagramType)) {
    case 'mindmap':
      return mindMapBeats(nodes, connections)
    case 'circle_map':
    case 'bubble_map':
      return satelliteBeats(nodes)
    case 'flow_map':
      return flowBeats(nodes, connections)
    case 'multi_flow_map':
      return multiFlowBeats(nodes)
    case 'tree_map':
    case 'brace_map':
      return groupedChildBeats(nodes, connections)
    case 'double_bubble_map':
      return doubleBubbleBeats(nodes)
    case 'bridge_map':
      return bridgeBeats(nodes)
    case 'concept_map':
      return conceptBeats(nodes, connections)
    default:
      return [beatFor('overview', nodes, null)]
  }
}
