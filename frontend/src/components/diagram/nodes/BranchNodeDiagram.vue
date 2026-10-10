<script setup lang="ts">
/**
 * BranchNodeDiagram — non-mind-map branch node (tree map, bridge map, etc.).
 */
import { computed, inject, ref, toValue } from 'vue'
import type { CSSProperties } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useTheme } from '@/composables/core/useTheme'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { cancelScheduledLearningSheetPick } from '@/composables/mindMap/useLearningSheetCustomMode'
import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { MIND_MAP_RAINBOW_TOPIC_COLORS } from '@/config/mindMapVibrantThemes'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { isBridgeMapPairNode } from '@/utils/bridgeMapIdentity'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import { resolveThinkingMapDisplayMaxWidthPx } from '@/utils/mindMapTextWrap'
import { applyNodeShapeToStyle, resolveNodeShape } from '@/utils/nodeShapeStyle'
import {
  THINKING_MAP_LEAF_TEXT,
  thinkingMapBorderWidth,
  thinkingMapBoxPadding,
  thinkingMapDisplayedFontSize,
} from '@/utils/thinkingMapChrome'
import { thinkingMapSolidThemeStroke } from '@/utils/thinkingMapConnectionStroke'
import { thinkingMapDisplayedNodeColors } from '@/utils/thinkingMapNodePaint'
import {
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
  readTreeCategoryIndex,
} from '@/utils/treeMapIdentity'

import InlineEditableText from './InlineEditableText.vue'
import NodeShapeUnderline from './NodeShapeUnderline.vue'

const props = defineProps<MindGraphNodeProps>()

const diagramStore = useDiagramSession()
const isTextReadonly = computed(() => {
  if (diagramPresentationReadOnlyRef.value || toValue(diagramStore.isReadonly)) return true
  return props.data.hidden === true && !diagramStore.isLearningSheet
})
const branchNodeRef = ref<HTMLDivElement | null>(null)

const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const isChild = computed(() => props.data.nodeType === 'branch' && Boolean(props.data.parentId))

const themeNodeType = computed(() => {
  if (props.data.diagramType === 'tree_map') {
    return props.data.nodeType === 'leaf' ? 'leaf' : 'branch'
  }
  return isChild.value ? 'child' : 'branch'
})

const defaultStyle = computed(() => getNodeStyle(themeNodeType.value))
const isTreeMap = computed(() => props.data.diagramType === 'tree_map')
const isBridgeMap = computed(() => props.data.diagramType === 'bridge_map')

const BRANCH_MAX_TEXT_WIDTH = 200

const resolvedStyle = computed(() => ({
  ...(diagramStore.data?._node_styles?.[props.id] || {}),
  ...(props.data.style || {}),
}))

const nodeShape = computed(() => resolveNodeShape(resolvedStyle.value, false))

const bridgeHasBody = computed(() => {
  const explicitShape = resolvedStyle.value.nodeShape
  return isBridgeMap.value && Boolean(explicitShape) && explicitShape !== 'underline'
})

const treeMapGroupColors = computed(() => {
  if (!isTreeMap.value) return null
  let idx = props.data.groupIndex as number | undefined
  if (idx === undefined) {
    const stamped = readTreeCategoryIndex({ id: props.id, data: props.data })
    idx = stamped >= 0 ? stamped : undefined
  }
  return idx !== undefined ? getMindmapBranchColor(idx) : null
})

const themeNodePaint = computed(() => {
  const node = props.data.originalNode
  if (!node) return null
  return thinkingMapDisplayedNodeColors(
    props.data.diagramType,
    diagramStore.data?._mindmap_theme,
    node,
    resolvedStyle.value,
    diagramStore.data?.connections
  )
})

const shapeLineColor = computed(() => {
  const style = resolvedStyle.value
  return (
    themeNodePaint.value?.borderColor ||
    style.borderColor ||
    (isTreeMap.value && treeMapGroupColors.value ? treeMapGroupColors.value.border : undefined) ||
    defaultStyle.value.borderColor ||
    MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
  )
})

const treeUnderlineSourceStyle = computed(() => {
  if (!isTreeMap.value || resolvedStyle.value.nodeShape !== 'underline') return undefined
  return {
    top: 'auto',
    bottom: '1px',
    transform: 'translate(-50%, 50%)',
  }
})

const nodeStyle = computed((): CSSProperties => {
  const style = resolvedStyle.value
  const bridgeBody = bridgeHasBody.value
  const shouldHaveBorder = !isBridgeMap.value || bridgeBody
  const shouldHaveBackground = !isBridgeMap.value || bridgeBody
  const shouldHaveShadow = !isBridgeMap.value || bridgeBody
  const bgColor = shouldHaveBackground
    ? themeNodePaint.value?.backgroundColor ||
      style.backgroundColor ||
      (isTreeMap.value && treeMapGroupColors.value
        ? treeMapGroupColors.value.fill
        : defaultStyle.value.backgroundColor) ||
      '#FFFFFF'
    : 'transparent'
  const borderColor = shouldHaveBorder
    ? themeNodePaint.value?.borderColor ||
      style.borderColor ||
      (isTreeMap.value && treeMapGroupColors.value
        ? treeMapGroupColors.value.border
        : defaultStyle.value.borderColor) ||
      MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
    : 'transparent'

  const borderWidth = shouldHaveBorder
    ? thinkingMapBorderWidth(
        themeNodePaint.value?.borderWidth,
        style.borderWidth,
        defaultStyle.value.borderWidth ?? MIND_MAP_GEOMETRY.borderWidth
      )
    : 0
  const borderStyle = shouldHaveBorder ? style.borderStyle || 'solid' : 'solid'

  const base: CSSProperties = {
    backgroundColor: bgColor,
    ...(shouldHaveBorder
      ? getBorderStyleProps(borderColor, borderWidth, borderStyle, {
          backgroundColor: bgColor,
        })
      : { borderColor: 'transparent', borderWidth: '0px', borderStyle: 'none' }),
    color:
      themeNodePaint.value?.textColor ||
      style.textColor ||
      defaultStyle.value.textColor ||
      THINKING_MAP_LEAF_TEXT,
    fontFamily: style.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${thinkingMapDisplayedFontSize(style.fontSize, themeNodePaint.value?.fontSize ?? defaultStyle.value.fontSize ?? MIND_MAP_GEOMETRY.branchFontSize)}px`,
    fontWeight: style.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: style.fontStyle || 'normal',
    textDecoration: style.textDecoration || 'none',
    padding: shouldHaveBackground ? thinkingMapBoxPadding(false) : '0',
    boxShadow: shouldHaveShadow ? MIND_MAP_GEOMETRY.branchShadow : 'none',
  }

  const shape = nodeShape.value
  const result: CSSProperties = { ...applyNodeShapeToStyle(base, shape, borderColor, true) }
  const solidTheme = Boolean(thinkingMapSolidThemeStroke(diagramStore.data?._mindmap_theme))
  const accentWidth = solidTheme
    ? 0
    : (themeNodePaint.value?.accentBarWidth ?? style.accentBarWidth ?? 0)
  const accentColor = solidTheme
    ? undefined
    : (themeNodePaint.value?.accentBarColor ?? style.accentBarColor)
  if (accentWidth > 0 && accentColor && shape !== 'underline') {
    result.boxShadow = `${MIND_MAP_GEOMETRY.branchShadow}, inset ${accentWidth}px 0 0 0 ${accentColor}`
    const pad = MIND_MAP_GEOMETRY.paddingX + accentWidth + 4
    result.paddingLeft = `${pad}px`
  }

  if (isTreeMap.value && props.data.style?.width != null) {
    result.width = `${props.data.style.width}px`
    result.minWidth = `${props.data.style.width}px`
    result.maxWidth = `${props.data.style.width}px`
  }
  if (isTreeMap.value && props.data.style?.height != null) {
    result.height = `${props.data.style.height}px`
    result.minHeight = `${props.data.style.height}px`
  }

  if (isTreeMap.value && shape === 'underline') {
    result.minHeight = '0'
    result.paddingTop = '0'
    result.paddingBottom = '2px'
    result.boxShadow = 'none'
  }

  return result
})

const textMaxWidth = computed(() => {
  const label = ((props.data.label as string) || '').trim()
  if (isTreeMap.value && props.data.style?.width != null) {
    const px = Number(props.data.style.width)
    return `${Math.max(60, px - 32)}px`
  }
  if (isBridgeMap.value) {
    return 'min(420px, 88vw)'
  }

  const fontSize = parseFloat(nodeStyle.value.fontSize as string) || 16
  const fontWeight = String(nodeStyle.value.fontWeight || 'normal')
  const fontFamily = String(nodeStyle.value.fontFamily || DIAGRAM_NODE_FONT_STACK)
  return `${resolveThinkingMapDisplayMaxWidthPx(label, fontSize, BRANCH_MAX_TEXT_WIDTH, {
    fontWeight,
    fontFamily,
  })}px`
})

const useAutoWrap = computed(() => !isTreeMap.value && !isBridgeMap.value)

const isEditing = ref(false)

const collabCanvas = inject<{ isNodeLockedByOther?: (nodeId: string) => boolean } | undefined>(
  'collabCanvas',
  undefined
)
const notifyCollab = useNotifications()
const { t } = useLanguage()

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
    (props.data.diagramType === 'tree_map' &&
      (isTreeMapCategoryNode({ id: props.id, data: props.data }) ||
        isTreeMapLeafNode({ id: props.id, data: props.data }))) ||
    (isBridgeMap.value && isBridgeMapPairNode({ id: props.id, data: props.data }))
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

useNodeDimensions(branchNodeRef, props.id)

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

function handleBranchNodeDoubleClick(): void {
  cancelScheduledLearningSheetPick()
  if (diagramPresentationReadOnlyRef.value || toValue(diagramStore.isReadonly)) return
  if ((props.data.hidden === true && !diagramStore.isLearningSheet) || isEditing.value) return
  if (collabCanvas?.isNodeLockedByOther?.(props.id)) {
    notifyCollab.warning(t('collab.nodeLocked'))
    return
  }
  isEditing.value = true
}

function handleBranchNodeClick(): void {
  if (isEditing.value) return
  diagramStore.selectNodes(props.id)
}
</script>

<template>
  <div
    ref="branchNodeRef"
    class="branch-node flex select-none border-solid relative items-center justify-center px-4 py-2"
    :class="{
      'tree-map-node': isTreeMap,
      'border-none': isBridgeMap && !bridgeHasBody,
      'cursor-grab': true,
    }"
    :style="nodeStyle"
    @mousedown.capture="handleBranchMovePointerDown"
    @mouseup.capture="handleBranchMovePointerUp"
    @touchstart.passive.capture="handleBranchMoveTouchStart"
    @click.capture="handleBranchNodeClick"
    @dblclick="handleBranchNodeDoubleClick"
  >
    <NodeShapeUnderline
      v-if="resolvedStyle.nodeShape === 'underline'"
      :color="shapeLineColor"
    />
    <InlineEditableText
      :text="data.label || ''"
      :node-id="id"
      :is-editing="isEditing"
      :readonly="isTextReadonly"
      :max-width="textMaxWidth"
      :text-align="resolvedStyle.textAlign || 'center'"
      :text-decoration="resolvedStyle.textDecoration || 'none'"
      :auto-wrap="useAutoWrap"
      render-markdown
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @close="handleEditCancel"
      @edit-start="isEditing = true"
    />

    <Handle
      v-if="!isTreeMap && !isBridgeMap"
      id="left"
      type="target"
      :position="Position.Left"
      class="bg-blue-400!"
    />
    <Handle
      v-if="!isTreeMap && !isBridgeMap"
      id="right"
      type="source"
      :position="Position.Right"
      class="bg-blue-400!"
    />

    <Handle
      v-if="isTreeMap"
      type="target"
      :position="Position.Top"
      class="bg-blue-400!"
    />
    <Handle
      v-if="isTreeMap"
      type="source"
      :position="Position.Bottom"
      class="bg-blue-400!"
      :style="treeUnderlineSourceStyle"
    />
  </div>
</template>

<style scoped>
.branch-node {
  min-width: 80px;
  min-height: 36px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  transition:
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.branch-node.tree-map-node {
  min-width: 80px;
}

.branch-node.border-none {
  box-shadow: none !important;
}

.branch-node:hover:not(.border-none) {
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.12);
  border-color: #3b82f6;
}

.branch-node:active {
  cursor: grabbing;
}

.branch-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
