<script setup lang="ts">
/**
 * LabelNode - Text label node for dimension labels and annotations
 * Tree Maps: classification dimension (分类维度); Brace Maps: decomposition dimension (拆解维度)
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'
import type { CSSProperties } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { translateDimension, useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { useUIStore } from '@/stores'
import type { MindGraphNodeProps } from '@/types'
import {
  BRIDGE_DIMENSION_LABEL_FONT_PX,
  bridgeDimensionLabelText,
  measureBridgeDimensionLabel,
} from '@/utils/bridgeMapLabelLayout'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import { resolveThinkingMapDisplayMaxWidthPx } from '@/utils/mindMapTextWrap'
import {
  thinkingMapAdaptiveTextColor,
  thinkingMapStructureColor,
} from '@/utils/thinkingMapConnectionStroke'
import {
  TREE_MAP_DIMENSION_LABEL_FONT_PX,
  TREE_MAP_DIMENSION_LABEL_MAX_TEXT_PX,
  thinkingMapDimensionLabelDisplayText,
} from '@/utils/treeMapLabelLayout'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const { t } = useLanguage()
const uiStore = useUIStore()
const isPlaceholder = computed(() => props.data.isPlaceholder || !props.data.label)
const isBridgeDimension = computed(
  () => props.data.diagramType === 'bridge_map' && props.data.isDimensionLabel
)
const isTreeMapDimension = computed(() => props.data.diagramType === 'tree_map')

const labelRef = ref<HTMLElement | null>(null)
useNodeDimensions(labelRef, props.id)
const diagramStore = useDiagramSession()

function bridgeTranslate(key: string): string {
  return String(t(key))
}

const bridgeMapDisplay = computed(() => {
  if (!isBridgeDimension.value) return null
  return bridgeDimensionLabelText(props.data.label || '', bridgeTranslate)
})

const bridgeLabelMetrics = computed(() => {
  if (!isBridgeDimension.value) return null
  return measureBridgeDimensionLabel(props.data.label || '', props.data.labelSecondary, {
    fontSize: props.data.style?.fontSize,
    fontFamily: props.data.style?.fontFamily,
    fontWeight: props.data.style?.fontWeight || 'bold',
    translate: bridgeTranslate,
  })
})

const nodeStyle = computed((): CSSProperties => {
  const bridgeDimension = isBridgeDimension.value
  const fontSize =
    props.data.style?.fontSize || (bridgeDimension ? BRIDGE_DIMENSION_LABEL_FONT_PX : 14)

  return {
    color: thinkingMapAdaptiveTextColor(
      diagramStore.data?._mindmap_theme,
      thinkingMapStructureColor(diagramStore.data?._mindmap_theme)
    ),
    opacity: isPlaceholder.value ? 0.4 : bridgeDimension ? 1 : 0.8,
    fontFamily: props.data.style?.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${fontSize}px`,
    fontStyle: props.data.style?.fontStyle || (bridgeDimension ? 'normal' : 'italic'),
    fontWeight: props.data.style?.fontWeight || (bridgeDimension ? 'bold' : 'normal'),
    textDecoration: props.data.style?.textDecoration || 'none',
    textAlign: (bridgeDimension ? 'right' : 'center') as
      'left' | 'right' | 'center' | 'justify' | 'start' | 'end',
    padding: '4px 8px',
    whiteSpace: bridgeDimension || isTreeMapDimension.value ? 'normal' : 'nowrap',
    overflowWrap: (bridgeDimension || isTreeMapDimension.value ? 'break-word' : 'normal') as
      'normal' | 'break-word' | 'anywhere',
    maxWidth:
      bridgeDimension && bridgeLabelMetrics.value
        ? `${bridgeLabelMetrics.value.boxMaxPx}px`
        : undefined,
  }
})

const displayText = computed(() => {
  // For bridge maps, return single string (will be handled separately in template)
  if (props.data.diagramType === 'bridge_map' && props.data.isDimensionLabel) {
    return props.data.label || ''
  }

  const braceMap = props.data.diagramType === 'brace_map'
  const raw = props.data.label || ''
  const dimensionValue =
    braceMap && raw && uiStore.language === 'zh' ? translateDimension(raw, true) : raw
  return thinkingMapDimensionLabelDisplayText(dimensionValue, braceMap ? 'brace' : 'tree')
})

const treeLabelMaxWidth = computed(() => {
  const fontSize = props.data.style?.fontSize || TREE_MAP_DIMENSION_LABEL_FONT_PX
  const fontWeight = String(props.data.style?.fontWeight || 'normal')
  const fontFamily = props.data.style?.fontFamily || DIAGRAM_NODE_FONT_STACK
  return `${resolveThinkingMapDisplayMaxWidthPx(
    displayText.value,
    fontSize,
    TREE_MAP_DIMENSION_LABEL_MAX_TEXT_PX,
    { fontWeight, fontFamily }
  )}px`
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
</script>

<template>
  <div
    ref="labelRef"
    class="label-node flex cursor-pointer"
    :class="{
      'items-center justify-center select-none': !isBridgeDimension,
      'flex-col items-end justify-center': isBridgeDimension,
    }"
    :style="nodeStyle"
    :data-bridge-dimension="isBridgeDimension ? '' : undefined"
  >
    <!-- Bridge map: prefix plus a wrapping dimension value -->
    <template v-if="isBridgeDimension && bridgeMapDisplay && bridgeLabelMetrics">
      <div
        class="bridge-dimension-prefix"
        :style="{ maxWidth: `${bridgeLabelMetrics.prefixMaxPx}px` }"
      >
        {{ bridgeMapDisplay.prefix }}
      </div>
      <div
        class="bridge-dimension-value"
        :style="{ maxWidth: `${bridgeLabelMetrics.valueMaxPx}px` }"
      >
        <InlineEditableText
          :text="bridgeMapDisplay.value"
          :node-id="id"
          :is-editing="isEditing"
          :max-width="`${bridgeLabelMetrics.valueMaxPx}px`"
          text-align="right"
          auto-wrap
          :text-decoration="data.style?.textDecoration || 'none'"
          :text-class="bridgeMapDisplay.isPlaceholder ? 'opacity-60' : ''"
          render-markdown
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
        :max-width="isTreeMapDimension ? treeLabelMaxWidth : '200px'"
        text-align="center"
        :text-decoration="data.style?.textDecoration || 'none'"
        :text-class="isTreeMapDimension ? '' : 'whitespace-nowrap'"
        :auto-wrap="isTreeMapDimension"
        render-markdown
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
}

/* Bridge map dimension labels: fit the wrapped column, then the pairs move aside. */
.label-node[data-bridge-dimension] {
  width: fit-content;
}

.bridge-dimension-prefix,
.bridge-dimension-value {
  line-height: 1.4;
  text-align: right;
  white-space: pre-wrap;
  overflow-wrap: break-word;
  word-break: normal;
  line-break: auto;
  text-wrap: balance;
}

.bridge-dimension-prefix {
  user-select: none;
}

.bridge-dimension-value {
  margin-top: 2px;
  max-width: 100%;
}

.label-node:hover {
  opacity: 1 !important;
}
</style>
