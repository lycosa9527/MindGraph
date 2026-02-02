/**
 * useBubbleMap - Composable for Bubble Map layout and data management
 * Bubble maps describe qualities and attributes around a central topic
 *
 * Layout logic matches the original D3 implementation from bubble-map-renderer.js
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import { DEFAULT_BUBBLE_RADIUS, DEFAULT_PADDING, DEFAULT_TOPIC_RADIUS } from './layoutConfig'

interface BubbleMapData {
  topic: string
  attributes: string[]
}

interface BubbleMapLayout {
  centerX: number
  centerY: number
  topicR: number
  uniformAttributeR: number
  childrenRadius: number
}

interface BubbleMapOptions {
  padding?: number
}

/**
 * Calculate bubble map layout based on node count
 * Uses the same formulas as the original D3 renderer
 */
function calculateLayout(nodeCount: number, padding: number = DEFAULT_PADDING): BubbleMapLayout {
  const uniformAttributeR = DEFAULT_BUBBLE_RADIUS // 40px
  const topicR = DEFAULT_TOPIC_RADIUS // 60px

  // Target distance from center (matching old JS: topicR + uniformAttributeR + 50)
  const targetDistance = topicR + uniformAttributeR + 50

  // Circumferential constraint for many nodes
  // Dynamic spacing multiplier based on node count
  const spacingMultiplier = nodeCount <= 3 ? 2.0 : nodeCount <= 6 ? 2.05 : 2.1
  const circumferentialMinRadius =
    nodeCount > 0 ? (uniformAttributeR * nodeCount * spacingMultiplier) / (2 * Math.PI) : 0

  // Use the larger of both constraints (minimum 100px)
  const childrenRadius = Math.max(targetDistance, circumferentialMinRadius, 100)

  // Dynamic canvas center based on calculated sizes
  const centerX = childrenRadius + uniformAttributeR + padding
  const centerY = childrenRadius + uniformAttributeR + padding

  return {
    centerX,
    centerY,
    topicR,
    uniformAttributeR,
    childrenRadius,
  }
}

export function useBubbleMap(options: BubbleMapOptions = {}) {
  const { padding = DEFAULT_PADDING } = options

  const { t } = useLanguage()
  const data = ref<BubbleMapData | null>(null)

  // Calculate layout based on current data
  const layout = computed<BubbleMapLayout>(() => {
    const nodeCount = data.value?.attributes.length || 0
    return calculateLayout(nodeCount, padding)
  })

  // Convert bubble map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []
    const l = layout.value
    const nodeCount = data.value.attributes.length

    // Central topic node - centered, non-draggable, perfect circle
    result.push({
      id: 'topic',
      type: 'circle', // Use CircleNode for perfect circle rendering
      position: { x: l.centerX - l.topicR, y: l.centerY - l.topicR },
      data: {
        label: data.value.topic,
        nodeType: 'topic', // Keep 'topic' in data for CircleNode styling
        diagramType: 'bubble_map',
        isDraggable: false,
        isSelectable: true,
        style: {
          size: l.topicR * 2, // Diameter for perfect circle
        },
      },
      draggable: false,
    })

    // Attribute bubble nodes arranged in a circle
    // Start from top (-90 degrees) with even angle distribution
    data.value.attributes.forEach((attr, index) => {
      const angleDeg = (index * 360) / nodeCount - 90 // Start from top
      const angleRad = (angleDeg * Math.PI) / 180

      // Position at childrenRadius from center
      const x = l.centerX + l.childrenRadius * Math.cos(angleRad) - l.uniformAttributeR
      const y = l.centerY + l.childrenRadius * Math.sin(angleRad) - l.uniformAttributeR

      result.push({
        id: `bubble-${index}`,
        type: 'circle', // Use CircleNode for perfect circle rendering
        position: { x, y },
        data: {
          label: attr,
          nodeType: 'bubble',
          diagramType: 'bubble_map',
          isDraggable: false,
          isSelectable: true,
          style: {
            size: l.uniformAttributeR * 2, // Diameter for perfect circle
          },
        },
        draggable: false,
      })
    })

    return result
  })

  // Generate edges from topic to each bubble (radial center-to-center lines)
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    return data.value.attributes.map((_, index) => ({
      id: `edge-topic-bubble-${index}`,
      source: 'topic',
      target: `bubble-${index}`,
      type: 'radial',
      data: {
        edgeType: 'radial' as const,
      },
    }))
  })

  // Set bubble map data
  function setData(newData: BubbleMapData) {
    data.value = newData
  }

  // Convert from flat diagram nodes
  function fromDiagramNodes(diagramNodes: DiagramNode[], _connections: Connection[]) {
    const topicNode = diagramNodes.find((n) => n.type === 'topic' || n.type === 'center')
    const bubbleNodes = diagramNodes.filter((n) => n.type === 'bubble' || n.type === 'child')

    if (topicNode) {
      data.value = {
        topic: topicNode.text,
        attributes: bubbleNodes.map((n) => n.text),
      }
    }
  }

  // Add a new attribute bubble
  // If selectedNodeId is provided, validates selection context (matching old JS behavior)
  // If text is not provided, uses default translated text (matching old JS behavior)
  function addAttribute(text?: string, selectedNodeId?: string): boolean {
    if (!data.value) return false

    // Selection-based validation (matching old JS behavior)
    // For bubble maps, you can add attributes without selection, but if selection is provided,
    // ensure it's not the topic node (topic nodes can't have children added directly)
    if (selectedNodeId === 'topic') {
      console.warn('Cannot add attributes to topic node directly')
      return false
    }

    // Use default translated text if not provided (matching old JS behavior)
    const attributeText = text || t('diagram.newAttribute', 'New Attribute')
    data.value.attributes.push(attributeText)
    return true
  }

  // Remove an attribute bubble
  function removeAttribute(index: number) {
    if (data.value && index >= 0 && index < data.value.attributes.length) {
      data.value.attributes.splice(index, 1)
    }
  }

  // Update attribute text
  function updateAttribute(index: number, text: string) {
    if (data.value && index >= 0 && index < data.value.attributes.length) {
      data.value.attributes[index] = text
    }
  }

  return {
    data,
    layout,
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addAttribute,
    removeAttribute,
    updateAttribute,
  }
}
