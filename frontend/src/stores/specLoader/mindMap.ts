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
  nodeInfos: Map<string, MindMapNodeInfo>,
  globalCounter: { value: number } = { value: 0 }
): void {
  branches.forEach((branch, _index) => {
    // Use global counter to ensure unique IDs across all branches
    // Format: branch-{side}-{depth}-{globalIndex}
    const globalIndex = globalCounter.value++
    const nodeId = `branch-${direction > 0 ? 'r' : 'l'}-${depth}-${globalIndex}`

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
        nodeInfos,
        globalCounter
      )
    }
  })
}

/**
 * Layout mindmap side with clockwise handle assignment
 * Right side: top branches → top-right handles, bottom branches → bottom-right handles
 * Left side: bottom branches → bottom-left handles, top branches → top-left handles
 */
function layoutMindMapSideWithClockwiseHandles(
  branches: MindMapBranch[],
  side: 'left' | 'right',
  topicX: number,
  topicY: number,
  horizontalSpacing: number,
  verticalSpacing: number,
  nodes: DiagramNode[],
  connections: Connection[],
  _startHandleIndex: number,
  _totalBranches: number
): void {
  if (branches.length === 0) return

  const direction = side === 'right' ? 1 : -1
  const dagreNodes: { id: string; width: number; height: number }[] = []
  const dagreEdges: { source: string; target: string }[] = []
  const nodeInfos = new Map<string, MindMapNodeInfo>()

  // Add virtual root for connecting to topic
  const virtualRoot = `virtual-${side}`
  dagreNodes.push({ id: virtualRoot, width: 1, height: 1 })

  // Flatten branch tree with global counter to ensure unique IDs across all branches
  const globalCounter = { value: 0 }
  flattenMindMapBranches(
    branches,
    virtualRoot,
    direction,
    1,
    dagreNodes,
    dagreEdges,
    nodeInfos,
    globalCounter
  )

  // Calculate layout with Dagre (LR for right side, RL for left side)
  // Use improved spacing to better distribute branches vertically
  const layoutDirection = side === 'right' ? 'LR' : 'RL'

  // Adjust vertical spacing based on number of branches for better distribution
  // More branches need more vertical space to spread out
  const adjustedVerticalSpacing = Math.max(
    verticalSpacing,
    branches.length > 2 ? verticalSpacing * 1.5 : verticalSpacing
  )

  const layoutResult = calculateDagreLayout(dagreNodes, dagreEdges, {
    direction: layoutDirection as 'LR' | 'RL',
    nodeSeparation: adjustedVerticalSpacing, // Vertical spacing between branches
    rankSeparation: horizontalSpacing, // Horizontal spacing between levels
    align: 'UL',
    marginX: DEFAULT_PADDING,
    marginY: DEFAULT_PADDING,
    ranker: 'network-simplex', // Better distribution algorithm
  })

  // Get virtual root position to calculate offset
  const virtualPos = layoutResult.positions.get(virtualRoot)
  if (!virtualPos) {
    return
  }

  // Topic edge position (where branches should connect)
  const topicEdgeX = topicX + (direction * DEFAULT_NODE_WIDTH) / 2
  // Virtual root center X (Dagre returns top-left, so add half width)
  const virtualRootCenterX = virtualPos.x + virtualPos.width / 2
  // Calculate offset to align virtual root center with topic edge
  const offsetX = topicEdgeX - virtualRootCenterX

  // Build parent-child map from edges for centering logic
  const childrenMap = new Map<string, string[]>()
  dagreEdges.forEach((edge) => {
    if (edge.source !== virtualRoot) {
      if (!childrenMap.has(edge.source)) {
        childrenMap.set(edge.source, [])
      }
      const children = childrenMap.get(edge.source)
      if (children) {
        children.push(edge.target)
      }
    }
  })

  // Calculate adjusted Y positions by centering each parent relative to its children
  // Process from deepest level to shallowest (bottom-up)
  const adjustedY = new Map<string, number>()
  const maxDepth = Math.max(...Array.from(nodeInfos.values()).map((info) => info.depth), 0)

  // Initialize with original Dagre positions
  nodeInfos.forEach((_info, nodeId) => {
    const pos = layoutResult.positions.get(nodeId)
    if (pos) {
      adjustedY.set(nodeId, pos.y)
    }
  })

  // Process each depth level from bottom to top, centering parents relative to children
  // Step 1: Children nodes (deepest level) stay at their Dagre positions
  // Step 2: For each parent level, center it relative to its children
  for (let depth = maxDepth; depth >= 1; depth--) {
    nodeInfos.forEach((info, nodeId) => {
      if (info.depth === depth) {
        const children = childrenMap.get(nodeId)
        if (children && children.length > 0) {
          // Calculate min and max Y of all children (using their top and bottom)
          let minChildY = Infinity
          let maxChildY = -Infinity
          children.forEach((childId) => {
            const childY = adjustedY.get(childId)
            if (childY !== undefined) {
              const childPos = layoutResult.positions.get(childId)
              if (childPos) {
                const childTop = childY
                const childBottom = childY + childPos.height
                if (childTop < minChildY) minChildY = childTop
                if (childBottom > maxChildY) maxChildY = childBottom
              }
            }
          })

          if (minChildY !== Infinity && maxChildY !== -Infinity) {
            // Center parent vertically relative to its children
            const childrenCenterY = (minChildY + maxChildY) / 2
            const currentPos = layoutResult.positions.get(nodeId)
            if (currentPos) {
              adjustedY.set(nodeId, childrenCenterY - currentPos.height / 2)
            }
          }
        }
      }
    })
  }

  // Calculate offset to align virtual root center with topic edge
  const virtualRootCenterY = virtualPos.y + virtualPos.height / 2
  const offsetY = topicY - virtualRootCenterY

  // Create all nodes using adjusted Y positions for proper centering
  nodeInfos.forEach((info, nodeId) => {
    const pos = layoutResult.positions.get(nodeId)
    if (!pos) {
      // This should never happen if all nodes are properly added to Dagre graph
      // If it does, it indicates a bug in flattenMindMapBranches or Dagre setup
      console.error(
        `MindMap: Dagre did not return position for node ${nodeId}. This indicates a bug - node should be in dagreNodes and connected via edges.`
      )
      return // Skip this node - it's not properly connected in the graph
    }

    // Use adjusted Y position if available, otherwise use original
    const finalY = adjustedY.get(nodeId) ?? pos.y

    nodes.push({
      id: nodeId,
      text: info.text,
      type: 'branch',
      position: {
        x: pos.x + offsetX - DEFAULT_NODE_WIDTH / 2,
        y: finalY + offsetY - DEFAULT_NODE_HEIGHT / 2,
      },
    })
  })

  // Assign handles based on clockwise order matching Python agent
  // Right side: distribute between top-right and bottom-right (first half → top-right, second half → bottom-right)
  // Left side: distribute between bottom-left and top-left (first half → bottom-left, second half → top-left)
  let handleIndex = 0

  dagreEdges.forEach((edge) => {
    if (edge.source === virtualRoot) {
      let handleId: string

      if (side === 'right') {
        // Right side: distribute branches between top-right and bottom-right
        // For 4 branches: Branch 1 → top-right-0, Branch 2 → bottom-right-0
        // For 6 branches: Branch 1,2 → top-right (0,1), Branch 3 → bottom-right-0
        const topRightCount = Math.ceil(branches.length / 2)
        if (handleIndex < topRightCount) {
          // Top-right quadrant
          handleId = `mindmap-top-right-${handleIndex}`
        } else {
          // Bottom-right quadrant
          handleId = `mindmap-bottom-right-${handleIndex - topRightCount}`
        }
      } else {
        // Left side: branches are reversed, distribute between bottom-left and top-left
        // For 4 branches: Branch 3 → bottom-left-0, Branch 4 → top-left-0
        // For 6 branches: Branch 4,5 → bottom-left (0,1), Branch 6 → top-left-0
        const bottomLeftCount = Math.ceil(branches.length / 2)
        if (handleIndex < bottomLeftCount) {
          // Bottom-left quadrant
          handleId = `mindmap-bottom-left-${handleIndex}`
        } else {
          // Top-left quadrant
          handleId = `mindmap-top-left-${handleIndex - bottomLeftCount}`
        }
      }

      // Topic-to-branch connections: right side branches connect via left handle, left side branches connect via right handle
      const targetHandle = side === 'left' ? 'right-target' : 'left'

      connections.push({
        id: `edge-topic-${edge.target}`,
        source: 'topic',
        target: edge.target,
        sourceHandle: handleId,
        targetHandle: targetHandle,
      })
      handleIndex++
    } else {
      // For branch-to-child connections, ensure correct handle positioning
      // Right side branches (LR): children connect via Right handle (source) → Left handle (target)
      // Left side branches (RL): children connect via Left handle (source) → Right handle (target)
      const sourceNodeInfo = nodeInfos.get(edge.source)
      const isLeftSideBranch = sourceNodeInfo?.direction === -1

      connections.push({
        id: `edge-${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        sourceHandle: isLeftSideBranch ? 'left-source' : 'right', // Left side uses left-source handle, right side uses right handle
        targetHandle: isLeftSideBranch ? 'right-target' : 'left', // Left side children use right-target handle, right side children use left handle
      })
    }
  })
}

function _layoutMindMapSideWithDagre(
  branches: MindMapBranch[],
  side: 'left' | 'right',
  topicX: number,
  topicY: number,
  horizontalSpacing: number,
  verticalSpacing: number,
  nodes: DiagramNode[],
  connections: Connection[],
  quadrant: 'topRight' | 'bottomRight' | 'bottomLeft' | 'topLeft' = 'topRight'
): void {
  if (branches.length === 0) return

  const direction = side === 'right' ? 1 : -1
  const dagreNodes: { id: string; width: number; height: number }[] = []
  const dagreEdges: { source: string; target: string }[] = []
  const nodeInfos = new Map<string, MindMapNodeInfo>()

  // Add virtual root for connecting to topic
  const virtualRoot = `virtual-${side}-${quadrant}`
  dagreNodes.push({ id: virtualRoot, width: 1, height: 1 })

  // Flatten branch tree with global counter to ensure unique IDs across all branches
  const globalCounter = { value: 0 }
  flattenMindMapBranches(
    branches,
    virtualRoot,
    direction,
    1,
    dagreNodes,
    dagreEdges,
    nodeInfos,
    globalCounter
  )

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
  // Virtual root should align with topic node's edge (not center)
  // For right side: align with topic's right edge (topicX + DEFAULT_NODE_WIDTH/2)
  // For left side: align with topic's left edge (topicX - DEFAULT_NODE_WIDTH/2)
  const virtualPos = layoutResult.positions.get(virtualRoot)
  if (!virtualPos) {
    return
  }

  // Topic edge position (where branches should connect)
  const topicEdgeX = topicX + (direction * DEFAULT_NODE_WIDTH) / 2
  // Virtual root center X (Dagre returns top-left, so add half width)
  const virtualRootCenterX = virtualPos.x + virtualPos.width / 2
  // Calculate offset to align virtual root center with topic edge
  const offsetX = topicEdgeX - virtualRootCenterX

  // Align vertically: virtual root center Y should match topic center Y
  const virtualRootCenterY = virtualPos.y + virtualPos.height / 2
  const offsetY = topicY - virtualRootCenterY

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
  // Use quadrant-specific handle IDs
  let handleIndex = 0
  const handlePrefix = `mindmap-${quadrant}`

  dagreEdges.forEach((edge) => {
    if (edge.source === virtualRoot) {
      // Connect to topic with quadrant-specific handle ID
      const handleId = `${handlePrefix}-${handleIndex++}`

      connections.push({
        id: `edge-topic-${edge.target}`,
        source: 'topic',
        target: edge.target,
        sourceHandle: handleId,
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
 * Distribute branches clockwise matching Python agent logic:
 * - First half → RIGHT side (top to bottom: Branch 1 top-right, Branch 2 bottom-right, etc.)
 * - Second half → LEFT side (reversed for clockwise: Branch 3 bottom-left, Branch 4 top-left, etc.)
 *
 * For 4 branches:
 * - Right: Branch 1 (top), Branch 2 (bottom)
 * - Left: Branch 3 (bottom), Branch 4 (top) - reversed order
 *
 * Returns branches organized by side and position
 */
function distributeBranchesClockwise(branches: MindMapBranch[]): {
  rightBranches: MindMapBranch[]
  leftBranches: MindMapBranch[]
} {
  const total = branches.length
  const midPoint = Math.ceil(total / 2) // For odd numbers, right gets more

  // First half → RIGHT side (keep original order)
  const rightBranches = branches.slice(0, midPoint)

  // Second half → LEFT side (reverse for clockwise)
  const leftBranches = branches.slice(midPoint).reverse()

  return { rightBranches, leftBranches }
}

/**
 * Load mind map spec into diagram nodes and connections
 *
 * @param spec - Mind map spec with topic and branches
 * @returns SpecLoaderResult with nodes and connections
 */

export function loadMindMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const topic = (spec.topic as string) || (spec.central_topic as string) || ''

  // Collect all branches
  let allBranches: MindMapBranch[] = []

  if (spec.leftBranches || spec.left || spec.rightBranches || spec.right) {
    // New format with explicit left/right branches - combine them
    const leftBranches =
      (spec.leftBranches as MindMapBranch[]) || (spec.left as MindMapBranch[]) || []
    const rightBranches =
      (spec.rightBranches as MindMapBranch[]) || (spec.right as MindMapBranch[]) || []
    allBranches = [...leftBranches, ...rightBranches]
  } else if (Array.isArray(spec.children)) {
    // Old format: single children array
    allBranches = spec.children as MindMapBranch[]
  }

  // Distribute branches clockwise: first half → RIGHT, second half → LEFT (reversed)
  const { rightBranches, leftBranches } = distributeBranchesClockwise(allBranches)

  // Layout constants from layoutConfig
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const horizontalSpacing = DEFAULT_HORIZONTAL_SPACING
  const verticalSpacing = DEFAULT_VERTICAL_SPACING

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Topic node at center - position will be adjusted after branches are laid out
  const topicNode: DiagramNode = {
    id: 'topic',
    text: topic,
    type: 'topic',
    position: {
      x: centerX - DEFAULT_NODE_WIDTH / 2,
      y: centerY - DEFAULT_NODE_HEIGHT / 2, // Temporary position, will be adjusted
    },
    data: {
      totalBranchCount: allBranches.length,
    },
  }
  nodes.push(topicNode)

  // Layout right side branches (first half: top to bottom)
  // These will be positioned with handles: top-right handles for top branches, bottom-right for bottom branches
  layoutMindMapSideWithClockwiseHandles(
    rightBranches,
    'right',
    centerX,
    centerY,
    horizontalSpacing,
    verticalSpacing,
    nodes,
    connections,
    0, // Start index for handle IDs
    allBranches.length
  )

  // Layout left side branches (second half: reversed for clockwise)
  // These will be positioned with handles: bottom-left handles for bottom branches, top-left for top branches
  layoutMindMapSideWithClockwiseHandles(
    leftBranches,
    'left',
    centerX,
    centerY,
    horizontalSpacing,
    verticalSpacing,
    nodes,
    connections,
    rightBranches.length, // Start index for handle IDs (continues from right)
    allBranches.length
  )

  // Step 3: Center topic node vertically relative to all first-level branches
  // Calculate min and max Y of all first-level branch nodes
  let minBranchY = Infinity
  let maxBranchY = -Infinity
  nodes.forEach((node) => {
    if (node.type === 'branch') {
      // Check if this is a first-level branch by checking if it's connected directly to topic
      const isFirstLevel = connections.some(
        (conn) => conn.source === 'topic' && conn.target === node.id
      )
      if (isFirstLevel && node.position) {
        const nodeTop = node.position.y
        const nodeBottom = node.position.y + DEFAULT_NODE_HEIGHT
        if (nodeTop < minBranchY) minBranchY = nodeTop
        if (nodeBottom > maxBranchY) maxBranchY = nodeBottom
      }
    }
  })

  // Calculate center Y of all first-level branches and update topic position
  if (minBranchY !== Infinity && maxBranchY !== -Infinity && topicNode.position) {
    const branchesCenterY = (minBranchY + maxBranchY) / 2
    topicNode.position.y = branchesCenterY - DEFAULT_NODE_HEIGHT / 2
  }

  // Step 4: Center entire layout so topic node is at canvas center
  // Calculate offset needed to move topic to centerX, centerY
  if (topicNode.position) {
    const topicCurrentCenterX = topicNode.position.x + DEFAULT_NODE_WIDTH / 2
    const topicCurrentCenterY = topicNode.position.y + DEFAULT_NODE_HEIGHT / 2
    const offsetXToCenter = centerX - topicCurrentCenterX
    const offsetYToCenter = centerY - topicCurrentCenterY

    // Apply offset to all nodes to center the entire layout
    nodes.forEach((node) => {
      if (node.position) {
        node.position.x += offsetXToCenter
        node.position.y += offsetYToCenter
      }
    })
  }

  return { nodes, connections }
}
