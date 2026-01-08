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
import { useDiagramStore, usePanelsStore } from '@/stores'
import type { MindGraphNode } from '@/types'

import BraceEdge from './edges/BraceEdge.vue'
// Import custom edge components
import CurvedEdge from './edges/CurvedEdge.vue'
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
import LabelNode from './nodes/LabelNode.vue'
// Import custom node components
import TopicNode from './nodes/TopicNode.vue'

// Panel width constants (matching old JS view-manager.js)
const PROPERTY_PANEL_WIDTH = 320
const MINDMATE_PANEL_WIDTH = 384 // w-96 = 24rem = 384px
const NODE_PALETTE_WIDTH = 288 // w-72 = 18rem = 288px

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

// Track if current fit was done with panel space reserved
const isFittedForPanel = ref(false)

// Canvas container reference for size calculations
const canvasContainer = ref<HTMLElement | null>(null)

// Custom node types registration
// Use markRaw to prevent Vue from making components reactive (performance optimization)
const nodeTypes = {
  topic: markRaw(TopicNode),
  bubble: markRaw(BubbleNode),
  branch: markRaw(BranchNode),
  flow: markRaw(FlowNode),
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
  tree: markRaw(TreeEdge), // Straight vertical lines for tree maps (no arrowhead)
  radial: markRaw(RadialEdge), // Center-to-center for radial layouts (bubble maps)
  brace: markRaw(BraceEdge),
  bridge: markRaw(StraightEdge), // Use straight for bridge maps
}

// Computed nodes and edges from store
const nodes = computed(() => diagramStore.vueFlowNodes)
const edges = computed(() => diagramStore.vueFlowEdges)

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

// ============================================================================
// Two-View Zoom System
// ============================================================================

/**
 * Get the width of currently open right-side panels
 */
function getRightPanelWidth(): number {
  let width = 0
  if (panelsStore.propertyPanel.isOpen) {
    width = PROPERTY_PANEL_WIDTH
  } else if (panelsStore.mindmatePanel.isOpen) {
    width = MINDMATE_PANEL_WIDTH
  }
  return width
}

/**
 * Get the width of currently open left-side panels
 */
function getLeftPanelWidth(): number {
  if (panelsStore.nodePalettePanel.isOpen) {
    return NODE_PALETTE_WIDTH
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
    padding: 0.15,
    duration: animate ? 300 : 0,
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
    fitView({ padding: 0.15, duration: animate ? 300 : 0 })
    return
  }

  const containerWidth = container.clientWidth
  // containerHeight reserved for future vertical panel support
  const _containerHeight = container.clientHeight

  // Calculate available canvas space (excluding panels) - used for ratio calculation
  const _availableWidth = containerWidth - totalPanelWidth

  // Calculate padding ratio based on panel width
  // More panel = more padding to shift diagram away from panel
  const basePadding = 0.15
  const panelPaddingRatio = totalPanelWidth / containerWidth
  const adjustedPadding = basePadding + panelPaddingRatio * 0.3

  // Use fitView with adjusted padding
  // The diagram will be slightly smaller to leave visual space for the panel
  fitView({
    padding: adjustedPadding,
    duration: animate ? 300 : 0,
  })

  // After fitView, adjust the viewport to account for panel offset
  // This shifts the diagram left/right to center it in the available space
  const delay = animate ? 350 : 50
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
      { duration: animate ? 150 : 0 }
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
    padding: 0.05,
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
      }, 100)
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
      setTimeout(() => fitDiagram(true), 50)
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
      setTimeout(() => fitDiagram(true), 50)
    }
  }
)

// ============================================================================
// EventBus Subscriptions
// ============================================================================

// Unsubscribe functions for cleanup
const unsubscribers: (() => void)[] = []

onMounted(() => {
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
</script>

<template>
  <div
    ref="canvasContainer"
    class="diagram-canvas w-full h-full"
  >
    <VueFlow
      :nodes="nodes"
      :edges="edges"
      :node-types="nodeTypes"
      :edge-types="edgeTypes"
      :default-viewport="{ x: 0, y: 0, zoom: 1 }"
      :min-zoom="0.1"
      :max-zoom="4"
      :snap-to-grid="true"
      :snap-grid="[10, 10]"
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
    >
      <!-- Background pattern -->
      <Background
        v-if="showBackground"
        :gap="20"
        :size="1"
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
    </VueFlow>
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

/* Circle node selection styles - use drop-shadow filter for circular glow */
/* Matches the old JS selection-manager.js behavior */
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.8))
    drop-shadow(0 0 4px rgba(102, 126, 234, 0.6));
}

/* Smooth transitions */
.vue-flow__node {
  transition:
    box-shadow 0.2s ease,
    filter 0.2s ease;
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
</style>
