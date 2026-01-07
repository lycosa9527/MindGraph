/**
 * useDoubleBubbleMap - Composable for Double Bubble Map layout and data management
 * Double bubble maps compare two topics with shared similarities and paired differences
 *
 * Layout logic matches the original D3 implementation from bubble-map-renderer.js
 *
 * Structure:
 * - Left topic (non-draggable, perfect circle)
 * - Right topic (non-draggable, perfect circle)
 * - Similarities (shared, in the middle)
 * - Left differences (left side only)
 * - Right differences (right side only)
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import {
  DEFAULT_BUBBLE_RADIUS,
  DEFAULT_PADDING,
  DEFAULT_TOPIC_RADIUS,
  DEFAULT_VERTICAL_SPACING,
} from './layoutConfig'

interface DoubleBubbleMapData {
  left: string
  right: string
  similarities: string[]
  leftDifferences: string[]
  rightDifferences: string[]
}

interface DoubleBubbleMapLayout {
  centerX: number
  centerY: number
  // Column X positions (left to right: leftDiff, leftTopic, sim, rightTopic, rightDiff)
  leftDiffX: number
  leftTopicX: number
  simX: number
  rightTopicX: number
  rightDiffX: number
  // Node sizes
  topicR: number
  simR: number
  diffR: number
  // Spacing
  simVerticalSpacing: number
  diffVerticalSpacing: number
}

interface DoubleBubbleMapOptions {
  padding?: number
}

/**
 * Calculate double bubble map layout based on node counts
 * Uses column-based layout matching the original D3 renderer:
 * [leftDiff] - [leftTopic] - [similarities] - [rightTopic] - [rightDiff]
 */
function calculateLayout(
  simCount: number,
  leftDiffCount: number,
  rightDiffCount: number,
  padding: number = DEFAULT_PADDING
): DoubleBubbleMapLayout {
  const topicR = DEFAULT_TOPIC_RADIUS // 60px
  const simR = DEFAULT_BUBBLE_RADIUS // 40px for similarities
  const diffR = DEFAULT_BUBBLE_RADIUS - 10 // 30px for differences (smaller)

  // Vertical spacing between nodes in each column
  const simVerticalSpacing = simR * 2 + 12 // diameter + gap
  const diffVerticalSpacing = diffR * 2 + 10 // diameter + gap

  // Column spacing (50px matching original)
  const columnSpacing = 50

  // Calculate X positions from left to right
  const leftDiffX = padding + diffR
  const leftTopicX = leftDiffX + diffR + columnSpacing + topicR
  const simX = leftTopicX + topicR + columnSpacing + simR
  const rightTopicX = simX + simR + columnSpacing + topicR
  const rightDiffX = rightTopicX + topicR + columnSpacing + diffR

  // Calculate required width
  const requiredWidth = rightDiffX + diffR + padding

  // Calculate column heights (differences are paired, so use max count)
  const simColHeight = simCount > 0 ? (simCount - 1) * simVerticalSpacing + simR * 2 : 0
  const maxDiffCount = Math.max(leftDiffCount, rightDiffCount)
  const diffColHeight = maxDiffCount > 0 ? (maxDiffCount - 1) * diffVerticalSpacing + diffR * 2 : 0
  const maxColHeight = Math.max(simColHeight, diffColHeight, topicR * 2)

  // Calculate required height
  const requiredHeight = maxColHeight + padding * 2

  // Center positions
  const centerX = requiredWidth / 2
  const centerY = requiredHeight / 2

  return {
    centerX,
    centerY,
    leftDiffX,
    leftTopicX,
    simX,
    rightTopicX,
    rightDiffX,
    topicR,
    simR,
    diffR,
    simVerticalSpacing,
    diffVerticalSpacing,
  }
}

export function useDoubleBubbleMap(options: DoubleBubbleMapOptions = {}) {
  const { padding = DEFAULT_PADDING } = options

  const { t } = useLanguage()
  const data = ref<DoubleBubbleMapData | null>(null)

  // Calculate layout based on current data
  const layout = computed<DoubleBubbleMapLayout>(() => {
    const simCount = data.value?.similarities.length || 0
    const leftDiffCount = data.value?.leftDifferences.length || 0
    const rightDiffCount = data.value?.rightDifferences.length || 0
    return calculateLayout(simCount, leftDiffCount, rightDiffCount, padding)
  })

  // Convert double bubble map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []
    const l = layout.value

    // Left topic node - perfect circle (column 2)
    result.push({
      id: 'left-topic',
      type: 'circle', // Use CircleNode for perfect circle
      position: { x: l.leftTopicX - l.topicR, y: l.centerY - l.topicR },
      data: {
        label: data.value.left,
        nodeType: 'topic', // Keep 'topic' for styling
        diagramType: 'double_bubble_map',
        isDraggable: false,
        isSelectable: true,
        style: {
          size: l.topicR * 2, // Diameter for perfect circle
        },
      },
      draggable: false,
    })

    // Right topic node - perfect circle (column 4)
    result.push({
      id: 'right-topic',
      type: 'circle', // Use CircleNode for perfect circle
      position: { x: l.rightTopicX - l.topicR, y: l.centerY - l.topicR },
      data: {
        label: data.value.right,
        nodeType: 'topic', // Keep 'topic' for styling
        diagramType: 'double_bubble_map',
        isDraggable: false,
        isSelectable: true,
        style: {
          size: l.topicR * 2, // Diameter for perfect circle
        },
      },
      draggable: false,
    })

    // Similarities (center column 3, stacked vertically)
    const simCount = data.value.similarities.length
    const simColHeight = simCount > 0 ? (simCount - 1) * l.simVerticalSpacing + l.simR * 2 : 0
    const simStartY = l.centerY - simColHeight / 2 + l.simR
    data.value.similarities.forEach((sim, index) => {
      result.push({
        id: `similarity-${index}`,
        type: 'bubble',
        position: {
          x: l.simX - l.simR,
          y: simStartY + index * l.simVerticalSpacing - l.simR,
        },
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

    // Left and Right differences are PAIRED - they share the same Y positions
    const leftDiffCount = data.value.leftDifferences.length
    const rightDiffCount = data.value.rightDifferences.length
    const maxDiffCount = Math.max(leftDiffCount, rightDiffCount)
    const diffColHeight =
      maxDiffCount > 0 ? (maxDiffCount - 1) * l.diffVerticalSpacing + l.diffR * 2 : 0
    const diffStartY = l.centerY - diffColHeight / 2 + l.diffR

    // Left differences (column 1)
    data.value.leftDifferences.forEach((diff, index) => {
      result.push({
        id: `left-diff-${index}`,
        type: 'bubble',
        position: {
          x: l.leftDiffX - l.diffR,
          y: diffStartY + index * l.diffVerticalSpacing - l.diffR,
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

    // Right differences (column 5) - same Y positions as left differences
    data.value.rightDifferences.forEach((diff, index) => {
      result.push({
        id: `right-diff-${index}`,
        type: 'bubble',
        position: {
          x: l.rightDiffX - l.diffR,
          y: diffStartY + index * l.diffVerticalSpacing - l.diffR,
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

  // Generate edges (radial center-to-center lines)
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    const result: MindGraphEdge[] = []

    // Edges from left topic to similarities
    data.value.similarities.forEach((_, index) => {
      result.push({
        id: `edge-left-sim-${index}`,
        source: 'left-topic',
        target: `similarity-${index}`,
        type: 'radial',
        data: { edgeType: 'radial' as const },
      })
    })

    // Edges from right topic to similarities
    data.value.similarities.forEach((_, index) => {
      result.push({
        id: `edge-right-sim-${index}`,
        source: 'right-topic',
        target: `similarity-${index}`,
        type: 'radial',
        data: { edgeType: 'radial' as const },
      })
    })

    // Edges from left topic to left differences
    data.value.leftDifferences.forEach((_, index) => {
      result.push({
        id: `edge-left-diff-${index}`,
        source: 'left-topic',
        target: `left-diff-${index}`,
        type: 'radial',
        data: { edgeType: 'radial' as const },
      })
    })

    // Edges from right topic to right differences
    data.value.rightDifferences.forEach((_, index) => {
      result.push({
        id: `edge-right-diff-${index}`,
        source: 'right-topic',
        target: `right-diff-${index}`,
        type: 'radial',
        data: { edgeType: 'radial' as const },
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
    layout,
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
