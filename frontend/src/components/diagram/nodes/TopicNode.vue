<script setup lang="ts">
/**
 * TopicNode - Central topic node for diagrams (non-draggable)
 * Used as the main/central node in bubble maps, mind maps, etc.
 * Supports inline text editing on double-click
 */
import { computed, nextTick, ref } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

// Get theme defaults matching old StyleManager
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const defaultStyle = computed(() => getNodeStyle('topic'))

// Tree map, brace map, and mindmap use pill shape (fully rounded ends)
const isPillShape = computed(
  () =>
    props.data.diagramType === 'tree_map' ||
    props.data.diagramType === 'brace_map' ||
    props.data.diagramType === 'mindmap' ||
    props.data.diagramType === 'mind_map'
)
// Multi-flow map and flow map use rounded rectangle
const isRoundedRectangle = computed(
  () => props.data.diagramType === 'multi_flow_map' || props.data.diagramType === 'flow_map'
)
// Flow map: main topic with single handle (right for horizontal, bottom for vertical)
const isFlowMap = computed(() => props.data.diagramType === 'flow_map')
const flowMapOrientation = computed(
  () => (props.data.orientation as 'horizontal' | 'vertical') || 'horizontal'
)

// Specific diagram type checks for handle positioning
const isTreeMap = computed(() => props.data.diagramType === 'tree_map')
const isBraceMap = computed(() => props.data.diagramType === 'brace_map')
const isMultiFlowMap = computed(() => props.data.diagramType === 'multi_flow_map')
const isMindMap = computed(() => props.data.diagramType === 'mindmap')

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

// For mindmaps: get total branch count for left/right handle distribution
const totalBranchCount = computed(() => {
  if (!isMindMap.value) return 0
  return (props.data.totalBranchCount as number) || 0
})

// Mindmap handles: only left and right edges, evenly distributed along each edge
const mindMapHandlePositions = computed(() => {
  if (totalBranchCount.value === 0) {
    return { right: [], left: [] }
  }

  const total = totalBranchCount.value
  const midPoint = Math.ceil(total / 2)
  const rightCount = midPoint
  const leftCount = total - midPoint

  const generateHandles = (count: number, prefix: string) => {
    const handles: Array<{ id: string; top: string; transform: string }> = []
    for (let i = 0; i < count; i++) {
      const topPercent = ((i + 1) / (count + 1)) * 100
      handles.push({
        id: `${prefix}-${i}`,
        top: `${topPercent}%`,
        transform: 'translateY(-50%)',
      })
    }
    return handles
  }

  return {
    right: generateHandles(rightCount, 'mindmap-right'),
    left: generateHandles(leftCount, 'mindmap-left'),
  }
})

const nodeStyle = computed(() => {
  const borderColor = props.data.style?.borderColor || defaultStyle.value.borderColor || '#0d47a1'
  const borderWidth = props.data.style?.borderWidth || defaultStyle.value.borderWidth || 3
  const borderStyle = props.data.style?.borderStyle || 'solid'
  const backgroundColor =
    props.data.style?.backgroundColor || defaultStyle.value.backgroundColor || '#1976d2'

  const baseStyle = {
    backgroundColor,
    color: props.data.style?.textColor || defaultStyle.value.textColor || '#ffffff',
    fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 18}px`,
    fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'bold',
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
    // Pill shape for tree map (9999px creates fully rounded ends)
    // Rounded rectangle for multi-flow map, circle for others
    borderRadius: isPillShape.value
      ? '9999px'
      : isRoundedRectangle.value
        ? `${props.data.style?.borderRadius || 8}px`
        : `${props.data.style?.borderRadius || 50}%`,
  }

  // Add dynamic width when editing (only for multi-flow map)
  if (isMultiFlowMap.value && dynamicWidth.value !== null) {
    return {
      ...baseStyle,
      width: `${dynamicWidth.value}px`,
      minWidth: `${dynamicWidth.value}px`,
      transition: 'width 0.2s ease',
    }
  }

  // Set default width for multi-flow map topic nodes (optimized for "事件")
  if (isMultiFlowMap.value && dynamicWidth.value === null) {
    return {
      ...baseStyle,
      width: '90px',
      minWidth: '90px',
    }
  }

  // Flow map topic: fixed width for layout consistency
  if (isFlowMap.value) {
    return {
      ...baseStyle,
      width: '120px',
      minWidth: '120px',
    }
  }

  return baseStyle
})

// Inline editing state
const isEditing = ref(false)

// Dynamic width for editing (only for multi-flow map)
const dynamicWidth = ref<number | null>(null)
const topicNodeRef = ref<HTMLDivElement | null>(null)

function handleTextSave(newText: string) {
  isEditing.value = false
  dynamicWidth.value = null // Reset width after saving
  // Emit event to update the node text in the store
  eventBus.emit('node:text_updated', {
    nodeId: props.id,
    text: newText,
  })
  // Trigger layout recalculation for multi-flow map
  if (isMultiFlowMap.value) {
    nextTick(() => {
      eventBus.emit('multi_flow_map:topic_width_changed', {
        nodeId: props.id,
        width: topicNodeRef.value?.offsetWidth || null,
      })
    })
  }
}

function handleEditCancel() {
  isEditing.value = false
  dynamicWidth.value = null // Reset width after canceling
}

function handleWidthChange(width: number) {
  // Update node width dynamically as user types (only for multi-flow map)
  if (isMultiFlowMap.value) {
    // Add padding to account for node padding (px-6 = 24px on each side = 48px total)
    dynamicWidth.value = width + 48

    // Emit width change event to trigger layout recalculation (both causes and effects reposition)
    // Use nextTick + setTimeout to ensure DOM has fully updated before measuring
    nextTick(() => {
      setTimeout(() => {
        if (topicNodeRef.value) {
          const actualWidth = topicNodeRef.value.offsetWidth
          eventBus.emit('multi_flow_map:topic_width_changed', {
            nodeId: props.id,
            width: actualWidth,
          })
        }
      }, 100)
    })
  }
}
</script>

<template>
  <div
    ref="topicNodeRef"
    class="topic-node flex items-center justify-center px-6 py-4 border-solid cursor-default select-none"
    :class="{
      'pill-shape': isPillShape,
      'rounded-rectangle': isRoundedRectangle,
      'multi-flow-map-node': isMultiFlowMap,
      'flow-map-topic-node': isFlowMap,
    }"
    :style="nodeStyle"
  >
    <InlineEditableText
      :text="data.label || ''"
      :node-id="id"
      :is-editing="isEditing"
      :readonly="data.hidden === true"
      max-width="300px"
      text-align="center"
      :text-decoration="data.style?.textDecoration || 'none'"
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
      @width-change="handleWidthChange"
    />

    <!-- Connection handles for horizontal layouts (bubble maps, etc.) -->
    <!-- Mindmaps use dynamic handles below, so exclude them here -->
    <!-- Flow map uses single handle below, so exclude it here -->
    <Handle
      v-if="!isPillShape && !isMultiFlowMap && !isMindMap && !isFlowMap"
      type="source"
      :position="Position.Right"
      class="bg-blue-500!"
    />
    <Handle
      v-if="!isPillShape && !isMultiFlowMap && !isMindMap && !isFlowMap"
      type="source"
      :position="Position.Left"
      class="bg-blue-500!"
    />
    <Handle
      v-if="!isPillShape && !isMultiFlowMap && !isMindMap && !isFlowMap"
      type="source"
      :position="Position.Top"
      class="bg-blue-500!"
    />
    <Handle
      v-if="!isPillShape && !isMultiFlowMap && !isMindMap && !isFlowMap"
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

    <!-- Flow map: single handle at right center (horizontal) or bottom center (vertical) -->
    <Handle
      v-if="isFlowMap && flowMapOrientation === 'horizontal'"
      id="right"
      type="source"
      :position="Position.Right"
      :style="{ top: '50%', transform: 'translateY(-50%)' }"
      class="bg-blue-500!"
    />
    <Handle
      v-if="isFlowMap && flowMapOrientation === 'vertical'"
      id="bottom"
      type="source"
      :position="Position.Bottom"
      :style="{ left: '50%', transform: 'translateX(-50%)' }"
      class="bg-blue-500!"
    />

    <!-- Connection handles for mindmaps: left and right edges, evenly distributed -->
    <template v-if="isMindMap">
      <Handle
        v-for="handle in mindMapHandlePositions.right"
        :id="handle.id"
        :key="handle.id"
        type="source"
        :position="Position.Right"
        :style="{ top: handle.top, transform: handle.transform }"
        class="bg-blue-500!"
      />
    </template>
    <template v-if="isMindMap">
      <Handle
        v-for="handle in mindMapHandlePositions.left"
        :id="handle.id"
        :key="handle.id"
        type="source"
        :position="Position.Left"
        :style="{ top: handle.top, transform: handle.transform }"
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
