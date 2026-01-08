/**
 * Spec Loader - Converts API spec format to DiagramData
 * Each diagram type has its own converter function
 *
 * This separates the spec-to-data conversion logic from the store,
 * making it easier to maintain and test each diagram type independently.
 */
import type { Connection, DiagramNode, DiagramType } from '@/types'

export interface SpecLoaderResult {
  nodes: DiagramNode[]
  connections: Connection[]
  metadata?: Record<string, unknown>
}

// ============================================================================
// Circle Map Layout Calculation
// Shared by both loadCircleMapSpec and recalculateCircleMapLayout
// ============================================================================
interface CircleMapLayoutResult {
  centerX: number
  centerY: number
  topicR: number
  uniformContextR: number
  childrenRadius: number
  outerCircleR: number
}

function calculateCircleMapLayout(nodeCount: number): CircleMapLayoutResult {
  // Node size constants (matching VueFlow node components)
  // Context nodes: 70px diameter circles
  // Topic node: 120px diameter circle
  const uniformContextR = 35
  const topicR = 60
  const padding = 40

  // Calculate childrenRadius using both constraints (matching original D3 logic)
  const targetRadialDistance = topicR + topicR * 0.5 + uniformContextR + 5
  const spacingMultiplier = nodeCount <= 3 ? 2.0 : nodeCount <= 6 ? 2.05 : 2.1
  const circumferentialMinRadius =
    nodeCount > 0 ? (uniformContextR * nodeCount * spacingMultiplier) / (2 * Math.PI) : 0
  const childrenRadius = Math.max(targetRadialDistance, circumferentialMinRadius, 100)
  const outerCircleR = childrenRadius + uniformContextR + 10
  const centerX = outerCircleR + padding
  const centerY = outerCircleR + padding

  return { centerX, centerY, topicR, uniformContextR, childrenRadius, outerCircleR }
}

/**
 * Recalculate circle map layout from existing nodes
 * Called when nodes are added/deleted to update boundary and positions
 */
export function recalculateCircleMapLayout(nodes: DiagramNode[]): DiagramNode[] {
  // Find topic node and context nodes
  const topicNode = nodes.find((n) => n.type === 'topic' || n.type === 'center')
  const contextNodes = nodes.filter(
    (n) => n.type === 'bubble' && n.id.startsWith('context-')
  )
  const nodeCount = contextNodes.length

  // Calculate layout based on current node count
  const layout = calculateCircleMapLayout(nodeCount)

  const result: DiagramNode[] = []

  // Outer boundary node (giant outer circle) - always recreate with correct size
  result.push({
    id: 'outer-boundary',
    text: '',
    type: 'boundary',
    position: { x: layout.centerX - layout.outerCircleR, y: layout.centerY - layout.outerCircleR },
    style: { width: layout.outerCircleR * 2, height: layout.outerCircleR * 2 },
  })

  // Topic node - centered
  if (topicNode) {
    result.push({
      id: 'topic',
      text: topicNode.text,
      type: 'center',
      position: { x: layout.centerX - layout.topicR, y: layout.centerY - layout.topicR },
      style: { size: layout.topicR * 2 },
    })
  }

  // Context nodes - evenly distributed around
  contextNodes.forEach((node, index) => {
    const angleDeg = (index * 360) / nodeCount - 90
    const angleRad = (angleDeg * Math.PI) / 180
    const x = layout.centerX + layout.childrenRadius * Math.cos(angleRad) - layout.uniformContextR
    const y = layout.centerY + layout.childrenRadius * Math.sin(angleRad) - layout.uniformContextR

    result.push({
      id: `context-${index}`,
      text: node.text,
      type: 'bubble',
      position: { x, y },
      style: { size: layout.uniformContextR * 2 },
    })
  })

  return result
}

// ============================================================================
// Circle Map
// Circle maps have: central topic circle, context circles around it, outer boundary ring
// NO connection lines between nodes (unlike bubble maps)
// ============================================================================
export function loadCircleMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const topic = (spec.topic as string) || ''
  const context = (spec.context as string[]) || []
  const nodeCount = context.length

  // Node size constants (matching VueFlow node components)
  // Context nodes: 70px diameter circles
  // Topic node: 120px diameter circle
  const uniformContextR = 35
  const topicR = 60
  const padding = 40

  // Calculate childrenRadius using both constraints (matching original D3 logic)
  const targetRadialDistance = topicR + topicR * 0.5 + uniformContextR + 5
  const spacingMultiplier = nodeCount <= 3 ? 2.0 : nodeCount <= 6 ? 2.05 : 2.1
  const circumferentialMinRadius =
    nodeCount > 0 ? (uniformContextR * nodeCount * spacingMultiplier) / (2 * Math.PI) : 0
  const childrenRadius = Math.max(targetRadialDistance, circumferentialMinRadius, 100)
  const outerCircleR = childrenRadius + uniformContextR + 10
  const centerX = outerCircleR + padding
  const centerY = outerCircleR + padding

  const nodes: DiagramNode[] = []
  // Circle maps have NO connections (no lines between nodes)
  const connections: Connection[] = []

  // Outer boundary node (giant outer circle)
  nodes.push({
    id: 'outer-boundary',
    text: '',
    type: 'boundary',
    position: { x: centerX - outerCircleR, y: centerY - outerCircleR },
    style: { width: outerCircleR * 2, height: outerCircleR * 2 },
  })

  // Topic node - perfect circle at center
  // Use 'center' type which maps to 'circle' in vueflow
  nodes.push({
    id: 'topic',
    text: topic,
    type: 'center', // Maps to 'circle' node type for perfect circle rendering
    position: { x: centerX - topicR, y: centerY - topicR },
    style: { size: topicR * 2 }, // Diameter for perfect circle
  })

  // Context nodes - perfect circles distributed around
  context.forEach((ctx, index) => {
    const angleDeg = (index * 360) / nodeCount - 90
    const angleRad = (angleDeg * Math.PI) / 180
    const x = centerX + childrenRadius * Math.cos(angleRad) - uniformContextR
    const y = centerY + childrenRadius * Math.sin(angleRad) - uniformContextR

    nodes.push({
      id: `context-${index}`,
      text: ctx,
      type: 'bubble', // Maps to 'circle' node type for circle maps
      position: { x, y },
      style: { size: uniformContextR * 2 }, // Diameter for perfect circle
    })
    // NO connection created - circle maps have no lines
  })

  return {
    nodes,
    connections, // Empty - no connections for circle maps
    metadata: {
      _circleMapLayout: {
        centerX,
        centerY,
        topicR,
        uniformContextR,
        childrenRadius,
        outerCircleR,
        innerRadius: topicR + uniformContextR + 5,
        outerRadius: outerCircleR - uniformContextR - 5,
      },
    },
  }
}

// ============================================================================
// Bubble Map
// ============================================================================
export function loadBubbleMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const topic = (spec.topic as string) || ''
  const attributes = (spec.attributes as string[]) || []

  // Layout constants matching useBubbleMap.ts
  const uniformAttributeR = 40 // DEFAULT_BUBBLE_RADIUS
  const topicR = 60 // DEFAULT_TOPIC_RADIUS
  const padding = 40 // DEFAULT_PADDING

  // Dynamic layout calculation (matching old JS: topicR + uniformAttributeR + 50)
  const nodeCount = attributes.length
  const targetDistance = topicR + uniformAttributeR + 50

  // Circumferential constraint for many nodes
  const spacingMultiplier = nodeCount <= 3 ? 2.0 : nodeCount <= 6 ? 2.05 : 2.1
  const circumferentialMinRadius =
    nodeCount > 0 ? (uniformAttributeR * nodeCount * spacingMultiplier) / (2 * Math.PI) : 0

  // Use the larger of both constraints (minimum 100px)
  const childrenRadius = Math.max(targetDistance, circumferentialMinRadius, 100)

  // Dynamic canvas center
  const centerX = childrenRadius + uniformAttributeR + padding
  const centerY = childrenRadius + uniformAttributeR + padding

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Topic node - perfect circle (uses CircleNode)
  nodes.push({
    id: 'topic',
    text: topic,
    type: 'topic',
    position: { x: centerX - topicR, y: centerY - topicR },
  })

  // Attribute bubbles arranged in a circle
  // Start from top (-90 degrees) with even angle distribution
  attributes.forEach((attr, index) => {
    const angleDeg = (index * 360) / nodeCount - 90 // Start from top
    const angleRad = (angleDeg * Math.PI) / 180

    // Position at childrenRadius from center
    const x = centerX + childrenRadius * Math.cos(angleRad) - uniformAttributeR
    const y = centerY + childrenRadius * Math.sin(angleRad) - uniformAttributeR

    nodes.push({
      id: `bubble-${index}`,
      text: attr,
      type: 'bubble',
      position: { x, y },
    })

    connections.push({
      id: `edge-topic-bubble-${index}`,
      source: 'topic',
      target: `bubble-${index}`,
    })
  })

  return { nodes, connections }
}

// ============================================================================
// Double Bubble Map
// ============================================================================
export function loadDoubleBubbleMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const left = (spec.left as string) || (spec.topic1 as string) || ''
  const right = (spec.right as string) || (spec.topic2 as string) || ''
  const similarities = (spec.similarities as string[]) || (spec.shared as string[]) || []
  const leftDifferences =
    (spec.leftDifferences as string[]) ||
    (spec.left_differences as string[]) ||
    (spec.left_unique as string[]) ||
    []
  const rightDifferences =
    (spec.rightDifferences as string[]) ||
    (spec.right_differences as string[]) ||
    (spec.right_unique as string[]) ||
    []

  // Layout constants matching useDoubleBubbleMap.ts
  const padding = 40
  const topicR = 60
  const simR = 40
  const diffR = 30
  const columnSpacing = 50

  // Vertical spacing
  const simVerticalSpacing = simR * 2 + 12
  const diffVerticalSpacing = diffR * 2 + 10

  // Calculate X positions (column-based layout from left to right)
  const leftDiffX = padding + diffR
  const leftTopicX = leftDiffX + diffR + columnSpacing + topicR
  const simX = leftTopicX + topicR + columnSpacing + simR
  const rightTopicX = simX + simR + columnSpacing + topicR
  const rightDiffX = rightTopicX + topicR + columnSpacing + diffR

  // Calculate heights
  const simCount = similarities.length
  const leftDiffCount = leftDifferences.length
  const rightDiffCount = rightDifferences.length

  // Calculate column heights (differences are paired, so use max count)
  const simColHeight = simCount > 0 ? (simCount - 1) * simVerticalSpacing + simR * 2 : 0
  const maxDiffCount = Math.max(leftDiffCount, rightDiffCount)
  const diffColHeight = maxDiffCount > 0 ? (maxDiffCount - 1) * diffVerticalSpacing + diffR * 2 : 0
  const maxColHeight = Math.max(simColHeight, diffColHeight, topicR * 2)

  const requiredHeight = maxColHeight + padding * 2
  const centerY = requiredHeight / 2

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Left topic (column 2) - perfect circle
  nodes.push({
    id: 'left-topic',
    text: left,
    type: 'topic',
    position: { x: leftTopicX - topicR, y: centerY - topicR },
  })

  // Right topic (column 4) - perfect circle
  nodes.push({
    id: 'right-topic',
    text: right,
    type: 'topic',
    position: { x: rightTopicX - topicR, y: centerY - topicR },
  })

  // Similarities (column 3, center)
  const simStartY = centerY - simColHeight / 2 + simR
  similarities.forEach((sim, index) => {
    nodes.push({
      id: `similarity-${index}`,
      text: sim,
      type: 'bubble',
      position: {
        x: simX - simR,
        y: simStartY + index * simVerticalSpacing - simR,
      },
    })
    connections.push(
      { id: `edge-left-sim-${index}`, source: 'left-topic', target: `similarity-${index}` },
      { id: `edge-right-sim-${index}`, source: 'right-topic', target: `similarity-${index}` }
    )
  })

  // Left and Right differences are PAIRED - they share the same Y positions
  const diffStartY = centerY - diffColHeight / 2 + diffR

  // Left differences (column 1, far left)
  leftDifferences.forEach((diff, index) => {
    nodes.push({
      id: `left-diff-${index}`,
      text: diff,
      type: 'bubble',
      position: {
        x: leftDiffX - diffR,
        y: diffStartY + index * diffVerticalSpacing - diffR,
      },
    })
    connections.push({
      id: `edge-left-diff-${index}`,
      source: 'left-topic',
      target: `left-diff-${index}`,
    })
  })

  // Right differences (column 5, far right) - same Y positions as left
  rightDifferences.forEach((diff, index) => {
    nodes.push({
      id: `right-diff-${index}`,
      text: diff,
      type: 'bubble',
      position: {
        x: rightDiffX - diffR,
        y: diffStartY + index * diffVerticalSpacing - diffR,
      },
    })
    connections.push({
      id: `edge-right-diff-${index}`,
      source: 'right-topic',
      target: `right-diff-${index}`,
    })
  })

  return { nodes, connections }
}

// ============================================================================
// Tree Map
// ============================================================================
interface TreeNode {
  id?: string
  text: string
  children?: TreeNode[]
}

/**
 * Tree Map Layout - Matches old JS tree-renderer.js:
 * - Topic (root) at top center with pill shape
 * - Categories (depth 1) spread horizontally below topic
 * - Leaves (depth 2+) stacked vertically below their parent category
 */
export function loadTreeMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Layout constants matching old JS
  const NODE_WIDTH = 120
  const NODE_HEIGHT = 50
  const CATEGORY_SPACING = 160 // Horizontal spacing between categories
  const LEAF_SPACING = 60 // Vertical spacing between leaves
  const TOPIC_TO_CATEGORY_GAP = 100 // Distance from topic to category row
  const CATEGORY_TO_LEAF_GAP = 80 // Distance from category to first leaf
  const START_X = 400 // Center X
  const START_Y = 60 // Topic Y position

  // Support both new format (root object) and old format (topic + children)
  let root: TreeNode | undefined = spec.root as TreeNode | undefined
  if (!root && spec.topic !== undefined) {
    // Convert old format to new format
    root = {
      id: 'tree-topic',
      text: (spec.topic as string) || '',
      children: (spec.children as TreeNode[]) || [],
    }
  }

  const dimension = spec.dimension as string | undefined
  const alternativeDimensions = spec.alternative_dimensions as string[] | undefined

  if (root) {
    const rootId = root.id || 'tree-topic'

    // Topic node at top center
    nodes.push({
      id: rootId,
      text: root.text,
      type: 'topic',
      position: { x: START_X - NODE_WIDTH / 2, y: START_Y },
    })

    // Categories (depth 1) - spread horizontally
    const categories = root.children || []
    if (categories.length > 0) {
      // Calculate total width for categories
      const totalWidth = categories.length * NODE_WIDTH + (categories.length - 1) * CATEGORY_SPACING
      // First category left edge X
      let categoryX = START_X - totalWidth / 2

      // Category Y position (below topic)
      const categoryY = START_Y + NODE_HEIGHT + TOPIC_TO_CATEGORY_GAP

      categories.forEach((category, catIndex) => {
        const categoryId = category.id || `tree-cat-${catIndex}`
        // Calculate center X for this category (used for edge connections)
        const categoryCenterX = categoryX + NODE_WIDTH / 2

        // Category node - position.x is the LEFT edge
        nodes.push({
          id: categoryId,
          text: category.text,
          type: 'branch',
          position: { x: categoryX, y: categoryY },
        })

        // Connection from topic to category (T-shape step edge)
        connections.push({
          id: `edge-${rootId}-${categoryId}`,
          source: rootId,
          target: categoryId,
          edgeType: 'step', // T-shape for topic to categories
          sourcePosition: 'bottom',
          targetPosition: 'top',
        })

        // Leaves (depth 2+) - stacked vertically below category
        const leaves = category.children || []
        if (leaves.length > 0) {
          let leafY = categoryY + NODE_HEIGHT + CATEGORY_TO_LEAF_GAP

          leaves.forEach((leaf, leafIndex) => {
            const leafId = leaf.id || `tree-leaf-${catIndex}-${leafIndex}`

            // Leaf node - same X as category for vertical alignment
            nodes.push({
              id: leafId,
              text: leaf.text,
              type: 'branch',
              position: { x: categoryX, y: leafY },
            })

            // Connection from category/previous leaf to this leaf (straight vertical)
            const sourceId =
              leafIndex === 0
                ? categoryId
                : leaves[leafIndex - 1].id || `tree-leaf-${catIndex}-${leafIndex - 1}`
            connections.push({
              id: `edge-${sourceId}-${leafId}`,
              source: sourceId,
              target: leafId,
              edgeType: 'tree', // Straight vertical line
              sourcePosition: 'bottom',
              targetPosition: 'top',
            })

            leafY += NODE_HEIGHT + LEAF_SPACING
          })
        }

        categoryX += NODE_WIDTH + CATEGORY_SPACING
      })
    }
  }

  // Add dimension label node if dimension field exists
  if (dimension !== undefined) {
    nodes.push({
      id: 'dimension-label',
      text: dimension || '',
      type: 'label',
      position: { x: START_X - 100, y: START_Y + NODE_HEIGHT + 20 }, // Below topic
    })
  }

  return {
    nodes,
    connections,
    metadata: {
      dimension,
      alternativeDimensions,
    },
  }
}

// ============================================================================
// Flow Map
// ============================================================================
export function loadFlowMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const steps = (spec.steps as Array<{ id?: string; text: string }>) || []
  const orientation = (spec.orientation as 'horizontal' | 'vertical') || 'horizontal'

  const startX = 100
  const startY = 100
  const centerX = 400
  const centerY = 300
  const stepSpacing = 200
  const nodeWidth = 140
  const nodeHeight = 60

  const isVertical = orientation === 'vertical'

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  steps.forEach((step, index) => {
    const id = step.id || `flow-step-${index}`

    let x: number
    let y: number

    if (isVertical) {
      // Vertical layout: nodes stacked top-to-bottom
      x = centerX - nodeWidth / 2
      y = startY + index * stepSpacing
    } else {
      // Horizontal layout: nodes arranged left-to-right
      x = startX + index * stepSpacing - nodeWidth / 2
      y = centerY - nodeHeight / 2
    }

    nodes.push({
      id,
      text: step.text,
      type: 'flow',
      position: { x, y },
    })

    if (index > 0) {
      const prevId = steps[index - 1].id || `flow-step-${index - 1}`
      connections.push({ id: `edge-${prevId}-${id}`, source: prevId, target: id })
    }
  })

  return {
    nodes,
    connections,
    metadata: { orientation },
  }
}

// ============================================================================
// Multi-Flow Map
// ============================================================================
export function loadMultiFlowMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const event = (spec.event as string) || ''
  const causes = (spec.causes as string[]) || []
  const effects = (spec.effects as string[]) || []

  const centerX = 400
  const centerY = 300
  const sideSpacing = 200
  const verticalSpacing = 70
  const nodeWidth = 120
  const nodeHeight = 50

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Event node
  nodes.push({
    id: 'event',
    text: event,
    type: 'topic',
    position: { x: centerX - nodeWidth / 2, y: centerY - nodeHeight / 2 },
  })

  // Causes
  const causeStartY = centerY - ((causes.length - 1) * verticalSpacing) / 2
  causes.forEach((cause, index) => {
    nodes.push({
      id: `cause-${index}`,
      text: cause,
      type: 'flow',
      position: {
        x: centerX - sideSpacing - nodeWidth / 2,
        y: causeStartY + index * verticalSpacing - nodeHeight / 2,
      },
    })
    connections.push({ id: `edge-cause-${index}`, source: `cause-${index}`, target: 'event' })
  })

  // Effects
  const effectStartY = centerY - ((effects.length - 1) * verticalSpacing) / 2
  effects.forEach((effect, index) => {
    nodes.push({
      id: `effect-${index}`,
      text: effect,
      type: 'flow',
      position: {
        x: centerX + sideSpacing - nodeWidth / 2,
        y: effectStartY + index * verticalSpacing - nodeHeight / 2,
      },
    })
    connections.push({ id: `edge-effect-${index}`, source: 'event', target: `effect-${index}` })
  })

  return { nodes, connections }
}

// ============================================================================
// Brace Map
// ============================================================================
interface BraceNode {
  id?: string
  text: string
  parts?: BraceNode[]
}

function layoutBraceNode(
  node: BraceNode,
  x: number,
  centerY: number,
  depth: number,
  parentId: string | null,
  nodes: DiagramNode[],
  connections: Connection[],
  levelWidth: number,
  nodeSpacing: number,
  nodeHeight: number
): { topY: number; bottomY: number } {
  const nodeId = node.id || `brace-${depth}-${nodes.length}`

  function calcHeight(n: BraceNode): number {
    if (!n.parts || n.parts.length === 0) return nodeHeight
    return n.parts.reduce((sum, p) => sum + calcHeight(p) + nodeSpacing, -nodeSpacing)
  }

  nodes.push({
    id: nodeId,
    text: node.text,
    type: depth === 0 ? 'topic' : 'brace',
    position: { x, y: centerY - nodeHeight / 2 },
  })

  if (parentId) {
    connections.push({ id: `edge-${parentId}-${nodeId}`, source: parentId, target: nodeId })
  }

  let topY = centerY - nodeHeight / 2
  let bottomY = centerY + nodeHeight / 2

  if (node.parts && node.parts.length > 0) {
    const heights = node.parts.map(calcHeight)
    const totalH = heights.reduce((s, h) => s + h, 0) + (node.parts.length - 1) * nodeSpacing
    let partY = centerY - totalH / 2

    node.parts.forEach((part, i) => {
      const partCenterY = partY + heights[i] / 2
      const result = layoutBraceNode(
        part,
        x + levelWidth,
        partCenterY,
        depth + 1,
        nodeId,
        nodes,
        connections,
        levelWidth,
        nodeSpacing,
        nodeHeight
      )
      topY = Math.min(topY, result.topY)
      bottomY = Math.max(bottomY, result.bottomY)
      partY += heights[i] + nodeSpacing
    })
  }

  return { topY, bottomY }
}

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
    const parts = spec.parts as Array<{ name: string; subparts?: Array<{ name: string }> }> | undefined
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
    layoutBraceNode(wholeNode, 100, 300, 0, null, nodes, connections, 200, 60, 50)
  }

  // Add dimension label if exists
  const dimension = spec.dimension as string | undefined
  if (dimension !== undefined) {
    nodes.push({
      id: 'dimension-label',
      text: dimension || '',
      type: 'label',
      position: { x: 100, y: 360 }, // Below whole
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

// ============================================================================
// Bridge Map
// ============================================================================
export function loadBridgeMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const pairs =
    (spec.pairs as Array<{ top: string; bottom: string; relation?: string }>) ||
    (spec.analogies as Array<{ top: string; bottom: string; relation?: string }>) ||
    []

  const startX = 150
  const centerY = 300
  const pairSpacing = 250
  const verticalGap = 100
  const nodeWidth = 120
  const nodeHeight = 45

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  pairs.forEach((pair, index) => {
    const x = startX + index * pairSpacing

    // Top node
    nodes.push({
      id: `pair-${index}-top`,
      text: pair.top,
      type: 'branch',
      position: { x: x - nodeWidth / 2, y: centerY - verticalGap / 2 - nodeHeight },
    })

    // Bottom node
    nodes.push({
      id: `pair-${index}-bottom`,
      text: pair.bottom,
      type: 'branch',
      position: { x: x - nodeWidth / 2, y: centerY + verticalGap / 2 },
    })

    // Vertical relation
    connections.push({
      id: `relation-${index}`,
      source: `pair-${index}-top`,
      target: `pair-${index}-bottom`,
      label: pair.relation || 'is to',
    })

    // Bridges to next pair
    if (index < pairs.length - 1) {
      connections.push({
        id: `bridge-top-${index}`,
        source: `pair-${index}-top`,
        target: `pair-${index + 1}-top`,
        label: 'as',
      })
      connections.push({
        id: `bridge-bottom-${index}`,
        source: `pair-${index}-bottom`,
        target: `pair-${index + 1}-bottom`,
      })
    }
  })

  return { nodes, connections }
}

// ============================================================================
// Mind Map
// ============================================================================
interface MindMapBranch {
  text: string
  children?: MindMapBranch[]
}

function layoutMindMapBranches(
  branches: MindMapBranch[],
  centerX: number,
  centerY: number,
  direction: 1 | -1,
  depth: number,
  horizontalSpacing: number,
  verticalSpacing: number,
  nodes: DiagramNode[],
  connections: Connection[],
  parentId: string
): void {
  const totalHeight = (branches.length - 1) * verticalSpacing
  let currentY = centerY - totalHeight / 2

  branches.forEach((branch, index) => {
    const nodeId = `branch-${direction > 0 ? 'r' : 'l'}-${depth}-${index}`
    const x = centerX + direction * horizontalSpacing * depth
    const y = currentY

    nodes.push({
      id: nodeId,
      text: branch.text,
      type: 'branch',
      position: { x: x - 60, y: y - 18 },
    })

    connections.push({ id: `edge-${parentId}-${nodeId}`, source: parentId, target: nodeId })

    if (branch.children && branch.children.length > 0) {
      layoutMindMapBranches(
        branch.children,
        x,
        y,
        direction,
        depth + 1,
        horizontalSpacing,
        verticalSpacing,
        nodes,
        connections,
        nodeId
      )
    }

    currentY += verticalSpacing
  })
}

export function loadMindMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const topic = (spec.topic as string) || (spec.central_topic as string) || ''

  // Handle multiple formats for branches
  let leftBranches: MindMapBranch[] = []
  let rightBranches: MindMapBranch[] = []

  if (spec.leftBranches || spec.left) {
    // New format with explicit left/right branches
    leftBranches = (spec.leftBranches as MindMapBranch[]) || (spec.left as MindMapBranch[]) || []
    rightBranches =
      (spec.rightBranches as MindMapBranch[]) || (spec.right as MindMapBranch[]) || []
  } else if (Array.isArray(spec.children)) {
    // Old format: single children array, split into left and right
    const children = spec.children as MindMapBranch[]
    const half = Math.ceil(children.length / 2)
    leftBranches = children.slice(0, half)
    rightBranches = children.slice(half)
  }

  const centerX = 400
  const centerY = 300
  const horizontalSpacing = 180
  const verticalSpacing = 60

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Topic node
  nodes.push({
    id: 'topic',
    text: topic,
    type: 'topic',
    position: { x: centerX - 80, y: centerY - 30 },
  })

  // Left branches
  layoutMindMapBranches(
    leftBranches,
    centerX,
    centerY,
    -1,
    1,
    horizontalSpacing,
    verticalSpacing,
    nodes,
    connections,
    'topic'
  )

  // Right branches
  layoutMindMapBranches(
    rightBranches,
    centerX,
    centerY,
    1,
    1,
    horizontalSpacing,
    verticalSpacing,
    nodes,
    connections,
    'topic'
  )

  return { nodes, connections }
}

// ============================================================================
// Generic Fallback
// ============================================================================
export function loadGenericSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  if (Array.isArray(spec.nodes)) {
    nodes.push(...(spec.nodes as DiagramNode[]))
  }
  if (Array.isArray(spec.connections)) {
    connections.push(...(spec.connections as Connection[]))
  }

  return { nodes, connections }
}

// ============================================================================
// Main Loader
// ============================================================================
const SPEC_LOADERS: Partial<
  Record<DiagramType, (spec: Record<string, unknown>) => SpecLoaderResult>
> = {
  circle_map: loadCircleMapSpec,
  bubble_map: loadBubbleMapSpec,
  double_bubble_map: loadDoubleBubbleMapSpec,
  tree_map: loadTreeMapSpec,
  flow_map: loadFlowMapSpec,
  multi_flow_map: loadMultiFlowMapSpec,
  brace_map: loadBraceMapSpec,
  bridge_map: loadBridgeMapSpec,
  // concept_map: handled by teammate
  mindmap: loadMindMapSpec,
  mind_map: loadMindMapSpec,
}

/**
 * Load diagram data from API spec
 * @param spec - The API spec object
 * @param diagramType - The type of diagram
 * @returns SpecLoaderResult with nodes, connections, and optional metadata
 * 
 * Note: Saved diagrams use a generic format with { nodes, connections },
 * while LLM-generated specs use type-specific formats (e.g., { topic, attributes }).
 * We detect saved diagrams by checking for the 'nodes' array and use loadGenericSpec.
 */
export function loadSpecForDiagramType(
  spec: Record<string, unknown>,
  diagramType: DiagramType
): SpecLoaderResult {
  // Check if this is a saved diagram (has nodes array)
  // Saved diagrams use generic format: { nodes: [...], connections: [...] }
  // LLM-generated specs use type-specific format: { topic, attributes, ... }
  if (Array.isArray(spec.nodes) && spec.nodes.length > 0) {
    return loadGenericSpec(spec)
  }

  // Use type-specific loader for LLM-generated specs
  const loader = SPEC_LOADERS[diagramType]
  if (loader) {
    return loader(spec)
  }
  return loadGenericSpec(spec)
}

// ============================================================================
// Default Templates
// Static templates with placeholder text for each diagram type
// Used when user clicks "新建" to create a blank canvas
// ============================================================================

// Default templates matching the old JS diagram-selector.js templates
const DEFAULT_TEMPLATES: Record<string, Record<string, unknown>> = {
  circle_map: {
    topic: '主题',
    context: ['联想1', '联想2', '联想3', '联想4', '联想5', '联想6', '联想7', '联想8'],
  },
  bubble_map: {
    topic: '主题',
    attributes: ['属性1', '属性2', '属性3', '属性4', '属性5'],
  },
  double_bubble_map: {
    left: '主题A',
    right: '主题B',
    similarities: ['相似点1', '相似点2'],
    left_differences: ['不同点A1', '不同点A2'],
    right_differences: ['不同点B1', '不同点B2'],
  },
  tree_map: {
    topic: '根主题',
    children: [
      {
        text: '类别1',
        children: [
          { text: '项目1.1', children: [] },
          { text: '项目1.2', children: [] },
          { text: '项目1.3', children: [] },
        ],
      },
      {
        text: '类别2',
        children: [
          { text: '项目2.1', children: [] },
          { text: '项目2.2', children: [] },
          { text: '项目2.3', children: [] },
        ],
      },
      {
        text: '类别3',
        children: [
          { text: '项目3.1', children: [] },
          { text: '项目3.2', children: [] },
          { text: '项目3.3', children: [] },
        ],
      },
      {
        text: '类别4',
        children: [
          { text: '项目4.1', children: [] },
          { text: '项目4.2', children: [] },
          { text: '项目4.3', children: [] },
        ],
      },
    ],
  },
  brace_map: {
    whole: '主题',
    dimension: '',
    parts: [
      { name: '部分1', subparts: [{ name: '子部分1.1' }, { name: '子部分1.2' }] },
      { name: '部分2', subparts: [{ name: '子部分2.1' }, { name: '子部分2.2' }] },
      { name: '部分3', subparts: [{ name: '子部分3.1' }, { name: '子部分3.2' }] },
    ],
  },
  flow_map: {
    title: '事件流程',
    steps: ['步骤1', '步骤2', '步骤3', '步骤4'],
    substeps: [
      { step: '步骤1', substeps: ['子步骤1.1', '子步骤1.2'] },
      { step: '步骤2', substeps: ['子步骤2.1', '子步骤2.2'] },
      { step: '步骤3', substeps: ['子步骤3.1', '子步骤3.2'] },
      { step: '步骤4', substeps: ['子步骤4.1', '子步骤4.2'] },
    ],
  },
  multi_flow_map: {
    event: '事件',
    causes: ['原因1', '原因2'],
    effects: ['结果1', '结果2'],
  },
  bridge_map: {
    relating_factor: '如同',
    dimension: '',
    analogies: [
      { left: '事物A1', right: '事物B1' },
      { left: '事物A2', right: '事物B2' },
      { left: '事物A3', right: '事物B3' },
    ],
  },
  mindmap: {
    topic: '中心主题',
    children: [
      {
        id: 'branch_0',
        label: '分支1',
        text: '分支1',
        children: [
          { id: 'sub_0_0', label: '子项1.1', text: '子项1.1', children: [] },
          { id: 'sub_0_1', label: '子项1.2', text: '子项1.2', children: [] },
        ],
      },
      {
        id: 'branch_1',
        label: '分支2',
        text: '分支2',
        children: [
          { id: 'sub_1_0', label: '子项2.1', text: '子项2.1', children: [] },
          { id: 'sub_1_1', label: '子项2.2', text: '子项2.2', children: [] },
        ],
      },
      {
        id: 'branch_2',
        label: '分支3',
        text: '分支3',
        children: [
          { id: 'sub_2_0', label: '子项3.1', text: '子项3.1', children: [] },
          { id: 'sub_2_1', label: '子项3.2', text: '子项3.2', children: [] },
        ],
      },
      {
        id: 'branch_3',
        label: '分支4',
        text: '分支4',
        children: [
          { id: 'sub_3_0', label: '子项4.1', text: '子项4.1', children: [] },
          { id: 'sub_3_1', label: '子项4.2', text: '子项4.2', children: [] },
        ],
      },
    ],
  },
  concept_map: {
    topic: '主要概念',
    concepts: ['概念1', '概念2', '概念3'],
    relationships: [
      { from: '主要概念', to: '概念1', label: '关联' },
      { from: '主要概念', to: '概念2', label: '包含' },
      { from: '概念1', to: '概念3', label: '导致' },
    ],
  },
}

/**
 * Get default template spec for a diagram type
 * Returns a static template with placeholder text
 */
export function getDefaultTemplate(diagramType: DiagramType): Record<string, unknown> | null {
  return DEFAULT_TEMPLATES[diagramType] || null
}
