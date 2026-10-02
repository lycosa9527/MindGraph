/**
 * Hierarchical outline for the eight thinking maps.
 * Connection direction matches a mind map on bubble, tree, brace, and flow maps.
 * Circle and bridge maps have no edges. Multi-flow causes point at the event.
 * Double-bubble similarities have two parents, so each node is listed once.
 */
import type { Connection, DiagramNode } from '@/types'
import {
  BRIDGE_DIMENSION_LABEL_ID,
  isBridgeMapPairNode,
  readBridgePairIndex,
  readBridgePairSide,
} from '@/utils/bridgeMapIdentity'
import {
  CIRCLE_BOUNDARY_NODE_ID,
  CIRCLE_TOPIC_NODE_ID,
  isCircleMapContextNode,
  readCircleContextIndex,
} from '@/utils/circleMapIdentity'
import {
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
  readDoubleBubbleIndex,
  readDoubleBubbleRole,
} from '@/utils/doubleBubbleMapIdentity'
import { type MindMapOutlineNode, buildMindMapOutlineTree } from '@/utils/mindMapOutlineTree'
import {
  MULTI_FLOW_EVENT_NODE_ID,
  readMultiFlowIndex,
  readMultiFlowRole,
} from '@/utils/multiFlowMapIdentity'

function nodeText(node: DiagramNode): string {
  return String(node.text ?? '').trim() || node.id
}

function outlineNode(
  node: DiagramNode,
  depth: number,
  children: MindMapOutlineNode[] = []
): MindMapOutlineNode {
  return { id: node.id, text: nodeText(node), depth, children }
}

function byNumber(readIndex: (node: DiagramNode) => number) {
  return (left: DiagramNode, right: DiagramNode): number => {
    const delta = readIndex(left) - readIndex(right)
    if (delta !== 0) return delta
    return left.id.localeCompare(right.id)
  }
}

function leaves(nodes: DiagramNode[], depth: number): MindMapOutlineNode[] {
  return nodes.map((node) => outlineNode(node, depth))
}

function circleOutline(nodes: DiagramNode[]): MindMapOutlineNode[] {
  const topic = nodes.find((node) => node.id === CIRCLE_TOPIC_NODE_ID)
  if (!topic) return []
  const contexts = nodes
    .filter((node) => node.id !== CIRCLE_BOUNDARY_NODE_ID && isCircleMapContextNode(node))
    .slice()
    .sort(byNumber(readCircleContextIndex))
  return [outlineNode(topic, 0, leaves(contexts, 1))]
}

function bridgeOutline(nodes: DiagramNode[]): MindMapOutlineNode[] {
  const label = nodes.find((node) => node.id === BRIDGE_DIMENSION_LABEL_ID)
  const pairs = nodes
    .filter((node) => isBridgeMapPairNode(node))
    .slice()
    .sort((left, right) => {
      const delta = readBridgePairIndex(left) - readBridgePairIndex(right)
      if (delta !== 0) return delta
      const leftSide = readBridgePairSide(left) === 'right' ? 1 : 0
      const rightSide = readBridgePairSide(right) === 'right' ? 1 : 0
      return leftSide - rightSide
    })
  if (!label) return leaves(pairs, 0)
  return [outlineNode(label, 0, leaves(pairs, 1))]
}

function multiFlowOutline(nodes: DiagramNode[]): MindMapOutlineNode[] {
  const event = nodes.find((node) => node.id === MULTI_FLOW_EVENT_NODE_ID)
  if (!event) return []
  const causes = nodes
    .filter((node) => readMultiFlowRole(node) === 'cause')
    .slice()
    .sort(byNumber(readMultiFlowIndex))
  const effects = nodes
    .filter((node) => readMultiFlowRole(node) === 'effect')
    .slice()
    .sort(byNumber(readMultiFlowIndex))
  return [outlineNode(event, 0, leaves([...causes, ...effects], 1))]
}

function doubleBubbleOutline(nodes: DiagramNode[]): MindMapOutlineNode[] {
  const left = nodes.find((node) => node.id === DOUBLE_BUBBLE_LEFT_TOPIC_ID)
  const right = nodes.find((node) => node.id === DOUBLE_BUBBLE_RIGHT_TOPIC_ID)
  const similarities = nodes
    .filter((node) => readDoubleBubbleRole(node) === 'similarity')
    .slice()
    .sort(byNumber(readDoubleBubbleIndex))
  const leftDiffs = nodes
    .filter((node) => readDoubleBubbleRole(node) === 'leftDiff')
    .slice()
    .sort(byNumber(readDoubleBubbleIndex))
  const rightDiffs = nodes
    .filter((node) => readDoubleBubbleRole(node) === 'rightDiff')
    .slice()
    .sort(byNumber(readDoubleBubbleIndex))
  const forest: MindMapOutlineNode[] = []
  if (left) {
    forest.push(outlineNode(left, 0, leaves([...similarities, ...leftDiffs], 1)))
  } else {
    forest.push(...leaves(similarities, 0))
  }
  if (right) {
    forest.push(outlineNode(right, 0, leaves(rightDiffs, 1)))
  }
  return forest
}

function connectionOutline(nodes: DiagramNode[], connections: Connection[]): MindMapOutlineNode[] {
  const visible = nodes.filter(
    (node) => node.type !== 'boundary' && node.type !== 'label' && node.id !== 'dimension-label'
  )
  return buildMindMapOutlineTree(visible, connections)
}

/** Outline rows for one thinking-map diagram. Mind maps keep {@link buildMindMapOutlineTree}. */
export function buildThinkingMapOutlineTree(
  diagramType: string | null | undefined,
  nodes: DiagramNode[],
  connections: Connection[]
): MindMapOutlineNode[] {
  if (diagramType === 'circle_map') return circleOutline(nodes)
  if (diagramType === 'bridge_map') return bridgeOutline(nodes)
  if (diagramType === 'multi_flow_map') return multiFlowOutline(nodes)
  if (diagramType === 'double_bubble_map') return doubleBubbleOutline(nodes)
  return connectionOutline(nodes, connections)
}
