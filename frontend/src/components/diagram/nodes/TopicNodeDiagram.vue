<script setup lang="ts">
/**
 * TopicNodeDiagram — non-mind-map topic node (bubble, tree, flow, brace, multi-flow, etc.).
 */
import { computed, nextTick, ref, toValue } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { storeToRefs } from 'pinia'

import LlmPhaseRing from '@/components/shared/LlmPhaseRing.vue'
import { eventBus } from '@/composables/core/useEventBus'
import { useTheme } from '@/composables/core/useTheme'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'
import { useLLMResultsStore } from '@/stores'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import { type NodeShape, applyNodeShapeToStyle, resolveNodeShape } from '@/utils/nodeShapeStyle'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const diagramStore = useDiagramSession()
const llmResultsStore = useLLMResultsStore()
const { isGenerating: isWholeDiagramGenerating } = storeToRefs(llmResultsStore)

const isTextReadonly = computed(
  () => props.data.hidden === true || (diagramPresentationReadOnlyRef.value || toValue(diagramStore.isReadonly))
)

const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const defaultStyle = computed(() => getNodeStyle('topic'))

const isPillShape = computed(
  () =>
    props.data.diagramType === 'tree_map' ||
    props.data.diagramType === 'brace_map' ||
    props.data.diagramType === 'multi_flow_map' ||
    props.data.diagramType === 'flow_map'
)
const isRoundedRectangle = computed(() => false)
const isFlowMap = computed(() => props.data.diagramType === 'flow_map')
const flowMapOrientation = computed(
  () => (props.data.orientation as 'horizontal' | 'vertical') || 'horizontal'
)

const isTreeMap = computed(() => props.data.diagramType === 'tree_map')
const isBraceMap = computed(() => props.data.diagramType === 'brace_map')
const isMultiFlowMap = computed(() => props.data.diagramType === 'multi_flow_map')

const isTopicAutoCompleteGlowing = computed(() => isWholeDiagramGenerating.value)

const resolvedStyle = computed(() => ({
  ...(diagramStore.data?._node_styles?.[props.id] || {}),
  ...(props.data.style || {}),
}))

const topicNodeShape = computed((): NodeShape => {
  const style = resolvedStyle.value
  return style.nodeShape ?? resolveNodeShape(style, false)
})

const causeCount = computed(() => {
  if (!isMultiFlowMap.value) return 0
  return (props.data.causeCount as number) || 4
})

const effectCount = computed(() => {
  if (!isMultiFlowMap.value) return 0
  return (props.data.effectCount as number) || 4
})

const leftHandlePositions = computed(() => {
  if (causeCount.value === 0) return []
  const positions: Array<{ id: string; top: string }> = []
  for (let i = 0; i < causeCount.value; i++) {
    const topPercent = ((i + 1) * 100) / (causeCount.value + 1)
    positions.push({
      id: `left-${i}`,
      top: `${topPercent}%`,
    })
  }
  return positions
})

const rightHandlePositions = computed(() => {
  if (effectCount.value === 0) return []
  const positions: Array<{ id: string; top: string }> = []
  for (let i = 0; i < effectCount.value; i++) {
    const topPercent = ((i + 1) * 100) / (effectCount.value + 1)
    positions.push({
      id: `right-${i}`,
      top: `${topPercent}%`,
    })
  }
  return positions
})

const nodeStyle = computed(() => {
  const style = resolvedStyle.value
  const borderColor = style.borderColor || defaultStyle.value.borderColor || '#0d47a1'
  const borderWidth = style.borderWidth ?? defaultStyle.value.borderWidth ?? 3
  const borderStyle = style.borderStyle || 'solid'
  const backgroundColor = style.backgroundColor || defaultStyle.value.backgroundColor || '#1976d2'

  const baseStyle = {
    backgroundColor,
    color: style.textColor || defaultStyle.value.textColor || '#ffffff',
    fontFamily: style.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${style.fontSize || defaultStyle.value.fontSize || 18}px`,
    fontWeight: style.fontWeight || defaultStyle.value.fontWeight || 'bold',
    fontStyle: style.fontStyle || 'normal',
    textDecoration: style.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
  }

  const shape = topicNodeShape.value
  const shapedStyle = style.nodeShape
    ? applyNodeShapeToStyle(baseStyle, shape, borderColor, false)
    : {
        ...baseStyle,
        borderRadius: isPillShape.value
          ? '9999px'
          : isRoundedRectangle.value
            ? `${style.borderRadius || 8}px`
            : `${style.borderRadius || 50}%`,
      }

  if (isMultiFlowMap.value && dynamicWidth.value !== null) {
    return {
      ...shapedStyle,
      width: `${dynamicWidth.value}px`,
      minWidth: `${dynamicWidth.value}px`,
      transition: 'width 0.2s ease',
    }
  }

  if (isMultiFlowMap.value && dynamicWidth.value === null) {
    return {
      ...shapedStyle,
      width: 'max-content',
      minWidth: '90px',
    }
  }

  if (isFlowMap.value) {
    return {
      ...shapedStyle,
      width: 'max-content',
      minWidth: '120px',
      minHeight: '48px',
      maxWidth: '400px',
    }
  }

  if (isTreeMap.value && props.data.style?.width != null) {
    return {
      ...shapedStyle,
      width: `${props.data.style.width}px`,
      minWidth: `${props.data.style.width}px`,
      maxWidth: `${props.data.style.width}px`,
      ...(props.data.style.height != null
        ? {
            height: `${props.data.style.height}px`,
            minHeight: `${props.data.style.height}px`,
          }
        : {}),
    }
  }

  if (isBraceMap.value) {
    return {
      ...shapedStyle,
      width: 'fit-content',
      maxWidth: '400px',
    }
  }

  return shapedStyle
})

const topicRingBorderRadius = computed(() => {
  const radius = nodeStyle.value.borderRadius
  if (typeof radius === 'string' && radius.length > 0) {
    return radius
  }
  if (typeof radius === 'number') {
    return `${radius}px`
  }
  return '9999px'
})

const TOPIC_MAX_TEXT_WIDTH = 300
const topicMaxWidth = computed(() => `${TOPIC_MAX_TEXT_WIDTH}px`)

const isEditing = ref(false)
const dynamicWidth = ref<number | null>(null)
const topicNodeRef = ref<HTMLDivElement | null>(null)

const { reportDimensions } = useNodeDimensions(topicNodeRef, props.id)

async function flushMultiFlowTopicWidthFromPinia(): Promise<void> {
  await nextTick()
  if (typeof document !== 'undefined' && document.fonts?.ready) {
    await document.fonts.ready
  }
  await nextTick()
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve())
  })
  reportDimensions()
  const fromStore = diagramStore.getNodeDimension(props.id)?.width
  const fallback = topicNodeRef.value?.offsetWidth ?? null
  const w = fromStore ?? fallback
  eventBus.emit('multi_flow_map:topic_width_changed', {
    nodeId: props.id,
    width: w,
  })
}

function handleTextSave(newText: string) {
  isEditing.value = false
  dynamicWidth.value = null

  eventBus.emit('node:text_updated', {
    nodeId: props.id,
    text: newText,
  })

  if (isMultiFlowMap.value) {
    void flushMultiFlowTopicWidthFromPinia()
  }
}

function handleEditCancel() {
  isEditing.value = false
  dynamicWidth.value = null
}

function handleTopicNodeClick(): void {
  if (isEditing.value) return
  diagramStore.selectNodes(props.id)
}

function handleWidthChange(width: number) {
  if (isMultiFlowMap.value) {
    dynamicWidth.value = width + 48

    void (async () => {
      await nextTick()
      if (typeof document !== 'undefined' && document.fonts?.ready) {
        await document.fonts.ready
      }
      await nextTick()
      await new Promise<void>((resolve) => {
        requestAnimationFrame(() => resolve())
      })
      reportDimensions()
      const fromStore = diagramStore.getNodeDimension(props.id)?.width
      const actualWidth = fromStore ?? topicNodeRef.value?.offsetWidth ?? null
      if (topicNodeRef.value && actualWidth != null) {
        eventBus.emit('multi_flow_map:topic_width_changed', {
          nodeId: props.id,
          width: actualWidth,
        })
      }
    })()
  }
}
</script>

<template>
  <LlmPhaseRing
    :phase="isTopicAutoCompleteGlowing ? 'waiting' : 'idle'"
    :active="isTopicAutoCompleteGlowing"
    :border-radius="topicRingBorderRadius"
    streaming-variant="primary"
    ring-padding="3px"
    class="topic-node-ring"
  >
    <div
      ref="topicNodeRef"
      class="topic-node flex border-solid cursor-default select-none relative items-center justify-center"
      :class="{
        'pill-shape': isPillShape,
        'rounded-rectangle': isRoundedRectangle,
        'multi-flow-map-node': isMultiFlowMap,
        'flow-map-topic-node': isFlowMap,
        'py-3': isFlowMap,
        'py-4': !isFlowMap,
        'px-6': true,
      }"
      :style="nodeStyle"
      @click.capture="handleTopicNodeClick"
    >
      <InlineEditableText
        :text="data.label || ''"
        :node-id="id"
        :is-editing="isEditing"
        :readonly="isTextReadonly"
        :max-width="topicMaxWidth"
        :text-align="resolvedStyle.textAlign || 'center'"
        :text-decoration="resolvedStyle.textDecoration || 'none'"
        auto-wrap
        render-markdown
        @save="handleTextSave"
        @cancel="handleEditCancel"
        @close="handleEditCancel"
        @edit-start="isEditing = true"
        @width-change="handleWidthChange"
      />

      <Handle
        v-if="!isPillShape && !isMultiFlowMap && !isFlowMap"
        type="source"
        :position="Position.Right"
        class="bg-blue-500!"
      />
      <Handle
        v-if="!isPillShape && !isMultiFlowMap && !isFlowMap"
        type="source"
        :position="Position.Left"
        class="bg-blue-500!"
      />
      <Handle
        v-if="!isPillShape && !isMultiFlowMap && !isFlowMap"
        type="source"
        :position="Position.Top"
        class="bg-blue-500!"
      />
      <Handle
        v-if="!isPillShape && !isMultiFlowMap && !isFlowMap"
        type="source"
        :position="Position.Bottom"
        class="bg-blue-500!"
      />

      <Handle
        v-if="isTreeMap"
        type="source"
        :position="Position.Bottom"
        class="bg-blue-500!"
      />

      <Handle
        v-if="isBraceMap"
        type="source"
        :position="Position.Right"
        class="bg-blue-500!"
      />

      <template v-if="isMultiFlowMap">
        <Handle
          v-for="handle in leftHandlePositions"
          :id="handle.id"
          :key="`${handle.id}-${handle.top}`"
          type="target"
          :position="Position.Left"
          :style="{ top: handle.top }"
          class="bg-blue-500!"
        />
      </template>
      <template v-if="isMultiFlowMap">
        <Handle
          v-for="handle in rightHandlePositions"
          :id="handle.id"
          :key="`${handle.id}-${handle.top}`"
          type="source"
          :position="Position.Right"
          :style="{ top: handle.top }"
          class="bg-blue-500!"
        />
      </template>

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
    </div>
  </LlmPhaseRing>
</template>

<style scoped>
.topic-node-ring {
  width: fit-content;
  height: fit-content;
}

.topic-node {
  min-width: 120px;
  min-height: 48px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: box-shadow 0.2s ease;
}

.topic-node:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

.topic-node :deep(.inline-edit-placeholder-display),
.topic-node :deep(.inline-edit-placeholder-display .inline-edit-plain),
.topic-node :deep(.inline-edit-placeholder-display.diagram-node-md),
.topic-node :deep(.inline-edit-placeholder-display.diagram-node-md *) {
  color: inherit;
  opacity: 1;
}

.topic-node.pill-shape {
  min-height: 40px;
  padding-left: 24px;
  padding-right: 24px;
}

.topic-node.rounded-rectangle {
  min-width: 140px;
  min-height: 50px;
}

.topic-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
