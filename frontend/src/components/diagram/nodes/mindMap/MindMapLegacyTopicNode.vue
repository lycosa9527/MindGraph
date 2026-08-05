<script setup lang="ts">
/**
 * MindMapLegacyTopicNode — classic mind map topic node only (oval pill, per-branch handles).
 */
import { computed, ref, toValue } from 'vue'
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
} from '@/composables/mindMap/useMindMapExportOutlineWireframe'
import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'
import { useLLMResultsStore } from '@/stores'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { buildClassicMindMapTopicHandlePositions } from '@/utils/classicMindMapTopicHandles'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import {
  resolveMindMapTopicTextMaxWidthPx,
} from '@/utils/mindMapTextWrap'

import InlineEditableText from '../InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const diagramStore = useDiagramSession()
const llmResultsStore = useLLMResultsStore()
const { isGenerating: isWholeDiagramGenerating } = storeToRefs(llmResultsStore)
const exportOutlineActive = useMindMapExportOutlineWireframeActive()

function finalizeMindMapExportNodeStyle(style: CSSProperties): CSSProperties {
  return wrapMindMapNodeStyleForExport(style, exportOutlineActive.value, {
    isMindMapV2: false,
    isUnderlineShape: false,
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

const resolvedStyle = computed(() => ({
  ...(diagramStore.data?._node_styles?.[props.id] || {}),
  ...(props.data.style || {}),
}))

const mindMapHandlePositions = computed(() => {
  void diagramStore.layoutRecalcTrigger

  const connections = diagramStore.data?.connections ?? []
  const classicTopicHeightPx =
    diagramStore.getNodeDimension(props.id)?.height ?? topicNodeRef.value?.offsetHeight ?? null

  return {
    right: buildClassicMindMapTopicHandlePositions(
      connections,
      'r',
      'mindmap-right',
      diagramStore.data?.nodes ?? [],
      classicTopicHeightPx
    ),
    left: buildClassicMindMapTopicHandlePositions(
      connections,
      'l',
      'mindmap-left',
      diagramStore.data?.nodes ?? [],
      classicTopicHeightPx
    ),
  }
})

const nodeStyle = computed(() => {
  const style = resolvedStyle.value
  const borderColor = defaultStyle.value.borderColor || '#0d47a1'
  const borderWidth = defaultStyle.value.borderWidth ?? 3
  const borderStyle = 'solid'
  const backgroundColor = defaultStyle.value.backgroundColor || '#1976d2'

  const classicStyle = {
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
    borderRadius: '9999px',
    width: 'fit-content',
    maxWidth: '400px',
  }

  return finalizeMindMapExportNodeStyle(classicStyle)
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
      class="topic-node flex border-solid cursor-default select-none relative items-center justify-center pill-shape py-4 px-6"
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

.topic-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
