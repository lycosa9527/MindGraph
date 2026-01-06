/**
 * useMindMap - Composable for Mind Map layout and data management
 * Mind maps organize thoughts with a central topic and branching ideas
 *
 * Phase 3: Added backend layout integration for recalculating positions
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'
import {
  type MindMapLayout,
  type MindMapSpec,
  diagramDataToMindMapSpec,
  recalculateMindMapLayout,
} from '@/utils'

import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_HORIZONTAL_SPACING,
  DEFAULT_VERTICAL_SPACING,
} from './layoutConfig'

interface MindMapBranch {
  text: string
  children?: MindMapBranch[]
}

interface MindMapData {
  topic: string
  leftBranches: MindMapBranch[]
  rightBranches: MindMapBranch[]
}

interface MindMapOptions {
  centerX?: number
  centerY?: number
  horizontalSpacing?: number
  verticalSpacing?: number
  /** Enable backend layout calculation (recommended for better positioning) */
  useBackendLayout?: boolean
}

export function useMindMap(options: MindMapOptions = {}) {
  const {
    centerX = DEFAULT_CENTER_X,
    centerY = DEFAULT_CENTER_Y,
    horizontalSpacing = DEFAULT_HORIZONTAL_SPACING,
    verticalSpacing = DEFAULT_VERTICAL_SPACING,
    useBackendLayout = false,
  } = options

  const { t } = useLanguage()
  const data = ref<MindMapData | null>(null)

  // Backend layout data (when useBackendLayout is enabled)
  const backendLayout = ref<MindMapLayout | null>(null)
  const isRecalculating = ref(false)
  const layoutError = ref<string | null>(null)

  // Recursively layout branches
  function layoutBranches(
    branches: MindMapBranch[],
    startX: number,
    startY: number,
    direction: 1 | -1,
    depth: number
  ): { nodes: MindGraphNode[]; edges: MindGraphEdge[]; parentId: string }[] {
    const results: { nodes: MindGraphNode[]; edges: MindGraphEdge[]; parentId: string }[] = []
    const totalHeight = (branches.length - 1) * verticalSpacing
    let currentY = startY - totalHeight / 2

    branches.forEach((branch, index) => {
      const nodeId = `branch-${direction > 0 ? 'r' : 'l'}-${depth}-${index}`
      const x = startX + direction * horizontalSpacing * depth
      const y = currentY

      const node: MindGraphNode = {
        id: nodeId,
        type: 'branch',
        position: { x: x - 60, y: y - 18 },
        data: {
          label: branch.text,
          nodeType: 'branch',
          diagramType: 'mindmap',
          isDraggable: true,
          isSelectable: true,
        },
        draggable: true,
      }

      results.push({ nodes: [node], edges: [], parentId: nodeId })

      // Recursively add children
      if (branch.children && branch.children.length > 0) {
        const childResults = layoutBranches(branch.children, x, y, direction, depth + 1)
        childResults.forEach((child) => {
          results.push(child)
          // Add edge from this node to child
          results[results.length - 1].edges.push({
            id: `edge-${nodeId}-${child.parentId}`,
            source: nodeId,
            target: child.parentId,
            type: 'curved',
            data: { edgeType: 'curved' as const },
          })
        })
      }

      currentY += verticalSpacing
    })

    return results
  }

  // Convert mind map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []

    // Central topic node
    result.push({
      id: 'topic',
      type: 'topic',
      position: { x: centerX - 80, y: centerY - 30 },
      data: {
        label: data.value.topic,
        nodeType: 'topic',
        diagramType: 'mindmap',
        isDraggable: false,
        isSelectable: true,
      },
      draggable: false,
    })

    // Left branches
    const leftResults = layoutBranches(data.value.leftBranches, centerX, centerY, -1, 1)
    leftResults.forEach((r) => result.push(...r.nodes))

    // Right branches
    const rightResults = layoutBranches(data.value.rightBranches, centerX, centerY, 1, 1)
    rightResults.forEach((r) => result.push(...r.nodes))

    return result
  })

  // Generate edges
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    const result: MindGraphEdge[] = []

    // Edges from topic to first-level branches
    data.value.leftBranches.forEach((_, index) => {
      result.push({
        id: `edge-topic-l-${index}`,
        source: 'topic',
        target: `branch-l-1-${index}`,
        type: 'curved',
        data: { edgeType: 'curved' as const },
      })
    })

    data.value.rightBranches.forEach((_, index) => {
      result.push({
        id: `edge-topic-r-${index}`,
        source: 'topic',
        target: `branch-r-1-${index}`,
        type: 'curved',
        data: { edgeType: 'curved' as const },
      })
    })

    // Add child edges
    const leftResults = layoutBranches(data.value.leftBranches, centerX, centerY, -1, 1)
    leftResults.forEach((r) => result.push(...r.edges))

    const rightResults = layoutBranches(data.value.rightBranches, centerX, centerY, 1, 1)
    rightResults.forEach((r) => result.push(...r.edges))

    return result
  })

  // Set mind map data
  function setData(newData: MindMapData) {
    data.value = newData
  }

  // Convert from flat diagram nodes
  function fromDiagramNodes(diagramNodes: DiagramNode[], _connections: Connection[]) {
    const topicNode = diagramNodes.find((n) => n.type === 'topic' || n.type === 'center')
    const branchNodes = diagramNodes.filter((n) => n.type !== 'topic' && n.type !== 'center')

    // Simple conversion - split branches left/right
    const leftNodes = branchNodes.filter(
      (n) => n.type === 'left' || branchNodes.indexOf(n) % 2 === 0
    )
    const rightNodes = branchNodes.filter(
      (n) => n.type === 'right' || branchNodes.indexOf(n) % 2 === 1
    )

    if (topicNode) {
      data.value = {
        topic: topicNode.text,
        leftBranches: leftNodes.map((n) => ({ text: n.text })),
        rightBranches: rightNodes.map((n) => ({ text: n.text })),
      }
    }
  }

  // Add branch (requires selection context matching old JS behavior)
  function addBranch(side: 'left' | 'right', text?: string, selectedNodeId?: string): boolean {
    if (!data.value) return false

    // Selection-based validation (matching old JS behavior)
    // If selection is provided, ensure it's not the topic node
    if (selectedNodeId === 'topic') {
      console.warn('Cannot add branches to central topic directly')
      return false
    }

    // Use default translated text if not provided (matching old JS behavior)
    const branchText = text || t('diagram.newBranch', 'New Branch')
    const branch = { text: branchText }
    if (side === 'left') {
      data.value.leftBranches.push(branch)
    } else {
      data.value.rightBranches.push(branch)
    }
    return true
  }

  // Add child to a branch (requires selection of a branch)
  function addChildToBranch(branchId: string, text?: string, selectedNodeId?: string): boolean {
    if (!data.value) return false

    // Selection validation - must select a branch
    if (!selectedNodeId || selectedNodeId === 'topic') {
      console.warn('Please select a branch to add a child')
      return false
    }

    // Find the branch in left or right branches
    const allBranches = [...data.value.leftBranches, ...data.value.rightBranches]
    const branchIndex = allBranches.findIndex((_, idx) => {
      const leftIndex = idx < data.value!.leftBranches.length ? idx : -1
      const rightIndex =
        idx >= data.value!.leftBranches.length ? idx - data.value!.leftBranches.length : -1
      const nodeId = leftIndex >= 0 ? `branch-l-1-${leftIndex}` : `branch-r-1-${rightIndex}`
      return nodeId === selectedNodeId
    })

    if (branchIndex === -1) {
      console.warn('Selected node is not a valid branch')
      return false
    }

    const branch =
      branchIndex < data.value.leftBranches.length
        ? data.value.leftBranches[branchIndex]
        : data.value.rightBranches[branchIndex - data.value.leftBranches.length]

    if (!branch.children) {
      branch.children = []
    }

    // Use default translated text if not provided (matching old JS behavior)
    const childText = text || t('diagram.newSubitem', 'Sub-item')
    branch.children.push({ text: childText })

    return true
  }

  // ===== Backend Layout Integration (Phase 3) =====

  /**
   * Convert current mind map data to backend spec format
   */
  function toBackendSpec(): MindMapSpec | null {
    if (!data.value) return null

    return diagramDataToMindMapSpec(
      data.value.topic,
      data.value.leftBranches,
      data.value.rightBranches
    )
  }

  /**
   * Recalculate layout using backend MindMapAgent
   * Call this after adding/removing nodes for optimal positioning
   */
  async function recalculateLayout(): Promise<boolean> {
    if (!data.value || !useBackendLayout) return false

    const spec = toBackendSpec()
    if (!spec) return false

    isRecalculating.value = true
    layoutError.value = null

    try {
      const result = await recalculateMindMapLayout(spec)

      if (result.success && result.spec?._layout) {
        backendLayout.value = result.spec._layout
        return true
      }

      layoutError.value = result.error || 'Layout recalculation failed'
      return false
    } catch (error) {
      layoutError.value = error instanceof Error ? error.message : 'Unknown error'
      return false
    } finally {
      isRecalculating.value = false
    }
  }

  /**
   * Apply backend layout positions to nodes
   * Returns nodes with positions from backend layout if available
   */
  const nodesWithBackendLayout = computed<MindGraphNode[]>(() => {
    const baseNodes = nodes.value
    if (!backendLayout.value?.positions) return baseNodes

    const positions = backendLayout.value.positions

    return baseNodes.map((node) => {
      const backendPos = positions[node.id]
      if (backendPos) {
        return {
          ...node,
          position: { x: backendPos.x, y: backendPos.y },
        }
      }
      return node
    })
  })

  /**
   * Clear backend layout (fall back to local calculation)
   */
  function clearBackendLayout(): void {
    backendLayout.value = null
    layoutError.value = null
  }

  /**
   * Set data and optionally recalculate layout
   */
  async function setDataWithLayout(
    newData: MindMapData,
    recalculate: boolean = true
  ): Promise<void> {
    data.value = newData
    if (recalculate && useBackendLayout) {
      await recalculateLayout()
    }
  }

  return {
    data,
    nodes: useBackendLayout ? nodesWithBackendLayout : nodes,
    edges,
    setData,
    fromDiagramNodes,
    addBranch,
    addChildToBranch,

    // Backend layout (Phase 3)
    backendLayout,
    isRecalculating,
    layoutError,
    toBackendSpec,
    recalculateLayout,
    clearBackendLayout,
    setDataWithLayout,
  }
}
