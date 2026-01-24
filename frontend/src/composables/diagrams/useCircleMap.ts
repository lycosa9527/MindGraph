/**
 * useCircleMap - Composable for Circle Map layout and data management
 * Circle maps define concepts in context with a central topic and context ring
 *
 * Layout logic matches the original D3 implementation from bubble-map-renderer.js
 */
import { computed, ref } from 'vue'

import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'
import { calculateAdaptiveCircleSize } from '@/stores/specLoader/utils'

import { DEFAULT_BUBBLE_RADIUS, DEFAULT_PADDING, DEFAULT_TOPIC_RADIUS } from './layoutConfig'

interface CircleMapData {
  topic: string
  context: string[]
  _customPositions?: Record<string, { x: number; y: number }>
}

interface CircleMapLayout {
  centerX: number
  centerY: number
  topicR: number
  uniformContextR: number
  childrenRadius: number
  outerCircleR: number
  innerRadius: number
  outerRadius: number
}

interface CircleMapOptions {
  padding?: number
}

/**
 * Calculate circle map layout based on node count and context texts
 * Uses adaptive sizing for context nodes based on text length
 * Uses the same formulas as the original D3 renderer, but accounts for variable node sizes
 */
function calculateLayout(
  nodeCount: number,
  padding: number = DEFAULT_PADDING,
  contextTexts: string[] = []
): CircleMapLayout {
  // Node size constants (matching VueFlow node components)
  // TopicNode: min-width 120px, so radius ~60px
  const topicR = DEFAULT_TOPIC_RADIUS // 60px

  // Calculate adaptive sizes for context nodes and find maximum radius
  // Default minimum radius for layout calculations
  const defaultContextR = DEFAULT_BUBBLE_RADIUS - 5 // 35px
  let maxContextR = defaultContextR

  if (contextTexts.length > 0) {
    // Calculate adaptive size for each context node and find maximum radius
    contextTexts.forEach((text) => {
      const adaptiveSize = calculateAdaptiveCircleSize(text, false)
      const adaptiveRadius = adaptiveSize / 2
      maxContextR = Math.max(maxContextR, adaptiveRadius)
    })
  }

  // Use maxContextR for layout calculations to ensure all nodes fit
  const uniformContextR = maxContextR

  // Calculate childrenRadius using both constraints (matching original D3 logic)
  // 1. Radial constraint: minimum distance from center
  const targetRadialDistance = topicR + topicR * 0.5 + uniformContextR + 5

  // 2. Circumferential constraint: spacing around circle
  // Dynamic spacing multiplier based on node count
  const spacingMultiplier = nodeCount <= 3 ? 2.0 : nodeCount <= 6 ? 2.05 : 2.1
  const circumferentialMinRadius =
    nodeCount > 0 ? (uniformContextR * nodeCount * spacingMultiplier) / (2 * Math.PI) : 0

  // Use the larger of both constraints (minimum 100px)
  const childrenRadius = Math.max(targetRadialDistance, circumferentialMinRadius, 100)

  // Outer circle radius for boundary
  const outerCircleR = childrenRadius + uniformContextR + 10

  // Dynamic canvas center based on calculated sizes
  const centerX = outerCircleR + padding
  const centerY = outerCircleR + padding

  // Donut boundary constraints
  const innerRadius = topicR + uniformContextR + 5
  const outerRadius = outerCircleR - uniformContextR - 5

  return {
    centerX,
    centerY,
    topicR,
    uniformContextR,
    childrenRadius,
    outerCircleR,
    innerRadius,
    outerRadius,
  }
}

export function useCircleMap(options: CircleMapOptions = {}) {
  const { padding = 40 } = options

  const data = ref<CircleMapData | null>(null)

  // Calculate layout based on current data
  // Pass context texts to calculate adaptive sizes for layout
  const layout = computed<CircleMapLayout>(() => {
    const nodeCount = data.value?.context.length || 0
    const contextTexts = data.value?.context || []
    return calculateLayout(nodeCount, padding, contextTexts)
  })

  // Convert circle map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []
    const l = layout.value
    const nodeCount = data.value.context.length
    const customPositions = data.value._customPositions || {}

    // Add outer circle boundary node (non-interactive visual element)
    result.push({
      id: 'outer-boundary',
      type: 'boundary',
      position: { x: l.centerX - l.outerCircleR, y: l.centerY - l.outerCircleR },
      data: {
        label: '',
        nodeType: 'boundary',
        diagramType: 'circle_map',
        isDraggable: false,
        isSelectable: false,
        style: {
          width: l.outerCircleR * 2,
          height: l.outerCircleR * 2,
        },
      },
      draggable: false,
      selectable: false,
    })

    // Central topic node - centered, non-draggable, perfect circle with adaptive sizing
    const topicSize = calculateAdaptiveCircleSize(data.value.topic, true)
    const topicRadius = topicSize / 2
    result.push({
      id: 'topic',
      type: 'circle', // Use CircleNode for perfect circle rendering
      position: { x: l.centerX - topicRadius, y: l.centerY - topicRadius },
      data: {
        label: data.value.topic,
        nodeType: 'topic',
        diagramType: 'circle_map',
        isDraggable: false,
        isSelectable: true,
        style: {
          size: topicSize, // Adaptive diameter based on text length
        },
      },
      draggable: false,
    })

    // Check if all nodes have custom positions
    // If new nodes added (some without positions), recalculate all evenly
    let nodesWithCustomPositions = 0
    for (let i = 0; i < nodeCount; i++) {
      const nodeId = `context-${i}`
      if (customPositions[nodeId]) {
        nodesWithCustomPositions++
      }
    }
    const hasNewNodesWithoutPositions =
      Object.keys(customPositions).length > 0 && nodesWithCustomPositions < nodeCount
    const shouldRecalculateEvenly = hasNewNodesWithoutPositions

    // Context nodes positioned around the circle
    // Start from top (-90 degrees) with even angle distribution
    // Context nodes use adaptive size based on text length
    data.value.context.forEach((ctx, index) => {
      const nodeId = `context-${index}`
      
      // Calculate adaptive size for each context node based on text length
      const contextSize = calculateAdaptiveCircleSize(ctx, false)
      const contextRadius = contextSize / 2
      
      let x: number
      let y: number

      if (customPositions[nodeId] && !shouldRecalculateEvenly) {
        // Use custom position (user-dragged position)
        x = customPositions[nodeId].x
        y = customPositions[nodeId].y
      } else {
        // Calculate even angle distribution around the circle
        const angleDeg = (index * 360) / nodeCount - 90 // Start from top
        const angleRad = (angleDeg * Math.PI) / 180

        // Position at childrenRadius from center
        x = l.centerX + l.childrenRadius * Math.cos(angleRad) - contextRadius
        y = l.centerY + l.childrenRadius * Math.sin(angleRad) - contextRadius
      }

      result.push({
        id: nodeId,
        type: 'circle', // Use CircleNode for perfect circle rendering
        position: { x, y },
        data: {
          label: ctx,
          nodeType: 'circle', // circle map context node
          diagramType: 'circle_map',
          isDraggable: true,
          isSelectable: true,
          style: {
            size: contextSize, // Adaptive diameter based on text length
          },
        },
        draggable: true,
      })
    })

    return result
  })

  // Circle maps have NO connection lines (unlike bubble maps)
  // Context nodes float freely within the outer boundary circle
  const edges = computed<MindGraphEdge[]>(() => {
    return [] // No edges for circle maps
  })

  // Set circle map data
  function setData(newData: CircleMapData) {
    data.value = newData
  }

  // Convert from flat diagram nodes
  function fromDiagramNodes(diagramNodes: DiagramNode[], _connections: Connection[]) {
    const topicNode = diagramNodes.find((n) => n.type === 'topic' || n.type === 'center')
    const contextNodes = diagramNodes.filter(
      (n) => n.type === 'child' || n.type === 'bubble' || n.type === 'boundary'
    )

    if (topicNode) {
      data.value = {
        topic: topicNode.text,
        context: contextNodes.filter((n) => n.type !== 'boundary').map((n) => n.text),
      }
    }
  }

  // Add context item - clears custom positions for even redistribution
  function addContext(text: string) {
    if (data.value) {
      data.value.context.push(text)
      // Clear custom positions to trigger even redistribution
      data.value._customPositions = undefined
    }
  }

  // Remove context item - clears custom positions for even redistribution
  function removeContext(index: number) {
    if (data.value && index >= 0 && index < data.value.context.length) {
      data.value.context.splice(index, 1)
      // Clear custom positions to trigger even redistribution
      data.value._customPositions = undefined
    }
  }

  // Save custom position for a node
  function saveCustomPosition(nodeId: string, x: number, y: number) {
    if (data.value) {
      if (!data.value._customPositions) {
        data.value._customPositions = {}
      }
      data.value._customPositions[nodeId] = { x, y }
    }
  }

  // Clear all custom positions (reset to auto-layout)
  function clearCustomPositions() {
    if (data.value) {
      data.value._customPositions = undefined
    }
  }

  // Check if a position is within the donut boundary
  function isWithinBoundary(x: number, y: number): boolean {
    const l = layout.value
    const dx = x + l.uniformContextR - l.centerX
    const dy = y + l.uniformContextR - l.centerY
    const distance = Math.sqrt(dx * dx + dy * dy)

    return distance >= l.innerRadius && distance <= l.outerRadius
  }

  // Constrain a position to be within the donut boundary
  function constrainToBoundary(x: number, y: number): { x: number; y: number } {
    const l = layout.value
    // Calculate center of node
    const nodeCenterX = x + l.uniformContextR
    const nodeCenterY = y + l.uniformContextR

    const dx = nodeCenterX - l.centerX
    const dy = nodeCenterY - l.centerY
    const distance = Math.sqrt(dx * dx + dy * dy)

    if (distance === 0) {
      // Node is at center, push to inner radius
      return {
        x: l.centerX + l.innerRadius - l.uniformContextR,
        y: l.centerY - l.uniformContextR,
      }
    }

    let constrainedDistance = distance

    // Constrain to outer boundary
    if (distance > l.outerRadius) {
      constrainedDistance = l.outerRadius
    }

    // Constrain to inner boundary
    if (distance < l.innerRadius) {
      constrainedDistance = l.innerRadius
    }

    if (constrainedDistance !== distance) {
      const scale = constrainedDistance / distance
      const constrainedCenterX = l.centerX + dx * scale
      const constrainedCenterY = l.centerY + dy * scale
      return {
        x: constrainedCenterX - l.uniformContextR,
        y: constrainedCenterY - l.uniformContextR,
      }
    }

    return { x, y }
  }

  return {
    data,
    layout,
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addContext,
    removeContext,
    saveCustomPosition,
    clearCustomPositions,
    isWithinBoundary,
    constrainToBoundary,
  }
}
