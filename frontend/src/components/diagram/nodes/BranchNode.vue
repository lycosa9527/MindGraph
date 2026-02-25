<script setup lang="ts">
/**
 * BranchNode - Branch/child node for mind maps and tree maps
 * Represents branches, children, or categories in hierarchical diagrams
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import type { MindGraphNodeProps } from '@/types'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

// Get theme defaults matching old StyleManager
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

// Determine if this is a child node (deeper in hierarchy)
const isChild = computed(() => props.data.nodeType === 'branch' && props.data.parentId)

const defaultStyle = computed(() => getNodeStyle(isChild.value ? 'child' : 'branch'))

// Check if this is a tree map (needs vertical handles)
const isTreeMap = computed(() => props.data.diagramType === 'tree_map')

// Check if this is a bridge map node (should be text-only, including first pair)
const isBridgeMap = computed(() => props.data.diagramType === 'bridge_map')
const isFirstPair = computed(() => {
  if (!isBridgeMap.value) return true
  const pairIndex = props.data.pairIndex
  return pairIndex === undefined || pairIndex === 0
})

const nodeStyle = computed(() => {
  // For all bridge map nodes (including first pair), remove borders, background, and shadows (text-only)
  const shouldHaveBorder = !isBridgeMap.value
  const shouldHaveBackground = !isBridgeMap.value
  const shouldHaveShadow = !isBridgeMap.value

  return {
    backgroundColor: shouldHaveBackground
      ? props.data.style?.backgroundColor || defaultStyle.value.backgroundColor || '#e3f2fd'
      : 'transparent',
    borderColor: shouldHaveBorder
      ? props.data.style?.borderColor || defaultStyle.value.borderColor || '#4e79a7'
      : 'transparent',
    color: props.data.style?.textColor || defaultStyle.value.textColor || '#333333',
    fontFamily: props.data.style?.fontFamily,
    fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 16}px`,
    fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    borderWidth: shouldHaveBorder
      ? `${props.data.style?.borderWidth || defaultStyle.value.borderWidth || 2}px`
      : '0px',
    borderRadius: `${props.data.style?.borderRadius || 8}px`,
    boxShadow: shouldHaveShadow ? undefined : 'none',
  }
})

// Inline editing state
const isEditing = ref(false)

function handleTextSave(newText: string) {
  isEditing.value = false
  eventBus.emit('node:text_updated', {
    nodeId: props.id,
    text: newText,
  })
}

function handleEditCancel() {
  isEditing.value = false
}
</script>

<template>
  <div
    class="branch-node flex items-center justify-center px-4 py-2 cursor-grab select-none"
    :class="{
      'tree-map-node': isTreeMap,
      'border-none': isBridgeMap,
    }"
    :style="nodeStyle"
  >
    <InlineEditableText
      :text="data.label || ''"
      :node-id="id"
      :is-editing="isEditing"
      max-width="150px"
      text-align="center"
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />

    <!-- Connection handles for horizontal layouts (mind maps, etc.) -->
    <!-- Hide handles for bridge maps (connections handled by overlay) -->
    <Handle
      v-if="!isTreeMap && !isBridgeMap"
      id="left"
      type="target"
      :position="Position.Left"
      class="bg-blue-400!"
    />
    <Handle
      v-if="!isTreeMap && !isBridgeMap"
      id="right"
      type="source"
      :position="Position.Right"
      class="bg-blue-400!"
    />
    <!-- Right target handle for mindmap left-side children (RL direction) -->
    <Handle
      v-if="!isTreeMap && !isBridgeMap && (data.diagramType === 'mindmap' || data.diagramType === 'mind_map')"
      id="right-target"
      type="target"
      :position="Position.Right"
      class="bg-blue-400!"
    />
    <!-- Left source handle for mindmap left-side branches (RL direction) -->
    <Handle
      v-if="!isTreeMap && !isBridgeMap && (data.diagramType === 'mindmap' || data.diagramType === 'mind_map')"
      id="left-source"
      type="source"
      :position="Position.Left"
      class="bg-blue-400!"
    />

    <!-- Connection handles for tree maps (vertical layout) -->
    <Handle
      v-if="isTreeMap"
      type="target"
      :position="Position.Top"
      class="bg-blue-400!"
    />
    <Handle
      v-if="isTreeMap"
      type="source"
      :position="Position.Bottom"
      class="bg-blue-400!"
    />
  </div>
</template>

<style scoped>
.branch-node {
  min-width: 80px;
  min-height: 36px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  transition:
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

/* Tree map nodes have min-width for consistent vertical alignment (no fixed width for NodeResizer support) */
.branch-node.tree-map-node {
  min-width: 120px;
}

/* Bridge map nodes (all pairs): no shadow */
.branch-node.border-none {
  box-shadow: none !important;
}

.branch-node:hover:not(.border-none) {
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.12);
  border-color: #3b82f6;
}

.branch-node:active {
  cursor: grabbing;
}

/* Hide handle dots visually while keeping them functional */
.branch-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
