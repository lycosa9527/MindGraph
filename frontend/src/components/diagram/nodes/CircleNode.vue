<script setup lang="ts">
/**
 * CircleNode - Perfect circular node for Circle Maps, Bubble Maps
 * Used for both topic and context nodes in circle/bubble maps
 * Always renders as a perfect circle regardless of content
 * Supports inline text editing on double-click
 * Adapts size based on text length
 * Uses mindmap branch color palette for context nodes (like double bubble map)
 *
 * Layout radii prefer Pinia nodeDimensions. The root circle has fixed width/height from the last
 * layout pass, so measuring only the outer box does not reflect KaTeX/markdown intrinsic size.
 * For circle_map / bubble_map / double-bubble topics we measure `.diagram-node-md` after fonts
 * and paint, and observe it so late font/layout updates still flow into layout.
 */
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { CSSProperties } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { eventBus } from '@/composables/core/useEventBus'
import { useTheme } from '@/composables/core/useTheme'
import { useDiagramNodeTextReadonly } from '@/composables/diagram/useDiagramNodeTextReadonly'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { cancelScheduledLearningSheetPick } from '@/composables/mindMap/useLearningSheetCustomMode'
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { MIND_MAP_RAINBOW_TOPIC_COLORS } from '@/config/mindMapVibrantThemes'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import {
  CIRCLE_MAP_TOPIC_MAX_TEXT_WIDTH,
  CONTEXT_FONT_SIZE,
  TOPIC_FONT_SIZE,
} from '@/stores/specLoader/textMeasurement'
import {
  CONTEXT_MAX_TEXT_WIDTH,
  calculateAdaptiveCircleSize,
  getTopicCircleDiameter,
} from '@/stores/specLoader/utils'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { isBubbleMapAttributeNode } from '@/utils/bubbleMapIdentity'
import { isCircleMapContextNode } from '@/utils/circleMapIdentity'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'
import {
  MIND_MAP_BRANCH_MAX_TEXT_WIDTH,
  resolveThinkingMapDisplayMaxWidthPx,
} from '@/utils/mindMapTextWrap'
import { CIRCLE_MAP_OVAL_WIDTH_RATIO, applyNodeShapeToStyle } from '@/utils/nodeShapeStyle'
import {
  THINKING_MAP_LEAF_TEXT,
  thinkingMapBorderWidth,
  thinkingMapDisplayedFontSize,
} from '@/utils/thinkingMapChrome'
import { thinkingMapDisplayedNodeColors } from '@/utils/thinkingMapNodePaint'

import DoubleBubbleTopicHandles from './DoubleBubbleTopicHandles.vue'
import InlineEditableText from './InlineEditableText.vue'
import NodeShapeUnderline from './NodeShapeUnderline.vue'

const props = defineProps<MindGraphNodeProps>()
const diagramStore = useDiagramSession()
const isTextReadonly = useDiagramNodeTextReadonly(() => props.data.hidden === true)

const topicBorderPx = MIND_MAP_GEOMETRY.borderWidth
const contextBorderPx = MIND_MAP_GEOMETRY.borderWidth

/**
 * Context labels use `px-2` on a border-box display, so that padding sits inside max-width.
 * Circle-map layout treats CONTEXT_MAX_TEXT_WIDTH as the text column. Bubble-map attributes
 * use the mind-map branch column. Add the padding back here or a string that still fits
 * the column wraps and leaves one CJK glyph on the next line.
 */
const CONTEXT_LABEL_PADDING_X = 16

/** Pinia layout sizes from `.diagram-node-md` (post–KaTeX) instead of the fixed-size root circle. */
const useIntrinsicMdMeasure =
  props.data.diagramType === 'circle_map' ||
  props.data.diagramType === 'bubble_map' ||
  (props.data.diagramType === 'double_bubble_map' && props.data.nodeType === 'topic')

const circleNodeRef = ref<HTMLElement | null>(null)
const { reportDimensions } = useNodeDimensions(circleNodeRef, props.id, {
  observeRoot: !useIntrinsicMdMeasure,
})

let markdownResizeObserver: ResizeObserver | null = null

function findContentElement(): HTMLElement | null {
  const root = circleNodeRef.value
  if (!root) return null
  // Prefer intrinsic text blocks. Measuring `.inline-edit-display` is wrong when it is
  // stretched to the full circle width (plain labels without markdown/KaTeX).
  return (
    (root.querySelector('.diagram-node-md') as HTMLElement | null) ??
    (root.querySelector('.inline-edit-plain') as HTMLElement | null) ??
    (root.querySelector('.inline-edit-display') as HTMLElement | null)
  )
}

function measureUnderlineTextStack(): void {
  const root = circleNodeRef.value
  const stack = root?.querySelector('.circle-node__text-wrapper--underline') as HTMLElement | null
  if (!stack) {
    reportDimensions()
    return
  }
  const w = Math.ceil(stack.offsetWidth)
  const h = Math.ceil(stack.offsetHeight)
  if (w <= 0 || h <= 0) {
    reportDimensions()
    return
  }
  diagramStore.setNodeDimensions(props.id, w, h)
}

function measureRenderedMarkdownAndReport(): void {
  if (props.data.style?.nodeShape === 'underline') {
    if (props.data.diagramType === 'double_bubble_map') {
      reportDimensions()
      return
    }
    measureUnderlineTextStack()
    return
  }
  if (!useIntrinsicMdMeasure) {
    reportDimensions()
    return
  }
  const el = findContentElement()
  if (!el) {
    reportDimensions()
    return
  }
  const w = Math.max(el.scrollWidth, el.clientWidth)
  const h = Math.max(el.scrollHeight, el.clientHeight)
  const diagonal = Math.ceil(Math.sqrt(w * w + h * h))
  const borderTotal = isTopicNode.value ? topicBorderPx * 2 : contextBorderPx * 2
  const innerSlack = isTopicNode.value ? 28 : 20
  const d = Math.ceil(Math.max(40, diagonal + borderTotal + innerSlack))
  diagramStore.setNodeDimensions(props.id, d, d)
}

async function flushRenderedMarkdownDimensions(): Promise<void> {
  if (!useIntrinsicMdMeasure) return
  await nextTick()
  if (typeof document !== 'undefined' && document.fonts?.ready) {
    await document.fonts.ready
  }
  await nextTick()
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve())
  })
  measureRenderedMarkdownAndReport()
}

function teardownMarkdownObserver(): void {
  if (markdownResizeObserver) {
    markdownResizeObserver.disconnect()
    markdownResizeObserver = null
  }
}

function setupMarkdownObserver(): void {
  teardownMarkdownObserver()
  if (!useIntrinsicMdMeasure || typeof ResizeObserver === 'undefined') return
  const el = findContentElement()
  if (!el) return
  markdownResizeObserver = new ResizeObserver(() => {
    measureRenderedMarkdownAndReport()
  })
  markdownResizeObserver.observe(el)
}

watch(
  () => props.data.label,
  () => {
    if (!useIntrinsicMdMeasure) return
    void flushRenderedMarkdownDimensions().then(() => {
      nextTick(() => setupMarkdownObserver())
    })
  }
)

watch(
  () => props.data.style?.nodeShape,
  () => {
    if (!useIntrinsicMdMeasure) return
    void flushRenderedMarkdownDimensions()
  }
)

onMounted(() => {
  if (!useIntrinsicMdMeasure) return
  void flushRenderedMarkdownDimensions().then(() => {
    nextTick(() => setupMarkdownObserver())
  })
})

onUnmounted(() => {
  teardownMarkdownObserver()
})

// Get theme defaults
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

// Determine if this is a topic or context node
const isTopicNode = computed(() => props.data.nodeType === 'topic')

// Circular topic (circle_map / bubble_map / double_bubble_map center) – use content-width block centering
const isCircularTopic = computed(
  () =>
    (diagramStore.type === 'circle_map' ||
      diagramStore.type === 'bubble_map' ||
      diagramStore.type === 'double_bubble_map') &&
    isTopicNode.value
)

// Double bubble map similarity/diff nodes render as capsule (pill)
const isCapsuleNode = computed(
  () => diagramStore.type === 'double_bubble_map' && !isTopicNode.value
)

// Double bubble map: show handles for curved edge connections at node boundary
const isDoubleBubbleMap = computed(() => diagramStore.type === 'double_bubble_map')
const capsuleWidth = computed(() => props.data.style?.width ?? circleSize.value)
const capsuleHeight = computed(() => props.data.style?.height ?? circleSize.value)

// Use 'context' for circle map context nodes (not 'bubble')
const defaultStyle = computed(() => getNodeStyle(isTopicNode.value ? 'topic' : 'context'))

// Per-group color from mindmap palette for bubble_map / circle_map context nodes
const groupColor = computed(() => {
  const idx = props.data.groupIndex as number | undefined
  if (idx === undefined) return null
  const isContext = diagramStore.type === 'bubble_map' || diagramStore.type === 'circle_map'
  return isContext && !isTopicNode.value ? getMindmapBranchColor(idx) : null
})

// Prefer style.size from layout (driven by Pinia nodeDimensions on circle/bubble maps); fallback text estimate
const circleSize = computed(() => {
  if (props.data.style?.size) {
    return props.data.style.size
  }
  const text = props.data.label || ''
  const isRadialTopic =
    (diagramStore.type === 'circle_map' || diagramStore.type === 'bubble_map') && isTopicNode.value
  if (isRadialTopic) {
    return getTopicCircleDiameter(text)
  }
  return calculateAdaptiveCircleSize(text, isTopicNode.value)
})

const textMaxWidth = computed(() => {
  const label = (props.data.label || '').trim()
  const fontFamily = props.data.style?.fontFamily || DIAGRAM_NODE_FONT_STACK
  if (isTopicNode.value) {
    if (diagramStore.type === 'circle_map' || diagramStore.type === 'bubble_map') {
      const fontSize =
        typeof props.data.style?.fontSize === 'number' ? props.data.style.fontSize : TOPIC_FONT_SIZE
      const fontWeight = String(props.data.style?.fontWeight || 'bold')
      return resolveThinkingMapDisplayMaxWidthPx(label, fontSize, CIRCLE_MAP_TOPIC_MAX_TEXT_WIDTH, {
        fontWeight,
        fontFamily,
      })
    }
    return circleSize.value - 2 * topicBorderPx
  }
  if (isCapsuleNode.value) {
    return capsuleWidth.value - 2 * contextBorderPx
  }
  const fontSize =
    typeof props.data.style?.fontSize === 'number' ? props.data.style.fontSize : CONTEXT_FONT_SIZE
  const fontWeight = String(props.data.style?.fontWeight || 'normal')
  const cap =
    diagramStore.type === 'bubble_map' ? MIND_MAP_BRANCH_MAX_TEXT_WIDTH : CONTEXT_MAX_TEXT_WIDTH
  return (
    resolveThinkingMapDisplayMaxWidthPx(label, fontSize, cap, { fontWeight, fontFamily }) +
    CONTEXT_LABEL_PADDING_X
  )
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

const shapeLineColor = computed(() => {
  const color = groupColor.value
  return (
    themeNodePaint.value?.borderColor ||
    props.data.style?.borderColor ||
    color?.border ||
    defaultStyle.value.borderColor ||
    MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
  )
})

const isDiskOval = computed(() => {
  if (props.data.style?.nodeShape !== 'oval' || isCapsuleNode.value) return false
  const diagramType = diagramStore.type
  return (
    diagramType === 'circle_map' ||
    diagramType === 'bubble_map' ||
    diagramType === 'double_bubble_map'
  )
})

const nodeStyle = computed(() => {
  const width = isCapsuleNode.value
    ? capsuleWidth.value
    : isDiskOval.value
      ? circleSize.value * CIRCLE_MAP_OVAL_WIDTH_RATIO
      : circleSize.value
  const height = isCapsuleNode.value ? capsuleHeight.value : circleSize.value
  const color = groupColor.value
  const borderColor =
    themeNodePaint.value?.borderColor ||
    props.data.style?.borderColor ||
    color?.border ||
    defaultStyle.value.borderColor ||
    MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
  const borderWidth = thinkingMapBorderWidth(
    themeNodePaint.value?.borderWidth,
    props.data.style?.borderWidth,
    defaultStyle.value.borderWidth ?? MIND_MAP_GEOMETRY.borderWidth
  )
  const borderStyle = props.data.style?.borderStyle || 'solid'
  const backgroundColor =
    themeNodePaint.value?.backgroundColor ||
    props.data.style?.backgroundColor ||
    color?.fill ||
    defaultStyle.value.backgroundColor ||
    (isTopicNode.value ? MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor : '#FFFFFF')

  const explicitShape = props.data.style?.nodeShape
  const isUnderline = explicitShape === 'underline'
  const styleSize = props.data.style?.size
  const styleWidth = props.data.style?.width
  const styleHeight = props.data.style?.height
  const hasLayoutBox =
    isCapsuleNode.value ||
    (typeof styleSize === 'number' && styleSize > 0) ||
    (typeof styleWidth === 'number' &&
      styleWidth > 0 &&
      typeof styleHeight === 'number' &&
      styleHeight > 0)
  const box: CSSProperties = {
    ...(!isUnderline || hasLayoutBox
      ? {
          width: typeof width === 'number' ? `${width}px` : width,
          height: typeof height === 'number' ? `${height}px` : height,
        }
      : {}),
    backgroundColor,
    color:
      themeNodePaint.value?.textColor ||
      props.data.style?.textColor ||
      defaultStyle.value.textColor ||
      (isTopicNode.value ? '#ffffff' : THINKING_MAP_LEAF_TEXT),
    fontFamily: props.data.style?.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: cssFontSize(
      thinkingMapDisplayedFontSize(
        props.data.style?.fontSize,
        isTopicNode.value
          ? MIND_MAP_GEOMETRY.topicFontSize
          : (defaultStyle.value.fontSize ?? MIND_MAP_GEOMETRY.branchFontSize)
      ),
      isTopicNode.value ? TOPIC_FONT_SIZE : MIND_MAP_GEOMETRY.branchFontSize
    ),
    fontWeight:
      props.data.style?.fontWeight ||
      defaultStyle.value.fontWeight ||
      (isTopicNode.value ? 'bold' : 'normal'),
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
    boxShadow: isUnderline
      ? 'none'
      : isTopicNode.value
        ? MIND_MAP_GEOMETRY.topicShadow
        : MIND_MAP_GEOMETRY.branchShadow,
  }
  if (explicitShape) return applyNodeShapeToStyle(box, explicitShape, borderColor, true)
  if (isCapsuleNode.value) return { ...box, borderRadius: '9999px' }
  return box
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

function cssFontSize(value: unknown, fallbackPx: number): string {
  if (typeof value === 'number' && Number.isFinite(value)) return `${value}px`
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return `${fallbackPx}px`
    return /[a-z%]$/i.test(trimmed) ? trimmed : `${trimmed}px`
  }
  return `${fallbackPx}px`
}

const circleTextAlign = computed<'left' | 'center' | 'right'>(() => {
  const align = props.data.style?.textAlign
  if (align === 'left' || align === 'right' || align === 'center') return align
  return 'center'
})

function handleCircleDoubleClick(event: MouseEvent): void {
  cancelScheduledLearningSheetPick()
  if (diagramStore.type !== 'circle_map') return
  if (isTextReadonly.value || isEditing.value) return
  event.preventDefault()
  event.stopPropagation()
  isEditing.value = true
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

const supportsBranchMove = computed(() => {
  if (isTopicNode.value) return false
  const dt = diagramStore.type
  if (dt === 'bubble_map')
    return isBubbleMapAttributeNode({
      id: props.id,
      type: (props.data?.nodeType as string) ?? props.type,
    })
  if (dt === 'circle_map')
    return isCircleMapContextNode({
      id: props.id,
      type: (props.data?.nodeType as string) ?? props.type,
    })
  if (dt === 'double_bubble_map') {
    return readDoubleBubbleRole({ id: props.id, data: props.data }) != null
  }
  return false
})

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
    ref="circleNodeRef"
    class="circle-node relative flex items-center justify-center border-solid select-none"
    :class="[
      isTopicNode ? 'cursor-default' : 'cursor-grab',
      isTopicNode ? 'topic-circle' : 'context-circle',
      isCapsuleNode ? 'circle-node--capsule' : '',
      isDiskOval ? 'circle-node--oval' : '',
      isDoubleBubbleMap ? 'circle-node--with-handles' : '',
      !data.style?.nodeShape || data.style.nodeShape === 'oval' ? 'rounded-full' : '',
      data.style?.nodeShape === 'underline' ? 'circle-node--underline' : '',
    ]"
    :style="nodeStyle"
    @dblclick="handleCircleDoubleClick"
    @mousedown.capture="handleBranchMovePointerDown"
    @mouseup.capture="handleBranchMovePointerUp"
    @touchstart.passive.capture="handleBranchMoveTouchStart"
  >
    <!-- Handles for double bubble map curved edges (connect at node boundary) -->
    <template v-if="isDoubleBubbleMap && isTopicNode && data.style?.nodeShape !== 'underline'">
      <DoubleBubbleTopicHandles />
    </template>
    <template v-else-if="isDoubleBubbleMap && data.style?.nodeShape !== 'underline'">
      <Handle
        id="left"
        :position="Position.Left"
      />
      <Handle
        id="right"
        :position="Position.Right"
      />
      <Handle
        id="top"
        :position="Position.Top"
      />
      <Handle
        id="bottom"
        :position="Position.Bottom"
      />
    </template>
    <div
      class="circle-node__text-wrapper"
      :class="{ 'circle-node__text-wrapper--underline': data.style?.nodeShape === 'underline' }"
    >
      <template v-if="isDoubleBubbleMap && data.style?.nodeShape === 'underline'">
        <DoubleBubbleTopicHandles v-if="isTopicNode" />
        <template v-else>
          <Handle
            id="left"
            :position="Position.Left"
          />
          <Handle
            id="right"
            :position="Position.Right"
          />
          <Handle
            id="top"
            :position="Position.Top"
          />
          <Handle
            id="bottom"
            :position="Position.Bottom"
          />
        </template>
      </template>
      <InlineEditableText
        :text="data.label || ''"
        :node-id="id"
        :is-editing="isEditing"
        :readonly="isTextReadonly"
        :max-width="`${textMaxWidth}px`"
        :text-align="circleTextAlign"
        :text-decoration="data.style?.textDecoration || 'none'"
        :text-class="isTopicNode ? 'py-2' : 'px-2 py-1'"
        :full-width="isTopicNode && !isCircularTopic"
        :center-block-in-circle="isCircularTopic"
        :no-wrap="isDoubleBubbleMap || !!data.style?.noWrap"
        :auto-wrap="!isDoubleBubbleMap"
        :truncate="false"
        render-markdown
        @save="handleTextSave"
        @cancel="handleEditCancel"
        @edit-start="isEditing = true"
      />
      <NodeShapeUnderline
        v-if="data.style?.nodeShape === 'underline'"
        inline
        :color="shapeLineColor"
      />
    </div>
  </div>
</template>

<style scoped>
.circle-node {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;
  flex-shrink: 0;
}

.circle-node:not(.circle-node--capsule):not(.circle-node--underline):not(.circle-node--oval) {
  aspect-ratio: 1;
}

.circle-node__text-wrapper {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  min-width: 0;
}

.circle-node__text-wrapper--underline {
  position: relative;
  width: fit-content;
  max-width: 100%;
  flex-direction: column;
  align-items: stretch;
}

.circle-node--underline:hover,
.context-circle.circle-node--underline:hover,
.topic-circle.circle-node--underline:hover {
  transform: none;
}

.context-circle:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: scale(1.02);
}

.context-circle:active {
  cursor: grabbing;
}

.topic-circle {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 10;
}

.topic-circle:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

/* Hide handle dots for double bubble map (handles are for connection points only) */
.circle-node--with-handles :deep(.vue-flow__handle) {
  width: 0;
  height: 0;
  border: none;
  background: transparent;
}
</style>
