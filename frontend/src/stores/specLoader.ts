/**
 * Spec Loader - Converts API spec format to DiagramData
 * Each diagram type has its own converter function
 *
 * This separates the spec-to-data conversion logic from the store,
 * making it easier to maintain and test each diagram type independently.
 */
import {
  DEFAULT_BUBBLE_RADIUS,
  DEFAULT_CATEGORY_SPACING,
  DEFAULT_CATEGORY_TO_LEAF_GAP,
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_COLUMN_SPACING,
  DEFAULT_CONTEXT_RADIUS,
  DEFAULT_DIFF_RADIUS,
  DEFAULT_HORIZONTAL_SPACING,
  DEFAULT_LEAF_SPACING,
  DEFAULT_LEVEL_HEIGHT,
  DEFAULT_LEVEL_WIDTH,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  DEFAULT_PAIR_SPACING,
  DEFAULT_SIDE_SPACING,
  DEFAULT_STEP_SPACING,
  DEFAULT_TOPIC_RADIUS,
  DEFAULT_TOPIC_TO_CATEGORY_GAP,
  DEFAULT_VERTICAL_SPACING,
  FLOW_GROUP_GAP,
  FLOW_MIN_STEP_SPACING,
  FLOW_NODE_HEIGHT,
  FLOW_NODE_WIDTH,
  FLOW_SUBSTEP_NODE_HEIGHT,
  FLOW_SUBSTEP_NODE_WIDTH,
  FLOW_SUBSTEP_OFFSET_X,
  FLOW_SUBSTEP_SPACING,
} from '@/composables/diagrams/layoutConfig'
import { calculateDagreLayout } from '@/composables/diagrams/useDagreLayout'
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
  // Node size constants from layoutConfig
  const uniformContextR = DEFAULT_CONTEXT_RADIUS
  const topicR = DEFAULT_TOPIC_RADIUS
  const padding = DEFAULT_PADDING

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
  const contextNodes = nodes.filter((n) => n.type === 'bubble' && n.id.startsWith('context-'))
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

  // Node size constants from layoutConfig
  const uniformContextR = DEFAULT_CONTEXT_RADIUS
  const topicR = DEFAULT_TOPIC_RADIUS
  const padding = DEFAULT_PADDING

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

  // Layout constants from layoutConfig
  const uniformAttributeR = DEFAULT_BUBBLE_RADIUS
  const topicR = DEFAULT_TOPIC_RADIUS
  const padding = DEFAULT_PADDING

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

  // Layout constants from layoutConfig
  const padding = DEFAULT_PADDING
  const topicR = DEFAULT_TOPIC_RADIUS
  const simR = DEFAULT_BUBBLE_RADIUS
  const diffR = DEFAULT_DIFF_RADIUS
  const columnSpacing = DEFAULT_COLUMN_SPACING

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

  // Layout constants from layoutConfig
  const NODE_WIDTH = DEFAULT_NODE_WIDTH
  const NODE_HEIGHT = DEFAULT_NODE_HEIGHT

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
    const categories = root.children || []

    // Build node list for Dagre layout
    interface DagreNode {
      id: string
      width: number
      height: number
    }
    interface DagreEdge {
      source: string
      target: string
    }

    const dagreNodes: DagreNode[] = []
    const dagreEdges: DagreEdge[] = []

    // Add topic node
    dagreNodes.push({ id: rootId, width: NODE_WIDTH, height: NODE_HEIGHT })

    // Add category and leaf nodes
    categories.forEach((category, catIndex) => {
      const categoryId = category.id || `tree-cat-${catIndex}`
      dagreNodes.push({ id: categoryId, width: NODE_WIDTH, height: NODE_HEIGHT })
      dagreEdges.push({ source: rootId, target: categoryId })

      // Add leaf nodes
      const leaves = category.children || []
      leaves.forEach((leaf, leafIndex) => {
        const leafId = leaf.id || `tree-leaf-${catIndex}-${leafIndex}`
        dagreNodes.push({ id: leafId, width: NODE_WIDTH, height: NODE_HEIGHT })

        // Connect leaf to category (first leaf) or previous leaf (chained)
        const sourceId =
          leafIndex === 0
            ? categoryId
            : leaves[leafIndex - 1].id || `tree-leaf-${catIndex}-${leafIndex - 1}`
        dagreEdges.push({ source: sourceId, target: leafId })
      })
    })

    // Calculate layout using Dagre (top-to-bottom direction)
    const layoutResult = calculateDagreLayout(dagreNodes, dagreEdges, {
      direction: 'TB',
      nodeSeparation: DEFAULT_CATEGORY_SPACING,
      rankSeparation: DEFAULT_TOPIC_TO_CATEGORY_GAP,
      align: 'UL',
      marginX: DEFAULT_PADDING,
      marginY: DEFAULT_PADDING,
    })

    // Create topic node with Dagre position
    const topicPos = layoutResult.positions.get(rootId)
    nodes.push({
      id: rootId,
      text: root.text,
      type: 'topic',
      position: topicPos ? { x: topicPos.x, y: topicPos.y } : { x: DEFAULT_CENTER_X - NODE_WIDTH / 2, y: 60 },
    })

    // Create category and leaf nodes with Dagre positions
    categories.forEach((category, catIndex) => {
      const categoryId = category.id || `tree-cat-${catIndex}`
      const categoryPos = layoutResult.positions.get(categoryId)

      nodes.push({
        id: categoryId,
        text: category.text,
        type: 'branch',
        position: categoryPos ? { x: categoryPos.x, y: categoryPos.y } : { x: 0, y: 0 },
      })

      // Connection from topic to category (T-shape step edge)
      connections.push({
        id: `edge-${rootId}-${categoryId}`,
        source: rootId,
        target: categoryId,
        edgeType: 'step',
        sourcePosition: 'bottom',
        targetPosition: 'top',
      })

      // Add leaf nodes
      const leaves = category.children || []
      leaves.forEach((leaf, leafIndex) => {
        const leafId = leaf.id || `tree-leaf-${catIndex}-${leafIndex}`
        const leafPos = layoutResult.positions.get(leafId)

        nodes.push({
          id: leafId,
          text: leaf.text,
          type: 'branch',
          position: leafPos ? { x: leafPos.x, y: leafPos.y } : { x: 0, y: 0 },
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
          edgeType: 'tree',
          sourcePosition: 'bottom',
          targetPosition: 'top',
        })
      })
    })

    // Add dimension label node if dimension field exists
    // Position it below the topic node
    if (dimension !== undefined) {
      const topicPosition = layoutResult.positions.get(rootId)
      const labelY = topicPosition ? topicPosition.y + NODE_HEIGHT + 20 : 60 + NODE_HEIGHT + 20
      const labelX = topicPosition ? topicPosition.x : DEFAULT_CENTER_X - NODE_WIDTH / 2
      nodes.push({
        id: 'dimension-label',
        text: dimension || '',
        type: 'label',
        position: { x: labelX, y: labelY },
      })
    }
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
// Flow Map (Using Dagre for substep layout, fixed X for step alignment)
// ============================================================================

interface FlowSubstepEntry {
  step: string
  substeps: string[]
}

export function loadFlowMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  // Steps can be strings or objects with text property
  const rawSteps = (spec.steps as Array<string | { id?: string; text: string }>) || []
  const orientation = (spec.orientation as 'horizontal' | 'vertical') || 'horizontal'
  const substepsData = (spec.substeps as FlowSubstepEntry[]) || []

  // Normalize steps to objects with text
  const steps = rawSteps.map((step, index) => {
    if (typeof step === 'string') {
      return { id: `flow-step-${index}`, text: step }
    }
    return { id: step.id || `flow-step-${index}`, text: step.text }
  })

  // Build substeps mapping: stepText -> substeps array
  const stepToSubsteps: Record<string, string[]> = {}
  substepsData.forEach((entry) => {
    if (entry && entry.step && Array.isArray(entry.substeps)) {
      stepToSubsteps[entry.step] = entry.substeps
    }
  })

  const isVertical = orientation === 'vertical'
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Substep node dimensions (from layout config for consistency)
  const substepWidth = FLOW_SUBSTEP_NODE_WIDTH
  const substepHeight = FLOW_SUBSTEP_NODE_HEIGHT

  if (isVertical) {
    // =========================================================================
    // VERTICAL LAYOUT: Steps stacked vertically (same X), substeps to the right
    // Use dagre for each substep group to get proper vertical distribution
    // =========================================================================
    const stepX = DEFAULT_CENTER_X - FLOW_NODE_WIDTH / 2 // All steps at same X
    const substepX = DEFAULT_CENTER_X + FLOW_NODE_WIDTH / 2 + FLOW_SUBSTEP_OFFSET_X

    // For each step, calculate substep positions using dagre
    interface SubstepGroup {
      stepId: string
      stepText: string
      substepIds: string[]
      substepTexts: string[]
      groupHeight: number
      substepPositions: { id: string; y: number }[]
    }

    const substepGroups: SubstepGroup[] = []

    steps.forEach((step, stepIndex) => {
      const stepId = step.id
      const substeps = stepToSubsteps[step.text] || []

      if (substeps.length > 0) {
        // Calculate substep positions manually (simple vertical stack)
        // This is more predictable than dagre for a simple stack
        const positions: { id: string; y: number }[] = []

        substeps.forEach((_, i) => {
          const substepId = `flow-substep-${stepIndex}-${i}`
          // Each substep is positioned with FLOW_SUBSTEP_SPACING between them
          const y = i * (substepHeight + FLOW_SUBSTEP_SPACING)
          positions.push({ id: substepId, y })
        })

        // Group height = all substeps + spacing between them
        const groupHeight =
          substeps.length * substepHeight + (substeps.length - 1) * FLOW_SUBSTEP_SPACING

        substepGroups.push({
          stepId,
          stepText: step.text,
          substepIds: positions.map((p) => p.id),
          substepTexts: substeps,
          groupHeight,
          substepPositions: positions,
        })
      } else {
        // No substeps
        substepGroups.push({
          stepId,
          stepText: step.text,
          substepIds: [],
          substepTexts: [],
          groupHeight: FLOW_NODE_HEIGHT,
          substepPositions: [],
        })
      }
    })

    // =========================================================================
    // Position steps vertically, centered on their substep groups
    // =========================================================================
    let currentY = DEFAULT_PADDING + 40

    substepGroups.forEach((group, groupIndex) => {
      const hasSubsteps = group.substepIds.length > 0

      if (hasSubsteps) {
        // Step Y is centered on substep group
        const groupCenterY = currentY + group.groupHeight / 2
        const stepY = groupCenterY - FLOW_NODE_HEIGHT / 2

        // Create step node
        nodes.push({
          id: group.stepId,
          text: group.stepText,
          type: 'flow',
          position: { x: stepX, y: stepY },
        })

        // Create substep nodes (center-aligned in a straight vertical line at substepX)
        // All substeps share the same X coordinate for consistent alignment
        group.substepPositions.forEach((pos, i) => {
          nodes.push({
            id: pos.id,
            text: group.substepTexts[i],
            type: 'flowSubstep',
            position: { x: substepX, y: currentY + pos.y },
          })
        })

        currentY += group.groupHeight + FLOW_GROUP_GAP + FLOW_MIN_STEP_SPACING
      } else {
        // No substeps - just place step
        nodes.push({
          id: group.stepId,
          text: group.stepText,
          type: 'flow',
          position: { x: stepX, y: currentY },
        })

        currentY += FLOW_NODE_HEIGHT + FLOW_MIN_STEP_SPACING
      }

      // Create edge to previous step (vertical: bottom-to-top flow)
      if (groupIndex > 0) {
        const prevId = substepGroups[groupIndex - 1].stepId
        connections.push({
          id: `edge-${prevId}-${group.stepId}`,
          source: prevId,
          target: group.stepId,
          sourcePosition: 'bottom',
          targetPosition: 'top',
          sourceHandle: 'bottom',
          targetHandle: 'top',
          edgeType: 'straight',
        })
      }

      // Create edges to substeps
      group.substepIds.forEach((substepId) => {
        connections.push({
          id: `edge-${group.stepId}-${substepId}`,
          source: group.stepId,
          target: substepId,
          sourcePosition: 'right',
          targetPosition: 'left',
          sourceHandle: 'substep-source',
          edgeType: 'horizontalStep',
        })
      })
    })
  } else {
    // =========================================================================
    // HORIZONTAL LAYOUT: Steps left-to-right (same Y), substeps below
    // =========================================================================
    const stepY = DEFAULT_CENTER_Y - FLOW_NODE_HEIGHT / 2

    steps.forEach((step, stepIndex) => {
      const stepId = step.id
      const substeps = stepToSubsteps[step.text] || []
      const stepX = DEFAULT_PADDING + stepIndex * DEFAULT_STEP_SPACING

      // Create step node
      nodes.push({
        id: stepId,
        text: step.text,
        type: 'flow',
        position: { x: stepX, y: stepY },
      })

      // Create edge to previous step (horizontal: right-to-left flow)
      if (stepIndex > 0) {
        const prevId = steps[stepIndex - 1].id
        connections.push({
          id: `edge-${prevId}-${stepId}`,
          source: prevId,
          target: stepId,
          sourcePosition: 'right',
          targetPosition: 'left',
          sourceHandle: 'right',
          targetHandle: 'left',
          edgeType: 'straight',
        })
      }

      // Create substep nodes below (center-aligned under the step, in a straight vertical line)
      // All substeps share the same X center as the parent step
      const stepCenterX = stepX + FLOW_NODE_WIDTH / 2
      const substepCenterAlignedX = stepCenterX - substepWidth / 2

      substeps.forEach((substepText, substepIndex) => {
        const substepId = `flow-substep-${stepIndex}-${substepIndex}`
        const substepY =
          stepY + FLOW_NODE_HEIGHT + FLOW_SUBSTEP_OFFSET_X + substepIndex * (substepHeight + FLOW_SUBSTEP_SPACING)

        nodes.push({
          id: substepId,
          text: substepText,
          type: 'flowSubstep',
          position: { x: substepCenterAlignedX, y: substepY },
        })

        connections.push({
          id: `edge-${stepId}-${substepId}`,
          source: stepId,
          target: substepId,
          sourcePosition: 'bottom',
          targetPosition: 'top',
          sourceHandle: 'bottom',
          targetHandle: 'top-target',
          edgeType: 'step',
        })
      })
    })
  }

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

  // Layout constants from layoutConfig
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const sideSpacing = DEFAULT_SIDE_SPACING
  const verticalSpacing = DEFAULT_VERTICAL_SPACING + 10 // 70px
  const nodeWidth = DEFAULT_NODE_WIDTH
  const nodeHeight = DEFAULT_NODE_HEIGHT

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
    flattenBraceTree(wholeNode, 0, null, DEFAULT_NODE_WIDTH, DEFAULT_NODE_HEIGHT, flatData, { value: 0 })

    // Calculate layout using Dagre (left-to-right direction for brace maps)
    const layoutResult = calculateDagreLayout(flatData.dagreNodes, flatData.dagreEdges, {
      direction: 'LR',
      nodeSeparation: DEFAULT_VERTICAL_SPACING,
      rankSeparation: DEFAULT_LEVEL_WIDTH,
      align: 'UL',
      marginX: DEFAULT_PADDING,
      marginY: DEFAULT_PADDING,
    })

    // Create nodes with Dagre positions
    flatData.dagreNodes.forEach((dagreNode) => {
      const info = flatData.nodeInfos.get(dagreNode.id)
      const pos = layoutResult.positions.get(dagreNode.id)

      nodes.push({
        id: dagreNode.id,
        text: info?.text || '',
        type: info?.depth === 0 ? 'topic' : 'brace',
        position: pos ? { x: pos.x, y: pos.y } : { x: 0, y: 0 },
      })
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

// ============================================================================
// Bridge Map
// ============================================================================
export function loadBridgeMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const pairs =
    (spec.pairs as Array<{ top: string; bottom: string; relation?: string }>) ||
    (spec.analogies as Array<{ top: string; bottom: string; relation?: string }>) ||
    []

  // Layout constants from layoutConfig
  const startX = DEFAULT_PADDING + DEFAULT_NODE_WIDTH / 2 + 50
  const centerY = DEFAULT_CENTER_Y
  const pairSpacing = DEFAULT_PAIR_SPACING
  const verticalGap = DEFAULT_LEVEL_HEIGHT
  const nodeWidth = DEFAULT_NODE_WIDTH
  const nodeHeight = DEFAULT_NODE_HEIGHT - 5 // Bridge nodes slightly shorter

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
      flattenMindMapBranches(branch.children, nodeId, direction, depth + 1, dagreNodes, dagreEdges, nodeInfos)
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
  const offsetX = topicX - (virtualPos?.x || 0) + (direction * DEFAULT_NODE_WIDTH / 2)
  const offsetY = topicY - (virtualPos?.y || 0)

  // Create nodes with adjusted positions
  nodeInfos.forEach((info, nodeId) => {
    const pos = layoutResult.positions.get(nodeId)
    if (pos) {
      nodes.push({
        id: nodeId,
        text: info.text,
        type: 'branch',
        position: { x: pos.x + offsetX - DEFAULT_NODE_WIDTH / 2, y: pos.y + offsetY - DEFAULT_NODE_HEIGHT / 2 },
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
