<script setup lang="ts">
/**
 * CircleNode - Perfect circular node for Circle Maps, Bubble Maps
 * Used for both topic and context nodes in circle/bubble maps
 * Always renders as a perfect circle regardless of content
 * Supports inline text editing on double-click
 * Adapts size based on text length
 * Uses mindmap branch color palette for context nodes (like double bubble map)
 */
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { eventBus } from '@/composables/core/useEventBus'
import { useTheme } from '@/composables/core/useTheme'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import { useDiagramStore } from '@/stores'
import { TOPIC_FONT_SIZE } from '@/stores/specLoader/textMeasurement'
import { calculateAdaptiveCircleSize, getTopicCircleDiameter } from '@/stores/specLoader/utils'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()
const diagramStore = useDiagramStore()

const circleNodeRef = ref<HTMLElement | null>(null)
useNodeDimensions(circleNodeRef, props.id)

// Get theme defaults
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

// Determine if this is a topic or context node
const isTopicNode = computed(() => props.data.nodeType === 'topic')

// Circular topic (circle_map / bubble_map / double_bubble_map center) – use content-width block centering
const isCircularTopic = computed(
  () =>
    (diagramStore.type === 'circle_map' ||
      diagramStore.type === 'bubble_map' ||
      diagramStore.type === 'double_bubble_map') &&
    isTopicNode.value
)

// Double bubble map similarity/diff nodes render as capsule (pill)
const isCapsuleNode = computed(
  () => diagramStore.type === 'double_bubble_map' && !isTopicNode.value
)

// Double bubble map: show handles for curved edge connections at node boundary
const isDoubleBubbleMap = computed(() => diagramStore.type === 'double_bubble_map')
const capsuleWidth = computed(() => props.data.style?.width ?? circleSize.value)
const capsuleHeight = computed(() => props.data.style?.height ?? circleSize.value)

// Use 'context' for circle map context nodes (not 'bubble')
const defaultStyle = computed(() => getNodeStyle(isTopicNode.value ? 'topic' : 'context'))

// Per-group color from mindmap palette for bubble_map / circle_map context nodes
const groupColor = computed(() => {
  const idx = props.data.groupIndex as number | undefined
  if (idx === undefined) return null
  const isContext = diagramStore.type === 'bubble_map' || diagramStore.type === 'circle_map'
  return isContext && !isTopicNode.value ? getMindmapBranchColor(idx) : null
})

// Get the circle size from data or calculate adaptively based on text length
// Topic node (circle_map / bubble_map): single-line, size from text measurement (same as layout)
// Context node: adaptive size from character bands
const circleSize = computed(() => {
  if (props.data.style?.size) {
    return props.data.style.size
  }
  const text = props.data.label || ''
  const isRadialTopic =
    (diagramStore.type === 'circle_map' || diagramStore.type === 'bubble_map') && isTopicNode.value
  if (isRadialTopic) {
    return getTopicCircleDiameter(text)
  }
  return calculateAdaptiveCircleSize(text, isTopicNode.value)
})

// Watch for text changes and update node size in store (topic nodes in circle_map / bubble_map)
watch(
  () => props.data.label,
  (newText) => {
    const isRadialTopic =
      (diagramStore.type === 'circle_map' || diagramStore.type === 'bubble_map') &&
      isTopicNode.value
    if (isRadialTopic) {
      const adaptiveSize = getTopicCircleDiameter(newText || '')
      nextTick(() => {
        diagramStore.saveNodeStyle(props.id, { size: adaptiveSize })
      })
    }
  }
)

// Listen for text_updated event to recalculate size (topic/context in circle_map / bubble_map)
function handleTextUpdated(payload: { nodeId: string; text: string }) {
  const isRadial = diagramStore.type === 'circle_map' || diagramStore.type === 'bubble_map'
  if (payload.nodeId !== props.id || !isRadial) return
  const adaptiveSize = isTopicNode.value
    ? getTopicCircleDiameter(payload.text)
    : calculateAdaptiveCircleSize(payload.text, false)
  nextTick(() => {
    diagramStore.saveNodeStyle(payload.nodeId, { size: adaptiveSize })
  })
}

onMounted(() => {
  eventBus.on('node:text_updated', handleTextUpdated)
})

onUnmounted(() => {
  eventBus.off('node:text_updated', handleTextUpdated)
})

// Symmetric inner width for text: circleSize or capsule width minus both borders (topic 3px, context 2px)
const topicBorderPx = 3
const contextBorderPx = 2
const textMaxWidth = computed(() => {
  const size = isCapsuleNode.value ? capsuleWidth.value : circleSize.value
  return size - 2 * (isTopicNode.value ? topicBorderPx : contextBorderPx)
})

// Circle Map colors matching old JS bubble-map-renderer.js THEME
// Topic: fill #1976d2 (blue), text #fff, stroke #0d47a1, strokeWidth 3
// Context: per-group colors from mindmap palette (bubble_map, circle_map)
const nodeStyle = computed(() => {
  const width = isCapsuleNode.value ? capsuleWidth.value : circleSize.value
  const height = isCapsuleNode.value ? capsuleHeight.value : circleSize.value
  const color = groupColor.value
  const borderColor =
    props.data.style?.borderColor ||
    color?.border ||
    defaultStyle.value.borderColor ||
    (isTopicNode.value ? '#0d47a1' : '#1976d2')
  const borderWidth =
    props.data.style?.borderWidth || defaultStyle.value.borderWidth || (isTopicNode.value ? 3 : 2)
  const borderStyle = props.data.style?.borderStyle || 'solid'
  const backgroundColor =
    props.data.style?.backgroundColor ||
    color?.fill ||
    defaultStyle.value.backgroundColor ||
    (isTopicNode.value ? '#1976d2' : '#e3f2fd')

  return {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
    ...(isCapsuleNode.value ? { borderRadius: '9999px' } : {}),
    backgroundColor,
    color:
      props.data.style?.textColor ||
      defaultStyle.value.textColor ||
      (isTopicNode.value ? '#ffffff' : '#333333'),
    fontFamily: props.data.style?.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${props.data.style?.fontSize ?? ((diagramStore.type === 'circle_map' || diagramStore.type === 'bubble_map') && isTopicNode.value ? TOPIC_FONT_SIZE : (defaultStyle.value.fontSize ?? (isTopicNode.value ? 20 : 14)))}px`,
    fontWeight:
      props.data.style?.fontWeight ||
      defaultStyle.value.fontWeight ||
      (isTopicNode.value ? 'bold' : 'normal'),
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
  }
})

// Inline editing state
const isEditing = ref(false)

function handleTextSave(newText: string) {
  isEditing.value = false
  const isRadialTopic =
    (diagramStore.type === 'circle_map' || diagramStore.type === 'bubble_map') && isTopicNode.value
  if (isRadialTopic) {
    diagramStore.saveNodeStyle(props.id, { size: getTopicCircleDiameter(newText) })
  }
  eventBus.emit('node:text_updated', {
    nodeId: props.id,
    text: newText,
  })
}

function handleEditCancel() {
  isEditing.value = false
}

const branchMove = inject<{
  onBranchMovePointerDown: (
    nodeId: string,
    isEditing: boolean,
    clientX?: number,
    clientY?: number,
    fromTouch?: boolean
  ) => boolean
  onBranchMovePointerUp: () => void
}>('branchMove', { onBranchMovePointerDown: () => false, onBranchMovePointerUp: () => {} })

const supportsBranchMove = computed(() => {
  if (isTopicNode.value) return false
  const dt = diagramStore.type
  if (dt === 'bubble_map') return props.id?.startsWith('bubble-')
  if (dt === 'circle_map') return props.id?.startsWith('context-')
  if (dt === 'double_bubble_map') {
    return (
      props.id?.startsWith('similarity-') ||
      props.id?.startsWith('left-diff-') ||
      props.id?.startsWith('right-diff-')
    )
  }
  return false
})

function handleBranchMovePointerDown(event: MouseEvent): void {
  if (supportsBranchMove.value) {
    branchMove.onBranchMovePointerDown(props.id, isEditing.value, event.clientX, event.clientY)
  }
}

function handleBranchMoveTouchStart(event: TouchEvent): void {
  if (!supportsBranchMove.value || event.touches.length !== 1) return
  const touch = event.touches[0]
  const consumed = branchMove.onBranchMovePointerDown(
    props.id,
    isEditing.value,
    touch.clientX,
    touch.clientY,
    true
  )
  if (consumed) {
    event.stopPropagation()
    event.preventDefault()
  }
}

function handleBranchMovePointerUp(): void {
  if (supportsBranchMove.value) {
    branchMove.onBranchMovePointerUp()
  }
}
</script>

<template>
  <div
    ref="circleNodeRef"
    class="circle-node flex items-center justify-center rounded-full border-solid select-none"
    :class="[
      isTopicNode ? 'cursor-default' : 'cursor-grab',
      isTopicNode ? 'topic-circle' : 'context-circle',
      isCapsuleNode ? 'circle-node--capsule' : '',
      isDoubleBubbleMap ? 'circle-node--with-handles' : '',
    ]"
    :style="nodeStyle"
    @mousedown.capture="handleBranchMovePointerDown"
    @mouseup.capture="handleBranchMovePointerUp"
    @touchstart.capture="handleBranchMoveTouchStart"
  >
    <!-- Handles for double bubble map curved edges (connect at node boundary) -->
    <template v-if="isDoubleBubbleMap">
      <Handle
        id="left"
        :position="Position.Left"
      />
      <Handle
        id="right"
        :position="Position.Right"
      />
      <Handle
        id="top"
        :position="Position.Top"
      />
      <Handle
        id="bottom"
        :position="Position.Bottom"
      />
    </template>
    <div
      class="circle-node__text-wrapper"
      :class="{ 'circle-node__text-wrapper--nowrap': diagramStore.type === 'double_bubble_map' }"
    >
      <InlineEditableText
        :text="data.label || ''"
        :node-id="id"
        :is-editing="isEditing"
        :readonly="data.hidden === true"
        :max-width="`${textMaxWidth}px`"
        text-align="center"
        :text-decoration="data.style?.textDecoration || 'none'"
        :text-class="isTopicNode ? 'py-2' : 'px-2 py-1'"
        :full-width="isTopicNode"
        :center-block-in-circle="isCircularTopic"
        :no-wrap="
          diagramStore.type === 'circle_map' ||
          diagramStore.type === 'bubble_map' ||
          diagramStore.type === 'double_bubble_map' ||
          !!data.style?.noWrap
        "
        :truncate="false"
        @save="handleTextSave"
        @cancel="handleEditCancel"
        @edit-start="isEditing = true"
      />
    </div>
  </div>
</template>

<style scoped>
.circle-node {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;
  flex-shrink: 0;
}

.circle-node:not(.circle-node--capsule) {
  aspect-ratio: 1;
}

.circle-node__text-wrapper {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  min-width: 0;
}

.circle-node__text-wrapper--nowrap {
  white-space: nowrap;
}

.context-circle:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: scale(1.02);
}

.context-circle:active {
  cursor: grabbing;
}

.topic-circle {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 10;
}

.topic-circle:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

/* Hide handle dots for double bubble map (handles are for connection points only) */
.circle-node--with-handles :deep(.vue-flow__handle) {
  width: 0;
  height: 0;
  border: none;
  background: transparent;
}
</style>
