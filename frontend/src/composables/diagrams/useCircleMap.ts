/**
 * useCircleMap - Composable for Circle Map layout and data management
 * Fixed font; circles from text; topic and context noWrap.
 */
import { computed, ref } from 'vue'

import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'
import { calculateCircleMapLayout } from '@/stores/specLoader/utils'
import { CONTEXT_FONT_SIZE, TOPIC_FONT_SIZE } from '@/stores/specLoader/textMeasurement'

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

export function useCircleMap(_options: CircleMapOptions = {}) {
  const data = ref<CircleMapData | null>(null)

  const layout = computed<CircleMapLayout>(() => {
    const nodeCount = data.value?.context.length || 0
    const topic = data.value?.topic ?? ''
    const context = data.value?.context ?? []
    const l = calculateCircleMapLayout(nodeCount, context, topic)
    return {
      ...l,
      innerRadius: l.topicR + l.uniformContextR + 5,
      outerRadius: l.outerCircleR - l.uniformContextR - 5,
    }
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

    const uniformContextDiameter = l.uniformContextR * 2
    const topicSize = l.topicR * 2

    result.push({
      id: 'topic',
      type: 'circle',
      position: { x: l.centerX - l.topicR, y: l.centerY - l.topicR },
      data: {
        label: data.value.topic,
        nodeType: 'topic',
        diagramType: 'circle_map',
        isDraggable: false,
        isSelectable: true,
        style: { size: topicSize, fontSize: TOPIC_FONT_SIZE, noWrap: true },
      },
      draggable: false,
    })

    let nodesWithCustomPositions = 0
    for (let i = 0; i < nodeCount; i++) {
      if (customPositions[`context-${i}`]) nodesWithCustomPositions++
    }
    const hasNewWithoutPositions =
      Object.keys(customPositions).length > 0 && nodesWithCustomPositions < nodeCount
    const useAutoLayout = hasNewWithoutPositions

    data.value.context.forEach((ctx, index) => {
      const nodeId = `context-${index}`
      const contextRadius = l.uniformContextR
      let x: number
      let y: number

      if (customPositions[nodeId] && !useAutoLayout) {
        x = customPositions[nodeId].x
        y = customPositions[nodeId].y
      } else {
        const angleDeg = (index * 360) / nodeCount - 90
        const angleRad = (angleDeg * Math.PI) / 180
        x = Math.round(l.centerX + l.childrenRadius * Math.cos(angleRad) - contextRadius)
        y = Math.round(l.centerY + l.childrenRadius * Math.sin(angleRad) - contextRadius)
      }

      result.push({
        id: nodeId,
        type: 'circle',
        position: { x, y },
        data: {
          label: ctx,
          nodeType: 'circle',
          diagramType: 'circle_map',
          isDraggable: true,
          isSelectable: true,
          style: {
            size: uniformContextDiameter,
            fontSize: CONTEXT_FONT_SIZE,
            noWrap: true,
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
