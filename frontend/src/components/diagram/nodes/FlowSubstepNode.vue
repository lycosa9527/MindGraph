<script setup lang="ts">
/**
 * FlowSubstepNode - Substep node for flow maps
 * Represents detailed sub-steps attached to main flow steps
 * Flow map: pill shape, mindmapColors (same as parent step), fixed size
 * Supports inline text editing on double-click
 */
import { computed, inject, ref } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramNodeTextReadonly } from '@/composables/diagram/useDiagramNodeTextReadonly'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { MIND_MAP_RAINBOW_TOPIC_COLORS } from '@/config/mindMapVibrantThemes'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import { isFlowMapSubstepNode } from '@/utils/flowMapIdentity'
import { resolveThinkingMapDisplayMaxWidthPx } from '@/utils/mindMapTextWrap'
import { paintNodeShape } from '@/utils/nodeShapeStyle'
import {
  THINKING_MAP_LEAF_TEXT,
  thinkingMapBorderWidth,
  thinkingMapBoxPadding,
  thinkingMapDisplayedFontSize,
} from '@/utils/thinkingMapChrome'
import { thinkingMapDisplayedNodeColors } from '@/utils/thinkingMapNodePaint'

import InlineEditableText from './InlineEditableText.vue'
import NodeShapeUnderline from './NodeShapeUnderline.vue'

const props = defineProps<MindGraphNodeProps>()
const diagramStore = useDiagramSession()
const isTextReadonly = useDiagramNodeTextReadonly(() => props.data.hidden === true)

const flowSubstepNodeRef = ref<HTMLElement | null>(null)
useNodeDimensions(flowSubstepNodeRef, props.id)

const isFlowMap = computed(() => props.data.diagramType === 'flow_map')
const groupColor = computed(() => {
  const idx = props.data.groupIndex as number | undefined
  return idx !== undefined && isFlowMap.value ? getMindmapBranchColor(idx) : null
})

const themeNodePaint = computed(() => {
  const node = props.data.originalNode
  if (!node) return null
  return thinkingMapDisplayedNodeColors(
    props.data.diagramType,
    diagramStore.data?._mindmap_theme,
    node,
    props.data.style,
    diagramStore.data?.connections
  )
})

const nodeStyle = computed(() => {
  const color = groupColor.value
  const borderColor =
    themeNodePaint.value?.borderColor ||
    props.data.style?.borderColor ||
    color?.border ||
    MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
  const borderWidth = thinkingMapBorderWidth(
    themeNodePaint.value?.borderWidth,
    props.data.style?.borderWidth,
    MIND_MAP_GEOMETRY.borderWidth
  )
  const borderStyle = props.data.style?.borderStyle || 'solid'
  const backgroundColor =
    themeNodePaint.value?.backgroundColor ||
    props.data.style?.backgroundColor ||
    color?.fill ||
    '#FFFFFF'
  const baseStyle = {
    backgroundColor,
    color: themeNodePaint.value?.textColor || props.data.style?.textColor || THINKING_MAP_LEAF_TEXT,
    fontFamily: props.data.style?.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${thinkingMapDisplayedFontSize(props.data.style?.fontSize, themeNodePaint.value?.fontSize ?? MIND_MAP_GEOMETRY.fontSize)}px`,
    padding: thinkingMapBoxPadding(true),
    boxShadow: MIND_MAP_GEOMETRY.branchShadow,
    fontWeight: props.data.style?.fontWeight || 'normal',
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
  }
  const shapedStyle = paintNodeShape(
    baseStyle,
    props.data.style?.nodeShape,
    borderColor,
    isFlowMap.value ? '9999px' : `${props.data.style?.borderRadius || 4.5}px`
  )
  if (props.data.style?.nodeShape === 'underline') {
    shapedStyle.minHeight = 0
    shapedStyle.boxShadow = 'none'
    shapedStyle.padding = '0'
  }
  if (isFlowMap.value) {
    return {
      ...shapedStyle,
      width: 'max-content',
      minWidth: '120px',
      minHeight:
        props.data.style?.nodeShape === 'underline' ? 0 : `${MIND_MAP_GEOMETRY.minHeight}px`,
      maxWidth: '230px',
    }
  }
  return shapedStyle
})

const SUBSTEP_MAX_TEXT_WIDTH = 180

const substepMaxWidth = computed(() => {
  if (!isFlowMap.value) return '140px'

  const label = ((props.data.label as string) || '').trim()
  const fontSize = parseFloat(nodeStyle.value.fontSize as string) || MIND_MAP_GEOMETRY.fontSize
  const fontWeight = String(nodeStyle.value.fontWeight || 'normal')
  const fontFamily = String(nodeStyle.value.fontFamily || '')
  return `${resolveThinkingMapDisplayMaxWidthPx(label, fontSize, SUBSTEP_MAX_TEXT_WIDTH, {
    fontWeight,
    fontFamily: fontFamily || undefined,
  })}px`
})

// Inline editing state
const isEditing = ref(false)

function handleTextSave(newText: string, textSecondary?: string) {
  isEditing.value = false
  eventBus.emit('node:text_updated', {
    nodeId: props.id,
    text: newText,
    ...(textSecondary !== undefined ? { textSecondary } : {}),
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

const supportsBranchMove = computed(
  () =>
    isFlowMap.value && isFlowMapSubstepNode({ id: props.id, type: props.type, data: props.data })
)

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
    ref="flowSubstepNodeRef"
    class="flow-substep-node relative flex items-center justify-center px-3 py-2 border-solid cursor-grab select-none"
    :class="{ 'pill-shape': isFlowMap }"
    :style="nodeStyle"
    @mousedown.capture="handleBranchMovePointerDown"
    @mouseup.capture="handleBranchMovePointerUp"
    @touchstart.passive.capture="handleBranchMoveTouchStart"
  >
    <NodeShapeUnderline
      v-if="data.style?.nodeShape === 'underline'"
      :color="
        themeNodePaint?.borderColor ||
        data.style?.borderColor ||
        groupColor?.border ||
        MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
      "
    />
    <InlineEditableText
      :text="data.label || ''"
      :readonly="isTextReadonly"
      :node-id="id"
      :is-editing="isEditing"
      :max-width="substepMaxWidth"
      :text-align="data.style?.textAlign || 'center'"
      :text-decoration="data.style?.textDecoration || 'none'"
      :truncate="!isFlowMap"
      :auto-wrap="isFlowMap"
      render-markdown
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />

    <!-- Connection handle on left side for step-to-substep (vertical layout) -->
    <Handle
      id="left"
      type="target"
      :position="Position.Left"
      class="bg-blue-400!"
    />
    <!-- Top handle for substeps below step (vertical layout) -->
    <Handle
      id="top-target"
      type="target"
      :position="Position.Top"
      class="bg-blue-400!"
    />
    <!-- Bottom handle for substeps above step (vertical layout) -->
    <Handle
      id="bottom-target"
      type="target"
      :position="Position.Bottom"
      class="bg-blue-400!"
    />
    <!-- Bottom source handle for main flow: connect from bottom substep to next step -->
    <Handle
      id="bottom-source"
      type="source"
      :position="Position.Bottom"
      class="bg-blue-400!"
    />
    <!-- Center handles for flow map: connect to node center (experiment to eliminate gap) -->
    <Handle
      id="center-target"
      type="target"
      :position="Position.Top"
      class="center-handle bg-blue-400!"
    />
    <Handle
      id="center-source"
      type="source"
      :position="Position.Top"
      class="center-handle bg-blue-400!"
    />
  </div>
</template>

<style scoped>
.flow-substep-node {
  width: max-content;
  min-width: 100px;
  min-height: 50px;
  overflow: visible;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  transition:
    box-shadow 0.2s ease,
    transform 0.15s ease;
}

.flow-substep-node.pill-shape {
  width: 120px;
  min-height: 48px;
  padding-left: 20px;
  padding-right: 20px;
}

.flow-substep-node:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  transform: translateY(-1px);
}

.flow-substep-node:active {
  cursor: grabbing;
  transform: translateY(0);
}

/* Hide handle dots visually while keeping them functional */
.flow-substep-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}

/* Center handle: position at node center */
.flow-substep-node :deep(.center-handle) {
  left: 50% !important;
  top: 50% !important;
  right: auto !important;
  bottom: auto !important;
  transform: translate(-50%, -50%);
}
</style>
