<script setup lang="ts">
/**
 * ConceptNode - Concept map node with CmapTools-style link icon on selection
 * Used for both topic and concept nodes in concept_map diagrams
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'

import { ElIcon } from 'element-plus'
import { Menu } from '@element-plus/icons-vue'
import { Handle, Position } from '@vue-flow/core'

import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import type { MindGraphNodeProps } from '@/types'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const isTopic = computed(() => props.data.nodeType === 'topic')
const defaultStyle = computed(() =>
  getNodeStyle(isTopic.value ? 'topic' : 'branch')
)

const nodeStyle = computed(() => {
  const pillRadius = '9999px'
  if (isTopic.value) {
    return {
      backgroundColor:
        props.data.style?.backgroundColor ||
        defaultStyle.value.backgroundColor ||
        '#e3f2fd',
      borderColor:
        props.data.style?.borderColor ||
        defaultStyle.value.borderColor ||
        '#35506b',
      color: props.data.style?.textColor || defaultStyle.value.textColor || '#000000',
      fontFamily: props.data.style?.fontFamily,
      fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 18}px`,
      fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'bold',
      fontStyle: props.data.style?.fontStyle || 'normal',
      textDecoration: props.data.style?.textDecoration || 'none',
      borderWidth: `${props.data.style?.borderWidth || defaultStyle.value.borderWidth || 3}px`,
      borderRadius: pillRadius,
      boxShadow: '0 2px 6px rgba(0, 0, 0, 0.08)',
    }
  }
  return {
    backgroundColor:
      props.data.style?.backgroundColor ||
      defaultStyle.value.backgroundColor ||
      '#e3f2fd',
    borderColor:
      props.data.style?.borderColor ||
      defaultStyle.value.borderColor ||
      '#4e79a7',
    color: props.data.style?.textColor || defaultStyle.value.textColor || '#333333',
    fontFamily: props.data.style?.fontFamily,
    fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 16}px`,
    fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    borderWidth: `${props.data.style?.borderWidth || defaultStyle.value.borderWidth || 2}px`,
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
    <!-- Menu icon - appears when node is selected (click). nodrag prevents Vue Flow from moving the node when dragging from icon. -->
    <div
      v-show="selected && !isEditing"
      class="concept-link-icon nodrag absolute left-1/2 cursor-grab active:cursor-grabbing"
      draggable="true"
      :data-node-id="id"
      @dragstart="handleLinkDragStart"
    >
      <ElIcon :size="20" class="text-blue-500">
        <Menu />
      </ElIcon>
    </div>

    <div
      class="concept-node concept-node-pill flex items-center justify-center px-4 py-2 cursor-grab select-none border-solid"
      :class="{ 'concept-topic': isTopic }"
      :style="nodeStyle"
    >
      <!-- Handles for smart connection routing (edges pick closest side) -->
      <Handle type="source" id="source-left" :position="Position.Left" />
      <Handle type="target" id="target-left" :position="Position.Left" />
      <Handle type="source" id="source-right" :position="Position.Right" />
      <Handle type="target" id="target-right" :position="Position.Right" />
      <Handle type="source" id="source-top" :position="Position.Top" />
      <Handle type="target" id="target-top" :position="Position.Top" />
      <Handle type="source" id="source-bottom" :position="Position.Bottom" />
      <Handle type="target" id="target-bottom" :position="Position.Bottom" />
      <InlineEditableText
        :text="data.label || ''"
        :node-id="id"
        :is-editing="isEditing"
        :max-width="isTopic ? '300px' : '150px'"
        text-align="center"
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
