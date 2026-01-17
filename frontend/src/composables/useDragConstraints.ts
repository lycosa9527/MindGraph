/**
 * useDragConstraints - Composable for diagram-specific drag constraints
 * Provides constraint logic for different diagram types during node dragging
 */
import { computed, ref } from 'vue'

import type { DiagramType, MindGraphNode } from '@/types'

export interface DragConstraints {
  minX?: number
  maxX?: number
  minY?: number
  maxY?: number
  snapToGrid?: boolean
  gridSize?: number
  lockAxis?: 'x' | 'y' | null
  preserveHierarchy?: boolean
}

/**
 * Circle map donut boundary layout information
 * Stores the calculated layout for constraining nodes to the donut ring
 */
export interface CircleMapBoundary {
  centerX: number
  centerY: number
  innerRadius: number
  outerRadius: number
  nodeRadius: number
}

export interface UseDragConstraintsOptions {
  diagramType?: DiagramType
  canvasWidth?: number
  canvasHeight?: number
  padding?: number
  gridSize?: number
}

export function useDragConstraints(options: UseDragConstraintsOptions = {}) {
  const { canvasWidth = 1200, canvasHeight = 800, padding = 50, gridSize = 20 } = options

  const currentDiagramType = ref<DiagramType | null>(options.diagramType || null)
  const snapToGrid = ref(false)
  const lockAxis = ref<'x' | 'y' | null>(null)

  // Circle map boundary info (set when loading a circle map)
  const circleMapBoundary = ref<CircleMapBoundary | null>(null)

  // Get constraints for a diagram type
  const constraints = computed<DragConstraints>(() => {
    const base: DragConstraints = {
      minX: padding,
      maxX: canvasWidth - padding,
      minY: padding,
      maxY: canvasHeight - padding,
      snapToGrid: snapToGrid.value,
      gridSize,
      lockAxis: lockAxis.value,
    }

    switch (currentDiagramType.value) {
      case 'flow_map':
        // Flow maps typically have horizontal flow, allow vertical adjustment
        return {
          ...base,
          lockAxis: 'y', // Lock to horizontal movement
        }

      case 'tree_map':
        // Tree maps have vertical hierarchy
        return {
          ...base,
          preserveHierarchy: true,
        }

      case 'bridge_map':
        // Bridge maps have pairs that should stay aligned
        return {
          ...base,
          preserveHierarchy: true,
        }

      case 'brace_map':
        // Brace maps have left-to-right hierarchy
        return {
          ...base,
          preserveHierarchy: true,
        }

      case 'bubble_map':
        // Radial layouts allow free movement
        return base

      case 'circle_map':
        // Circle maps use donut boundary constraint
        // Actual constraining is done in constrainToDonut function
        return base

      case 'mindmap':
        // Mind maps allow relatively free movement
        return base

      default:
        return base
    }
  })

  // Set diagram type
  function setDiagramType(type: DiagramType) {
    currentDiagramType.value = type
  }

  // Toggle snap to grid
  function toggleSnapToGrid() {
    snapToGrid.value = !snapToGrid.value
  }

  // Set axis lock
  function setAxisLock(axis: 'x' | 'y' | null) {
    lockAxis.value = axis
  }

  /**
   * Set circle map boundary info from diagram layout
   * Called when a circle map is loaded or recalculated
   */
  function setCircleMapBoundary(boundary: CircleMapBoundary | null) {
    circleMapBoundary.value = boundary
  }

  /**
   * Update circle map boundary from spec layout metadata
   */
  function updateCircleMapBoundaryFromSpec(spec: Record<string, unknown>) {
    const layout = spec._circleMapLayout as CircleMapBoundary | undefined
    if (layout) {
      circleMapBoundary.value = {
        centerX: layout.centerX,
        centerY: layout.centerY,
        innerRadius: layout.innerRadius,
        outerRadius: layout.outerRadius,
        nodeRadius: (layout as { uniformContextR?: number }).uniformContextR || 35,
      }
    }
  }

  /**
   * Constrain a position to be within the circle map donut boundary
   * Returns constrained position if boundary is set, otherwise original position
   */
  function constrainToDonut(x: number, y: number): { x: number; y: number } {
    if (currentDiagramType.value !== 'circle_map' || !circleMapBoundary.value) {
      return { x, y }
    }

    const b = circleMapBoundary.value
    const nodeR = b.nodeRadius

    // Calculate center of the node
    const nodeCenterX = x + nodeR
    const nodeCenterY = y + nodeR

    // Calculate distance from diagram center to node center
    const dx = nodeCenterX - b.centerX
    const dy = nodeCenterY - b.centerY
    const distance = Math.sqrt(dx * dx + dy * dy)

    // If node is at center (shouldn't happen), push to inner radius
    if (distance === 0) {
      return {
        x: b.centerX + b.innerRadius - nodeR,
        y: b.centerY - nodeR,
      }
    }

    let constrainedDistance = distance

    // Constrain to outer boundary
    if (distance > b.outerRadius) {
      constrainedDistance = b.outerRadius
    }

    // Constrain to inner boundary (push away from center)
    if (distance < b.innerRadius) {
      constrainedDistance = b.innerRadius
    }

    // If distance was modified, calculate new position
    if (constrainedDistance !== distance) {
      const scale = constrainedDistance / distance
      const constrainedCenterX = b.centerX + dx * scale
      const constrainedCenterY = b.centerY + dy * scale
      return {
        x: constrainedCenterX - nodeR,
        y: constrainedCenterY - nodeR,
      }
    }

    return { x, y }
  }

  /**
   * Check if a position is within the circle map donut boundary
   */
  function isWithinDonutBoundary(x: number, y: number): boolean {
    if (!circleMapBoundary.value) {
      return true
    }

    const b = circleMapBoundary.value
    const nodeR = b.nodeRadius

    // Calculate center of the node
    const nodeCenterX = x + nodeR
    const nodeCenterY = y + nodeR

    // Calculate distance from diagram center to node center
    const dx = nodeCenterX - b.centerX
    const dy = nodeCenterY - b.centerY
    const distance = Math.sqrt(dx * dx + dy * dy)

    return distance >= b.innerRadius && distance <= b.outerRadius
  }

  // Apply constraints to a position
  function constrainPosition(
    x: number,
    y: number,
    nodeWidth = 120,
    nodeHeight = 40
  ): { x: number; y: number } {
    // For circle maps, use donut constraint
    if (currentDiagramType.value === 'circle_map') {
      return constrainToDonut(x, y)
    }

    let constrainedX = x
    let constrainedY = y
    const c = constraints.value

    // Apply bounds
    if (c.minX !== undefined) {
      constrainedX = Math.max(c.minX, constrainedX)
    }
    if (c.maxX !== undefined) {
      constrainedX = Math.min(c.maxX - nodeWidth, constrainedX)
    }
    if (c.minY !== undefined) {
      constrainedY = Math.max(c.minY, constrainedY)
    }
    if (c.maxY !== undefined) {
      constrainedY = Math.min(c.maxY - nodeHeight, constrainedY)
    }

    // Apply grid snap
    if (c.snapToGrid && c.gridSize) {
      constrainedX = Math.round(constrainedX / c.gridSize) * c.gridSize
      constrainedY = Math.round(constrainedY / c.gridSize) * c.gridSize
    }

    return { x: constrainedX, y: constrainedY }
  }

  // Apply axis lock during drag
  function applyAxisLock(
    newX: number,
    newY: number,
    startX: number,
    startY: number
  ): { x: number; y: number } {
    const c = constraints.value

    if (c.lockAxis === 'x') {
      return { x: newX, y: startY }
    }
    if (c.lockAxis === 'y') {
      return { x: startX, y: newY }
    }

    return { x: newX, y: newY }
  }

  // Check if node can be dragged (some nodes may be locked)
  function canDrag(node: MindGraphNode): boolean {
    // Topic/center/boundary nodes are not draggable
    if (node.data?.nodeType === 'topic' || node.data?.nodeType === 'boundary') {
      return false
    }

    // Check the node's draggable property
    if (node.draggable === false) {
      return false
    }

    return true
  }

  // Get drag handle position for a node type
  function getDragHandlePosition(nodeType: string): 'center' | 'top' | 'left' {
    switch (nodeType) {
      case 'topic':
        return 'center'
      case 'flow':
        return 'center'
      case 'branch':
        return 'left'
      default:
        return 'center'
    }
  }

  // Calculate snap preview position
  function getSnapPreview(x: number, y: number): { x: number; y: number } | null {
    if (!snapToGrid.value) return null

    return {
      x: Math.round(x / gridSize) * gridSize,
      y: Math.round(y / gridSize) * gridSize,
    }
  }

  // Validate drag result for hierarchy preservation
  function validateHierarchyDrag(
    _movedNodeId: string,
    _newX: number,
    _newY: number,
    _allNodes: MindGraphNode[]
  ): boolean {
    if (!constraints.value.preserveHierarchy) {
      return true
    }

    // For diagram types that preserve hierarchy,
    // we may want to validate that the node doesn't cross hierarchy boundaries
    // This is a simplified version - could be enhanced based on specific needs
    return true
  }

  return {
    // State
    currentDiagramType,
    snapToGrid,
    lockAxis,
    constraints,
    circleMapBoundary,

    // Actions
    setDiagramType,
    toggleSnapToGrid,
    setAxisLock,
    setCircleMapBoundary,
    updateCircleMapBoundaryFromSpec,

    // Constraint functions
    constrainPosition,
    constrainToDonut,
    isWithinDonutBoundary,
    applyAxisLock,
    canDrag,
    getDragHandlePosition,
    getSnapPreview,
    validateHierarchyDrag,
  }
}
