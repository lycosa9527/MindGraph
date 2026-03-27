<script setup lang="ts">
/**
 * BraceNode - Part node for brace maps
 * Represents parts in a part-whole relationship
 * Supports inline text editing on double-click
 * Uses mindmap branch color palette for part/subpart groups (like double bubble map)
 */
import { computed, inject, ref } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { eventBus } from '@/composables/core/useEventBus'
import { useTheme } from '@/composables/core/useTheme'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const braceNodeRef = ref<HTMLElement | null>(null)
useNodeDimensions(braceNodeRef, props.id)

// Get theme defaults matching old StyleManager
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const isWholeNode = computed(() => props.data.originalNode?.type === 'topic')
const _isPart = computed(() => !isWholeNode.value && !props.data.parentId)
const isSubpart = computed(() => !isWholeNode.value && !!props.data.parentId)

// Per-group color from mindmap palette (same as double bubble map / mindmap)
const groupColor = computed(() => {
  const idx = props.data.groupIndex as number | undefined
  return idx !== undefined ? getMindmapBranchColor(idx) : null
})

const defaultStyle = computed(() => {
  if (isWholeNode.value) return getNodeStyle('topic')
  if (isSubpart.value) return getNodeStyle('subpart')
  return getNodeStyle('part')
})

// Pill shape for part/subpart nodes to match topic (brace map uses pill for topic)
const usePillShape = computed(() => !isWholeNode.value)

const nodeStyle = computed(() => {
  const color = groupColor.value
  const borderColor =
    props.data.style?.borderColor ||
    color?.border ||
    defaultStyle.value.borderColor ||
    (isWholeNode.value ? '#0d47a1' : '#1976d2')
  const borderWidth =
    props.data.style?.borderWidth ||
    defaultStyle.value.borderWidth ||
    (isWholeNode.value ? 3 : isSubpart.value ? 1 : 2)
  const borderStyle = props.data.style?.borderStyle || 'solid'
  const backgroundColor =
    props.data.style?.backgroundColor ||
    color?.fill ||
    defaultStyle.value.backgroundColor ||
    (isWholeNode.value ? '#1976d2' : '#e3f2fd')

  return {
    backgroundColor,
    color:
      props.data.style?.textColor ||
      defaultStyle.value.textColor ||
      (isWholeNode.value ? '#ffffff' : '#333333'),
    fontFamily: props.data.style?.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || (isWholeNode.value ? 18 : isSubpart.value ? 12 : 16)}px`,
    fontWeight: isWholeNode.value
      ? 'bold'
      : props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
    borderRadius: usePillShape.value ? '9999px' : `${props.data.style?.borderRadius || 6}px`,
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

const supportsBranchMove = computed(() => !isWholeNode.value)

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
    ref="braceNodeRef"
    class="brace-node flex items-center justify-center px-4 py-2 border-solid cursor-grab select-none"
    :class="{ 'pill-shape': usePillShape }"
    :style="nodeStyle"
    @mousedown.capture="handleBranchMovePointerDown"
    @mouseup.capture="handleBranchMovePointerUp"
    @touchstart.capture="handleBranchMoveTouchStart"
  >
    <InlineEditableText
      :text="data.label || ''"
      :readonly="data.hidden === true"
      :node-id="id"
      :is-editing="isEditing"
      max-width="240px"
      :text-align="data.style?.textAlign || 'center'"
      :text-decoration="data.style?.textDecoration || 'none'"
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />

    <!-- Connection handles -->
    <Handle
      v-if="!isWholeNode"
      type="target"
      :position="Position.Left"
      class="!bg-slate-400"
    />
    <Handle
      type="source"
      :position="Position.Right"
      class="!bg-slate-400"
    />
  </div>
</template>

<style scoped>
.brace-node {
  min-width: 100px;
  min-height: 40px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.brace-node.pill-shape:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: scale(1.02);
}

/* Pill shape for part/subpart nodes (matches double bubble map appearance) */
.brace-node.pill-shape {
  min-height: 40px;
  padding-left: 20px;
  padding-right: 20px;
}

.brace-node.pill-shape:active {
  cursor: grabbing;
}

/* Hide handle dots visually while keeping them functional */
.brace-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
