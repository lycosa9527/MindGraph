/**
 * Brace Map Loader
 */
import {
  BRACE_MAP_LEVEL_WIDTH,
  BRACE_MAP_NODE_SPACING,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  NODE_MIN_DIMENSIONS,
} from '@/composables/diagrams/layoutConfig'
import { calculateDagreLayout } from '@/composables/diagrams/useDagreLayout'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'

import { measureTextWidth } from './textMeasurement'
import type { SpecLoaderResult } from './types'

interface BraceNode {
  id?: string
  text: string
  parts?: BraceNode[]
}

// Font sizes and padding match BraceNode.vue (topic: 18px bold, part: 16px, subpart: 12px)
const BRACE_TOPIC_FONT_SIZE = 18
const BRACE_PART_FONT_SIZE = 16
const BRACE_SUBPART_FONT_SIZE = 12
const BRACE_TOPIC_PADDING_X = 32
const BRACE_PILL_PADDING_X = 40
const BRACE_MAX_NODE_WIDTH = 280

/**
 * Estimate brace node width from text content.
 * Uses text measurement to match actual rendered width, preventing overlap with braces
 * when auto-complete generates longer text.
 */
function estimateBraceNodeWidth(text: string, depth: number): number {
  const trimmed = (text || '').trim()
  const fontSize =
    depth === 0
      ? BRACE_TOPIC_FONT_SIZE
      : depth === 1
        ? BRACE_PART_FONT_SIZE
        : BRACE_SUBPART_FONT_SIZE
  const paddingX = depth === 0 ? BRACE_TOPIC_PADDING_X : BRACE_PILL_PADDING_X

  let textWidth = 0
  if (typeof document !== 'undefined') {
    textWidth = measureTextWidth(trimmed || ' ', fontSize)
    if (depth === 0) {
      textWidth *= 1.08
    }
  }

  const width = Math.ceil(textWidth + paddingX)
  return Math.max(
    NODE_MIN_DIMENSIONS.brace.minWidth,
    Math.min(BRACE_MAX_NODE_WIDTH, width || DEFAULT_NODE_WIDTH)
  )
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
  result: FlattenedBraceData,
  counter: { value: number }
): string {
  const nodeId = node.id || `brace-${depth}-${counter.value++}`
  const nodeWidth = estimateBraceNodeWidth(node.text, depth)

  result.dagreNodes.push({ id: nodeId, width: nodeWidth, height: DEFAULT_NODE_HEIGHT })
  result.nodeInfos.set(nodeId, { text: node.text, depth })

  if (parentId) {
    result.dagreEdges.push({ source: parentId, target: nodeId })
  }

  if (node.parts && node.parts.length > 0) {
    node.parts.forEach((part) => {
      flattenBraceTree(part, depth + 1, nodeId, result, counter)
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
    flattenBraceTree(wholeNode, 0, null, flatData, { value: 0 })

    // Calculate layout using Dagre (left-to-right direction for brace maps)
    const layoutResult = calculateDagreLayout(flatData.dagreNodes, flatData.dagreEdges, {
      direction: 'LR',
      nodeSeparation: BRACE_MAP_NODE_SPACING,
      rankSeparation: BRACE_MAP_LEVEL_WIDTH,
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

    // Compute groupIndex for each node (for color scheme like mindmap/double bubble)
    // Root's direct children: index 0, 1, 2... Subparts inherit parent's groupIndex
    const rootId = flatData.dagreNodes.find(
      (n) => !flatData.dagreEdges.some((e) => e.target === n.id)
    )?.id
    const groupIndexMap = new Map<string, number>()
    if (rootId) {
      const rootChildren = childrenMap.get(rootId) ?? []
      rootChildren.forEach((childId, idx) => {
        groupIndexMap.set(childId, idx)
      })
      flatData.dagreNodes.forEach((node) => {
        if (node.id === rootId) return
        const parentEdge = flatData.dagreEdges.find((e) => e.target === node.id)
        const parentId = parentEdge?.source
        if (parentId && groupIndexMap.has(parentId)) {
          const parentGroup = groupIndexMap.get(parentId)
          if (parentGroup !== undefined) {
            groupIndexMap.set(node.id, parentGroup)
          }
        }
      })
    }

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

    // Create nodes with adjusted positions and groupIndex for color scheme
    flatData.dagreNodes.forEach((dagreNode) => {
      const info = flatData.nodeInfos.get(dagreNode.id)
      const pos = layoutResult.positions.get(dagreNode.id)
      const adjustedPosY = adjustedY.get(dagreNode.id)
      const groupIndex = groupIndexMap.get(dagreNode.id)

      if (info && pos) {
        const node: DiagramNode = {
          id: dagreNode.id,
          text: info.text || '',
          type: info.depth === 0 ? 'topic' : 'brace',
          position: { x: pos.x, y: adjustedPosY !== undefined ? adjustedPosY : pos.y },
        }
        if (groupIndex !== undefined) {
          const color = getMindmapBranchColor(groupIndex)
          node.data = { groupIndex }
          node.style = {
            ...node.style,
            backgroundColor: color.fill,
            borderColor: color.border,
          }
        }
        nodes.push(node)
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

    // Add dimension label if exists - center-aligned under main topic node
    const dimension = spec.dimension as string | undefined
    if (dimension !== undefined) {
      const wholeId = wholeNode?.id || 'brace-0-0'
      const wholePos = nodes.find((n) => n.id === wholeId)?.position
      const wholeDagreNode = flatData.dagreNodes.find(
        (dn: { id: string; width: number }) => dn.id === wholeId
      )
      const topicWidth = wholeDagreNode?.width ?? DEFAULT_NODE_WIDTH
      const topicCenterX = (wholePos?.x ?? 100) + topicWidth / 2
      const labelWidth = NODE_MIN_DIMENSIONS.label.minWidth
      nodes.push({
        id: 'dimension-label',
        text: dimension || '',
        type: 'label',
        position: {
          x: topicCenterX - labelWidth / 2,
          y: (wholePos?.y ?? 300) + DEFAULT_NODE_HEIGHT + 20,
        },
      })
    }
  }

  const dimension = spec.dimension as string | undefined
  return {
    nodes,
    connections,
    metadata: {
      dimension,
      alternativeDimensions: spec.alternative_dimensions as string[] | undefined,
    },
  }
}

/**
 * Recalculate brace map layout from nodes and connections.
 * Used when nodes are added/removed to update positions via Dagre.
 *
 * @param nodes - Diagram nodes (topic + brace parts/subparts, optionally dimension-label)
 * @param connections - Parent-child connections
 * @returns Nodes with updated positions
 */
export function recalculateBraceMapLayout(
  nodes: DiagramNode[],
  connections: Connection[]
): DiagramNode[] {
  const labelNode = nodes.find((n) => n.type === 'label' || n.id === 'dimension-label')
  const treeNodes = nodes.filter((n) => n.type !== 'label' && n.id !== 'dimension-label')
  if (treeNodes.length === 0) return nodes

  const targetIds = new Set(connections.map((c) => c.target))
  const rootNode = treeNodes.find((n) => !targetIds.has(n.id)) || treeNodes[0]
  const rootId = rootNode.id

  const childrenMap = new Map<string, string[]>()
  connections.forEach((conn) => {
    if (!childrenMap.has(conn.source)) childrenMap.set(conn.source, [])
    const children = childrenMap.get(conn.source)
    if (children) children.push(conn.target)
  })

  // Recompute groupIndex for color scheme (same logic as loadBraceMapSpec)
  const groupIndexMap = new Map<string, number>()
  const rootChildren = childrenMap.get(rootId) ?? []
  rootChildren.forEach((childId, idx) => {
    groupIndexMap.set(childId, idx)
  })
  treeNodes.forEach((node) => {
    if (node.id === rootId) return
    const parentConn = connections.find((c) => c.target === node.id)
    const parentId = parentConn?.source
    if (parentId && groupIndexMap.has(parentId)) {
      const parentGroup = groupIndexMap.get(parentId)
      if (parentGroup !== undefined) {
        groupIndexMap.set(node.id, parentGroup)
      }
    }
  })

  function buildTree(nodeId: string): BraceNode {
    const node = treeNodes.find((n) => n.id === nodeId)
    const text = node?.text ?? ''
    const childIds = childrenMap.get(nodeId) ?? []
    const parts = childIds.map((id) => buildTree(id))
    return {
      id: nodeId,
      text,
      parts: parts.length > 0 ? parts : undefined,
    }
  }

  const wholeNode = buildTree(rootId)
  const flatData: FlattenedBraceData = {
    dagreNodes: [],
    dagreEdges: [],
    nodeInfos: new Map(),
  }
  flattenBraceTree(wholeNode, 0, null, flatData, { value: 0 })

  const layoutResult = calculateDagreLayout(flatData.dagreNodes, flatData.dagreEdges, {
    direction: 'LR',
    nodeSeparation: BRACE_MAP_NODE_SPACING,
    rankSeparation: BRACE_MAP_LEVEL_WIDTH,
    align: 'UL',
    marginX: DEFAULT_PADDING,
    marginY: DEFAULT_PADDING,
  })

  const adjustedY = new Map<string, number>()
  const maxDepth = Math.max(...Array.from(flatData.nodeInfos.values()).map((info) => info.depth), 0)

  flatData.dagreNodes.forEach((node) => {
    const pos = layoutResult.positions.get(node.id)
    if (pos) adjustedY.set(node.id, pos.y)
  })

  for (let depth = maxDepth; depth >= 0; depth--) {
    flatData.dagreNodes.forEach((node) => {
      const info = flatData.nodeInfos.get(node.id)
      if (info?.depth === depth) {
        const directChildren = childrenMap.get(node.id) || []
        if (directChildren.length > 0) {
          let minY = Infinity
          let maxY = -Infinity
          directChildren.forEach((childId) => {
            const childY = adjustedY.get(childId)
            if (childY !== undefined) {
              minY = Math.min(minY, childY)
              maxY = Math.max(maxY, childY + DEFAULT_NODE_HEIGHT)
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

  const nodeMap = new Map(treeNodes.map((n) => [n.id, { ...n }]))
  flatData.dagreNodes.forEach((dagreNode) => {
    const pos = layoutResult.positions.get(dagreNode.id)
    const adjustedPosY = adjustedY.get(dagreNode.id)
    const node = nodeMap.get(dagreNode.id)
    if (node && pos) {
      node.position = { x: pos.x, y: adjustedPosY !== undefined ? adjustedPosY : pos.y }
      const groupIndex = groupIndexMap.get(dagreNode.id)
      if (groupIndex !== undefined) {
        const color = getMindmapBranchColor(groupIndex)
        node.data = { ...node.data, groupIndex }
        node.style = { ...node.style, backgroundColor: color.fill, borderColor: color.border }
      }
    }
  })

  let result = Array.from(nodeMap.values())
  if (labelNode) {
    const wholePos = result.find((n) => n.id === rootId)?.position
    const rootDagreNode = flatData.dagreNodes.find(
      (dn: { id: string; width: number }) => dn.id === rootId
    )
    const topicWidth = rootDagreNode?.width ?? DEFAULT_NODE_WIDTH
    const topicCenterX = (wholePos?.x ?? 100) + topicWidth / 2
    const labelWidth = NODE_MIN_DIMENSIONS.label.minWidth
    result = [
      ...result,
      {
        ...labelNode,
        position: {
          x: topicCenterX - labelWidth / 2,
          y: (wholePos?.y ?? 300) + DEFAULT_NODE_HEIGHT + 20,
        },
      },
    ]
  }
  return result
}
