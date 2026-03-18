<script setup lang="ts">
/**
 * ConceptNode - Concept map node with CmapTools-style link icon on selection
 * Used for both topic and concept nodes in concept_map diagrams
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { ElIcon } from 'element-plus'

import { Menu } from '@element-plus/icons-vue'

import { eventBus } from '@/composables/useEventBus'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { useTheme } from '@/composables/useTheme'
import type { MindGraphNodeProps } from '@/types'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const isTopic = computed(() => props.data.nodeType === 'topic')
const defaultStyle = computed(() => getNodeStyle(isTopic.value ? 'topic' : 'branch'))

const nodeStyle = computed(() => {
  const pillRadius = '9999px'
  if (isTopic.value) {
    const borderColor =
      props.data.style?.borderColor || defaultStyle.value.borderColor || '#35506b'
    const borderWidth =
      props.data.style?.borderWidth || defaultStyle.value.borderWidth || 3
    const borderStyle = props.data.style?.borderStyle || 'solid'
    const backgroundColor =
      props.data.style?.backgroundColor || defaultStyle.value.backgroundColor || '#e3f2fd'
    return {
      backgroundColor,
      color: props.data.style?.textColor || defaultStyle.value.textColor || '#000000',
      fontFamily: props.data.style?.fontFamily,
      fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 18}px`,
      fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'bold',
      fontStyle: props.data.style?.fontStyle || 'normal',
      textDecoration: props.data.style?.textDecoration || 'none',
      ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
        backgroundColor,
      }),
      borderRadius: pillRadius,
      boxShadow: '0 2px 6px rgba(0, 0, 0, 0.08)',
    }
  }
  const borderColor =
    props.data.style?.borderColor || defaultStyle.value.borderColor || '#4e79a7'
  const borderWidth =
    props.data.style?.borderWidth || defaultStyle.value.borderWidth || 2
  const borderStyle = props.data.style?.borderStyle || 'solid'
  const backgroundColor =
    props.data.style?.backgroundColor || defaultStyle.value.backgroundColor || '#e3f2fd'
  return {
    backgroundColor,
    color: props.data.style?.textColor || defaultStyle.value.textColor || '#333333',
    fontFamily: props.data.style?.fontFamily,
    fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 16}px`,
    fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
    borderRadius: pillRadius,
    boxShadow: '0 2px 6px rgba(0, 0, 0, 0.08)',
  }
})

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

const CONCEPT_LINK_DATA_TYPE = 'application/mindgraph-concept-link'

function handleLinkDragStart(event: DragEvent) {
  if (!event.dataTransfer) return
  event.dataTransfer.setData(CONCEPT_LINK_DATA_TYPE, props.id)
  event.dataTransfer.effectAllowed = 'copy'
  event.dataTransfer.setDragImage(new Image(), 0, 0)
  eventBus.emit('concept_map:link_drag_start', { sourceId: props.id })
}

function handleLinkDragEnd() {
  eventBus.emit('concept_map:link_drag_end', {})
}

function handleLinkDragOver(event: DragEvent) {
  const hasLinkData = event.dataTransfer?.types.includes(CONCEPT_LINK_DATA_TYPE)
  if (hasLinkData) {
    event.preventDefault()
    event.dataTransfer!.dropEffect = 'copy'
  }
}

function handleLinkDrop(event: DragEvent) {
  const sourceId = event.dataTransfer?.getData(CONCEPT_LINK_DATA_TYPE)
  if (!sourceId || sourceId === props.id) return
  event.preventDefault()
  event.stopPropagation()
  eventBus.emit('concept_map:link_drop', { sourceId, targetId: props.id })
}

</script>

<template>
  <div
    class="concept-node-wrapper relative"
    @dragover="handleLinkDragOver"
    @drop="handleLinkDrop"
  >
    <!-- Menu icon - for link creation only (drag to another node). nodrag prevents node drag when dragging from icon. Container has pointer-events:none so clicks pass through to node body for select/reposition; icon has pointer-events:auto for drag. -->
    <div
      v-show="selected && !isEditing"
      class="concept-link-icon absolute left-1/2"
    >
      <ElIcon
        :size="20"
        class="text-blue-500 concept-link-icon-inner nodrag"
        draggable="true"
        :data-node-id="id"
        @dragstart="handleLinkDragStart"
        @dragend="handleLinkDragEnd"
      >
        <Menu />
      </ElIcon>
    </div>

    <div
      class="concept-node concept-node-pill flex items-center justify-center px-4 py-2 cursor-grab select-none border-solid"
      :class="{ 'concept-topic': isTopic }"
      :style="nodeStyle"
    >
      <!-- Primary handles: centered on each side -->
      <Handle
        id="source-left"
        type="source"
        :position="Position.Left"
      />
      <Handle
        id="target-left"
        type="target"
        :position="Position.Left"
      />
      <Handle
        id="source-right"
        type="source"
        :position="Position.Right"
      />
      <Handle
        id="target-right"
        type="target"
        :position="Position.Right"
      />
      <Handle
        id="source-top"
        type="source"
        :position="Position.Top"
      />
      <Handle
        id="target-top"
        type="target"
        :position="Position.Top"
      />
      <Handle
        id="source-bottom"
        type="source"
        :position="Position.Bottom"
      />
      <Handle
        id="target-bottom"
        type="target"
        :position="Position.Bottom"
      />
      <!-- Split handles: offset from center for mixed arrow/no-arrow separation -->
      <!-- -2 handles: offset toward start (up for L/R, left for T/B) -->
      <Handle
        id="source-left-2"
        type="source"
        :position="Position.Left"
        :style="{ top: 'calc(50% - 8px)' }"
      />
      <Handle
        id="target-left-2"
        type="target"
        :position="Position.Left"
        :style="{ top: 'calc(50% - 8px)' }"
      />
      <Handle
        id="source-right-2"
        type="source"
        :position="Position.Right"
        :style="{ top: 'calc(50% - 8px)' }"
      />
      <Handle
        id="target-right-2"
        type="target"
        :position="Position.Right"
        :style="{ top: 'calc(50% - 8px)' }"
      />
      <Handle
        id="source-top-2"
        type="source"
        :position="Position.Top"
        :style="{ left: 'calc(50% - 8px)' }"
      />
      <Handle
        id="target-top-2"
        type="target"
        :position="Position.Top"
        :style="{ left: 'calc(50% - 8px)' }"
      />
      <Handle
        id="source-bottom-2"
        type="source"
        :position="Position.Bottom"
        :style="{ left: 'calc(50% - 8px)' }"
      />
      <Handle
        id="target-bottom-2"
        type="target"
        :position="Position.Bottom"
        :style="{ left: 'calc(50% - 8px)' }"
      />
      <!-- -3 handles: offset toward end (down for L/R, right for T/B) -->
      <Handle
        id="source-left-3"
        type="source"
        :position="Position.Left"
        :style="{ top: 'calc(50% + 8px)' }"
      />
      <Handle
        id="target-left-3"
        type="target"
        :position="Position.Left"
        :style="{ top: 'calc(50% + 8px)' }"
      />
      <Handle
        id="source-right-3"
        type="source"
        :position="Position.Right"
        :style="{ top: 'calc(50% + 8px)' }"
      />
      <Handle
        id="target-right-3"
        type="target"
        :position="Position.Right"
        :style="{ top: 'calc(50% + 8px)' }"
      />
      <Handle
        id="source-top-3"
        type="source"
        :position="Position.Top"
        :style="{ left: 'calc(50% + 8px)' }"
      />
      <Handle
        id="target-top-3"
        type="target"
        :position="Position.Top"
        :style="{ left: 'calc(50% + 8px)' }"
      />
      <Handle
        id="source-bottom-3"
        type="source"
        :position="Position.Bottom"
        :style="{ left: 'calc(50% + 8px)' }"
      />
      <Handle
        id="target-bottom-3"
        type="target"
        :position="Position.Bottom"
        :style="{ left: 'calc(50% + 8px)' }"
      />
      <InlineEditableText
        :text="data.label || ''"
        :readonly="data.hidden === true"
        :node-id="id"
        :is-editing="isEditing"
        :max-width="isTopic ? '300px' : '150px'"
        text-align="center"
        :text-decoration="data.style?.textDecoration || 'none'"
        placeholder="输入文本..."
        @save="handleTextSave"
        @cancel="handleEditCancel"
        @edit-start="isEditing = true"
      />
    </div>
  </div>
</template>

<style scoped>
.concept-node-wrapper {
  transform: translate(0, 0);
}

.concept-link-icon {
  bottom: 100%;
  margin-bottom: 1px;
  transform: translateX(-50%);
  z-index: 10;
  /* Let clicks pass through transparent area so overlapping nodes can be selected */
  pointer-events: none;
}

.concept-link-icon-inner {
  pointer-events: auto;
  cursor: grab;
}

.concept-link-icon-inner:active {
  cursor: grabbing;
}

.concept-node {
  min-width: 80px;
  min-height: 36px;
  transition:
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.concept-node.concept-topic {
  min-width: 120px;
  min-height: 48px;
  padding-left: 24px;
  padding-right: 24px;
}

.concept-node.concept-node-pill {
  padding-left: 20px;
  padding-right: 20px;
}

.concept-node:active {
  cursor: grabbing;
}

/* Hide handle dots visually while keeping them functional for smart routing */
.concept-node-wrapper :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
