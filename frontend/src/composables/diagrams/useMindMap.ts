/**
 * useMindMap - Composable for Mind Map layout and data management
 * Mind maps organize thoughts with a central topic and branching ideas
 *
 * Hybrid Layout System:
 * - Backend layout: Python MindMapAgent for initial generation (sophisticated positioning)
 * - Dagre layout: For local sub-tree recalculation when nodes are added/edited
 * - Falls back to Dagre for faster local updates without API calls
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
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  DEFAULT_VERTICAL_SPACING,
} from './layoutConfig'
import { calculateDagreLayout, type DagreEdgeInput, type DagreNodeInput } from './useDagreLayout'

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
  /** Enable backend layout calculation (recommended for initial generation) */
  useBackendLayout?: boolean
  /** Use Dagre for local layout (faster for edits, no API calls) */
  useDagreLayout?: boolean
}

export function useMindMap(options: MindMapOptions = {}) {
  const {
    centerX = DEFAULT_CENTER_X,
    centerY = DEFAULT_CENTER_Y,
    horizontalSpacing = DEFAULT_HORIZONTAL_SPACING,
    verticalSpacing = DEFAULT_VERTICAL_SPACING,
    useBackendLayout = false,
    useDagreLayout = true, // Default to Dagre for local operations
  } = options

  const { t } = useLanguage()
  const data = ref<MindMapData | null>(null)

  // Backend layout data (when useBackendLayout is enabled)
  const backendLayout = ref<MindMapLayout | null>(null)
  const isRecalculating = ref(false)
  const layoutError = ref<string | null>(null)

  // ===== Dagre-based Layout (Hybrid Approach) =====

  /**
   * Flatten a branch tree into nodes and edges for Dagre layout
   * Used for sub-tree layout calculation
   */
  function flattenBranchTree(
    branches: MindMapBranch[],
    parentId: string,
    direction: 1 | -1,
    depth: number,
    dagreNodes: DagreNodeInput[],
    dagreEdges: DagreEdgeInput[],
    nodeInfos: Map<string, { text: string; depth: number; direction: 1 | -1 }>
  ): void {
    branches.forEach((branch, index) => {
      const nodeId = `branch-${direction > 0 ? 'r' : 'l'}-${depth}-${index}`

      dagreNodes.push({ id: nodeId, width: DEFAULT_NODE_WIDTH, height: DEFAULT_NODE_HEIGHT })
      nodeInfos.set(nodeId, { text: branch.text, depth, direction })
      dagreEdges.push({ source: parentId, target: nodeId })

      if (branch.children && branch.children.length > 0) {
        flattenBranchTree(branch.children, nodeId, direction, depth + 1, dagreNodes, dagreEdges, nodeInfos)
      }
    })
  }

  /**
   * Calculate layout for one side using Dagre
   * Returns positioned nodes for that side
   */
  function layoutSideWithDagre(
    branches: MindMapBranch[],
    side: 'left' | 'right',
    topicX: number,
    topicY: number
  ): { nodes: MindGraphNode[]; edges: MindGraphEdge[] } {
    if (branches.length === 0) return { nodes: [], edges: [] }

    const direction = side === 'right' ? 1 : -1
    const dagreNodes: DagreNodeInput[] = []
    const dagreEdges: DagreEdgeInput[] = []
    const nodeInfos = new Map<string, { text: string; depth: number; direction: 1 | -1 }>()

    // Add virtual root for connecting to topic
    const virtualRoot = `virtual-${side}`
    dagreNodes.push({ id: virtualRoot, width: 1, height: 1 })

    // Flatten branch tree
    flattenBranchTree(branches, virtualRoot, direction, 1, dagreNodes, dagreEdges, nodeInfos)

    // Calculate layout with Dagre
    // Use LR for right side, RL for left side
    const layoutDirection = side === 'right' ? 'LR' : 'RL'
    const layoutResult = calculateDagreLayout(dagreNodes, dagreEdges, {
      direction: layoutDirection,
      nodeSeparation: verticalSpacing,
      rankSeparation: horizontalSpacing,
      align: 'UL',
      marginX: DEFAULT_PADDING,
      marginY: DEFAULT_PADDING,
    })

    // Get virtual root position to calculate offset
    // Virtual root should align with topic node's edge (not center)
    // For right side: align with topic's right edge (topicX + DEFAULT_NODE_WIDTH/2)
    // For left side: align with topic's left edge (topicX - DEFAULT_NODE_WIDTH/2)
    const virtualPos = layoutResult.positions.get(virtualRoot)
    if (!virtualPos) {
      return { nodes: [], edges: [] }
    }
    
    // Topic edge position (where branches should connect)
    const topicEdgeX = topicX + (direction * DEFAULT_NODE_WIDTH / 2)
    // Virtual root center X (Dagre returns top-left, so add half width)
    const virtualRootCenterX = virtualPos.x + virtualPos.width / 2
    // Calculate offset to align virtual root center with topic edge
    const offsetX = topicEdgeX - virtualRootCenterX
    
    // Align vertically: virtual root center Y should match topic center Y
    const virtualRootCenterY = virtualPos.y + virtualPos.height / 2
    const offsetY = topicY - virtualRootCenterY

    const nodes: MindGraphNode[] = []
    const edges: MindGraphEdge[] = []

    // Create nodes with adjusted positions
    nodeInfos.forEach((info, nodeId) => {
      const pos = layoutResult.positions.get(nodeId)
      if (pos) {
        nodes.push({
          id: nodeId,
          type: 'branch',
          position: { x: pos.x + offsetX - DEFAULT_NODE_WIDTH / 2, y: pos.y + offsetY - DEFAULT_NODE_HEIGHT / 2 },
          data: {
            label: info.text,
            nodeType: 'branch',
            diagramType: 'mindmap',
            isDraggable: true,
            isSelectable: true,
          },
          draggable: true,
        })
      }
    })

    // Create edges (skip virtual root edges, connect to topic instead)
    // Track handle index for each side to assign correct handle IDs
    let leftHandleIndex = 0
    let rightHandleIndex = 0

    dagreEdges.forEach((edge) => {
      if (edge.source === virtualRoot) {
        // Connect to topic with specific handle ID based on side
        const handleId = side === 'left' 
          ? `mindmap-left-${leftHandleIndex++}`
          : `mindmap-right-${rightHandleIndex++}`
        
        edges.push({
          id: `edge-topic-${edge.target}`,
          source: 'topic',
          target: edge.target,
          sourceHandle: handleId,
          type: 'straight',
          data: { edgeType: 'straight' as const },
        })
      } else {
        edges.push({
          id: `edge-${edge.source}-${edge.target}`,
          source: edge.source,
          target: edge.target,
          type: 'straight',
          data: { edgeType: 'straight' as const },
        })
      }
    })

    return { nodes, edges }
  }

  // ===== Legacy recursive layout (fallback) =====

  // Recursively layout branches (original algorithm, kept as fallback)
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
            type: 'straight',
            data: { edgeType: 'straight' as const },
          })
        })
      }

      currentY += verticalSpacing
    })

    return results
  }

  // ===== Dagre-based layout computation =====

  const dagreNodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []

    // Central topic node with total branch count for dynamic handles (clockwise distribution)
    const totalBranches = data.value.leftBranches.length + data.value.rightBranches.length
    result.push({
      id: 'topic',
      type: 'topic',
      position: { x: centerX - DEFAULT_NODE_WIDTH / 2, y: centerY - DEFAULT_NODE_HEIGHT / 2 },
      data: {
        label: data.value.topic,
        nodeType: 'topic',
        diagramType: 'mindmap',
        isDraggable: false,
        isSelectable: true,
        totalBranchCount: totalBranches,
      },
      draggable: false,
    })

    // Layout left side with Dagre
    const leftLayout = layoutSideWithDagre(data.value.leftBranches, 'left', centerX, centerY)
    result.push(...leftLayout.nodes)

    // Layout right side with Dagre
    const rightLayout = layoutSideWithDagre(data.value.rightBranches, 'right', centerX, centerY)
    result.push(...rightLayout.nodes)

    return result
  })

  const dagreEdges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    const result: MindGraphEdge[] = []

    // Layout left side with Dagre
    const leftLayout = layoutSideWithDagre(data.value.leftBranches, 'left', centerX, centerY)
    result.push(...leftLayout.edges)

    // Layout right side with Dagre
    const rightLayout = layoutSideWithDagre(data.value.rightBranches, 'right', centerX, centerY)
    result.push(...rightLayout.edges)

    return result
  })

  // ===== Legacy layout computation (fallback) =====

  // Convert mind map data to Vue Flow nodes
  const legacyNodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result: MindGraphNode[] = []

    // Central topic node with branch counts for dynamic handles
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
        leftBranchCount: data.value.leftBranches.length,
        rightBranchCount: data.value.rightBranches.length,
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
  const legacyEdges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    const result: MindGraphEdge[] = []

    // Edges from topic to first-level branches with handle IDs
    data.value.leftBranches.forEach((_, index) => {
      result.push({
        id: `edge-topic-l-${index}`,
        source: 'topic',
        target: `branch-l-1-${index}`,
        sourceHandle: `mindmap-left-${index}`,
        type: 'straight',
        data: { edgeType: 'straight' as const },
      })
    })

    data.value.rightBranches.forEach((_, index) => {
      result.push({
        id: `edge-topic-r-${index}`,
        source: 'topic',
        target: `branch-r-1-${index}`,
        sourceHandle: `mindmap-right-${index}`,
        type: 'straight',
        data: { edgeType: 'straight' as const },
      })
    })

    // Add child edges
    const leftResults = layoutBranches(data.value.leftBranches, centerX, centerY, -1, 1)
    leftResults.forEach((r) => result.push(...r.edges))

    const rightResults = layoutBranches(data.value.rightBranches, centerX, centerY, 1, 1)
    rightResults.forEach((r) => result.push(...r.edges))

    return result
  })

  // Select which layout to use based on options
  const nodes = computed<MindGraphNode[]>(() => {
    return useDagreLayout ? dagreNodes.value : legacyNodes.value
  })

  const edges = computed<MindGraphEdge[]>(() => {
    return useDagreLayout ? dagreEdges.value : legacyEdges.value
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

  /**
   * Recalculate layout locally using Dagre (no API call)
   * Faster than backend recalculation for real-time editing
   */
  function recalculateLocalLayout(): void {
    // Dagre layout is reactive - just trigger a re-computation
    // by touching the data ref
    if (data.value) {
      data.value = { ...data.value }
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

    // Dagre layout (hybrid approach)
    recalculateLocalLayout,
    useDagreLayout,
  }
}
