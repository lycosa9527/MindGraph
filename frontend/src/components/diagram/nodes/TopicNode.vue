<script setup lang="ts">
/**
 * TopicNode - Central topic node for diagrams (non-draggable)
 * Used as the main/central node in bubble maps, mind maps, etc.
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

const defaultStyle = computed(() => getNodeStyle('topic'))

// Tree map and brace map use pill shape (fully rounded ends)
const isPillShape = computed(
  () => props.data.diagramType === 'tree_map' || props.data.diagramType === 'brace_map'
)
// Multi-flow map uses rounded rectangle
const isRoundedRectangle = computed(() => props.data.diagramType === 'multi_flow_map')

// Specific diagram type checks for handle positioning
const isTreeMap = computed(() => props.data.diagramType === 'tree_map')
const isBraceMap = computed(() => props.data.diagramType === 'brace_map')
const isMultiFlowMap = computed(() => props.data.diagramType === 'multi_flow_map')

// For multi-flow maps: get cause count to generate handles dynamically
const causeCount = computed(() => {
  if (!isMultiFlowMap.value) return 0
  return (props.data.causeCount as number) || 4 // Default to 4 if not specified
})

// For multi-flow maps: get effect count to generate handles dynamically
const effectCount = computed(() => {
  if (!isMultiFlowMap.value) return 0
  return (props.data.effectCount as number) || 4 // Default to 4 if not specified
})

// Generate handle positions for multi-flow map causes (evenly distributed)
const leftHandlePositions = computed(() => {
  if (causeCount.value === 0) return []
  const positions: Array<{ id: string; top: string }> = []
  for (let i = 0; i < causeCount.value; i++) {
    // Distribute evenly: for 4 causes, positions are at 20%, 40%, 60%, 80%
    const topPercent = ((i + 1) * 100) / (causeCount.value + 1)
    positions.push({
      id: `left-${i}`,
      top: `${topPercent}%`,
    })
  }
  return positions
})

// Generate handle positions for multi-flow map effects (evenly distributed)
const rightHandlePositions = computed(() => {
  if (effectCount.value === 0) return []
  const positions: Array<{ id: string; top: string }> = []
  for (let i = 0; i < effectCount.value; i++) {
    // Distribute evenly: for 4 effects, positions are at 20%, 40%, 60%, 80%
    const topPercent = ((i + 1) * 100) / (effectCount.value + 1)
    positions.push({
      id: `right-${i}`,
      top: `${topPercent}%`,
    })
  }
  return positions
})

const nodeStyle = computed(() => ({
  backgroundColor:
    props.data.style?.backgroundColor || defaultStyle.value.backgroundColor || '#1976d2',
  borderColor: props.data.style?.borderColor || defaultStyle.value.borderColor || '#0d47a1',
  color: props.data.style?.textColor || defaultStyle.value.textColor || '#ffffff',
  fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 18}px`,
  fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'bold',
  borderWidth: `${props.data.style?.borderWidth || defaultStyle.value.borderWidth || 3}px`,
  // Pill shape for tree map (9999px creates fully rounded ends)
  // Rounded rectangle for multi-flow map, circle for others
  borderRadius: isPillShape.value
    ? '9999px'
    : isRoundedRectangle.value
      ? `${props.data.style?.borderRadius || 8}px`
      : `${props.data.style?.borderRadius || 50}%`,
}))

// Inline editing state
const isEditing = ref(false)

function handleTextSave(newText: string) {
  isEditing.value = false
  // Emit event to update the node text in the store
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
    class="topic-node flex items-center justify-center px-6 py-4 border-solid cursor-default select-none"
    :class="{ 'pill-shape': isPillShape, 'rounded-rectangle': isRoundedRectangle }"
    :style="nodeStyle"
  >
    <InlineEditableText
      :text="data.label || ''"
      :node-id="id"
      :is-editing="isEditing"
      max-width="200px"
      text-align="center"
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />

    <!-- Connection handles for horizontal layouts (mind maps, bubble maps, etc.) -->
    <Handle
      v-if="!isPillShape && !isMultiFlowMap"
      type="source"
      :position="Position.Right"
      class="bg-blue-500!"
    />
    <Handle
      v-if="!isPillShape && !isMultiFlowMap"
      type="source"
      :position="Position.Left"
      class="bg-blue-500!"
    />
    <Handle
      v-if="!isPillShape && !isMultiFlowMap"
      type="source"
      :position="Position.Top"
      class="bg-blue-500!"
    />
    <Handle
      v-if="!isPillShape && !isMultiFlowMap"
      type="source"
      :position="Position.Bottom"
      class="bg-blue-500!"
    />

    <!-- Connection handle for tree maps (vertical layout - bottom only) -->
    <Handle
      v-if="isTreeMap"
      type="source"
      :position="Position.Bottom"
      class="bg-blue-500!"
    />

    <!-- Connection handle for brace maps (horizontal layout - right only) -->
    <Handle
      v-if="isBraceMap"
      type="source"
      :position="Position.Right"
      class="bg-blue-500!"
    />

    <!-- Connection handles for multi-flow maps (left target for causes, right source for effects) -->
    <!-- Dynamically generate left handles based on cause count, evenly distributed -->
    <template v-if="isMultiFlowMap">
      <Handle
        v-for="handle in leftHandlePositions"
        :id="handle.id"
        :key="handle.id"
        type="target"
        :position="Position.Left"
        :style="{ top: handle.top }"
        class="bg-blue-500!"
      />
    </template>
    <!-- Dynamically generate right handles based on effect count, evenly distributed -->
    <template v-if="isMultiFlowMap">
      <Handle
        v-for="handle in rightHandlePositions"
        :id="handle.id"
        :key="handle.id"
        type="source"
        :position="Position.Right"
        :style="{ top: handle.top }"
        class="bg-blue-500!"
      />
    </template>
  </div>
</template>

<style scoped>
.topic-node {
  min-width: 120px;
  min-height: 48px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: box-shadow 0.2s ease;
}

.topic-node:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

/* Tree map pill shape adjustments */
.topic-node.pill-shape {
  min-height: 40px;
  padding-left: 24px;
  padding-right: 24px;
}

/* Multi-flow map rounded rectangle adjustments */
.topic-node.rounded-rectangle {
  min-width: 140px;
  min-height: 50px;
}

/* Hide handle dots visually while keeping them functional */
.topic-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
