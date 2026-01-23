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
  // Start X accounts for dimension label on the left (label positioned relative to startX)
  const startX = DEFAULT_PADDING + 110
  const centerY = DEFAULT_CENTER_Y
  const gapBetweenPairs = 50 // Actual gap between node edges (right edge to left edge)
  // Bridge map nodes should be close to the bridge line (smaller gap than default)
  const verticalGap = 5 // Small gap between node edge and bridge line (was DEFAULT_LEVEL_HEIGHT = 100)
  const nodeWidth = DEFAULT_NODE_WIDTH
  // Use consistent height for both nodes to ensure symmetry
  // Use BRANCH_NODE_HEIGHT (36px) which matches BranchNode's min-height
  const nodeHeight = BRANCH_NODE_HEIGHT

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
  // Always show label if either exists (even if empty, show relating_factor as default)
  const dimension =
    (spec.dimension as string | undefined)?.trim() ||
    (spec.relating_factor as string | undefined)?.trim()
  if (dimension) {
    // Position dimension label on the left side, vertically centered with the horizontal bridge line
    // The bridge line is at centerY (same Y as the center of all analogy pairs)
    // Vue Flow positions nodes by top-left corner, so we need to adjust Y to center the node
    // Label node has two lines: "类比关系:" (14px) + gap (2px) + "[点击设置]" (14px) + padding (8px total)
    // Estimated total height: ~38px, use 40px for safety
    const labelHeight = 40
    const labelY = centerY - labelHeight / 2

    // Position label so its right edge has enough gap from the nodes' left edge
    // Nodes start at startX (left edge)
    // Label's right edge should be at: startX - gapFromNodes
    // Label's left edge (labelX) should be at: startX - gapFromNodes - estimatedLabelWidth
    const gapFromNodes = 8 // Small gap from nodes
    const estimatedLabelWidth = 180 // Based on max-width constraint
    const labelX = startX - gapFromNodes - estimatedLabelWidth

    nodes.push({
      id: 'dimension-label',
      text: dimension.trim(),
      type: 'label',
      position: { x: labelX, y: labelY },
      data: {
        diagramType: 'bridge_map',
        isDimensionLabel: true,
      },
    })
  }

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
