<script setup lang="ts">
/**
 * DiagramCanvas - Vue Flow wrapper for MindGraph diagrams
 * Provides unified interface for all diagram types with drag-drop, zoom, and pan
 */
import { computed, watch } from 'vue'

import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'

import { useTheme } from '@/composables/useTheme'
import { useDiagramStore } from '@/stores'
import type { MindGraphNode } from '@/types'

import BraceEdge from './edges/BraceEdge.vue'
// Import custom edge components
import CurvedEdge from './edges/CurvedEdge.vue'
import StraightEdge from './edges/StraightEdge.vue'
import BraceNode from './nodes/BraceNode.vue'
import BranchNode from './nodes/BranchNode.vue'
import BubbleNode from './nodes/BubbleNode.vue'
import FlowNode from './nodes/FlowNode.vue'
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

// Store
const diagramStore = useDiagramStore()

// Theme for background color
const { backgroundColor } = useTheme({
  diagramType: computed(() => diagramStore.type),
})

// Vue Flow instance
const { onNodesChange, onNodeClick, onNodeDoubleClick, onNodeDragStop, fitView } = useVueFlow()

// Custom node types registration
const nodeTypes = {
  topic: TopicNode,
  bubble: BubbleNode,
  branch: BranchNode,
  flow: FlowNode,
  brace: BraceNode,
  // Default fallbacks
  tree: BranchNode,
  bridge: BranchNode,
  circle: BubbleNode,
}

// Custom edge types registration
const edgeTypes = {
  curved: CurvedEdge,
  straight: StraightEdge,
  brace: BraceEdge,
  bridge: StraightEdge, // Use straight for bridge maps
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

// Fit view when nodes change
watch(
  () => nodes.value.length,
  () => {
    if (props.fitViewOnInit && nodes.value.length > 0) {
      setTimeout(() => fitView({ padding: 0.2 }), 100)
    }
  }
)
</script>

<template>
  <div class="diagram-canvas w-full h-full">
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
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
      :pan-on-scroll="true"
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

/* Custom node selection styles */
.vue-flow__node.selected {
  box-shadow: 0 0 0 2px #3b82f6;
}

/* Smooth transitions */
.vue-flow__node {
  transition: box-shadow 0.2s ease;
}
</style>
