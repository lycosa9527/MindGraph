/**
 * useDoubleBubbleMap - Composable for Double Bubble Map layout and data management
 * Double bubble maps compare two topics with shared similarities and paired differences
 *
 * Structure:
 * - Left topic (non-draggable)
 * - Right topic (non-draggable)
 * - Similarities (shared, in the middle)
 * - Left differences (left side only)
 * - Right differences (right side only)
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

interface DoubleBubbleMapData {
  left: string
  right: string
  similarities: string[]
  leftDifferences: string[]
  rightDifferences: string[]
}

interface DoubleBubbleMapOptions {
  centerX?: number
  centerY?: number
  topicSpacing?: number
  verticalSpacing?: number
  bubbleRadius?: number
}

export function useDoubleBubbleMap(options: DoubleBubbleMapOptions = {}) {
  const {
    centerX = 400,
    centerY = 300,
    topicSpacing = 300,
    verticalSpacing = 80,
    bubbleRadius = 40,
  } = options

  const { t } = useLanguage()
  const data = ref<DoubleBubbleMapData | null>(null)

  // Convert double bubble map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []
    const leftX = centerX - topicSpacing / 2
    const rightX = centerX + topicSpacing / 2

    // Left topic node
    result.push({
      id: 'left-topic',
      type: 'topic',
      position: { x: leftX - 60, y: centerY - 30 },
      data: {
        label: data.value.left,
        nodeType: 'topic',
        diagramType: 'double_bubble_map',
        isDraggable: false,
        isSelectable: true,
      },
      draggable: false,
    })

    // Right topic node
    result.push({
      id: 'right-topic',
      type: 'topic',
      position: { x: rightX - 60, y: centerY - 30 },
      data: {
        label: data.value.right,
        nodeType: 'topic',
        diagramType: 'double_bubble_map',
        isDraggable: false,
        isSelectable: true,
      },
      draggable: false,
    })

    // Similarities (between the two topics, stacked vertically)
    const simCount = data.value.similarities.length
    const simStartY = centerY - ((simCount - 1) * verticalSpacing) / 2
    data.value.similarities.forEach((sim, index) => {
      result.push({
        id: `similarity-${index}`,
        type: 'bubble',
        position: { x: centerX - bubbleRadius, y: simStartY + index * verticalSpacing - bubbleRadius },
        data: {
          label: sim,
          nodeType: 'bubble',
          diagramType: 'double_bubble_map',
          isDraggable: true,
          isSelectable: true,
        },
        draggable: true,
      })
    })

    // Left differences (stacked vertically on the left side)
    const leftDiffCount = data.value.leftDifferences.length
    const leftDiffStartY = centerY - ((leftDiffCount - 1) * verticalSpacing) / 2
    data.value.leftDifferences.forEach((diff, index) => {
      result.push({
        id: `left-diff-${index}`,
        type: 'bubble',
        position: {
          x: leftX - topicSpacing / 2 - bubbleRadius,
          y: leftDiffStartY + index * verticalSpacing - bubbleRadius,
        },
        data: {
          label: diff,
          nodeType: 'bubble',
          diagramType: 'double_bubble_map',
          isDraggable: true,
          isSelectable: true,
        },
        draggable: true,
      })
    })

    // Right differences (stacked vertically on the right side)
    const rightDiffCount = data.value.rightDifferences.length
    const rightDiffStartY = centerY - ((rightDiffCount - 1) * verticalSpacing) / 2
    data.value.rightDifferences.forEach((diff, index) => {
      result.push({
        id: `right-diff-${index}`,
        type: 'bubble',
        position: {
          x: rightX + topicSpacing / 2 - bubbleRadius,
          y: rightDiffStartY + index * verticalSpacing - bubbleRadius,
        },
        data: {
          label: diff,
          nodeType: 'bubble',
          diagramType: 'double_bubble_map',
          isDraggable: true,
          isSelectable: true,
        },
        draggable: true,
      })
    })

    return result
  })

  // Generate edges
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    const result: MindGraphEdge[] = []

    // Edges from left topic to similarities
    data.value.similarities.forEach((_, index) => {
      result.push({
        id: `edge-left-sim-${index}`,
        source: 'left-topic',
        target: `similarity-${index}`,
        type: 'curved',
        data: { edgeType: 'curved' as const },
      })
    })

    // Edges from right topic to similarities
    data.value.similarities.forEach((_, index) => {
      result.push({
        id: `edge-right-sim-${index}`,
        source: 'right-topic',
        target: `similarity-${index}`,
        type: 'curved',
        data: { edgeType: 'curved' as const },
      })
    })

    // Edges from left topic to left differences
    data.value.leftDifferences.forEach((_, index) => {
      result.push({
        id: `edge-left-diff-${index}`,
        source: 'left-topic',
        target: `left-diff-${index}`,
        type: 'curved',
        data: { edgeType: 'curved' as const },
      })
    })

    // Edges from right topic to right differences
    data.value.rightDifferences.forEach((_, index) => {
      result.push({
        id: `edge-right-diff-${index}`,
        source: 'right-topic',
        target: `right-diff-${index}`,
        type: 'curved',
        data: { edgeType: 'curved' as const },
      })
    })

    return result
  })

  // Set data
  function setData(newData: DoubleBubbleMapData) {
    data.value = newData
  }

  // Convert from flat diagram nodes
  function fromDiagramNodes(diagramNodes: DiagramNode[], _connections: Connection[]) {
    const leftNode = diagramNodes.find((n) => n.type === 'left' || n.id === 'left-topic')
    const rightNode = diagramNodes.find((n) => n.type === 'right' || n.id === 'right-topic')
    const simNodes = diagramNodes.filter((n) => n.id?.startsWith('similarity-'))
    const leftDiffNodes = diagramNodes.filter((n) => n.id?.startsWith('left-diff-'))
    const rightDiffNodes = diagramNodes.filter((n) => n.id?.startsWith('right-diff-'))

    data.value = {
      left: leftNode?.text || '',
      right: rightNode?.text || '',
      similarities: simNodes.map((n) => n.text),
      leftDifferences: leftDiffNodes.map((n) => n.text),
      rightDifferences: rightDiffNodes.map((n) => n.text),
    }
  }

  // Add a similarity (shared between both topics)
  function addSimilarity(text?: string, selectedNodeId?: string): boolean {
    if (!data.value) return false

    // Cannot add from topic nodes
    if (selectedNodeId === 'left-topic' || selectedNodeId === 'right-topic') {
      console.warn('Cannot add to topic nodes directly')
      return false
    }

    const simText = text || t('diagram.newSimilarity', 'New Similarity')
    data.value.similarities.push(simText)
    return true
  }

  // Add paired differences (adds to both left and right)
  function addDifferencePair(leftText?: string, rightText?: string): boolean {
    if (!data.value) return false

    const leftDiff = leftText || t('diagram.leftDifference', 'Left Difference')
    const rightDiff = rightText || t('diagram.rightDifference', 'Right Difference')
    data.value.leftDifferences.push(leftDiff)
    data.value.rightDifferences.push(rightDiff)
    return true
  }

  // Remove similarity
  function removeSimilarity(index: number) {
    if (data.value && index >= 0 && index < data.value.similarities.length) {
      data.value.similarities.splice(index, 1)
    }
  }

  // Remove difference pair (removes same index from both sides)
  function removeDifferencePair(index: number) {
    if (!data.value) return

    if (index >= 0 && index < data.value.leftDifferences.length) {
      data.value.leftDifferences.splice(index, 1)
    }
    if (index >= 0 && index < data.value.rightDifferences.length) {
      data.value.rightDifferences.splice(index, 1)
    }
  }

  // Update similarity text
  function updateSimilarity(index: number, text: string) {
    if (data.value && index >= 0 && index < data.value.similarities.length) {
      data.value.similarities[index] = text
    }
  }

  // Update left difference text
  function updateLeftDifference(index: number, text: string) {
    if (data.value && index >= 0 && index < data.value.leftDifferences.length) {
      data.value.leftDifferences[index] = text
    }
  }

  // Update right difference text
  function updateRightDifference(index: number, text: string) {
    if (data.value && index >= 0 && index < data.value.rightDifferences.length) {
      data.value.rightDifferences[index] = text
    }
  }

  // Update left topic
  function updateLeftTopic(text: string) {
    if (data.value) {
      data.value.left = text
    }
  }

  // Update right topic
  function updateRightTopic(text: string) {
    if (data.value) {
      data.value.right = text
    }
  }

  return {
    data,
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addSimilarity,
    addDifferencePair,
    removeSimilarity,
    removeDifferencePair,
    updateSimilarity,
    updateLeftDifference,
    updateRightDifference,
    updateLeftTopic,
    updateRightTopic,
  }
}
