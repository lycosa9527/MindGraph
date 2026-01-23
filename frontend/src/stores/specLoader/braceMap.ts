/**
 * Brace Map Loader
 */
import {
  DEFAULT_LEVEL_WIDTH,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  DEFAULT_VERTICAL_SPACING,
} from '@/composables/diagrams/layoutConfig'
import { calculateDagreLayout } from '@/composables/diagrams/useDagreLayout'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

interface BraceNode {
  id?: string
  text: string
  parts?: BraceNode[]
}

// Helper to flatten brace tree into nodes and edges for Dagre
interface FlattenedBraceData {
  dagreNodes: { id: string; width: number; height: number }[]
  dagreEdges: { source: string; target: string }[]
  nodeInfos: Map<string, { text: string; depth: number }>
}

function flattenBraceTree(
  node: BraceNode,
  depth: number,
  parentId: string | null,
  nodeWidth: number,
  nodeHeight: number,
  result: FlattenedBraceData,
  counter: { value: number }
): string {
  const nodeId = node.id || `brace-${depth}-${counter.value++}`

  result.dagreNodes.push({ id: nodeId, width: nodeWidth, height: nodeHeight })
  result.nodeInfos.set(nodeId, { text: node.text, depth })

  if (parentId) {
    result.dagreEdges.push({ source: parentId, target: nodeId })
  }

  if (node.parts && node.parts.length > 0) {
    node.parts.forEach((part) => {
      flattenBraceTree(part, depth + 1, nodeId, nodeWidth, nodeHeight, result, counter)
    })
  }

  return nodeId
}

/**
 * Load brace map spec into diagram nodes and connections
 *
 * @param spec - Brace map spec with whole and parts
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadBraceMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Support both new format (whole as BraceNode) and old format (whole as string + parts array)
  let wholeNode: BraceNode | undefined

  if (typeof spec.whole === 'object' && spec.whole !== null) {
    // New format: whole is already a BraceNode
    wholeNode = spec.whole as BraceNode
  } else if (typeof spec.whole === 'string') {
    // Old format: whole is string, parts is array
    const parts = spec.parts as
      | Array<{ name: string; subparts?: Array<{ name: string }> }>
      | undefined
    wholeNode = {
      id: 'brace-whole',
      text: spec.whole,
      parts: parts?.map((p, i) => ({
        id: `brace-part-${i}`,
        text: p.name || '',
        parts: p.subparts?.map((sp, j) => ({
          id: `brace-subpart-${i}-${j}`,
          text: sp.name || '',
        })),
      })),
    }
  }

  if (wholeNode) {
    // Flatten brace tree for Dagre
    const flatData: FlattenedBraceData = {
      dagreNodes: [],
      dagreEdges: [],
      nodeInfos: new Map(),
    }
    flattenBraceTree(wholeNode, 0, null, DEFAULT_NODE_WIDTH, DEFAULT_NODE_HEIGHT, flatData, {
      value: 0,
    })

    // Calculate layout using Dagre (left-to-right direction for brace maps)
    const layoutResult = calculateDagreLayout(flatData.dagreNodes, flatData.dagreEdges, {
      direction: 'LR',
      nodeSeparation: DEFAULT_VERTICAL_SPACING,
      rankSeparation: DEFAULT_LEVEL_WIDTH,
      align: 'UL',
      marginX: DEFAULT_PADDING,
      marginY: DEFAULT_PADDING,
    })

    // Build parent-child map from edges
    const childrenMap = new Map<string, string[]>()
    flatData.dagreEdges.forEach((edge) => {
      if (!childrenMap.has(edge.source)) {
        childrenMap.set(edge.source, [])
      }
      const children = childrenMap.get(edge.source)
      if (children) {
        children.push(edge.target)
      }
    })

    // Calculate adjusted Y positions by centering each parent relative to its children
    // Process from deepest level to shallowest (bottom-up)
    const adjustedY = new Map<string, number>()
    const maxDepth = Math.max(
      ...Array.from(flatData.nodeInfos.values()).map((info) => info.depth),
      0
    )

    // Initialize with original positions
    flatData.dagreNodes.forEach((node) => {
      const pos = layoutResult.positions.get(node.id)
      if (pos) {
        adjustedY.set(node.id, pos.y)
      }
    })

    // Process each depth level from bottom to top
    for (let depth = maxDepth; depth >= 0; depth--) {
      flatData.dagreNodes.forEach((node) => {
        const info = flatData.nodeInfos.get(node.id)
        if (info?.depth === depth) {
          const directChildren = childrenMap.get(node.id) || []
          if (directChildren.length > 0) {
            // Calculate vertical center of direct children
            let minY = Infinity
            let maxY = -Infinity
            directChildren.forEach((childId) => {
              const childY = adjustedY.get(childId)
              if (childY !== undefined) {
                const childTop = childY
                const childBottom = childY + DEFAULT_NODE_HEIGHT
                if (childTop < minY) minY = childTop
                if (childBottom > maxY) maxY = childBottom
              }
            })
            if (minY !== Infinity && maxY !== -Infinity) {
              const childrenCenterY = (minY + maxY) / 2
              adjustedY.set(node.id, childrenCenterY - DEFAULT_NODE_HEIGHT / 2)
            }
          }
        }
      })
    }

    // Create nodes with adjusted positions
    flatData.dagreNodes.forEach((dagreNode) => {
      const info = flatData.nodeInfos.get(dagreNode.id)
      const pos = layoutResult.positions.get(dagreNode.id)
      const adjustedPosY = adjustedY.get(dagreNode.id)

      if (info && pos) {
        nodes.push({
          id: dagreNode.id,
          text: info.text || '',
          type: info.depth === 0 ? 'topic' : 'brace',
          position: { x: pos.x, y: adjustedPosY !== undefined ? adjustedPosY : pos.y },
        })
      }
    })

    // Create connections
    flatData.dagreEdges.forEach((edge) => {
      connections.push({
        id: `edge-${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
      })
    })
  }

  // Add dimension label if exists
  const dimension = spec.dimension as string | undefined
  if (dimension !== undefined) {
    // Position below the whole node using Dagre layout info
    const wholeId = wholeNode?.id || 'brace-0-0'
    const wholePos = nodes.find((n) => n.id === wholeId)?.position
    nodes.push({
      id: 'dimension-label',
      text: dimension || '',
      type: 'label',
      position: { x: wholePos?.x || 100, y: (wholePos?.y || 300) + DEFAULT_NODE_HEIGHT + 20 },
    })
  }

  return {
    nodes,
    connections,
    metadata: {
      dimension,
      alternativeDimensions: spec.alternative_dimensions as string[] | undefined,
    },
  }
}
