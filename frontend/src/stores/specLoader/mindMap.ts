/**
 * Mind Map Loader
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_HORIZONTAL_SPACING,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  DEFAULT_VERTICAL_SPACING,
} from '@/composables/diagrams/layoutConfig'
import { calculateDagreLayout } from '@/composables/diagrams/useDagreLayout'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

interface MindMapBranch {
  text: string
  children?: MindMapBranch[]
}

// Helper to flatten mind map branch tree for Dagre
interface MindMapNodeInfo {
  text: string
  depth: number
  direction: 1 | -1
}

function flattenMindMapBranches(
  branches: MindMapBranch[],
  parentId: string,
  direction: 1 | -1,
  depth: number,
  dagreNodes: { id: string; width: number; height: number }[],
  dagreEdges: { source: string; target: string }[],
  nodeInfos: Map<string, MindMapNodeInfo>
): void {
  branches.forEach((branch, index) => {
    const nodeId = `branch-${direction > 0 ? 'r' : 'l'}-${depth}-${index}`

    dagreNodes.push({ id: nodeId, width: DEFAULT_NODE_WIDTH, height: DEFAULT_NODE_HEIGHT })
    nodeInfos.set(nodeId, { text: branch.text, depth, direction })
    dagreEdges.push({ source: parentId, target: nodeId })

    if (branch.children && branch.children.length > 0) {
      flattenMindMapBranches(
        branch.children,
        nodeId,
        direction,
        depth + 1,
        dagreNodes,
        dagreEdges,
        nodeInfos
      )
    }
  })
}

function layoutMindMapSideWithDagre(
  branches: MindMapBranch[],
  side: 'left' | 'right',
  topicX: number,
  topicY: number,
  horizontalSpacing: number,
  verticalSpacing: number,
  nodes: DiagramNode[],
  connections: Connection[]
): void {
  if (branches.length === 0) return

  const direction = side === 'right' ? 1 : -1
  const dagreNodes: { id: string; width: number; height: number }[] = []
  const dagreEdges: { source: string; target: string }[] = []
  const nodeInfos = new Map<string, MindMapNodeInfo>()

  // Add virtual root for connecting to topic
  const virtualRoot = `virtual-${side}`
  dagreNodes.push({ id: virtualRoot, width: 1, height: 1 })

  // Flatten branch tree
  flattenMindMapBranches(branches, virtualRoot, direction, 1, dagreNodes, dagreEdges, nodeInfos)

  // Calculate layout with Dagre (LR for right side, RL for left side)
  const layoutDirection = side === 'right' ? 'LR' : 'RL'
  const layoutResult = calculateDagreLayout(dagreNodes, dagreEdges, {
    direction: layoutDirection as 'LR' | 'RL',
    nodeSeparation: verticalSpacing,
    rankSeparation: horizontalSpacing,
    align: 'UL',
    marginX: DEFAULT_PADDING,
    marginY: DEFAULT_PADDING,
  })

  // Get virtual root position to calculate offset
  const virtualPos = layoutResult.positions.get(virtualRoot)
  const offsetX = topicX - (virtualPos?.x || 0) + (direction * DEFAULT_NODE_WIDTH) / 2
  const offsetY = topicY - (virtualPos?.y || 0)

  // Create nodes with adjusted positions
  nodeInfos.forEach((info, nodeId) => {
    const pos = layoutResult.positions.get(nodeId)
    if (pos) {
      nodes.push({
        id: nodeId,
        text: info.text,
        type: 'branch',
        position: {
          x: pos.x + offsetX - DEFAULT_NODE_WIDTH / 2,
          y: pos.y + offsetY - DEFAULT_NODE_HEIGHT / 2,
        },
      })
    }
  })

  // Create connections (skip virtual root edges, connect to topic instead)
  dagreEdges.forEach((edge) => {
    if (edge.source === virtualRoot) {
      connections.push({
        id: `edge-topic-${edge.target}`,
        source: 'topic',
        target: edge.target,
      })
    } else {
      connections.push({
        id: `edge-${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
      })
    }
  })
}

/**
 * Load mind map spec into diagram nodes and connections
 *
 * @param spec - Mind map spec with topic and branches
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadMindMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const topic = (spec.topic as string) || (spec.central_topic as string) || ''

  // Handle multiple formats for branches
  let leftBranches: MindMapBranch[] = []
  let rightBranches: MindMapBranch[] = []

  if (spec.leftBranches || spec.left) {
    // New format with explicit left/right branches
    leftBranches = (spec.leftBranches as MindMapBranch[]) || (spec.left as MindMapBranch[]) || []
    rightBranches = (spec.rightBranches as MindMapBranch[]) || (spec.right as MindMapBranch[]) || []
  } else if (Array.isArray(spec.children)) {
    // Old format: single children array, split into left and right
    const children = spec.children as MindMapBranch[]
    const half = Math.ceil(children.length / 2)
    leftBranches = children.slice(0, half)
    rightBranches = children.slice(half)
  }

  // Layout constants from layoutConfig
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const horizontalSpacing = DEFAULT_HORIZONTAL_SPACING
  const verticalSpacing = DEFAULT_VERTICAL_SPACING

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Topic node at center
  nodes.push({
    id: 'topic',
    text: topic,
    type: 'topic',
    position: {
      x: centerX - DEFAULT_NODE_WIDTH / 2,
      y: centerY - DEFAULT_NODE_HEIGHT / 2,
    },
  })

  // Layout left side with Dagre
  layoutMindMapSideWithDagre(
    leftBranches,
    'left',
    centerX,
    centerY,
    horizontalSpacing,
    verticalSpacing,
    nodes,
    connections
  )

  // Layout right side with Dagre
  layoutMindMapSideWithDagre(
    rightBranches,
    'right',
    centerX,
    centerY,
    horizontalSpacing,
    verticalSpacing,
    nodes,
    connections
  )

  return { nodes, connections }
}
