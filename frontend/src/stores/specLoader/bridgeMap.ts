/**
 * Bridge Map Loader
 */
import {
  BRANCH_NODE_HEIGHT,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

const BRIDGE_VERTICAL_GAP = 5
const BRIDGE_GAP_BETWEEN_PAIRS = 50

/**
 * Post-render layout correction for bridge maps.
 * Uses actual DOM-measured heights from Pinia so each pair node sits the
 * correct distance above/below the bridge centre line.
 */
export function recalculateBridgeMapLayout(
  nodes: DiagramNode[],
  nodeDimensions: Record<string, { width: number; height: number }> = {}
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) return nodes

  const centerY = DEFAULT_CENTER_Y

  const getH = (id: string): number => {
    const pinia = nodeDimensions[id]?.height
    return pinia ?? BRANCH_NODE_HEIGHT
  }

  const getW = (id: string): number => nodeDimensions[id]?.width ?? DEFAULT_NODE_WIDTH

  const pairNodes = nodes.filter((n) => n.id?.startsWith('pair-'))
  const otherNodes = nodes.filter((n) => !n.id?.startsWith('pair-'))

  if (pairNodes.length === 0) return nodes

  const maxPairIndex = pairNodes.reduce((max, n) => {
    const idx = Number(n.data?.pairIndex ?? -1)
    return idx > max ? idx : max
  }, -1)

  const result = otherNodes.map((n) => ({ ...n }))

  let currentX = nodes.find((n) => n.id === 'pair-0-left')?.position?.x ?? DEFAULT_PADDING + 110

  for (let i = 0; i <= maxPairIndex; i++) {
    const leftId = `pair-${i}-left`
    const rightId = `pair-${i}-right`
    const leftNode = pairNodes.find((n) => n.id === leftId)
    const rightNode = pairNodes.find((n) => n.id === rightId)
    if (!leftNode || !rightNode) continue

    const leftH = getH(leftId)
    const pairWidth = Math.max(getW(leftId), getW(rightId))

    const leftY = centerY - BRIDGE_VERTICAL_GAP - leftH
    const rightY = centerY + BRIDGE_VERTICAL_GAP
    result.push({
      ...leftNode,
      position: { x: currentX, y: leftY },
    })
    result.push({
      ...rightNode,
      position: { x: currentX, y: rightY },
    })

    currentX += pairWidth + BRIDGE_GAP_BETWEEN_PAIRS
  }

  return result
}

/**
 * Load bridge map spec into diagram nodes and connections
 *
 * @param spec - Bridge map spec with analogies or pairs
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadBridgeMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  // Bridge maps use analogies array with left/right properties
  // Support both old format (pairs with top/bottom) and new format (analogies with left/right)
  let analogies: Array<{ left: string; right: string }> = []

  if (spec.analogies && Array.isArray(spec.analogies)) {
    // New format: analogies with left/right
    analogies = spec.analogies.map(
      (a: { left?: string; right?: string; top?: string; bottom?: string }) => ({
        left: a.left || a.top || '',
        right: a.right || a.bottom || '',
      })
    )
  } else if (spec.pairs && Array.isArray(spec.pairs)) {
    // Old format: pairs with top/bottom
    analogies = spec.pairs.map(
      (p: { top?: string; bottom?: string; left?: string; right?: string }) => ({
        left: p.left || p.top || '',
        right: p.right || p.bottom || '',
      })
    )
  }

  // Layout constants from layoutConfig
  const centerY = DEFAULT_CENTER_Y
  const gapBetweenPairs = 50 // Actual gap between node edges (right edge to left edge)
  // Bridge map nodes should be close to the bridge line (smaller gap than default)
  const verticalGap = 5 // Small gap between node edge and bridge line (was DEFAULT_LEVEL_HEIGHT = 100)
  const nodeWidth = DEFAULT_NODE_WIDTH
  // Use consistent height for both nodes to ensure symmetry
  // Use BRANCH_NODE_HEIGHT (36px) which matches BranchNode's min-height
  const nodeHeight = BRANCH_NODE_HEIGHT

  // Layout constants from layoutConfig
  // Position label first, then position nodes relative to label
  // Gap is measured from label's RIGHT edge to horizontal bridge line start (node's LEFT edge)
  // The horizontal bridge line starts at the leftmost node position
  const gapFromLabelRight = 10 // Gap from label's right edge to horizontal line start (leftmost node's left edge)
  const estimatedLabelWidth = 100 // Estimated label width (actual width will be measured by LabelNode)
  // Start X for nodes: padding + estimated label width + gap from label right
  // This positions nodes so there's a 10px gap between label's right edge and horizontal line start
  const startX = DEFAULT_PADDING + estimatedLabelWidth + gapFromLabelRight

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Calculate positions based on actual node edges (not centers)
  let currentX = startX

  analogies.forEach((analogy, index) => {
    // Position nodes at currentX (left edge)
    const nodeX = currentX

    // Left node (top position, close to bridge line)
    // Align all left nodes by their centers so they're visually aligned regardless of height
    // Center Y = centerY - verticalGap - nodeHeight/2
    // Top-left Y = centerY - verticalGap - nodeHeight/2 - nodeHeight/2 = centerY - verticalGap - nodeHeight
    const leftNodeY = centerY - verticalGap - nodeHeight

    // Right node (bottom position, close to bridge line)
    // Align all right nodes by their centers so they're visually aligned regardless of height
    // Center Y = centerY + verticalGap + nodeHeight/2
    // Top-left Y = centerY + verticalGap + nodeHeight/2 - nodeHeight/2 = centerY + verticalGap
    const rightNodeY = centerY + verticalGap

    nodes.push({
      id: `pair-${index}-left`,
      text: analogy.left,
      type: 'branch',
      position: { x: nodeX, y: leftNodeY },
      data: {
        pairIndex: index,
        position: 'left',
        diagramType: 'bridge_map',
      },
    })

    nodes.push({
      id: `pair-${index}-right`,
      text: analogy.right,
      type: 'branch',
      position: { x: nodeX, y: rightNodeY },
      data: {
        pairIndex: index,
        position: 'right',
        diagramType: 'bridge_map',
      },
    })

    // Move to next position: right edge of current node + gap
    currentX = nodeX + nodeWidth + gapBetweenPairs
  })

  // Add dimension label node on the left side
  // Use dimension if available, otherwise fall back to relating_factor
  // Always create the label — LabelNode shows placeholder text when empty
  const dimension =
    (spec.dimension as string | undefined)?.trim() ||
    (spec.relating_factor as string | undefined)?.trim() ||
    ''

  const labelHeight = 40
  const labelY = centerY - labelHeight / 2
  const labelX = DEFAULT_PADDING

  nodes.push({
    id: 'dimension-label',
    text: dimension,
    type: 'label',
    position: { x: labelX, y: labelY },
    data: {
      diagramType: 'bridge_map',
      isDimensionLabel: true,
    },
  })

  // Store dimension, relating_factor, and alternative_dimensions in metadata for BridgeOverlay
  const metadata: Record<string, unknown> = {}
  if (spec.dimension) {
    metadata.dimension = spec.dimension
  }
  if (spec.relating_factor) {
    metadata.relating_factor = spec.relating_factor
  }
  if (spec.alternative_dimensions) {
    metadata.alternative_dimensions = spec.alternative_dimensions
  }

  return { nodes, connections, metadata }
}
