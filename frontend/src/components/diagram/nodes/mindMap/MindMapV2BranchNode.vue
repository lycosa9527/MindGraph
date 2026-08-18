<script setup lang="ts">
/**
 * MindMapV2BranchNode — v2 mind map branch node (themes, shapes, underline, subgraph ring).
 */
import { type WritableComputedRef, computed, inject, onMounted, ref, toValue, watch } from 'vue'
import type { CSSProperties } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import LlmPhaseRing from '@/components/shared/LlmPhaseRing.vue'
import { useLanguage, useNotifications } from '@/composables'
import { aiBrainstormGlowingNodeIds } from '@/composables/aiBrainstorm/useAiBrainstorm'
import { eventBus } from '@/composables/core/useEventBus'
import { useTheme } from '@/composables/core/useTheme'
import { diagramSessionRef, useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import {
  handleLearningSheetPickNodeClick,
  isLearningSheetCustomPickActive,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import { useMindMapBranchNumbering } from '@/composables/mindMap/useMindMapBranchNumbering'
import {
  useMindMapExportOutlineWireframeActive,
  wrapMindMapNodeStyleForExport,
} from '@/composables/mindMap/useMindMapExportOutlineWireframe'
import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import {
  MINDMAP_UNDERLINE_STROKE_WIDTH,
  MIND_MAP_GEOMETRY,
  mindMapBranchDepth,
  mindMapBranchFontSize,
  mindMapHorizontalPadding,
  mindMapUnderlineContentPadding,
} from '@/config/mindMapGeometry'
import { getMindMapThemeForDiagram } from '@/config/mindMapThemes'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { stripMatchingBranchNumberPrefix } from '@/utils/mindMapBranchNumbering'
import { markMindMapInlineEditStage } from '@/utils/mindMapInlineEditDebug'
import { markMindMapLoadShellMounted } from '@/utils/mindMapLoadDebug'
import {
  MIND_MAP_BRANCH_MAX_TEXT_WIDTH,
  MIND_MAP_NUMBER_PREFIX_GAP_PX,
  resolveMindMapBranchBodyMaxWidthPx,
} from '@/utils/mindMapTextWrap'
import { applyNodeShapeToStyle, mindMapUnderlineHandleStyle } from '@/utils/nodeShapeStyle'

import InlineEditableText from '../InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const diagramStore = useDiagramSession()
const mindMapPendingEditNodeId = diagramSessionRef(diagramStore, 'mindMapPendingEditNodeId')
const mindMapEditingNodeId = diagramSessionRef(diagramStore, 'mindMapEditingNodeId')
const isTextReadonly = computed(
  () =>
    (props.data.hidden === true && diagramStore.isLearningSheet) ||
    diagramPresentationReadOnlyRef.value ||
    toValue(diagramStore.isReadonly)
)
const branchNodeRef = ref<HTMLDivElement | null>(null)
const exportOutlineActive = useMindMapExportOutlineWireframeActive()

const resolvedStyle = computed(() => ({
  ...(diagramStore.data?._node_styles?.[props.id] || {}),
  ...(props.data.style || {}),
}))

const nodeShape = computed(() =>
  resolveMindMapNodeShape(
    { id: props.id, type: 'branch', style: resolvedStyle.value },
    diagramStore.data?._mindmap_diagram_style as string | undefined
  )
)
const isUnderlineShape = computed(() => nodeShape.value === 'underline')

function finalizeMindMapExportNodeStyle(style: CSSProperties): CSSProperties {
  return wrapMindMapNodeStyleForExport(style, exportOutlineActive.value, {
    isMindMapV2: true,
    isUnderlineShape: isUnderlineShape.value,
  })
}

const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const isChild = computed(() =>
  mindMapBranchDepth(props.id, { data: props.data }, diagramStore.data?.connections) >= 2
)
const themeNodeType = computed(() => (isChild.value ? 'child' : 'branch'))
const defaultStyle = computed(() => getNodeStyle(themeNodeType.value))
const defaultMindMapTheme = computed(() => getMindMapThemeForDiagram(diagramStore.data))

const mindMapThemeColors = computed(() => {
  const theme = defaultMindMapTheme.value
  return {
    fill: theme.backgroundColor,
    border: theme.borderColor,
    text: theme.textColor,
  }
})

const contentJustifyClass = computed(() =>
  isUnderlineShape.value ? 'justify-start' : 'justify-center'
)

const underlineTextStyle = computed((): CSSProperties => {
  const padX = mindMapHorizontalPadding('underline')
  return {
    paddingLeft: `${padX}px`,
    paddingRight: `${padX}px`,
  }
})

const underlineLineStyle = computed((): CSSProperties => {
  const { textGap } = mindMapUnderlineContentPadding()
  return {
    backgroundColor: 'transparent',
    marginTop: `${textGap}px`,
    height: `${MINDMAP_UNDERLINE_STROKE_WIDTH}px`,
  }
})

const nodeStyle = computed((): CSSProperties => {
  const style = resolvedStyle.value
  const bgColor =
    style.backgroundColor ||
    mindMapThemeColors.value.fill ||
    defaultStyle.value.backgroundColor ||
    '#e3f2fd'
  const borderColor =
    style.borderColor ||
    mindMapThemeColors.value.border ||
    defaultStyle.value.borderColor ||
    '#4e79a7'
  const borderWidth =
    style.borderWidth ?? MIND_MAP_GEOMETRY.borderWidth ?? defaultStyle.value.borderWidth ?? 2
  const borderStyle = style.borderStyle || 'solid'

  const base: CSSProperties = {
    backgroundColor: bgColor,
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor: bgColor,
    }),
    color:
      style.textColor || mindMapThemeColors.value.text || defaultStyle.value.textColor || '#333333',
    fontFamily: style.fontFamily || MIND_MAP_GEOMETRY.fontFamily,
    fontSize: `${style.fontSize || defaultStyle.value.fontSize || mindMapBranchFontSize(props.id, { data: props.data }, diagramStore.data?.connections)}px`,
    fontWeight: style.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: style.fontStyle || 'normal',
    textDecoration: style.textDecoration || 'none',
    boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06)',
  }

  const shape = nodeShape.value
  const result: CSSProperties = { ...applyNodeShapeToStyle(base, shape, borderColor, true) }

  const padX = mindMapHorizontalPadding(shape)
  const isBlankedForSheet =
    diagramStore.isLearningSheet && diagramStore.isNodeBlankedForLearningSheet(props.id)
  const layoutWidth = props.data?.estimatedWidth as number | undefined
  const layoutHeight = props.data?.estimatedHeight as number | undefined

  if (isUnderlineShape.value) {
    const { top } = mindMapUnderlineContentPadding()
    result.padding = `${top}px 0 0`
    result.minWidth = `${MIND_MAP_GEOMETRY.minWidth}px`
    result.minHeight = 'auto'
    result.boxShadow = 'none'
  } else {
    result.padding = `${MIND_MAP_GEOMETRY.paddingY}px ${padX}px`
    result.minWidth = `${MIND_MAP_GEOMETRY.minWidth}px`
    result.minHeight = `${MIND_MAP_GEOMETRY.minHeight}px`
  }

  if (isBlankedForSheet && layoutWidth && layoutWidth > 0) {
    const widthPx = Math.max(layoutWidth, MIND_MAP_GEOMETRY.minWidth)
    result.width = `${widthPx}px`
    result.minWidth = `${widthPx}px`
  }
  if (isBlankedForSheet && layoutHeight && layoutHeight > 0) {
    result.minHeight = `${Math.max(layoutHeight, MIND_MAP_GEOMETRY.minHeight)}px`
  }

  return finalizeMindMapExportNodeStyle(result)
})

// Store-owned session survives Vue Flow remount after Enter sibling write-back.
const isEditing: WritableComputedRef<boolean> = computed({
  get: () => mindMapEditingNodeId.value === props.id,
  set: (value: boolean) => {
    if (value) {
      diagramStore.setMindMapEditingNodeId(props.id)
      return
    }
    diagramStore.clearMindMapEditingNodeId(props.id)
  },
})

const { prefixFor } = useMindMapBranchNumbering()
const numberPrefix = computed(() => prefixFor(props.id))
const showNumberPrefix = computed(() => Boolean(numberPrefix.value) && !isEditing.value)
const numberPrefixGapStyle = {
  gap: `${MIND_MAP_NUMBER_PREFIX_GAP_PX}px`,
}
const accessibleBranchLabel = computed(() => {
  const label = String(props.data.label || '').trim()
  const prefix = numberPrefix.value
  if (!prefix) return label || undefined
  return label ? `${prefix} ${label}` : prefix
})

const textMaxWidth = computed(() => {
  const label = ((props.data.label as string) || '').trim()
  if (!label && !numberPrefix.value) return `${MIND_MAP_BRANCH_MAX_TEXT_WIDTH}px`
  const fontSize =
    parseFloat(nodeStyle.value.fontSize as string) ||
    mindMapBranchFontSize(props.id, { data: props.data }, diagramStore.data?.connections)
  const fontWeight = String(nodeStyle.value.fontWeight || 'normal')
  return `${resolveMindMapBranchBodyMaxWidthPx(label, numberPrefix.value, fontSize, {
    fontWeight,
    fontFamily: MIND_MAP_GEOMETRY.fontFamily,
  })}px`
})

const previewStore = useMindMapSubgraphPreviewStore()
const isSubgraphGenerating = computed(
  () => previewStore.isGeneratingFor(props.id) || aiBrainstormGlowingNodeIds.value.has(props.id)
)
const subgraphRingBorderRadius = computed(() => {
  const radius = nodeStyle.value.borderRadius
  if (typeof radius === 'string' && radius.length > 0) {
    return radius
  }
  if (typeof radius === 'number') {
    return `${radius}px`
  }
  return '4.5px'
})

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

const isSheetPickActive = computed(() => isLearningSheetCustomPickActive())

/**
 * Post-add open path (Enter sibling / Tab child): pending is armed on the store
 * before this host mounts. Do NOT open edit on the first paint — ResizeObserver
 * must measure display chrome first. One rAF later, flip store session so
 * InlineEditableText's isEditing watch starts the input.
 */
watch(
  mindMapPendingEditNodeId,
  (pendingId) => {
    if (pendingId !== props.id) return
    markMindMapInlineEditStage('branch:pending-seen', {
      nodeId: props.id,
      pendingId,
      editingId: mindMapEditingNodeId.value,
      readonly: isTextReadonly.value,
    })
    if (isTextReadonly.value) {
      markMindMapInlineEditStage('branch:session-skip', {
        nodeId: props.id,
        reason: 'readonly',
      })
      return
    }
    if (collabCanvas?.isNodeLockedByOther?.(props.id)) {
      markMindMapInlineEditStage('branch:session-skip', {
        nodeId: props.id,
        reason: 'collab-locked',
      })
      return
    }
    requestAnimationFrame(() => {
      if (mindMapPendingEditNodeId.value !== props.id) {
        markMindMapInlineEditStage('branch:session-skip', {
          nodeId: props.id,
          reason: 'pending-cleared-before-raf',
          pendingId: mindMapPendingEditNodeId.value,
        })
        return
      }
      if (mindMapEditingNodeId.value === props.id) {
        markMindMapInlineEditStage('branch:session-skip', {
          nodeId: props.id,
          reason: 'session-already-open',
        })
        return
      }
      markMindMapInlineEditStage('branch:session-open', {
        nodeId: props.id,
        pendingId: mindMapPendingEditNodeId.value,
        source: 'pending-watch-raf',
      })
      isEditing.value = true
    })
  },
  { immediate: true }
)

function handleBranchMovePointerDown(event: MouseEvent): void {
  if (isSheetPickActive.value) return
  branchMove.onBranchMovePointerDown(props.id, isEditing.value, event.clientX, event.clientY)
}

function handleBranchMoveTouchStart(event: TouchEvent): void {
  if (isSheetPickActive.value) return
  if (event.touches.length !== 1) return
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
  branchMove.onBranchMovePointerUp()
}

useNodeDimensions(branchNodeRef, props.id, {
  onResize(w, h) {
    // Height while editing: Enter opens inline edit immediately; height SoT must
    // update for the next sibling insert. Width while editing comes from the
    // tighter <input> box and must not run the X pass (canvas-click slide).
    if (diagramStore.isLearningSheet && diagramStore.isNodeBlankedForLearningSheet(props.id)) {
      return
    }
    if (isEditing.value) {
      diagramStore.setMindMapNodeDimensions(props.id, undefined, h)
      return
    }
    diagramStore.setMindMapNodeDimensions(props.id, w, h)
  },
})

onMounted(() => {
  markMindMapLoadShellMounted('branch')
})

function handleTextSave(newText: string) {
  isEditing.value = false
  eventBus.emit('node:text_updated', {
    nodeId: props.id,
    text: stripMatchingBranchNumberPrefix(newText, numberPrefix.value),
  })
}

function handleEditCancel() {
  isEditing.value = false
}

function handleBranchNodeDoubleClick(): void {
  if (isLearningSheetCustomPickActive()) return
  if (diagramPresentationReadOnlyRef.value || toValue(diagramStore.isReadonly)) return
  if ((props.data.hidden === true && diagramStore.isLearningSheet) || isEditing.value) return
  if (collabCanvas?.isNodeLockedByOther?.(props.id)) {
    notifyCollab.warning(t('collab.nodeLocked'))
    return
  }
  diagramStore.selectNodes(props.id)
  isEditing.value = true
}

function handleBranchNodeClick(event: MouseEvent): void {
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
    :phase="isSubgraphGenerating ? 'waiting' : 'idle'"
    :active="isSubgraphGenerating"
    :border-radius="subgraphRingBorderRadius"
    streaming-variant="primary"
    ring-padding="3px"
    class="branch-node-ring"
  >
    <div
      ref="branchNodeRef"
      class="branch-node flex select-none border-solid relative mind-map-node"
      :class="[
        isUnderlineShape ? 'flex-col items-stretch mind-map-underline-node' : 'items-center',
        contentJustifyClass,
        {
          'cursor-grab': !isSheetPickActive,
          'branch-node--sheet-pick': isSheetPickActive,
        },
      ]"
      :style="nodeStyle"
      :aria-label="accessibleBranchLabel"
      @mousedown.capture="handleBranchMovePointerDown"
      @mouseup.capture="handleBranchMovePointerUp"
      @touchstart.passive.capture="handleBranchMoveTouchStart"
      @click.capture="handleBranchNodeClick"
      @dblclick="handleBranchNodeDoubleClick"
    >
      <template v-if="isUnderlineShape">
        <div
          class="mind-map-underline-text"
          :style="underlineTextStyle"
        >
          <div
            class="mm-branch-text-row"
            :style="numberPrefixGapStyle"
          >
            <span
              v-if="showNumberPrefix"
              class="mm-branch-number"
              aria-hidden="true"
              >{{ numberPrefix }}</span
            >
            <InlineEditableText
              :text="data.label || ''"
              :node-id="id"
              :is-editing="isEditing"
              :readonly="isTextReadonly"
              :max-width="textMaxWidth"
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
        </div>
        <div
          class="mind-map-underline-line"
          :style="underlineLineStyle"
        />
      </template>
      <div
        v-else
        class="mm-branch-text-row"
        :style="numberPrefixGapStyle"
      >
        <span
          v-if="showNumberPrefix"
          class="mm-branch-number"
          aria-hidden="true"
          >{{ numberPrefix }}</span
        >
        <InlineEditableText
          :text="data.label || ''"
          :node-id="id"
          :is-editing="isEditing"
          :readonly="isTextReadonly"
          :max-width="textMaxWidth"
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

      <Handle
        id="left"
        type="target"
        :position="Position.Left"
        :style="isUnderlineShape ? mindMapUnderlineHandleStyle('left') : undefined"
        class="bg-blue-400!"
      />
      <Handle
        id="right"
        type="source"
        :position="Position.Right"
        :style="isUnderlineShape ? mindMapUnderlineHandleStyle('right') : undefined"
        class="bg-blue-400!"
      />
      <Handle
        id="right-target"
        type="target"
        :position="Position.Right"
        :style="isUnderlineShape ? mindMapUnderlineHandleStyle('right') : undefined"
        class="bg-blue-400!"
      />
      <Handle
        id="left-source"
        type="source"
        :position="Position.Left"
        :style="isUnderlineShape ? mindMapUnderlineHandleStyle('left') : undefined"
        class="bg-blue-400!"
      />
    </div>
  </LlmPhaseRing>
</template>

<style scoped>
.branch-node.mind-map-node.mind-map-underline-node {
  min-width: unset;
  min-height: unset;
  height: fit-content;
  width: fit-content;
  box-shadow: none !important;
}

.branch-node.mind-map-underline-node {
  width: fit-content;
  height: fit-content;
  box-shadow: none !important;
}

.branch-node.mind-map-underline-node .mind-map-underline-text {
  width: 100%;
}

.branch-node.mind-map-underline-node :deep(.inline-editable-text) {
  min-height: 0;
  line-height: 1.35;
}

.branch-node.mind-map-underline-node :deep(.inline-edit-display) {
  line-height: 1.35;
}

.branch-node.mind-map-underline-node .mind-map-underline-line {
  width: 100%;
  flex-shrink: 0;
}

.branch-node.mind-map-underline-node:hover {
  box-shadow: none !important;
}

.branch-node.mind-map-node {
  min-width: 90px;
  min-height: 34px;
  width: fit-content;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.branch-node.mind-map-node:hover {
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.1);
  border-color: #94a3b8;
}

.branch-node {
  min-width: 80px;
  min-height: 36px;
  transition:
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.branch-node:active:not(.branch-node--sheet-pick) {
  cursor: grabbing;
}

.branch-node-ring {
  width: fit-content;
  height: fit-content;
}

.branch-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}

.mm-branch-text-row {
  display: flex;
  align-items: center;
  width: fit-content;
  min-width: 0;
  max-width: 100%;
}

.mind-map-underline-node .mm-branch-text-row {
  align-items: flex-start;
  width: 100%;
}

.mm-branch-number {
  flex-shrink: 0;
  white-space: nowrap;
  color: inherit;
  user-select: none;
  pointer-events: none;
}
</style>
