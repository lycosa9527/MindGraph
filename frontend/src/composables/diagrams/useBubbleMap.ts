/**
 * useBubbleMap - Composable for Bubble Map layout and data management
 * Bubble maps describe qualities and attributes around a central topic
 *
 * Layout: first child at 0° (top, above topic); even distribution via polar positions.
 * Uses no-overlap formula (like circle map) for circumferential spacing.
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import {
  DEFAULT_PADDING,
  DEFAULT_TOPIC_RADIUS,
  DEFAULT_CONTEXT_RADIUS,
} from './layoutConfig'
import {
  computeMinDiameterForNoWrap,
  CONTEXT_FONT_SIZE,
} from '@/stores/specLoader/textMeasurement'
import {
  bubbleMapChildrenRadius,
  polarToPosition,
} from './useRadialLayout'

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
 * Calculate bubble map layout based on node count.
 * Ring radius uses no-overlap formula for even circumferential spacing.
 */
function calculateLayout(
  nodeCount: number,
  attributeTexts: string[],
  padding: number = DEFAULT_PADDING
): BubbleMapLayout & { radii: number[] } {
  const topicR = DEFAULT_TOPIC_RADIUS

  const radii =
    attributeTexts.length > 0
      ? attributeTexts.map((t) =>
          Math.max(
            DEFAULT_CONTEXT_RADIUS,
            computeMinDiameterForNoWrap(t || ' ', CONTEXT_FONT_SIZE, false) / 2
          )
        )
      : []
  const uniformRadius =
    radii.length > 0 ? Math.max(DEFAULT_CONTEXT_RADIUS, ...radii) : DEFAULT_CONTEXT_RADIUS

  const childrenRadius = bubbleMapChildrenRadius(
    nodeCount,
    topicR,
    uniformRadius,
    uniformRadius
  )

  const centerX = childrenRadius + uniformRadius + padding
  const centerY = childrenRadius + uniformRadius + padding

  return {
    centerX,
    centerY,
    topicR,
    uniformAttributeR: uniformRadius,
    childrenRadius,
    radii: radii.map(() => uniformRadius),
  }
}

export function useBubbleMap(options: BubbleMapOptions = {}) {
  const { padding = DEFAULT_PADDING } = options

  const { t } = useLanguage()
  const data = ref<BubbleMapData | null>(null)

  // Calculate layout based on current data (text-adaptive)
  const layout = computed(() => {
    const attributes = data.value?.attributes || []
    return calculateLayout(attributes.length, attributes, padding)
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

    // Attribute nodes (circles): uniform size from max text
    const uniformR = l.uniformAttributeR
    data.value.attributes.forEach((attr, index) => {
      const { x, y } = polarToPosition(
        index,
        nodeCount,
        l.centerX,
        l.centerY,
        l.childrenRadius,
        uniformR,
        uniformR
      )

      result.push({
        id: `bubble-${index}`,
        type: 'circle',
        position: { x: Math.round(x), y: Math.round(y) },
        data: {
          label: attr,
          nodeType: 'bubble',
          diagramType: 'bubble_map',
          isDraggable: false,
          isSelectable: true,
          style: {
            size: uniformR * 2,
            fontSize: CONTEXT_FONT_SIZE,
            noWrap: true,
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
