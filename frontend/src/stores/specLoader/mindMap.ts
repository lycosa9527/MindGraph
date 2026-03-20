/**
 * Mind Map Loader
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_MINDMAP_RANK_SEPARATION,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  DEFAULT_VERTICAL_SPACING,
  MINDMAP_TARGET_EXTENT,
} from '@/composables/diagrams/layoutConfig'
import { calculateDagreLayout } from '@/composables/diagrams/useDagreLayout'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

interface MindMapBranch {
  text: string
  children?: MindMapBranch[]
}

/** Canonical field is text; accept label for backward compatibility with older specs */
function getBranchText(branch: { text?: string; label?: string }): string {
  return (branch.text ?? branch.label ?? '') as string
}

/**
 * Estimate rendered BranchNode width from text content.
 * BranchNode auto-sizes: min-width 80px, InlineEditableText max-width 150px,
 * plus px-4 padding (32px) and border (~6px). CJK chars ~16px, Latin ~9px at 16px font.
 */
function estimateNodeWidth(text: string): number {
  if (!text) return DEFAULT_NODE_WIDTH
  const cjkRegex = /[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF]/g
  const cjkMatches = text.match(cjkRegex)
  const cjkCount = cjkMatches ? cjkMatches.length : 0
  const otherCount = text.length - cjkCount
  const rawTextWidth = cjkCount * 16 + otherCount * 9
  const maxTextWidth = 150
  const nodeHorizontalExtra = 38
  const minNodeWidth = 80
  const textWidth = Math.min(rawTextWidth, maxTextWidth)
  return Math.max(minNodeWidth, textWidth + nodeHorizontalExtra)
}

/**
 * Compute vertical span of a branch's subtree for Dagre layout.
 * Nodes with children need height = subtree span so siblings don't overlap.
 */
function getSubtreeHeight(branch: MindMapBranch, verticalSpacing: number): number {
  if (!branch.children || branch.children.length === 0) {
    return DEFAULT_NODE_HEIGHT
  }
  const children = branch.children
  const childHeights = children.map((c) => getSubtreeHeight(c, verticalSpacing))
  const total = childHeights.reduce((a, b) => a + b, 0) + (children.length - 1) * verticalSpacing
  return Math.max(DEFAULT_NODE_HEIGHT, total)
}

// Helper to flatten mind map branch tree for Dagre
interface MindMapNodeInfo {
  text: string
  depth: number
  direction: 1 | -1
  estimatedWidth: number
}

function flattenMindMapBranches(
  branches: MindMapBranch[],
  parentId: string,
  direction: 1 | -1,
  depth: number,
  verticalSpacing: number,
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

    const text = getBranchText(branch)
    const estimatedWidth = estimateNodeWidth(text)
    const nodeHeight = getSubtreeHeight(branch, verticalSpacing)
    dagreNodes.push({ id: nodeId, width: estimatedWidth, height: nodeHeight })
    nodeInfos.set(nodeId, { text, depth, direction, estimatedWidth })
    dagreEdges.push({ source: parentId, target: nodeId })

    if (branch.children && branch.children.length > 0) {
      flattenMindMapBranches(
        branch.children,
        nodeId,
        direction,
        depth + 1,
        verticalSpacing,
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
  rankSeparation: number,
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

  // Adjust vertical spacing based on number of branches for better distribution
  const adjustedVerticalSpacing = Math.max(
    verticalSpacing,
    branches.length > 2 ? verticalSpacing * 1.5 : verticalSpacing
  )

  // Flatten branch tree with global counter to ensure unique IDs across all branches
  const globalCounter = { value: 0 }
  flattenMindMapBranches(
    branches,
    virtualRoot,
    direction,
    1,
    adjustedVerticalSpacing,
    dagreNodes,
    dagreEdges,
    nodeInfos,
    globalCounter
  )

  // Use LR for BOTH sides to guarantee identical Dagre output (root cause of asymmetry).
  const layoutDirection = 'LR'

  const layoutResult = calculateDagreLayout(dagreNodes, dagreEdges, {
    direction: layoutDirection as 'LR' | 'RL',
    nodeSeparation: adjustedVerticalSpacing, // Vertical spacing between branches
    rankSeparation, // Column width (horizontal between depth levels)
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

  // Use SAME anchor (topic right edge) for both sides so LR produces identical raw positions.
  // Left side is then mirrored - this guarantees symmetric column widths and curve lengths.
  const topicRightEdgeX = topicX + DEFAULT_NODE_WIDTH / 2
  const virtualRootCenterX = virtualPos.x + virtualPos.width / 2
  const offsetX = topicRightEdgeX - virtualRootCenterX

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
  for (let depth = maxDepth; depth >= 1; depth--) {
    nodeInfos.forEach((info, nodeId) => {
      if (info.depth === depth) {
        const children = childrenMap.get(nodeId)
        if (children && children.length > 0) {
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
            const childrenCenterY = (minChildY + maxChildY) / 2
            adjustedY.set(nodeId, childrenCenterY - DEFAULT_NODE_HEIGHT / 2)
          }
        }
      }
    })
  }

  // Map each node to its top-level branch (depth-1 ancestor) for cross-branch gap
  const branchRoots = new Set(
    dagreEdges.filter((e) => e.source === virtualRoot).map((e) => e.target)
  )
  const nodeToBranch = new Map<string, string>()
  const getBranchRoot = (nid: string): string => {
    if (branchRoots.has(nid)) return nid
    const cached = nodeToBranch.get(nid)
    if (cached) return cached
    const parent = dagreEdges.find((e) => e.target === nid)?.source
    if (!parent) return nid
    const root = getBranchRoot(parent)
    nodeToBranch.set(nid, root)
    return root
  }

  // Push siblings down when subtrees overlap (e.g. Child 2 must clear Child 1's grandchildren)
  const getSubtreeBounds = (nid: string): { minY: number; maxY: number } => {
    const y = adjustedY.get(nid) ?? 0
    const kids = childrenMap.get(nid)
    if (!kids?.length) {
      return { minY: y, maxY: y + DEFAULT_NODE_HEIGHT }
    }
    let minY = y
    let maxY = y + DEFAULT_NODE_HEIGHT
    kids.forEach((cid) => {
      const b = getSubtreeBounds(cid)
      minY = Math.min(minY, b.minY)
      maxY = Math.max(maxY, b.maxY)
    })
    return { minY, maxY }
  }

  const collectDescendants = (nodeId: string): string[] => {
    const out: string[] = [nodeId]
    childrenMap.get(nodeId)?.forEach((cid) => {
      out.push(...collectDescendants(cid))
    })
    return out
  }

  // Process all nodes at each depth together so cross-branch overlap is resolved
  // (e.g. Branch 2's children must clear Branch 1's grandchildren; Branch 3's children must clear Branch 2's)
  for (let depth = 1; depth <= maxDepth; depth++) {
    const nodesAtDepth =
      depth === 1
        ? dagreEdges.filter((e) => e.source === virtualRoot).map((e) => e.target)
        : Array.from(nodeInfos.entries())
            .filter(([, info]) => info.depth === depth)
            .map(([id]) => id)

    if (nodesAtDepth.length < 2) continue

    const sorted = [...nodesAtDepth].sort((a, b) => {
      const ya = adjustedY.get(a) ?? 0
      const yb = adjustedY.get(b) ?? 0
      return ya - yb
    })

    let prevMax = -Infinity
    let prevNodeId: string | null = null
    for (const nodeId of sorted) {
      const bounds = getSubtreeBounds(nodeId)
      const baseGap = adjustedVerticalSpacing
      const crossBranch = prevNodeId !== null && getBranchRoot(nodeId) !== getBranchRoot(prevNodeId)
      const gap = crossBranch ? baseGap * 1.5 : baseGap
      const requiredMin = prevMax + gap
      if (bounds.minY < requiredMin) {
        const delta = requiredMin - bounds.minY
        collectDescendants(nodeId).forEach((nid) => {
          const cur = adjustedY.get(nid) ?? 0
          adjustedY.set(nid, cur + delta)
        })
        prevMax = requiredMin + (bounds.maxY - bounds.minY)
      } else {
        prevMax = bounds.maxY
      }
      prevNodeId = nodeId
    }
  }

  // Calculate offset to align virtual root center with topic edge
  const virtualRootCenterY = virtualPos.y + virtualPos.height / 2
  const offsetY = topicY - virtualRootCenterY

  // Build branchIndex map: first-level from handleIndex, children inherit from parent
  const branchIndexMap = new Map<string, number>()
  let handleIndexForBranch = 0
  dagreEdges.forEach((edge) => {
    if (edge.source === virtualRoot) {
      const branchIndex =
        side === 'right' ? handleIndexForBranch : _startHandleIndex + handleIndexForBranch
      branchIndexMap.set(edge.target, branchIndex)
      handleIndexForBranch++
    } else {
      const parentIndex = branchIndexMap.get(edge.source)
      if (parentIndex !== undefined) {
        branchIndexMap.set(edge.target, parentIndex)
      }
    }
  })

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

    const rawX = pos.x + offsetX
    const finalX = side === 'left' ? 2 * topicX - rawX - info.estimatedWidth : rawX

    const branchIndex = branchIndexMap.get(nodeId) ?? 0

    nodes.push({
      id: nodeId,
      text: info.text,
      type: 'branch',
      position: {
        x: finalX,
        y: finalY + offsetY,
      },
      data: { branchIndex, estimatedWidth: info.estimatedWidth },
    })
  })

  // Assign handles: right side uses mindmap-right-*, left side uses mindmap-left-*
  let handleIndex = 0

  dagreEdges.forEach((edge) => {
    if (edge.source === virtualRoot) {
      const handleId =
        side === 'right' ? `mindmap-right-${handleIndex}` : `mindmap-left-${handleIndex}`

      // Topic-to-branch connections: right side branches connect via left handle, left side branches connect via right handle
      const targetHandle = side === 'left' ? 'right-target' : 'left'
      const branchIndex = branchIndexMap.get(edge.target) ?? 0
      const strokeColor = getMindmapBranchColor(branchIndex).border

      connections.push({
        id: `edge-topic-${edge.target}`,
        source: 'topic',
        target: edge.target,
        sourceHandle: handleId,
        targetHandle: targetHandle,
        style: { strokeColor },
      })
      handleIndex++
    } else {
      // For branch-to-child connections, ensure correct handle positioning
      // Right side branches (LR): children connect via Right handle (source) → Left handle (target)
      // Left side branches (RL): children connect via Left handle (source) → Right handle (target)
      const sourceNodeInfo = nodeInfos.get(edge.source)
      const isLeftSideBranch = sourceNodeInfo?.direction === -1
      const childBranchIndex = branchIndexMap.get(edge.target) ?? 0
      const childStrokeColor = getMindmapBranchColor(childBranchIndex).border

      connections.push({
        id: `edge-${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        sourceHandle: isLeftSideBranch ? 'left-source' : 'right', // Left side uses left-source handle, right side uses right handle
        targetHandle: isLeftSideBranch ? 'right-target' : 'left', // Left side children use right-target handle, right side children use left handle
        style: { strokeColor: childStrokeColor },
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
    verticalSpacing,
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
          x: pos.x + offsetX,
          y: pos.y + offsetY,
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
export function distributeBranchesClockwise(branches: MindMapBranch[]): {
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
 * Normalize horizontal extent so left and right sides have equal curve length from center.
 * Shrinks the side with greater extent to match the shorter side (avoids over-extending).
 * Expands the shorter side when below minExtent (fixes short curves after branch move).
 * Exported for use when loading saved mindmap diagrams (loadGenericSpec path).
 */
export function normalizeMindMapHorizontalSymmetry(
  nodes: DiagramNode[],
  centerX: number,
  minExtent: number = DEFAULT_MINDMAP_RANK_SEPARATION
): void {
  const leftNodes = nodes.filter((n) => n.type === 'branch' && n.id.startsWith('branch-l-'))
  const rightNodes = nodes.filter((n) => n.type === 'branch' && n.id.startsWith('branch-r-'))

  if (leftNodes.length === 0 && rightNodes.length === 0) return

  const getNodeWidth = (node: DiagramNode): number =>
    (node.data?.estimatedWidth as number) || DEFAULT_NODE_WIDTH
  const getCenterX = (node: DiagramNode): number => (node.position?.x ?? 0) + getNodeWidth(node) / 2

  function scaleNodeX(
    node: DiagramNode,
    centerX: number,
    scale: number,
    side: 'left' | 'right'
  ): void {
    if (!node.position) return
    const nodeWidth = getNodeWidth(node)
    const center = getCenterX(node)
    const distFromCenter = side === 'left' ? centerX - center : center - centerX
    const newCenter =
      side === 'left' ? centerX - distFromCenter * scale : centerX + distFromCenter * scale
    node.position.x = newCenter - nodeWidth / 2
  }

  let leftExtent = leftNodes.length > 0 ? centerX - Math.min(...leftNodes.map(getCenterX)) : 0
  let rightExtent = rightNodes.length > 0 ? Math.max(...rightNodes.map(getCenterX)) - centerX : 0

  console.log('[CurveDebug] normalize before', {
    centerX,
    leftCount: leftNodes.length,
    rightCount: rightNodes.length,
    leftExtent,
    rightExtent,
    leftExtentDelta: leftExtent - rightExtent,
    minExtent,
  })
  // Scale both sides up when extent is below target (e.g. after branch move)
  const currentExtent = Math.min(leftExtent, rightExtent) || Math.max(leftExtent, rightExtent)
  if (currentExtent > 0 && currentExtent < MINDMAP_TARGET_EXTENT) {
    const scale = MINDMAP_TARGET_EXTENT / currentExtent
    leftNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'left'))
    rightNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'right'))
    leftExtent = leftExtent > 0 ? leftExtent * scale : 0
    rightExtent = rightExtent > 0 ? rightExtent * scale : 0
  }

  const leftExpanded = leftExtent > 0 && leftExtent < minExtent
  const rightExpanded = rightExtent > 0 && rightExtent < minExtent
  // Expand shorter side when below minimum (e.g. after branch move leaves one side sparse)
  if (leftExpanded) {
    const scale = minExtent / leftExtent
    leftNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'left'))
    leftExtent = minExtent
  }
  if (rightExpanded) {
    const scale = minExtent / rightExtent
    rightNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'right'))
    rightExtent = minExtent
  }

  // Expand smaller to match larger (never shrink) - same behavior as manual add
  const targetExtent = Math.max(leftExtent, rightExtent) || Math.min(leftExtent, rightExtent)
  if (targetExtent <= 0) return

  if (leftExtent > 0 && leftExtent < targetExtent) {
    const scale = targetExtent / leftExtent
    leftNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'left'))
  }

  if (rightExtent > 0 && rightExtent < targetExtent) {
    const scale = targetExtent / rightExtent
    rightNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'right'))
  }
  const leftExtentAfter =
    leftNodes.length > 0 ? centerX - Math.min(...leftNodes.map(getCenterX)) : 0
  const rightExtentAfter =
    rightNodes.length > 0 ? Math.max(...rightNodes.map(getCenterX)) - centerX : 0
  console.log('[CurveDebug] normalize after', {
    targetExtent,
    leftExtentAfter,
    rightExtentAfter,
    extentDiff: Math.abs(leftExtentAfter - rightExtentAfter),
    leftExpanded,
    rightExpanded,
  })
}

/**
 * Normalize branch-to-child curve spans so left and right match.
 * Layout can produce asymmetric spans (e.g. left 224.72 vs right 240); scale the shorter
 * side's children relative to their parents to match.
 */
function normalizeBranchToChildSpans(nodes: DiagramNode[], connections: Connection[]): void {
  const getNodeWidth = (n: DiagramNode): number =>
    (n.data?.estimatedWidth as number) || DEFAULT_NODE_WIDTH
  const getCenterX = (n: DiagramNode) => (n.position?.x ?? 0) + getNodeWidth(n) / 2
  const nodeCenterX = new Map<string, number>()
  nodes.forEach((n) => {
    if (n.position) {
      nodeCenterX.set(n.id, getCenterX(n))
    }
  })

  const leftSpans: { parentId: string; childId: string; span: number }[] = []
  const rightSpans: { parentId: string; childId: string; span: number }[] = []
  connections.forEach((conn) => {
    if (
      conn.source.startsWith('branch-') &&
      conn.target.startsWith('branch-') &&
      conn.source !== conn.target
    ) {
      const srcX = nodeCenterX.get(conn.source)
      const tgtX = nodeCenterX.get(conn.target)
      if (srcX != null && tgtX != null) {
        const span = Math.abs(tgtX - srcX)
        if (conn.source.startsWith('branch-l-')) {
          leftSpans.push({ parentId: conn.source, childId: conn.target, span })
        } else {
          rightSpans.push({ parentId: conn.source, childId: conn.target, span })
        }
      }
    }
  })

  const leftAvg =
    leftSpans.length > 0 ? leftSpans.reduce((s, p) => s + p.span, 0) / leftSpans.length : 0
  const rightAvg =
    rightSpans.length > 0 ? rightSpans.reduce((s, p) => s + p.span, 0) / rightSpans.length : 0
  if (leftAvg <= 0 || rightAvg <= 0) return

  const target = Math.max(leftAvg, rightAvg)
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))

  if (leftAvg < target) {
    const scale = target / leftAvg
    leftSpans.forEach(({ parentId, childId }) => {
      const parent = nodeMap.get(parentId)
      const child = nodeMap.get(childId)
      if (!parent?.position || !child?.position) return
      const parentCenter = getCenterX(parent)
      const childCenter = getCenterX(child)
      const distFromParent = childCenter - parentCenter
      const newChildCenter = parentCenter + distFromParent * scale
      child.position.x = newChildCenter - getNodeWidth(child) / 2
    })
  }
  if (rightAvg < target) {
    const scale = target / rightAvg
    rightSpans.forEach(({ parentId, childId }) => {
      const parent = nodeMap.get(parentId)
      const child = nodeMap.get(childId)
      if (!parent?.position || !child?.position) return
      const parentCenter = getCenterX(parent)
      const childCenter = getCenterX(child)
      const distFromParent = childCenter - parentCenter
      const newChildCenter = parentCenter + distFromParent * scale
      child.position.x = newChildCenter - getNodeWidth(child) / 2
    })
  }
}

/**
 * Convert diagram nodes and connections back to mindmap spec.
 * Used when adding/removing nodes to rebuild and reload layout.
 */
export function nodesAndConnectionsToMindMapSpec(
  nodes: DiagramNode[],
  connections: Connection[]
): { topic: string; leftBranches: MindMapBranch[]; rightBranches: MindMapBranch[] } {
  const topicNode = nodes.find((n) => n.id === 'topic')
  const topic = topicNode?.text ?? ''

  const childrenMap = new Map<string, string[]>()
  connections.forEach((c) => {
    if (!childrenMap.has(c.source)) {
      childrenMap.set(c.source, [])
    }
    const sourceChildren = childrenMap.get(c.source)
    if (sourceChildren) {
      sourceChildren.push(c.target)
    }
  })

  const nodeMap = new Map(nodes.map((n) => [n.id, n]))

  function buildBranch(nodeId: string): MindMapBranch | null {
    const node = nodeMap.get(nodeId)
    if (!node || nodeId === 'topic') return null
    const childIds = childrenMap.get(nodeId) ?? []
    const children = childIds
      .map((id) => buildBranch(id))
      .filter((b): b is MindMapBranch => b !== null)
    return {
      text: node.text ?? '',
      children: children.length > 0 ? children : undefined,
    }
  }

  const topicChildIds = childrenMap.get('topic') ?? []
  // ID format: branch-{side}-{depth}-{globalIndex}; sort by globalIndex to preserve layout order
  const sortByGlobalIndex = (a: string, b: string): number => {
    const aParts = a.split('-')
    const bParts = b.split('-')
    const aIdx = parseInt(aParts[3] ?? '0', 10)
    const bIdx = parseInt(bParts[3] ?? '0', 10)
    return aIdx - bIdx
  }
  const rightIds = topicChildIds.filter((id) => id.startsWith('branch-r-')).sort(sortByGlobalIndex)
  const leftIds = topicChildIds.filter((id) => id.startsWith('branch-l-')).sort(sortByGlobalIndex)

  const rightBranches = rightIds
    .map((id) => buildBranch(id))
    .filter((b): b is MindMapBranch => b !== null)
  const leftBranches = leftIds
    .map((id) => buildBranch(id))
    .filter((b): b is MindMapBranch => b !== null)

  return { topic, leftBranches, rightBranches }
}

export interface FindBranchResult {
  branch: MindMapBranch
  parentArray: MindMapBranch[]
  indexInParent: number
}

/**
 * Find a branch in the spec tree by node ID (matches layout ID generation order).
 */
export function findBranchByNodeId(
  rightBranches: MindMapBranch[],
  leftBranches: MindMapBranch[],
  nodeId: string
): FindBranchResult | null {
  const counter = { value: 0 }
  let result: FindBranchResult | null = null

  function traverse(
    branches: MindMapBranch[],
    side: 'r' | 'l',
    depth: number,
    parentArray: MindMapBranch[]
  ): boolean {
    for (let i = 0; i < branches.length; i++) {
      const id = `branch-${side}-${depth}-${counter.value}`
      counter.value++
      if (id === nodeId) {
        result = { branch: branches[i], parentArray, indexInParent: i }
        return true
      }
      const childBranches = branches[i].children
      if (childBranches?.length) {
        if (traverse(childBranches, side, depth + 1, childBranches)) {
          return true
        }
      }
    }
    return false
  }

  if (traverse(rightBranches, 'r', 1, rightBranches)) return result
  counter.value = 0
  if (traverse(leftBranches, 'l', 1, leftBranches)) return result
  return null
}

/**
 * Load mind map spec into diagram nodes and connections
 *
 * @param spec - Mind map spec with topic and branches
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadMindMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const topic = (spec.topic as string) || (spec.central_topic as string) || ''

  let rightBranches: MindMapBranch[]
  let leftBranches: MindMapBranch[]

  if (spec.preserveLeftRight && spec.leftBranches && spec.rightBranches) {
    console.log('[BranchMove] loadMindMapSpec (preserveLeftRight)', {
      topic,
      leftCount: (spec.leftBranches as MindMapBranch[]).length,
      rightCount: (spec.rightBranches as MindMapBranch[]).length,
    })
    rightBranches = spec.rightBranches as MindMapBranch[]
    leftBranches = spec.leftBranches as MindMapBranch[]
  } else if (spec.leftBranches || spec.left || spec.rightBranches || spec.right) {
    const left = (spec.leftBranches as MindMapBranch[]) || (spec.left as MindMapBranch[]) || []
    const right = (spec.rightBranches as MindMapBranch[]) || (spec.right as MindMapBranch[]) || []
    const allBranches = [...left, ...right]
    const distributed = distributeBranchesClockwise(allBranches)
    rightBranches = distributed.rightBranches
    leftBranches = distributed.leftBranches
  } else if (Array.isArray(spec.children)) {
    const allBranches = spec.children as MindMapBranch[]
    const distributed = distributeBranchesClockwise(allBranches)
    rightBranches = distributed.rightBranches
    leftBranches = distributed.leftBranches
  } else {
    rightBranches = []
    leftBranches = []
  }

  const allBranches = [...rightBranches, ...leftBranches]

  // Layout constants from layoutConfig
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  // Same rankSeparation for auto-complete and manual add so layout is identical
  const rankSeparation = DEFAULT_MINDMAP_RANK_SEPARATION
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
    rankSeparation,
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
    rankSeparation,
    verticalSpacing,
    nodes,
    connections,
    rightBranches.length, // Start index for handle IDs (continues from right)
    allBranches.length
  )

  // Step 2.5: Normalize horizontal extent for symmetry (equal curve length on both sides)
  // Diagnostic: log raw layout positions before normalize
  const leftBefore = nodes.filter((n) => n.type === 'branch' && n.id.startsWith('branch-l-'))
  const rightBefore = nodes.filter((n) => n.type === 'branch' && n.id.startsWith('branch-r-'))
  const getCenterX = (n: DiagramNode) =>
    (n.position?.x ?? 0) + ((n.data?.estimatedWidth as number) || DEFAULT_NODE_WIDTH) / 2
  if (leftBefore.length > 0 || rightBefore.length > 0) {
    const leftMin = leftBefore.length ? Math.min(...leftBefore.map(getCenterX)) : 0
    const rightMax = rightBefore.length ? Math.max(...rightBefore.map(getCenterX)) : 0
    console.log('[CurveDebug] layout before normalize', {
      leftCount: leftBefore.length,
      rightCount: rightBefore.length,
      leftMinCenterX: leftMin,
      rightMaxCenterX: rightMax,
      leftExtentRaw: centerX - leftMin,
      rightExtentRaw: rightMax - centerX,
    })
  }
  // Single pass: extent + branch-to-child. Expand smaller side (never shrink) so layout stays consistent.
  normalizeBranchToChildSpans(nodes, connections)
  normalizeMindMapHorizontalSymmetry(nodes, centerX)

  // Step 3: Center topic node vertically relative to all first-level branches
  let minBranchY = Infinity
  let maxBranchY = -Infinity
  nodes.forEach((node) => {
    if (node.type === 'branch') {
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

  if (minBranchY !== Infinity && maxBranchY !== -Infinity && topicNode.position) {
    const branchesCenterY = (minBranchY + maxBranchY) / 2
    topicNode.position.y = branchesCenterY - DEFAULT_NODE_HEIGHT / 2
  }

  // Step 4: Center entire layout so topic node is at canvas center
  if (topicNode.position) {
    const topicCurrentCenterX = topicNode.position.x + DEFAULT_NODE_WIDTH / 2
    const topicCurrentCenterY = topicNode.position.y + DEFAULT_NODE_HEIGHT / 2
    const offsetXToCenter = centerX - topicCurrentCenterX
    const offsetYToCenter = centerY - topicCurrentCenterY
    nodes.forEach((node) => {
      if (node.position) {
        node.position.x += offsetXToCenter
        node.position.y += offsetYToCenter
      }
    })
  }

  // Diagnostic: branch-to-child curve lengths (horizontal span from parent to child)
  const nodeCenterX = new Map<string, number>()
  nodes.forEach((n) => {
    if (n.position) {
      const nodeWidth = (n.data?.estimatedWidth as number) || DEFAULT_NODE_WIDTH
      nodeCenterX.set(n.id, (n.position.x ?? 0) + nodeWidth / 2)
    }
  })
  const leftChildSpans: number[] = []
  const rightChildSpans: number[] = []
  connections.forEach((conn) => {
    if (
      conn.source.startsWith('branch-') &&
      conn.target.startsWith('branch-') &&
      conn.source !== conn.target
    ) {
      const srcX = nodeCenterX.get(conn.source)
      const tgtX = nodeCenterX.get(conn.target)
      if (srcX != null && tgtX != null) {
        const span = Math.abs(tgtX - srcX)
        if (conn.source.startsWith('branch-l-')) {
          leftChildSpans.push(span)
        } else {
          rightChildSpans.push(span)
        }
      }
    }
  })
  if (leftChildSpans.length > 0 || rightChildSpans.length > 0) {
    const sum = (a: number[]) => a.reduce((s, v) => s + v, 0)
    const avg = (a: number[]) => (a.length ? sum(a) / a.length : 0)
    console.log('[CurveDebug] branch-to-child spans', {
      leftCount: leftChildSpans.length,
      rightCount: rightChildSpans.length,
      leftMin: leftChildSpans.length ? Math.min(...leftChildSpans) : 0,
      leftMax: leftChildSpans.length ? Math.max(...leftChildSpans) : 0,
      leftAvg: avg(leftChildSpans),
      rightMin: rightChildSpans.length ? Math.min(...rightChildSpans) : 0,
      rightMax: rightChildSpans.length ? Math.max(...rightChildSpans) : 0,
      rightAvg: avg(rightChildSpans),
    })
  }

  return { nodes, connections }
}
