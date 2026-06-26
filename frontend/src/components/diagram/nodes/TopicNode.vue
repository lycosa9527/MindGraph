<script setup lang="ts">
/**
 * TopicNode - Central topic node for diagrams (non-draggable)
 * Used as the main/central node in bubble maps, mind maps, etc.
 * Supports inline text editing on double-click
 */
import { computed, nextTick, ref } from 'vue'

import type { CSSProperties } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { eventBus } from '@/composables/core/useEventBus'
import { presentationDiagramEditLockedRef } from '@/composables/presentation/presentationDiagramEdit'
import {
  handleLearningSheetPickNodeClick,
  isLearningSheetCustomPickActive,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import { useTheme } from '@/composables/core/useTheme'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { useDiagramStore } from '@/stores'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import {
  applyNodeShapeToStyle,
  mindMapUnderlineHandleStyle,
  resolveNodeShape,
  type NodeShape,
} from '@/utils/nodeShapeStyle'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import {
  MIND_MAP_GEOMETRY,
  MINDMAP_UNDERLINE_STROKE_WIDTH,
  mindMapHorizontalPadding,
  mindMapUnderlineContentPadding,
} from '@/config/mindMapGeometry'
import { getMindMapThemeForDiagram } from '@/config/mindMapThemes'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const diagramStore = useDiagramStore()
const useMindMapV2Visuals = useMindMapV2Chrome()
const isTextReadonly = computed(
  () => props.data.hidden === true || presentationDiagramEditLockedRef.value
)

// Get theme defaults matching old StyleManager
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const defaultStyle = computed(() => getNodeStyle('topic'))

// Tree map, brace map, mindmap, and flow maps use pill shape (fully rounded ends)
const isPillShape = computed(
  () =>
    props.data.diagramType === 'tree_map' ||
    props.data.diagramType === 'brace_map' ||
    props.data.diagramType === 'mindmap' ||
    props.data.diagramType === 'mind_map' ||
    props.data.diagramType === 'multi_flow_map' ||
    props.data.diagramType === 'flow_map'
)
// Rounded rectangle (fallback when not pill or circle - e.g. bridge map)
const isRoundedRectangle = computed(() => false)
// Flow map: main topic with single handle (right for horizontal, bottom for vertical)
const isFlowMap = computed(() => props.data.diagramType === 'flow_map')
const flowMapOrientation = computed(
  () => (props.data.orientation as 'horizontal' | 'vertical') || 'horizontal'
)

// Specific diagram type checks for handle positioning
const isTreeMap = computed(() => props.data.diagramType === 'tree_map')
const isBraceMap = computed(() => props.data.diagramType === 'brace_map')
const isMultiFlowMap = computed(() => props.data.diagramType === 'multi_flow_map')
const isMindMap = computed(
  () => props.data.diagramType === 'mindmap' || props.data.diagramType === 'mind_map'
)

const topicNodeShape = computed((): NodeShape => {
  if (isMindMap.value && !useMindMapV2Visuals.value) {
    return 'oval'
  }
  const style = resolvedStyle.value
  if (isMindMap.value) {
    return resolveMindMapNodeShape(
      { id: props.id, type: 'topic', style },
      diagramStore.data?._mindmap_diagram_style as string | undefined
    )
  }
  return style.nodeShape ?? resolveNodeShape(style, false)
})

const isUnderlineTopic = computed(
  () => useMindMapV2Visuals.value && isMindMap.value && topicNodeShape.value === 'underline'
)

const defaultMindMapTheme = computed(() =>
  useMindMapV2Visuals.value ? getMindMapThemeForDiagram(diagramStore.data) : null
)

const resolvedStyle = computed(() => ({
  ...(diagramStore.data?._node_styles?.[props.id] || {}),
  ...(props.data.style || {}),
}))

const contentJustifyClass = computed(() => 'justify-center')

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
    style.borderColor ||
    defaultStyle.value.borderColor ||
    theme?.topicBorderColor ||
    '#0d47a1'
  const { textGap } = mindMapUnderlineContentPadding()
  return {
    backgroundColor: lineColor,
    opacity: MIND_MAP_GEOMETRY.edgeStrokeOpacity,
    marginTop: `${textGap}px`,
    height: `${MINDMAP_UNDERLINE_STROKE_WIDTH}px`,
  }
})

// For multi-flow maps: get cause count to generate handles dynamically
const causeCount = computed(() => {
  if (!isMultiFlowMap.value) return 0
  return (props.data.causeCount as number) || 4 // Default to 4 if not specified
})

// For multi-flow maps: get effect count to generate handles dynamically
const effectCount = computed(() => {
  if (!isMultiFlowMap.value) return 0
  return (props.data.effectCount as number) || 4 // Default to 4 if not specified
})

// Generate handle positions for multi-flow map causes (evenly distributed)
const leftHandlePositions = computed(() => {
  if (causeCount.value === 0) return []
  const positions: Array<{ id: string; top: string }> = []
  for (let i = 0; i < causeCount.value; i++) {
    // Distribute evenly: for 4 causes, positions are at 20%, 40%, 60%, 80%
    const topPercent = ((i + 1) * 100) / (causeCount.value + 1)
    positions.push({
      id: `left-${i}`,
      top: `${topPercent}%`,
    })
  }
  return positions
})

// Generate handle positions for multi-flow map effects (evenly distributed)
const rightHandlePositions = computed(() => {
  if (effectCount.value === 0) return []
  const positions: Array<{ id: string; top: string }> = []
  for (let i = 0; i < effectCount.value; i++) {
    // Distribute evenly: for 4 effects, positions are at 20%, 40%, 60%, 80%
    const topPercent = ((i + 1) * 100) / (effectCount.value + 1)
    positions.push({
      id: `right-${i}`,
      top: `${topPercent}%`,
    })
  }
  return positions
})

// For mindmaps: get total branch count for left/right handle distribution
const totalBranchCount = computed(() => {
  if (!isMindMap.value) return 0
  return (props.data.totalBranchCount as number) || 0
})

// Mindmap handles: v2 uses one trunk exit per side; classic distributes along each edge.
const mindMapHandlePositions = computed(() => {
  if (totalBranchCount.value === 0) {
    return { right: [], left: [] }
  }

  const total = totalBranchCount.value
  const midPoint = Math.ceil(total / 2)
  const rightCount = midPoint
  const leftCount = total - midPoint

  if (!useMindMapV2Visuals.value) {
    const generateHandles = (count: number, prefix: string) => {
      const handles: Array<{ id: string; top: string; transform: string }> = []
      for (let i = 0; i < count; i++) {
        const topPercent = ((i + 1) / (count + 1)) * 100
        handles.push({
          id: `${prefix}-${i}`,
          top: `${topPercent}%`,
          transform: 'translateY(-50%)',
        })
      }
      return handles
    }
    return {
      right: generateHandles(rightCount, 'mindmap-right'),
      left: generateHandles(leftCount, 'mindmap-left'),
    }
  }

  const rightHandleStyle = isUnderlineTopic.value
    ? mindMapUnderlineHandleStyle('right')
    : { top: '50%', transform: 'translate(50%, -50%)' }
  const leftHandleStyle = isUnderlineTopic.value
    ? mindMapUnderlineHandleStyle('left')
    : { top: '50%', transform: 'translate(-50%, -50%)' }

  return {
    right:
      rightCount > 0
        ? [{ id: 'mindmap-right', ...rightHandleStyle }]
        : [],
    left:
      leftCount > 0
        ? [{ id: 'mindmap-left', ...leftHandleStyle }]
        : [],
  }
})

const nodeStyle = computed(() => {
  const style = resolvedStyle.value

  // Classic canvas: pill topic with pre-v2 defaults (ignore v2 theme presets in _node_styles).
  if (isMindMap.value && !useMindMapV2Visuals.value) {
    const borderColor = style.borderColor || defaultStyle.value.borderColor || '#0d47a1'
    const borderWidth = style.borderWidth ?? defaultStyle.value.borderWidth ?? 3
    const borderStyle = style.borderStyle || 'solid'
    const backgroundColor =
      style.backgroundColor || defaultStyle.value.backgroundColor || '#1976d2'

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

    return classicStyle
  }

  const theme = defaultMindMapTheme.value
  const borderColor =
    style.borderColor ||
    defaultStyle.value.borderColor ||
    (isMindMap.value && theme ? theme.topicBorderColor : '#0d47a1')
  const borderWidth =
    style.borderWidth ??
    defaultStyle.value.borderWidth ??
    (isMindMap.value && useMindMapV2Visuals.value ? MIND_MAP_GEOMETRY.borderWidth : 3)
  const borderStyle = style.borderStyle || 'solid'
  const backgroundColor =
    style.backgroundColor ||
    defaultStyle.value.backgroundColor ||
    (isMindMap.value && theme ? theme.topicBackgroundColor : '#1976d2')

  const baseStyle = {
    backgroundColor,
    color:
      style.textColor ||
      defaultStyle.value.textColor ||
      (isMindMap.value && theme ? theme.topicTextColor : '#ffffff'),
    fontFamily:
      style.fontFamily ||
      (isMindMap.value && useMindMapV2Visuals.value
        ? MIND_MAP_GEOMETRY.fontFamily
        : DIAGRAM_NODE_FONT_STACK),
    fontSize: `${style.fontSize || defaultStyle.value.fontSize || (isMindMap.value && useMindMapV2Visuals.value ? MIND_MAP_GEOMETRY.topicFontSize : 18)}px`,
    fontWeight: style.fontWeight || defaultStyle.value.fontWeight || 'bold',
    fontStyle: style.fontStyle || 'normal',
    textDecoration: style.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
  }

  const shape = topicNodeShape.value
  const shapedStyle =
    isMindMap.value && useMindMapV2Visuals.value
      ? applyNodeShapeToStyle(baseStyle, shape, borderColor, true)
      : isMindMap.value || style.nodeShape
        ? applyNodeShapeToStyle(baseStyle, shape, borderColor, isMindMap.value)
        : {
            ...baseStyle,
            borderRadius: isPillShape.value
              ? '9999px'
              : isRoundedRectangle.value
                ? `${style.borderRadius || 8}px`
                : `${style.borderRadius || 50}%`,
          }

  const withMindMapBox =
    isMindMap.value && useMindMapV2Visuals.value
      ? {
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
        }
      : shapedStyle

  // Add dynamic width when editing (only for multi-flow map)
  if (isMultiFlowMap.value && dynamicWidth.value !== null) {
    return {
      ...withMindMapBox,
      width: `${dynamicWidth.value}px`,
      minWidth: `${dynamicWidth.value}px`,
      transition: 'width 0.2s ease',
    }
  }

  // Multi-flow map topic: adaptive width so node grows/shrinks with text
  if (isMultiFlowMap.value && dynamicWidth.value === null) {
    return {
      ...withMindMapBox,
      width: 'max-content',
      minWidth: '90px',
    }
  }

  // Flow map topic: adaptive width and height so full text displays
  if (isFlowMap.value) {
    return {
      ...withMindMapBox,
      width: 'max-content',
      minWidth: '120px',
      minHeight: '48px',
      maxWidth: '400px',
    }
  }

  // Tree map: measured box from layout so wrapped text stays inside the pill (Vue Flow + CSS match)
  if (isTreeMap.value && props.data.style?.width != null) {
    return {
      ...withMindMapBox,
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

  // Brace map / mind map: hard-cap width so the pill never exceeds the layout algorithm's maximum
  if (isBraceMap.value || isMindMap.value) {
    return {
      ...withMindMapBox,
      width: 'fit-content',
      maxWidth: '400px',
    }
  }

  return withMindMapBox
})

const TOPIC_MAX_TEXT_WIDTH = 300

const topicMaxWidth = computed(() => `${TOPIC_MAX_TEXT_WIDTH}px`)

// Inline editing state
const isEditing = ref(false)

// Dynamic width for editing (only for multi-flow map)
const dynamicWidth = ref<number | null>(null)
const topicNodeRef = ref<HTMLDivElement | null>(null)

const { reportDimensions } = useNodeDimensions(topicNodeRef, props.id, {
  onResize(w, h) {
    if (!isMindMap.value || isEditing.value) return
    diagramStore.setMindMapTopicMeasured(w, h)
  },
})

/**
 * After display mode shows markdown/KaTeX, flush DOM size into Pinia and emit
 * topic width for multi-flow layout (uses getNodeDimension like other nodes).
 */
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
  dynamicWidth.value = null // Reset width after canceling
}

function handleTopicNodeClick(event: MouseEvent): void {
  if (isEditing.value) return
  if (isMindMap.value && isLearningSheetCustomPickActive()) {
    event.stopPropagation()
    event.preventDefault()
    handleLearningSheetPickNodeClick(props.id)
    return
  }
  if (isMindMap.value) return
  diagramStore.selectNodes(props.id)
}

function handleWidthChange(width: number) {
  // Update node width dynamically as user types (only for multi-flow map)
  if (isMultiFlowMap.value) {
    // Add padding to account for node padding (px-6 = 24px on each side = 48px total)
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
  <div
    ref="topicNodeRef"
    class="topic-node flex border-solid cursor-default select-none relative"
    :class="[
      isUnderlineTopic ? 'flex-col items-stretch' : 'items-center',
      contentJustifyClass,
      {
        'pill-shape': isPillShape && (!isMindMap || !useMindMapV2Visuals),
        'rounded-rectangle': isRoundedRectangle,
        'multi-flow-map-node': isMultiFlowMap,
        'flow-map-topic-node': isFlowMap,
        'mind-map-topic-node': isMindMap && useMindMapV2Visuals,
        'mind-map-underline-node': isUnderlineTopic,
        'py-3': isFlowMap,
        'py-4': !isFlowMap && (!isMindMap || !useMindMapV2Visuals),
        'px-6': !isMindMap || !useMindMapV2Visuals,
      },
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
          @edit-start="isEditing = true"
          @width-change="handleWidthChange"
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
      @edit-start="isEditing = true"
      @width-change="handleWidthChange"
    />

    <!-- Connection handles for horizontal layouts (bubble maps, etc.) -->
    <!-- Mindmaps use dynamic handles below, so exclude them here -->
    <!-- Flow map uses single handle below, so exclude it here -->
    <Handle
      v-if="!isPillShape && !isMultiFlowMap && !isMindMap && !isFlowMap"
      type="source"
      :position="Position.Right"
      class="bg-blue-500!"
    />
    <Handle
      v-if="!isPillShape && !isMultiFlowMap && !isMindMap && !isFlowMap"
      type="source"
      :position="Position.Left"
      class="bg-blue-500!"
    />
    <Handle
      v-if="!isPillShape && !isMultiFlowMap && !isMindMap && !isFlowMap"
      type="source"
      :position="Position.Top"
      class="bg-blue-500!"
    />
    <Handle
      v-if="!isPillShape && !isMultiFlowMap && !isMindMap && !isFlowMap"
      type="source"
      :position="Position.Bottom"
      class="bg-blue-500!"
    />

    <!-- Connection handle for tree maps (vertical layout - bottom only) -->
    <Handle
      v-if="isTreeMap"
      type="source"
      :position="Position.Bottom"
      class="bg-blue-500!"
    />

    <!-- Connection handle for brace maps (horizontal layout - right only) -->
    <Handle
      v-if="isBraceMap"
      type="source"
      :position="Position.Right"
      class="bg-blue-500!"
    />

    <!-- Connection handles for multi-flow maps (left target for causes, right source for effects) -->
    <!-- Dynamically generate left handles based on cause count, evenly distributed -->
    <template v-if="isMultiFlowMap">
      <Handle
        v-for="handle in leftHandlePositions"
        :id="handle.id"
        :key="handle.id"
        type="target"
        :position="Position.Left"
        :style="{ top: handle.top }"
        class="bg-blue-500!"
      />
    </template>
    <!-- Dynamically generate right handles based on effect count, evenly distributed -->
    <template v-if="isMultiFlowMap">
      <Handle
        v-for="handle in rightHandlePositions"
        :id="handle.id"
        :key="handle.id"
        type="source"
        :position="Position.Right"
        :style="{ top: handle.top }"
        class="bg-blue-500!"
      />
    </template>

    <!-- Flow map: single handle at right center (horizontal) or bottom center (vertical) -->
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

    <!-- Connection handles for mindmaps: left and right edges, evenly distributed -->
    <template v-if="isMindMap">
      <Handle
        v-for="handle in mindMapHandlePositions.right"
        :id="handle.id"
        :key="handle.id"
        type="source"
        :position="Position.Right"
        :style="{ top: handle.top, transform: handle.transform }"
        class="bg-blue-500!"
      />
    </template>
    <template v-if="isMindMap">
      <Handle
        v-for="handle in mindMapHandlePositions.left"
        :id="handle.id"
        :key="handle.id"
        type="source"
        :position="Position.Left"
        :style="{ top: handle.top, transform: handle.transform }"
        class="bg-blue-500!"
      />
    </template>
  </div>
</template>

<style scoped>
.topic-node {
  min-width: 120px;
  min-height: 48px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: box-shadow 0.2s ease;
}

.topic-node:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

.topic-node.mind-map-underline-node {
  min-height: unset;
  box-shadow: none !important;
}

.topic-node.mind-map-underline-node .mind-map-underline-text {
  width: 100%;
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

/* Placeholder label ("中心主题") keeps topic text color — not muted gray. */
.topic-node :deep(.inline-edit-placeholder-display),
.topic-node :deep(.inline-edit-placeholder-display .inline-edit-plain),
.topic-node :deep(.inline-edit-placeholder-display.diagram-node-md),
.topic-node :deep(.inline-edit-placeholder-display.diagram-node-md *) {
  color: inherit;
  opacity: 1;
}

/* Tree map pill shape adjustments */
.topic-node.pill-shape {
  min-height: 40px;
  padding-left: 24px;
  padding-right: 24px;
}

/* Multi-flow map rounded rectangle adjustments */
.topic-node.rounded-rectangle {
  min-width: 140px;
  min-height: 50px;
}

/* Hide handle dots visually while keeping them functional */
.topic-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
