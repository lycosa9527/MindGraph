<script setup lang="ts">
/**
 * MindMapV2TopicNode — v2 mind map topic node (themes, shapes, underline, trunk handles).
 */
import { computed, onMounted, ref, toValue } from 'vue'
import type { CSSProperties } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { storeToRefs } from 'pinia'

import LlmPhaseRing from '@/components/shared/LlmPhaseRing.vue'
import { aiBrainstormGlowingNodeIds } from '@/composables/aiBrainstorm/useAiBrainstorm'
import { eventBus } from '@/composables/core/useEventBus'
import { useTheme } from '@/composables/core/useTheme'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import {
  handleLearningSheetPickNodeClick,
  isLearningSheetCustomPickActive,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import {
  useMindMapExportOutlineWireframeActive,
  wrapMindMapNodeStyleForExport,
  wrapMindMapUnderlineBarForExport,
} from '@/composables/mindMap/useMindMapExportOutlineWireframe'
import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import {
  MINDMAP_UNDERLINE_STROKE_WIDTH,
  MIND_MAP_GEOMETRY,
  mindMapHorizontalPadding,
  mindMapUnderlineContentPadding,
} from '@/config/mindMapGeometry'
import { getMindMapThemeForDiagram } from '@/config/mindMapThemes'
import { useLLMResultsStore } from '@/stores'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { markMindMapLoadShellMounted } from '@/utils/mindMapLoadDebug'
import { resolveMindMapTopicTextMaxWidthPx } from '@/utils/mindMapTextWrap'
import {
  type NodeShape,
  applyNodeShapeToStyle,
  mindMapUnderlineHandleStyle,
} from '@/utils/nodeShapeStyle'

import InlineEditableText from '../InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const diagramStore = useDiagramSession()
const llmResultsStore = useLLMResultsStore()
const { isGenerating: isWholeDiagramGenerating } = storeToRefs(llmResultsStore)
const exportOutlineActive = useMindMapExportOutlineWireframeActive()

const resolvedStyle = computed(() => ({
  ...(diagramStore.data?._node_styles?.[props.id] || {}),
  ...(props.data.style || {}),
}))

const topicNodeShape = computed(
  (): NodeShape =>
    resolveMindMapNodeShape(
      { id: props.id, type: 'topic', style: resolvedStyle.value },
      diagramStore.data?._mindmap_diagram_style as string | undefined
    )
)

const isUnderlineTopic = computed(() => topicNodeShape.value === 'underline')

function finalizeMindMapExportNodeStyle(style: CSSProperties): CSSProperties {
  return wrapMindMapNodeStyleForExport(style, exportOutlineActive.value, {
    isMindMapV2: true,
    isUnderlineShape: isUnderlineTopic.value,
  })
}

const isTextReadonly = computed(
  () => props.data.hidden === true || (diagramPresentationReadOnlyRef.value || toValue(diagramStore.isReadonly))
)

const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const defaultStyle = computed(() => getNodeStyle('topic'))
const isTopicAutoCompleteGlowing = computed(
  () =>
    isWholeDiagramGenerating.value || aiBrainstormGlowingNodeIds.value.has(props.id)
)
const defaultMindMapTheme = computed(() => getMindMapThemeForDiagram(diagramStore.data))

const contentJustifyClass = computed(() =>
  isUnderlineTopic.value ? 'justify-start' : 'justify-center'
)

const underlineTextStyle = computed((): CSSProperties => {
  const padX = mindMapHorizontalPadding('underline')
  return {
    paddingLeft: `${padX}px`,
    paddingRight: `${padX}px`,
  }
})

const underlineLineStyle = computed((): CSSProperties => {
  const style = resolvedStyle.value
  const theme = defaultMindMapTheme.value
  const lineColor =
    style.borderColor || defaultStyle.value.borderColor || theme?.topicBorderColor || '#0d47a1'
  const { textGap } = mindMapUnderlineContentPadding()
  const base = {
    backgroundColor: lineColor,
    opacity: MIND_MAP_GEOMETRY.edgeStrokeOpacity,
    marginTop: `${textGap}px`,
    height: `${MINDMAP_UNDERLINE_STROKE_WIDTH}px`,
  }
  return wrapMindMapUnderlineBarForExport(base, exportOutlineActive.value)
})

const mindMapHandlePositions = computed(() => {
  void diagramStore.layoutRecalcTrigger

  const connections = diagramStore.data?.connections ?? []
  const total = connections.filter((c) => c.source === 'topic').length
  if (total === 0) {
    return { right: [], left: [] }
  }
  const midPoint = Math.ceil(total / 2)
  const rightCount = midPoint
  const leftCount = total - midPoint

  const rightHandleStyle = isUnderlineTopic.value
    ? mindMapUnderlineHandleStyle('right')
    : { top: '50%', transform: 'translate(50%, -50%)' }
  const leftHandleStyle = isUnderlineTopic.value
    ? mindMapUnderlineHandleStyle('left')
    : { top: '50%', transform: 'translate(-50%, -50%)' }

  return {
    right: rightCount > 0 ? [{ id: 'mindmap-right', ...rightHandleStyle }] : [],
    left: leftCount > 0 ? [{ id: 'mindmap-left', ...leftHandleStyle }] : [],
  }
})

const nodeStyle = computed(() => {
  const style = resolvedStyle.value
  const theme = defaultMindMapTheme.value
  const shape = topicNodeShape.value
  const borderColor =
    style.borderColor || defaultStyle.value.borderColor || theme?.topicBorderColor || '#0d47a1'
  const borderWidth =
    style.borderWidth ?? defaultStyle.value.borderWidth ?? MIND_MAP_GEOMETRY.borderWidth
  const borderStyle = style.borderStyle || 'solid'
  const backgroundColor =
    style.backgroundColor ||
    defaultStyle.value.backgroundColor ||
    theme?.topicBackgroundColor ||
    '#1976d2'

  const baseStyle = {
    backgroundColor,
    color: style.textColor || defaultStyle.value.textColor || theme?.topicTextColor || '#ffffff',
    fontFamily: style.fontFamily || MIND_MAP_GEOMETRY.fontFamily,
    fontSize: `${style.fontSize || defaultStyle.value.fontSize || MIND_MAP_GEOMETRY.topicFontSize}px`,
    fontWeight: style.fontWeight || defaultStyle.value.fontWeight || 'bold',
    fontStyle: style.fontStyle || 'normal',
    textDecoration: style.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
  }

  const shapedStyle = applyNodeShapeToStyle(baseStyle, shape, borderColor, true)

  const withMindMapBox = {
    ...shapedStyle,
    ...(isUnderlineTopic.value
      ? (() => {
          const { top } = mindMapUnderlineContentPadding()
          return {
            padding: `${top}px 0 0`,
            minWidth: `${MIND_MAP_GEOMETRY.minWidth}px`,
            minHeight: 'auto',
            boxShadow: 'none',
          }
        })()
      : {
          padding: `${MIND_MAP_GEOMETRY.paddingY}px ${mindMapHorizontalPadding(shape)}px`,
          minWidth: `${MIND_MAP_GEOMETRY.minWidth}px`,
          minHeight: `${MIND_MAP_GEOMETRY.minHeight}px`,
          boxShadow: '0 1px 4px rgba(15, 23, 42, 0.12)',
        }),
    width: 'fit-content',
    maxWidth: '400px',
  }

  return finalizeMindMapExportNodeStyle(withMindMapBox)
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

const topicMaxWidth = computed(() => `${resolveMindMapTopicTextMaxWidthPx()}px`)

const isEditing = ref(false)
const topicNodeRef = ref<HTMLDivElement | null>(null)

useNodeDimensions(topicNodeRef, props.id, {
  onResize(w, h) {
    if (isEditing.value) return
    diagramStore.setMindMapTopicMeasured(w, h)
  },
})

onMounted(() => {
  markMindMapLoadShellMounted('topic')
})

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

function handleTopicNodeClick(event: MouseEvent): void {
  if (isEditing.value) return
  if (isLearningSheetCustomPickActive()) {
    event.stopPropagation()
    event.preventDefault()
    handleLearningSheetPickNodeClick(props.id)
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
      class="topic-node flex border-solid cursor-default select-none relative mind-map-topic-node"
      :class="[
        isUnderlineTopic ? 'flex-col items-stretch mind-map-underline-node' : 'items-center',
        contentJustifyClass,
      ]"
      :style="nodeStyle"
      @click.capture="handleTopicNodeClick"
    >
      <template v-if="isUnderlineTopic">
        <div
          class="mind-map-underline-text"
          :style="underlineTextStyle"
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
          />
        </div>
        <div
          class="mind-map-underline-line"
          :style="underlineLineStyle"
        />
      </template>
      <InlineEditableText
        v-else
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
      />

      <Handle
        v-for="handle in mindMapHandlePositions.right"
        :id="handle.id"
        :key="`${handle.id}-${handle.top}`"
        type="source"
        :position="Position.Right"
        :style="{ top: handle.top, transform: handle.transform }"
        class="bg-blue-500!"
      />
      <Handle
        v-for="handle in mindMapHandlePositions.left"
        :id="handle.id"
        :key="`${handle.id}-${handle.top}`"
        type="source"
        :position="Position.Left"
        :style="{ top: handle.top, transform: handle.transform }"
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
  transition: box-shadow 0.2s ease;
}

.topic-node.mind-map-underline-node {
  min-height: unset;
  height: fit-content;
  box-shadow: none !important;
}

.topic-node.mind-map-underline-node .mind-map-underline-text {
  width: 100%;
}

.topic-node.mind-map-underline-node :deep(.inline-editable-text) {
  min-height: 0;
  line-height: 1.35;
}

.topic-node.mind-map-underline-node :deep(.inline-edit-display) {
  line-height: 1.35;
}

.topic-node.mind-map-underline-node .mind-map-underline-line {
  width: 100%;
  flex-shrink: 0;
}

.topic-node.mind-map-underline-node:hover {
  box-shadow: none !important;
}

.topic-node.mind-map-topic-node {
  width: fit-content;
  max-width: 400px;
}

.topic-node :deep(.inline-edit-placeholder-display),
.topic-node :deep(.inline-edit-placeholder-display .inline-edit-plain),
.topic-node :deep(.inline-edit-placeholder-display.diagram-node-md),
.topic-node :deep(.inline-edit-placeholder-display.diagram-node-md *) {
  color: inherit;
  opacity: 1;
}

.topic-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
