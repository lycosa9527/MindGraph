/**
 * useBubbleMap - Composable for Bubble Map layout and data management
 * Bubble maps describe qualities and attributes around a central topic
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import {
  DEFAULT_BUBBLE_RADIUS,
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_TOPIC_RADIUS,
} from './layoutConfig'

interface BubbleMapData {
  topic: string
  attributes: string[]
}

interface BubbleMapOptions {
  centerX?: number
  centerY?: number
  radius?: number
  topicRadius?: number
  bubbleRadius?: number
}

export function useBubbleMap(options: BubbleMapOptions = {}) {
  const {
    centerX = DEFAULT_CENTER_X,
    centerY = DEFAULT_CENTER_Y,
    radius = 150,
    topicRadius = DEFAULT_TOPIC_RADIUS,
    bubbleRadius = DEFAULT_BUBBLE_RADIUS,
  } = options

  const { t } = useLanguage()
  const data = ref<BubbleMapData | null>(null)

  // Convert bubble map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []

    // Central topic node
    result.push({
      id: 'topic',
      type: 'topic',
      position: { x: centerX - topicRadius, y: centerY - topicRadius / 2 },
      data: {
        label: data.value.topic,
        nodeType: 'topic',
        diagramType: 'bubble_map',
        isDraggable: false,
        isSelectable: true,
      },
      draggable: false,
    })

    // Attribute bubble nodes arranged in a circle
    const attributeCount = data.value.attributes.length
    data.value.attributes.forEach((attr, index) => {
      const angle = (2 * Math.PI * index) / attributeCount - Math.PI / 2
      const x = centerX + radius * Math.cos(angle) - bubbleRadius
      const y = centerY + radius * Math.sin(angle) - bubbleRadius

      result.push({
        id: `bubble-${index}`,
        type: 'bubble',
        position: { x, y },
        data: {
          label: attr,
          nodeType: 'bubble',
          diagramType: 'bubble_map',
          isDraggable: true,
          isSelectable: true,
        },
        draggable: true,
      })
    })

    return result
  })

  // Generate edges from topic to each bubble
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    return data.value.attributes.map((_, index) => ({
      id: `edge-topic-bubble-${index}`,
      source: 'topic',
      target: `bubble-${index}`,
      type: 'curved',
      data: {
        edgeType: 'curved' as const,
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
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addAttribute,
    removeAttribute,
    updateAttribute,
  }
}
