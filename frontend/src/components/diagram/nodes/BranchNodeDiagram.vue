<script setup lang="ts">
/**
 * BranchNodeDiagram — non-mind-map branch node (tree map, bridge map, etc.).
 */
import { computed, inject, ref } from 'vue'
import type { CSSProperties } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useTheme } from '@/composables/core/useTheme'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import { useDiagramStore } from '@/stores/diagram'
import { measureTextWidth } from '@/stores/specLoader/textMeasurement'
import { computeScriptAwareMaxWidth } from '@/stores/specLoader/textMeasurementFallback'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import { applyNodeShapeToStyle, resolveNodeShape } from '@/utils/nodeShapeStyle'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const diagramStore = useDiagramStore()
const isTextReadonly = computed(
  () =>
    (props.data.hidden === true && diagramStore.isLearningSheet) ||
    diagramPresentationReadOnlyRef.value
)
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

const treeMapGroupColors = computed(() => {
  if (!isTreeMap.value) return null
  let idx = props.data.groupIndex as number | undefined
  if (idx === undefined) {
    const catMatch = props.id.match(/^tree-cat-(\d+)$/)
    const leafMatch = props.id.match(/^tree-leaf-(\d+)-\d+$/)
    idx = catMatch ? parseInt(catMatch[1], 10) : leafMatch ? parseInt(leafMatch[1], 10) : undefined
  }
  return idx !== undefined ? getMindmapBranchColor(idx) : null
})

const nodeStyle = computed((): CSSProperties => {
  const shouldHaveBorder = !isBridgeMap.value
  const shouldHaveBackground = !isBridgeMap.value
  const shouldHaveShadow = !isBridgeMap.value

  const style = resolvedStyle.value
  const bgColor = shouldHaveBackground
    ? style.backgroundColor ||
      (isTreeMap.value && treeMapGroupColors.value
        ? treeMapGroupColors.value.fill
        : defaultStyle.value.backgroundColor) ||
      '#e3f2fd'
    : 'transparent'
  const borderColor = shouldHaveBorder
    ? style.borderColor ||
      (isTreeMap.value && treeMapGroupColors.value
        ? treeMapGroupColors.value.border
        : defaultStyle.value.borderColor) ||
      '#4e79a7'
    : 'transparent'

  const borderWidth = shouldHaveBorder
    ? (style.borderWidth ?? defaultStyle.value.borderWidth ?? 2)
    : 0
  const borderStyle = shouldHaveBorder ? style.borderStyle || 'solid' : 'solid'

  const base: CSSProperties = {
    backgroundColor: bgColor,
    ...(shouldHaveBorder
      ? getBorderStyleProps(borderColor, borderWidth, borderStyle, {
          backgroundColor: bgColor,
        })
      : { borderColor: 'transparent', borderWidth: '0px', borderStyle: 'none' }),
    color: style.textColor || defaultStyle.value.textColor || '#333333',
    fontFamily: style.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${style.fontSize || defaultStyle.value.fontSize || 16}px`,
    fontWeight: style.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: style.fontStyle || 'normal',
    textDecoration: style.textDecoration || 'none',
    boxShadow: shouldHaveShadow ? undefined : 'none',
  }

  const shape = nodeShape.value
  const result: CSSProperties = { ...applyNodeShapeToStyle(base, shape, borderColor, false) }

  if (shape === 'rounded' && !style.nodeShape) {
    result.borderRadius = `${style.borderRadius || 8}px`
  }

  if (isTreeMap.value && props.data.style?.width != null) {
    result.width = `${props.data.style.width}px`
    result.minWidth = `${props.data.style.width}px`
    result.maxWidth = `${props.data.style.width}px`
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

  if (!label) return `${BRANCH_MAX_TEXT_WIDTH}px`

  const wrapThreshold = computeScriptAwareMaxWidth(label, BRANCH_MAX_TEXT_WIDTH)
  const fontSize = parseFloat(nodeStyle.value.fontSize as string) || 16
  const fontWeight = String(nodeStyle.value.fontWeight || 'normal')
  const textWidth = measureTextWidth(label, fontSize, { fontWeight })

  if (textWidth <= wrapThreshold) {
    return `${wrapThreshold}px`
  }

  return `${BRANCH_MAX_TEXT_WIDTH}px`
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
      (props.id?.startsWith('tree-cat-') || props.id?.startsWith('tree-leaf-'))) ||
    (isBridgeMap.value && props.id?.startsWith('pair-'))
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

function handleBranchNodeDoubleClick(): void {
  if (diagramPresentationReadOnlyRef.value) return
  if ((props.data.hidden === true && diagramStore.isLearningSheet) || isEditing.value) return
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
      'border-none': isBridgeMap,
      'cursor-grab': true,
    }"
    :style="nodeStyle"
    @mousedown.capture="handleBranchMovePointerDown"
    @mouseup.capture="handleBranchMovePointerUp"
    @touchstart.passive.capture="handleBranchMoveTouchStart"
    @click.capture="handleBranchNodeClick"
    @dblclick="handleBranchNodeDoubleClick"
  >
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
