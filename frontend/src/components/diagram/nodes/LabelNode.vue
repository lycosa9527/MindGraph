<script setup lang="ts">
/**
 * LabelNode - Text label node for dimension labels and annotations
 * Used for displaying classification dimensions in Tree Maps and Brace Maps
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'

import { eventBus } from '@/composables/useEventBus'
import type { MindGraphNodeProps } from '@/types'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const isPlaceholder = computed(() => props.data.isPlaceholder || !props.data.label)
const isBridgeDimension = computed(() => props.data.diagramType === 'bridge_map' && props.data.isDimensionLabel)

const nodeStyle = computed(() => {
  // For bridge map dimension labels, use different styling (no italic, bold, dark blue)
  const isBridgeDimension = props.data.diagramType === 'bridge_map' && props.data.isDimensionLabel
  
  return {
    color: isPlaceholder.value ? '#1976d2' : (isBridgeDimension ? '#1976d2' : '#1976d2'),
    opacity: isPlaceholder.value ? 0.4 : (isBridgeDimension ? 1 : 0.8),
    fontSize: `${props.data.style?.fontSize || (isBridgeDimension ? 14 : 14)}px`,
    fontStyle: isBridgeDimension ? 'normal' : 'italic',
    fontWeight: props.data.style?.fontWeight || (isBridgeDimension ? 'bold' : 'normal'),
    textAlign: isBridgeDimension ? 'right' : 'center', // Right aligned for bridge maps
    padding: isBridgeDimension ? '4px 8px' : '4px 8px',
  }
})

// For bridge maps, return two-line format
const bridgeMapDisplay = computed(() => {
  if (props.data.diagramType !== 'bridge_map' || !props.data.isDimensionLabel) {
    return null
  }
  
  // Detect language from label or diagram type
  const hasChinese = props.data.label
    ? /[\u4e00-\u9fa5]/.test(props.data.label)
    : /[\u4e00-\u9fa5]/.test(String(props.data.diagramType || ''))
  
  const labelText = hasChinese ? '类比关系:' : 'Analogy relationship:'
  
  // Wrap dimension value in brackets []
  // Strip existing brackets if present to avoid double brackets
  let rawValue = props.data.label?.trim() || ''
  if (rawValue.startsWith('[') && rawValue.endsWith(']')) {
    rawValue = rawValue.slice(1, -1) // Remove existing brackets
  }
  const valueText = rawValue
    ? `[${rawValue}]` // Add brackets around actual value
    : (hasChinese ? '[点击设置]' : '[Click to set]') // Placeholder already has brackets
  
  return {
    label: labelText,
    value: valueText,
    isPlaceholder: !rawValue,
  }
})

const displayText = computed(() => {
  // For bridge maps, return single string (will be handled separately in template)
  if (props.data.diagramType === 'bridge_map' && props.data.isDimensionLabel) {
    return props.data.label || ''
  }
  
  if (props.data.label) {
    // For other diagram types (tree_map, brace_map), show with prefix
    const hasChinese = /[\u4e00-\u9fa5]/.test(props.data.label)
    const prefix = hasChinese ? '分类维度' : 'Classification by'
    return `[${prefix}: ${props.data.label}]`
  }
  // Placeholder text
  const hasChinese = /[\u4e00-\u9fa5]/.test(String(props.data.diagramType || ''))
  return hasChinese ? '[分类维度: 点击填写...]' : '[Classification by: click to specify...]'
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
    class="label-node flex cursor-pointer"
    :class="{
      'items-center justify-center select-none': !isBridgeDimension,
      'flex-col items-end justify-center': isBridgeDimension,
    }"
    :style="nodeStyle"
  >
    <!-- Bridge map: two-line format -->
    <template v-if="isBridgeDimension && bridgeMapDisplay">
      <div class="label-line text-right select-none" style="line-height: 1.2; user-select: none;">
        {{ bridgeMapDisplay.label }}
      </div>
      <div class="value-line text-right" style="line-height: 1.2; margin-top: 2px;">
        <InlineEditableText
          :text="bridgeMapDisplay.value"
          :node-id="id"
          :is-editing="isEditing"
          max-width="180px"
          text-align="right"
          :text-class="bridgeMapDisplay.isPlaceholder ? 'opacity-60' : ''"
          @save="handleTextSave"
          @cancel="handleEditCancel"
          @edit-start="isEditing = true"
        />
      </div>
    </template>
    
    <!-- Other diagram types: single line -->
    <template v-else>
      <InlineEditableText
        :text="displayText"
        :node-id="id"
        :is-editing="isEditing"
        max-width="200px"
        text-align="center"
        text-class="whitespace-nowrap"
        @save="handleTextSave"
        @cancel="handleEditCancel"
        @edit-start="isEditing = true"
      />
    </template>
  </div>
</template>

<style scoped>
.label-node {
  min-width: 100px;
  min-height: 24px;
  transition: opacity 0.2s ease;
  font-family: 'Inter', 'Segoe UI', sans-serif;
}

.label-node:hover {
  opacity: 1 !important;
}
</style>
