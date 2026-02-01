<script setup lang="ts">
/**
 * DiagramCanvas - Vue Flow wrapper for MindGraph diagrams
 * Provides unified interface for all diagram types with drag-drop, zoom, and pan
 *
 * Two-View Zoom System:
 * - fitToFullCanvas(): Fits diagram to full canvas (no panel space reserved)
 * - fitWithPanel(): Fits diagram with space reserved for right-side panels
 * - Automatically re-fits when panels open/close
 */
import { computed, markRaw, onMounted, onUnmounted, ref, watch } from 'vue'

import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'

import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import { ANIMATION, FIT_PADDING, GRID, PANEL, ZOOM } from '@/config/uiConfig'
import { useDiagramStore, usePanelsStore } from '@/stores'
import type { MindGraphNode } from '@/types'

import BraceOverlay from './BraceOverlay.vue'
import BridgeOverlay from './BridgeOverlay.vue'
import ContextMenu from './ContextMenu.vue'
import BraceEdge from './edges/BraceEdge.vue'
// Import custom edge components
import CurvedEdge from './edges/CurvedEdge.vue'
import HorizontalStepEdge from './edges/HorizontalStepEdge.vue'
import RadialEdge from './edges/RadialEdge.vue'
import StepEdge from './edges/StepEdge.vue'
import StraightEdge from './edges/StraightEdge.vue'
import TreeEdge from './edges/TreeEdge.vue'
import BoundaryNode from './nodes/BoundaryNode.vue'
import BraceNode from './nodes/BraceNode.vue'
import BranchNode from './nodes/BranchNode.vue'
import BubbleNode from './nodes/BubbleNode.vue'
import CircleNode from './nodes/CircleNode.vue'
import FlowNode from './nodes/FlowNode.vue'
import FlowSubstepNode from './nodes/FlowSubstepNode.vue'
import LabelNode from './nodes/LabelNode.vue'
// Import custom node components
import TopicNode from './nodes/TopicNode.vue'

// Props
interface Props {
  showBackground?: boolean
  showControls?: boolean
  showMinimap?: boolean
  fitViewOnInit?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showBackground: true,
  showControls: true,
  showMinimap: false,
  fitViewOnInit: true,
})

// Emits
const emit = defineEmits<{
  (e: 'nodeClick', node: MindGraphNode): void
  (e: 'nodeDoubleClick', node: MindGraphNode): void
  (e: 'nodeDragStop', node: MindGraphNode): void
  (e: 'selectionChange', nodes: MindGraphNode[]): void
  (e: 'paneClick'): void
}>()

// Stores
const diagramStore = useDiagramStore()
const panelsStore = usePanelsStore()

// Theme for background color
const { backgroundColor } = useTheme({
  diagramType: computed(() => diagramStore.type),
})

// Vue Flow instance
const {
  onNodesChange,
  onNodeClick,
  onNodeDoubleClick,
  onNodeDragStop,
  fitView,
  getNodes,
  setViewport,
  getViewport,
} = useVueFlow()

// Vue Flow wrapper reference for context menu
const vueFlowWrapper = ref<HTMLElement | null>(null)

// Track if current fit was done with panel space reserved
const isFittedForPanel = ref(false)

// Canvas container reference for size calculations
const canvasContainer = ref<HTMLElement | null>(null)

// Context menu state
const contextMenuVisible = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextMenuNode = ref<MindGraphNode | null>(null)
const contextMenuTarget = ref<'node' | 'pane'>('pane')

// Custom node types registration
// Use markRaw to prevent Vue from making components reactive (performance optimization)
const nodeTypes = {
  topic: markRaw(TopicNode),
  bubble: markRaw(BubbleNode),
  branch: markRaw(BranchNode),
  flow: markRaw(FlowNode),
  flowSubstep: markRaw(FlowSubstepNode), // Substep nodes for flow maps
  brace: markRaw(BraceNode),
  boundary: markRaw(BoundaryNode),
  label: markRaw(LabelNode),
  circle: markRaw(CircleNode), // Perfect circular nodes for circle maps
  // Default fallbacks
  tree: markRaw(BranchNode),
  bridge: markRaw(BranchNode),
}

// Custom edge types registration
// Use markRaw to prevent Vue from making components reactive (performance optimization)
const edgeTypes = {
  curved: markRaw(CurvedEdge),
  straight: markRaw(StraightEdge),
  step: markRaw(StepEdge), // T/L shaped orthogonal connectors for tree maps
  horizontalStep: markRaw(HorizontalStepEdge), // Horizontal-first T/L for flow map substeps
  tree: markRaw(TreeEdge), // Straight vertical lines for tree maps (no arrowhead)
  radial: markRaw(RadialEdge), // Center-to-center for radial layouts (bubble maps)
  brace: markRaw(BraceEdge),
  bridge: markRaw(StraightEdge), // Use straight for bridge maps
}

// Computed nodes and edges from store
const nodes = computed(() => diagramStore.vueFlowNodes)
// For brace maps, hide individual edges since BraceOverlay draws the braces
const edges = computed(() => {
  if (diagramStore.type === 'brace_map') {
    // Hide edges for brace maps - the BraceOverlay component draws them
    return []
  }
  return diagramStore.vueFlowEdges
})

// Handle node changes (position updates, etc.)
onNodesChange((changes) => {
  changes.forEach((change) => {
    if (change.type === 'position' && change.position) {
      // During drag, update position but don't mark as custom yet
      diagramStore.updateNodePosition(change.id, change.position, false)
    }
  })
})

// Handle node click
onNodeClick(({ node }) => {
  diagramStore.selectNodes(node.id)
  emit('nodeClick', node as unknown as MindGraphNode)
})

// Handle node double-click for editing
onNodeDoubleClick(({ node }) => {
  emit('nodeDoubleClick', node as unknown as MindGraphNode)
})

// Handle node drag stop - mark position as custom (user-dragged)
onNodeDragStop(({ node }) => {
  // Save as custom position since user dragged it
  diagramStore.saveCustomPosition(node.id, node.position.x, node.position.y)
  diagramStore.pushHistory('Move node')
  emit('nodeDragStop', node as unknown as MindGraphNode)
})

// Handle pane click (deselect)
function handlePaneClick() {
  diagramStore.clearSelection()
  emit('paneClick')
}

// Handle pane context menu (right-click on empty canvas)
function handlePaneContextMenu(event: MouseEvent) {
  event.preventDefault()
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuNode.value = null
  contextMenuTarget.value = 'pane'
  contextMenuVisible.value = true
}

// Handle node context menu (right-click on node)
function handleNodeContextMenu(event: MouseEvent, node: MindGraphNode) {
  event.preventDefault()
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuNode.value = node
  contextMenuTarget.value = 'node'
  contextMenuVisible.value = true
}

// Set up context menu listeners on mount
onMounted(() => {
  // Use nextTick to ensure Vue Flow is rendered
  setTimeout(() => {
    const vueFlowElement = vueFlowWrapper.value?.querySelector('.vue-flow')
    if (vueFlowElement) {
      // Listen for contextmenu events on Vue Flow pane
      vueFlowElement.addEventListener('contextmenu', (event: Event) => {
        const mouseEvent = event as MouseEvent
        const target = mouseEvent.target as HTMLElement
        
        // Check if clicking on a node
        const nodeElement = target.closest('.vue-flow__node')
        if (nodeElement) {
          const nodeId = nodeElement.getAttribute('data-id')
          if (nodeId) {
            const node = getNodes.value.find((n) => n.id === nodeId)
            if (node) {
              handleNodeContextMenu(mouseEvent, node as unknown as MindGraphNode)
              return
            }
          }
        }
        
        // Otherwise, it's a pane click
        handlePaneContextMenu(mouseEvent)
      })
    }
  }, 100)
})

// Close context menu
function closeContextMenu() {
  contextMenuVisible.value = false
  contextMenuNode.value = null
}

// Handle nodes initialized - flow maps now use fixed dimensions, no recalculation needed
function handleNodesInitialized() {
  // Flow maps use fixed node dimensions, layout is deterministic from specLoader
  // No runtime measurement or recalculation required
}

// ============================================================================
// Two-View Zoom System
// ============================================================================

/**
 * Get the width of currently open right-side panels
 */
function getRightPanelWidth(): number {
  let width = 0
  if (panelsStore.propertyPanel.isOpen) {
    width = PANEL.PROPERTY_WIDTH
  } else if (panelsStore.mindmatePanel.isOpen) {
    width = PANEL.MINDMATE_WIDTH
  }
  return width
}

/**
 * Get the width of currently open left-side panels
 */
function getLeftPanelWidth(): number {
  if (panelsStore.nodePalettePanel.isOpen) {
    return PANEL.NODE_PALETTE_WIDTH
  }
  return 0
}

/**
 * Check if any panel is currently visible
 */
function isAnyPanelOpen(): boolean {
  return panelsStore.anyPanelOpen
}

/**
 * Fit diagram to full canvas (no panel space reserved)
 * Use when no panels are open or when you want the diagram centered on full screen
 */
function fitToFullCanvas(animate = true): void {
  if (getNodes.value.length === 0) return

  isFittedForPanel.value = false

  // Use Vue Flow's fitView with standard padding
  fitView({
    padding: FIT_PADDING.STANDARD,
    duration: animate ? ANIMATION.DURATION_NORMAL : 0,
  })

  eventBus.emit('view:fit_completed', {
    mode: 'full_canvas',
    animate,
  })
}

/**
 * Fit diagram with panel space reserved
 * Calculates available canvas area excluding panel widths
 */
function fitWithPanel(animate = true): void {
  if (getNodes.value.length === 0) return

  const rightPanelWidth = getRightPanelWidth()
  const leftPanelWidth = getLeftPanelWidth()
  const totalPanelWidth = rightPanelWidth + leftPanelWidth

  if (totalPanelWidth === 0) {
    // No panels open, use full canvas fit
    fitToFullCanvas(animate)
    return
  }

  isFittedForPanel.value = true

  // Get container dimensions
  const container = canvasContainer.value
  if (!container) {
    // Fallback to standard fitView if container not available
    fitView({ padding: FIT_PADDING.STANDARD, duration: animate ? ANIMATION.DURATION_NORMAL : 0 })
    return
  }

  const containerWidth = container.clientWidth
  // containerHeight reserved for future vertical panel support
  const _containerHeight = container.clientHeight

  // Calculate available canvas space (excluding panels) - used for ratio calculation
  const _availableWidth = containerWidth - totalPanelWidth

  // Calculate padding ratio based on panel width
  // More panel = more padding to shift diagram away from panel
  const basePadding = FIT_PADDING.STANDARD
  const panelPaddingRatio = totalPanelWidth / containerWidth
  const adjustedPadding = basePadding + panelPaddingRatio * 0.3

  // Use fitView with adjusted padding
  // The diagram will be slightly smaller to leave visual space for the panel
  fitView({
    padding: adjustedPadding,
    duration: animate ? ANIMATION.DURATION_NORMAL : 0,
  })

  // After fitView, adjust the viewport to account for panel offset
  // This shifts the diagram left/right to center it in the available space
  const delay = animate ? ANIMATION.FIT_VIEWPORT_DELAY : ANIMATION.PANEL_DELAY
  setTimeout(() => {
    const currentViewport = getViewport()

    // Calculate horizontal offset to center in available space
    // If right panel is open, shift diagram left
    // If left panel is open, shift diagram right
    const rightOffset = rightPanelWidth / 2
    const leftOffset = leftPanelWidth / 2
    const netOffset = leftOffset - rightOffset

    setViewport(
      {
        x: currentViewport.x + netOffset,
        y: currentViewport.y,
        zoom: currentViewport.zoom,
      },
      { duration: animate ? ANIMATION.DURATION_FAST : 0 }
    )
  }, delay)

  eventBus.emit('view:fit_completed', {
    mode: 'with_panel',
    animate,
    panelWidth: totalPanelWidth,
  })
}

/**
 * Smart fit based on current panel visibility
 * Automatically chooses full canvas or panel-aware fit
 */
function fitDiagram(animate = true): void {
  if (isAnyPanelOpen()) {
    fitWithPanel(animate)
  } else {
    fitToFullCanvas(animate)
  }
}

/**
 * Fit diagram for export (no animation, minimal padding)
 */
function fitForExport(): void {
  fitView({
    padding: FIT_PADDING.EXPORT,
    duration: 0,
  })
}

// ============================================================================
// Watchers and Event Handlers
// ============================================================================

// Fit view when nodes change (initial render)
watch(
  () => nodes.value.length,
  (newLength, oldLength) => {
    if (props.fitViewOnInit && newLength > 0) {
      // On initial canvas entry (oldLength === 0), always fit to full canvas
      // This gives the user a full view of the diagram first
      // Panel-aware fit only triggers when panels actually open/close
      const isInitialLoad = oldLength === 0
      setTimeout(() => {
        if (isInitialLoad) {
          fitToFullCanvas(true)
        } else {
          fitDiagram(true)
        }
      }, ANIMATION.FIT_DELAY)
    }
  }
)

// Watch panel state changes and re-fit diagram
watch(
  () => panelsStore.anyPanelOpen,
  (isOpen, wasOpen) => {
    // Only re-fit if we have nodes and panel state actually changed
    if (nodes.value.length > 0 && isOpen !== wasOpen) {
      // Delay to allow panel animation to start
      setTimeout(() => fitDiagram(true), ANIMATION.PANEL_DELAY)
    }
  }
)

// Watch individual panel changes for more responsive fitting
watch(
  () => [
    panelsStore.mindmatePanel.isOpen,
    panelsStore.propertyPanel.isOpen,
    panelsStore.nodePalettePanel.isOpen,
  ],
  () => {
    // Re-fit when any panel opens/closes
    if (nodes.value.length > 0) {
      setTimeout(() => fitDiagram(true), ANIMATION.PANEL_DELAY)
    }
  }
)

// ============================================================================
// EventBus Subscriptions
// ============================================================================

// Unsubscribe functions for cleanup
const unsubscribers: (() => void)[] = []

onMounted(() => {
  // Listen for node edit requests from context menu
  unsubscribers.push(
    eventBus.on('node:edit_requested', ({ nodeId }) => {
      const node = getNodes.value.find((n) => n.id === nodeId)
      if (node) {
        emit('nodeDoubleClick', node as unknown as MindGraphNode)
      }
    })
  )

  // Listen for fit requests from other components
  unsubscribers.push(
    eventBus.on('view:fit_to_window_requested', (data) => {
      const animate = data?.animate !== false
      fitToFullCanvas(animate)
    })
  )

  unsubscribers.push(
    eventBus.on('view:fit_to_canvas_requested', (data) => {
      const animate = data?.animate !== false
      fitWithPanel(animate)
    })
  )

  unsubscribers.push(
    eventBus.on('view:fit_diagram_requested', () => {
      fitDiagram(true)
    })
  )

  unsubscribers.push(
    eventBus.on('view:fit_for_export_requested', () => {
      fitForExport()
    })
  )

  // Listen for inline text updates from node components
  unsubscribers.push(
    eventBus.on('node:text_updated', ({ nodeId, text }) => {
      // Update the node text in the diagram store
      diagramStore.pushHistory('Edit node text')
      diagramStore.updateNode(nodeId, { text })
      // Flow maps use fixed dimensions with text truncation, no layout recalculation needed
    })
  )

  // Listen for topic node width changes in multi-flow maps
  // When topic node becomes wider, store the width and trigger layout recalculation
  unsubscribers.push(
    eventBus.on('multi_flow_map:topic_width_changed', ({ nodeId, width }) => {
      if (diagramStore.type !== 'multi_flow_map' || nodeId !== 'event' || width === null) {
        return
      }

      // Store the topic node width in the diagram store
      // This will trigger the vueFlowNodes computed to recalculate with the new width
      diagramStore.setTopicNodeWidth(width)
    })
  )

  // Listen for node width changes in multi-flow maps
  // Store widths for visual balance calculation
  unsubscribers.push(
    eventBus.on('multi_flow_map:node_width_changed', ({ nodeId, width }) => {
      if (diagramStore.type !== 'multi_flow_map' || !nodeId || width === null) {
        return
      }

      // Store the node width for visual balance
      diagramStore.setNodeWidth(nodeId, width)
    })
  )
})

onUnmounted(() => {
  // Clean up all subscriptions
  unsubscribers.forEach((unsub) => unsub())
  unsubscribers.length = 0
})

// Expose methods for parent components
defineExpose({
  fitToFullCanvas,
  fitWithPanel,
  fitDiagram,
  fitForExport,
  isFittedForPanel,
})

// ============================================================================
// Template Constants (expose config values for template use)
// ============================================================================

const zoomConfig = {
  min: ZOOM.MIN,
  max: ZOOM.MAX,
  default: ZOOM.DEFAULT,
}

const gridConfig = {
  snapSize: [...GRID.SNAP_SIZE] as [number, number],
  backgroundGap: GRID.BACKGROUND_GAP,
  backgroundDotSize: GRID.BACKGROUND_DOT_SIZE,
}
</script>

<template>
  <div
    ref="canvasContainer"
    class="diagram-canvas w-full h-full"
  >
    <div
      ref="vueFlowWrapper"
      class="vue-flow-wrapper w-full h-full"
    >
      <VueFlow
      :nodes="nodes"
      :edges="edges"
      :node-types="nodeTypes"
      :edge-types="edgeTypes"
      :default-viewport="{ x: 0, y: 0, zoom: zoomConfig.default }"
      :min-zoom="zoomConfig.min"
      :max-zoom="zoomConfig.max"
      :snap-to-grid="true"
      :snap-grid="gridConfig.snapSize"
      :nodes-draggable="true"
      :nodes-connectable="false"
      :elements-selectable="true"
      :pan-on-scroll="false"
      :zoom-on-scroll="true"
      :pan-on-drag="[1, 2]"
      fit-view-on-init
      class="bg-gray-50 dark:bg-gray-900"
      :style="{ backgroundColor: backgroundColor }"
      @pane-click="handlePaneClick"
      @nodes-initialized="handleNodesInitialized"
    >
      <!-- Background pattern -->
      <Background
        v-if="showBackground"
        :gap="gridConfig.backgroundGap"
        :size="gridConfig.backgroundDotSize"
        pattern-color="#e5e7eb"
      />

      <!-- Zoom/pan controls -->
      <Controls
        v-if="showControls"
        :show-zoom="true"
        :show-fit-view="true"
        :show-interactive="false"
        position="bottom-right"
      />

      <!-- Minimap for overview -->
      <MiniMap
        v-if="showMinimap"
        position="bottom-left"
        :pannable="true"
        :zoomable="true"
      />

      <!-- Brace overlay for brace maps (draws unified curly braces) -->
      <BraceOverlay />

      <!-- Bridge overlay for bridge maps (draws vertical lines, triangles, and dimension label) -->
      <BridgeOverlay />
      </VueFlow>
    </div>

    <!-- Custom context menu -->
    <ContextMenu
      :visible="contextMenuVisible"
      :x="contextMenuX"
      :y="contextMenuY"
      :node="contextMenuNode"
      :target="contextMenuTarget"
      @close="closeContextMenu"
    />
  </div>
</template>

<style>
/* Vue Flow base styles */
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';
@import '@vue-flow/controls/dist/style.css';
@import '@vue-flow/minimap/dist/style.css';

.diagram-canvas {
  position: relative;
}

/* Default node selection styles (box-shadow for rectangular nodes) */
.vue-flow__node.selected {
  box-shadow: 0 0 0 2px #3b82f6;
}

/* ============================================
   CIRCLE NODE SELECTION ANIMATION OPTIONS
   ============================================
   Uncomment ONE of the options below to use it.
   Each option provides a different visual style for selected circle nodes.
   ============================================ */

/* OPTION 1: Pulsing Glow (Animated) - Smooth pulsing effect */
/* Creates a breathing/pulsing animation that draws attention */
@keyframes pulseGlow {
  0%, 100% {
    filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.6))
      drop-shadow(0 0 4px rgba(102, 126, 234, 0.4));
  }
  50% {
    filter: drop-shadow(0 0 16px rgba(102, 126, 234, 0.9))
      drop-shadow(0 0 8px rgba(102, 126, 234, 0.7));
  }
}
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  animation: pulseGlow 2s ease-in-out infinite;
}

/* OPTION 2: Clean Ring Border - Minimalist approach */
/* Simple, clean ring that doesn't distract from content */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 0 3px rgba(102, 126, 234, 0.8))
    drop-shadow(0 0 0 1px rgba(102, 126, 234, 0.4));
}
*/

/* OPTION 3: Scale + Glow - Subtle size increase with glow */
/* Node slightly grows and glows when selected */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.8))
    drop-shadow(0 0 4px rgba(102, 126, 234, 0.6));
  transform: scale(1.05);
}
*/

/* OPTION 4: Gradient Border Glow - Animated gradient ring */
/* Creates a rotating gradient effect around the border */
/*
@keyframes gradientRotate {
  0% {
    filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.8))
      drop-shadow(0 0 4px rgba(147, 51, 234, 0.6));
  }
  50% {
    filter: drop-shadow(0 0 12px rgba(147, 51, 234, 0.8))
      drop-shadow(0 0 4px rgba(102, 126, 234, 0.6));
  }
  100% {
    filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.8))
      drop-shadow(0 0 4px rgba(147, 51, 234, 0.6));
  }
}
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  animation: gradientRotate 3s ease-in-out infinite;
}
*/

/* OPTION 5: Expanding Shadow - Growing shadow effect */
/* Shadow expands outward creating depth */
/*
@keyframes expandShadow {
  0% {
    filter: drop-shadow(0 0 4px rgba(102, 126, 234, 0.6));
  }
  100% {
    filter: drop-shadow(0 0 20px rgba(102, 126, 234, 0.9))
      drop-shadow(0 0 10px rgba(102, 126, 234, 0.7));
  }
}
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  animation: expandShadow 1.5s ease-out forwards;
}
*/

/* OPTION 6: Color Shift + Glow - Subtle color change */
/* Node color shifts slightly warmer with glow */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.8))
    drop-shadow(0 0 4px rgba(102, 126, 234, 0.6))
    brightness(1.1) saturate(1.1);
}
*/

/* OPTION 7: Ripple Effect - Concentric expanding circles */
/* Creates a ripple animation effect */
/*
@keyframes ripple {
  0% {
    filter: drop-shadow(0 0 0 rgba(102, 126, 234, 0));
  }
  50% {
    filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.6))
      drop-shadow(0 0 16px rgba(102, 126, 234, 0.3));
  }
  100% {
    filter: drop-shadow(0 0 16px rgba(102, 126, 234, 0.4))
      drop-shadow(0 0 24px rgba(102, 126, 234, 0.2));
  }
}
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  animation: ripple 2s ease-out infinite;
}
*/

/* OPTION 8: Golden Accent - Warm golden glow */
/* Elegant golden/yellow accent instead of blue */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 12px rgba(234, 179, 8, 0.8))
    drop-shadow(0 0 4px rgba(234, 179, 8, 0.6));
}
*/

/* OPTION 9: Dual Ring - Two concentric rings */
/* Clean double-ring effect for emphasis */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 0 4px rgba(102, 126, 234, 0.3))
    drop-shadow(0 0 0 2px rgba(102, 126, 234, 0.8))
    drop-shadow(0 0 8px rgba(102, 126, 234, 0.6));
}
*/

/* OPTION 10: Subtle Pulse - Very gentle pulsing */
/* Minimal animation, less distracting */
/*
@keyframes subtlePulse {
  0%, 100% {
    filter: drop-shadow(0 0 10px rgba(102, 126, 234, 0.7));
  }
  50% {
    filter: drop-shadow(0 0 14px rgba(102, 126, 234, 0.8));
  }
}
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  animation: subtlePulse 3s ease-in-out infinite;
}
*/

/* OPTION 11: Original Blue Glow (Current) - Static blue glow */
/* The original implementation - no animation */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.8))
    drop-shadow(0 0 4px rgba(102, 126, 234, 0.6));
}
*/

/* Smooth transitions */
.vue-flow__node {
  transition:
    box-shadow 0.2s ease,
    filter 0.2s ease,
    transform 0.2s ease;
}

/* Boundary node styling - ensure it's visible and not clipped */
.vue-flow__node-boundary {
  overflow: visible !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  z-index: -1 !important;
}

/* Ensure boundary node doesn't interfere with other nodes */
.vue-flow__node-boundary:hover {
  box-shadow: none !important;
}

/* Boundary nodes should never show selection */
.vue-flow__node-boundary.selected {
  box-shadow: none !important;
  filter: none !important;
}

/* Multi-flow map node selection - matches circle map approach */
/* Use :has() selector to target wrapper when it contains multi-flow-map-node component */
/* This is the SAME approach as circle map - target by node type classes */
.vue-flow__node-flow.selected:has(.multi-flow-map-node),
.vue-flow__node-topic.selected:has(.multi-flow-map-node) {
  box-shadow: none !important;
  filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.6))
    drop-shadow(0 0 4px rgba(102, 126, 234, 0.4)) !important;
  animation: pulseGlow 2s ease-in-out infinite !important;
}

/* Fallback: Target by ID patterns if :has() not supported (older browsers) */
.vue-flow__node-flow[id^="cause-"].selected,
.vue-flow__node-flow[id^="effect-"].selected,
.vue-flow__node-topic[id="event"].selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.6))
    drop-shadow(0 0 4px rgba(102, 126, 234, 0.4)) !important;
  animation: pulseGlow 2s ease-in-out infinite !important;
}
</style>
