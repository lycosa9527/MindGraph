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
import {
  doubleBubbleDiffRequiredRadius,
  doubleBubbleRequiredRadius,
} from '@/stores/specLoader/textMeasurement'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import { DEFAULT_PADDING, DOUBLE_BUBBLE_MAX_CAPSULE_HEIGHT } from './layoutConfig'

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

/** Capsule: 长度随 radius，高度有上限；与 CircleNode / doubleBubbleMap 一致 */
function capsuleFromRadius(radius: number): { width: number; height: number; diameter: number } {
  const diameter = radius * 2
  const height = Math.min(
    Math.round(diameter * 0.56),
    DOUBLE_BUBBLE_MAX_CAPSULE_HEIGHT
  )
  return {
    width: Math.round(diameter * 1.22),
    height,
    diameter,
  }
}

/**
 * Layout from unified radii (per-type). Symmetry line = similarity column midline (centerX).
 */
function computeLayoutFromRadii(
  simCount: number,
  leftDiffCount: number,
  rightDiffCount: number,
  padding: number,
  topicR: number,
  simR: number,
  diffR: number
): DoubleBubbleMapLayout {
  const columnSpacing = 50
  const diffCap = capsuleFromRadius(diffR)
  const maxLeftW = diffCap.width
  const maxRightW = diffCap.width
  const simCap = capsuleFromRadius(simR)
  const simVerticalSpacing = simCap.height + 12
  const diffVerticalSpacing = diffCap.height + 10

  const D = simR + 2 * columnSpacing + 2 * topicR
  const requiredWidth = 2 * D + maxLeftW + maxRightW + padding * 2
  const centerX = requiredWidth / 2
  const simX = centerX
  const leftTopicX = centerX - simR - columnSpacing - topicR
  const rightTopicX = centerX + simR + columnSpacing + topicR
  const leftDiffX = centerX - D
  const rightDiffX = centerX + D + maxRightW

  const simColHeight = simCount > 0 ? (simCount - 1) * simVerticalSpacing + simCap.height : 0
  const maxDiffCount = Math.max(leftDiffCount, rightDiffCount)
  const diffColHeight =
    maxDiffCount > 0 ? (maxDiffCount - 1) * diffVerticalSpacing + diffCap.height : 0
  const maxColHeight = Math.max(simColHeight, diffColHeight, topicR * 2)
  const requiredHeight = maxColHeight + padding * 2
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

  // Per-type unified radius; 不同点左右统一半径，任一侧变化时两侧同步
  const layout = computed<DoubleBubbleMapLayout>(() => {
    const d = data.value
    if (!d) return computeLayoutFromRadii(0, 0, 0, padding, 60, 40, 30)
    const topicLeftR = doubleBubbleRequiredRadius(d.left, { isTopic: true })
    const topicRightR = doubleBubbleRequiredRadius(d.right, { isTopic: true })
    const topicR = Math.max(topicLeftR, topicRightR)
    const simRadii = d.similarities.map((t) => doubleBubbleRequiredRadius(t, { isTopic: false }))
    const simR = simRadii.length > 0 ? Math.max(...simRadii) : 30
    const leftDiffRadii = d.leftDifferences.map((t) => doubleBubbleDiffRequiredRadius(t))
    const rightDiffRadii = d.rightDifferences.map((t) => doubleBubbleDiffRequiredRadius(t))
    const leftDiffR = leftDiffRadii.length > 0 ? Math.max(...leftDiffRadii) : 30
    const rightDiffR = rightDiffRadii.length > 0 ? Math.max(...rightDiffRadii) : 30
    const diffR = Math.max(leftDiffR, rightDiffR)
    return computeLayoutFromRadii(
      d.similarities.length,
      d.leftDifferences.length,
      d.rightDifferences.length,
      padding,
      topicR,
      simR,
      diffR
    )
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

    const simCount = data.value.similarities.length
    const simCap = capsuleFromRadius(l.simR)
    const simColHeight = simCount > 0 ? (simCount - 1) * l.simVerticalSpacing + simCap.height : 0
    const simStartY = l.centerY - simColHeight / 2 + simCap.height / 2
    data.value.similarities.forEach((sim, index) => {
      const cy = simStartY + index * l.simVerticalSpacing
      result.push({
        id: `similarity-${index}`,
        type: 'bubble',
        position: { x: l.simX - simCap.width / 2, y: cy - simCap.height / 2 },
        data: {
          label: sim,
          nodeType: 'bubble',
          diagramType: 'double_bubble_map',
          isDraggable: false,
          isSelectable: true,
          style: { size: l.simR * 2 },
        },
        draggable: false,
      })
    })

    const leftDiffCount = data.value.leftDifferences.length
    const rightDiffCount = data.value.rightDifferences.length
    const maxDiffCount = Math.max(leftDiffCount, rightDiffCount)
    const diffCap = capsuleFromRadius(l.diffR)
    const maxLeftW = diffCap.width
    const diffColHeight =
      maxDiffCount > 0 ? (maxDiffCount - 1) * l.diffVerticalSpacing + diffCap.height : 0
    const diffStartY = l.centerY - diffColHeight / 2 + diffCap.height / 2

    data.value.leftDifferences.forEach((diff, index) => {
      const cy = diffStartY + index * l.diffVerticalSpacing
      result.push({
        id: `left-diff-${index}`,
        type: 'bubble',
        position: { x: l.leftDiffX - maxLeftW, y: cy - diffCap.height / 2 },
        data: {
          label: diff,
          nodeType: 'bubble',
          diagramType: 'double_bubble_map',
          isDraggable: false,
          isSelectable: true,
          style: { size: l.diffR * 2 },
        },
        draggable: false,
      })
    })

    data.value.rightDifferences.forEach((diff, index) => {
      const cy = diffStartY + index * l.diffVerticalSpacing
      result.push({
        id: `right-diff-${index}`,
        type: 'bubble',
        position: { x: l.rightDiffX - diffCap.width, y: cy - diffCap.height / 2 },
        data: {
          label: diff,
          nodeType: 'bubble',
          diagramType: 'double_bubble_map',
          isDraggable: false,
          isSelectable: true,
          style: { size: l.diffR * 2 },
        },
        draggable: false,
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
