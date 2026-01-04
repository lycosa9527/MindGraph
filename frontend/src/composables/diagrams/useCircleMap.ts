/**
 * useCircleMap - Composable for Circle Map layout and data management
 * Circle maps define concepts in context with a central topic and context ring
 */
import { computed, ref } from 'vue'

import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

interface CircleMapData {
  topic: string
  context: string[]
}

interface CircleMapOptions {
  centerX?: number
  centerY?: number
  innerRadius?: number
  outerRadius?: number
}

export function useCircleMap(options: CircleMapOptions = {}) {
  const { centerX = 400, centerY = 300, innerRadius = 60, outerRadius = 150 } = options

  const data = ref<CircleMapData | null>(null)

  // Convert circle map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []

    // Central topic node
    result.push({
      id: 'topic',
      type: 'topic',
      position: { x: centerX - innerRadius, y: centerY - innerRadius / 2 },
      data: {
        label: data.value.topic,
        nodeType: 'topic',
        diagramType: 'circle_map',
        isDraggable: false,
        isSelectable: true,
      },
      draggable: false,
    })

    // Context nodes arranged in outer circle
    const contextCount = data.value.context.length
    data.value.context.forEach((ctx, index) => {
      const angle = (2 * Math.PI * index) / contextCount - Math.PI / 2
      const x = centerX + outerRadius * Math.cos(angle) - 40
      const y = centerY + outerRadius * Math.sin(angle) - 20

      result.push({
        id: `context-${index}`,
        type: 'bubble',
        position: { x, y },
        data: {
          label: ctx,
          nodeType: 'circle',
          diagramType: 'circle_map',
          isDraggable: true,
          isSelectable: true,
        },
        draggable: true,
      })
    })

    return result
  })

  // Generate edges from topic to each context node
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    return data.value.context.map((_, index) => ({
      id: `edge-topic-context-${index}`,
      source: 'topic',
      target: `context-${index}`,
      type: 'curved',
      data: {
        edgeType: 'curved' as const,
      },
    }))
  })

  // Set circle map data
  function setData(newData: CircleMapData) {
    data.value = newData
  }

  // Convert from flat diagram nodes
  function fromDiagramNodes(diagramNodes: DiagramNode[], _connections: Connection[]) {
    const topicNode = diagramNodes.find((n) => n.type === 'topic' || n.type === 'center')
    const contextNodes = diagramNodes.filter((n) => n.type === 'child' || n.type === 'bubble')

    if (topicNode) {
      data.value = {
        topic: topicNode.text,
        context: contextNodes.map((n) => n.text),
      }
    }
  }

  // Add context item
  function addContext(text: string) {
    if (data.value) {
      data.value.context.push(text)
    }
  }

  // Remove context item
  function removeContext(index: number) {
    if (data.value && index >= 0 && index < data.value.context.length) {
      data.value.context.splice(index, 1)
    }
  }

  return {
    data,
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addContext,
    removeContext,
  }
}
