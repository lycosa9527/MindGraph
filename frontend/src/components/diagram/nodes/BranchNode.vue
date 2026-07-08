<script setup lang="ts">
/**
 * BranchNode - Branch/child node for mind maps and tree maps
 * Represents branches, children, or categories in hierarchical diagrams
 * Supports inline text editing on double-click
 */
import { computed, inject, ref } from 'vue'
import type { CSSProperties } from 'vue'

import { Handle, Position } from '@vue-flow/core'
import { storeToRefs } from 'pinia'

import LlmPhaseRing from '@/components/shared/LlmPhaseRing.vue'
import { useLanguage, useNotifications } from '@/composables'
import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'
import { eventBus } from '@/composables/core/useEventBus'
import {
  handleLearningSheetPickNodeClick,
  isLearningSheetCustomPickActive,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import {
  useMindMapExportOutlineWireframeActive,
  wrapMindMapNodeStyleForExport,
} from '@/composables/mindMap/useMindMapExportOutlineWireframe'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import { useTheme } from '@/composables/core/useTheme'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import {
  MIND_MAP_GEOMETRY,
  MINDMAP_UNDERLINE_STROKE_WIDTH,
  mindMapBranchDepth,
  mindMapBranchFontSize,
  mindMapHorizontalPadding,
  mindMapUnderlineContentPadding,
} from '@/config/mindMapGeometry'
import { getMindMapThemeForDiagram } from '@/config/mindMapThemes'
import { useDiagramStore } from '@/stores/diagram'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'
import { measureTextWidth } from '@/stores/specLoader/textMeasurement'
import { computeScriptAwareMaxWidth } from '@/stores/specLoader/textMeasurementFallback'
import type { MindGraphNodeProps } from '@/types'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { applyNodeShapeToStyle, mindMapUnderlineHandleStyle, resolveNodeShape } from '@/utils/nodeShapeStyle'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const diagramStore = useDiagramStore()
const isTextReadonly = computed(
  () =>
    (props.data.hidden === true && diagramStore.isLearningSheet) ||
    diagramPresentationReadOnlyRef.value
)
const branchNodeRef = ref<HTMLDivElement | null>(null)
const useMindMapV2Visuals = useMindMapV2Chrome()
const exportOutlineActive = useMindMapExportOutlineWireframeActive()

function finalizeMindMapExportNodeStyle(style: CSSProperties): CSSProperties {
  return wrapMindMapNodeStyleForExport(style, exportOutlineActive.value, {
    isMindMapV2: isMindMap.value && useMindMapV2Visuals.value,
    isUnderlineShape: isUnderlineShape.value,
  })
}

// Get theme defaults matching old StyleManager
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const isMindMap = computed(
  () => props.data.diagramType === 'mindmap' || props.data.diagramType === 'mind_map'
)

// Determine if this is a child node (deeper in hierarchy)
const isChild = computed(() => {
  if (isMindMap.value && !useMindMapV2Visuals.value) {
    return props.data.nodeType === 'branch' && props.data.parentId
  }
  if (isMindMap.value) {
    return mindMapBranchDepth(props.id) >= 2
  }
  return props.data.nodeType === 'branch' && props.data.parentId
})

// Tree map: use branch style for categories, leaf style for children
const themeNodeType = computed(() => {
  if (props.data.diagramType === 'tree_map') {
    return props.data.nodeType === 'leaf' ? 'leaf' : 'branch'
  }
  return isChild.value ? 'child' : 'branch'
})

const defaultStyle = computed(() => getNodeStyle(themeNodeType.value))

// Check if this is a tree map (needs vertical handles)
const isTreeMap = computed(() => props.data.diagramType === 'tree_map')

const BRANCH_MAX_TEXT_WIDTH = 200

const textMaxWidth = computed(() => {
  const label = ((props.data.label as string) || '').trim()
  if (isTreeMap.value && props.data.style?.width != null) {
    const px = Number(props.data.style.width)
    return `${Math.max(60, px - 32)}px`
  }
  if (props.data.diagramType === 'bridge_map') {
    return 'min(420px, 88vw)'
  }

  if (!label) return `${BRANCH_MAX_TEXT_WIDTH}px`

  const wrapThreshold = computeScriptAwareMaxWidth(label, BRANCH_MAX_TEXT_WIDTH)
  const fontSize =
    parseFloat(nodeStyle.value.fontSize as string) ||
    mindMapBranchFontSize(isMindMap.value ? props.id : undefined)
  const fontWeight = String(nodeStyle.value.fontWeight || 'normal')
  const textWidth = measureTextWidth(label, fontSize, { fontWeight })

  if (textWidth <= wrapThreshold) {
    return `${wrapThreshold}px`
  }

  return `${BRANCH_MAX_TEXT_WIDTH}px`
})

const useAutoWrap = computed(() => !isTreeMap.value && !isBridgeMap.value)

// Check if this is a bridge map node (should be text-only, including first pair)
const isBridgeMap = computed(() => props.data.diagramType === 'bridge_map')

const mindmapBranchColors = computed(() => {
  const index = (props.data.branchIndex as number) ?? 0
  if (isMindMap.value && !useMindMapV2Visuals.value) {
    return getMindmapBranchColor(index, 'legacy')
  }
  return getMindmapBranchColor(index)
})

const nodeShape = computed(() => {
  if (isMindMap.value) {
    return resolveMindMapNodeShape(
      { id: props.id, type: 'branch', style: resolvedStyle.value },
      diagramStore.data?._mindmap_diagram_style as string | undefined
    )
  }
  return resolveNodeShape(resolvedStyle.value, false)
})
const isUnderlineShape = computed(() => isMindMap.value && nodeShape.value === 'underline')

const defaultMindMapTheme = computed(() =>
  useMindMapV2Visuals.value ? getMindMapThemeForDiagram(diagramStore.data) : null
)

const resolvedStyle = computed(() => ({
  ...(diagramStore.data?._node_styles?.[props.id] || {}),
  ...(props.data.style || {}),
}))

const mindMapThemeColors = computed(() => {
  const theme = defaultMindMapTheme.value
  if (!theme) {
    return { fill: '', border: '', text: '' }
  }
  return {
    fill: theme.backgroundColor,
    border: theme.borderColor,
    text: theme.textColor,
  }
})

const contentJustifyClass = computed(() => 'justify-center')

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

const underlineTextStyle = computed((): CSSProperties => {
  const padX = mindMapHorizontalPadding('underline')
  return {
    paddingLeft: `${padX}px`,
    paddingRight: `${padX}px`,
  }
})

const underlineLineStyle = computed((): CSSProperties => {
  const style = resolvedStyle.value
  const { textGap } = mindMapUnderlineContentPadding()
  if (isMindMap.value) {
    // The visible bar is painted in the SVG edge layer (MindMapOrthogonalEdge) so it shares
    // the connector's pixel grid and never seams under the fractional viewport transform.
    // Keep this box's height so node measurement/layout stays identical; just don't paint.
    return {
      backgroundColor: 'transparent',
      marginTop: `${textGap}px`,
      height: `${MINDMAP_UNDERLINE_STROKE_WIDTH}px`,
    }
  }
  const lineColor =
    style.borderColor ||
    (isTreeMap.value && treeMapGroupColors.value
      ? treeMapGroupColors.value.border
      : mindMapThemeColors.value.border) ||
    '#4e79a7'
  return {
    backgroundColor: lineColor,
    marginTop: `${textGap}px`,
    height: `${MINDMAP_UNDERLINE_STROKE_WIDTH}px`,
  }
})

const nodeStyle = computed((): CSSProperties => {
  // For all bridge map nodes (including first pair), remove borders, background, and shadows (text-only)
  const shouldHaveBorder = !isBridgeMap.value
  const shouldHaveBackground = !isBridgeMap.value
  const shouldHaveShadow = !isBridgeMap.value

  const style = resolvedStyle.value

  // Classic canvas: pill nodes with per-branch palette colors (pre-v2 design).
  if (isMindMap.value && !useMindMapV2Visuals.value) {
    const bgColor = shouldHaveBackground ? mindmapBranchColors.value.fill : 'transparent'
    const borderColor = shouldHaveBorder ? mindmapBranchColors.value.border : 'transparent'
    const borderWidth = shouldHaveBorder
      ? (style.borderWidth ?? defaultStyle.value.borderWidth ?? 3)
      : 0
    const borderStyleVal = shouldHaveBorder ? style.borderStyle || 'solid' : 'solid'

    const legacy: CSSProperties = {
      backgroundColor: bgColor,
      ...(shouldHaveBorder
        ? getBorderStyleProps(borderColor, borderWidth, borderStyleVal, { backgroundColor: bgColor })
        : { borderColor: 'transparent', borderWidth: '0px', borderStyle: 'none' }),
      color: style.textColor || defaultStyle.value.textColor || '#333333',
      fontFamily: style.fontFamily || DIAGRAM_NODE_FONT_STACK,
      fontSize: `${style.fontSize || defaultStyle.value.fontSize || 16}px`,
      fontWeight: style.fontWeight || defaultStyle.value.fontWeight || 'normal',
      fontStyle: style.fontStyle || 'normal',
      textDecoration: style.textDecoration || 'none',
      borderRadius: '9999px',
      boxShadow: shouldHaveShadow ? undefined : 'none',
    }
    return finalizeMindMapExportNodeStyle(legacy)
  }

  const bgColor = shouldHaveBackground
    ? style.backgroundColor ||
      (isTreeMap.value && treeMapGroupColors.value
        ? treeMapGroupColors.value.fill
        : isMindMap.value
          ? mindMapThemeColors.value.fill
          : defaultStyle.value.backgroundColor) ||
      '#e3f2fd'
    : 'transparent'
  const borderColor = shouldHaveBorder
    ? style.borderColor ||
      (isTreeMap.value && treeMapGroupColors.value
        ? treeMapGroupColors.value.border
        : isMindMap.value
          ? mindMapThemeColors.value.border
          : defaultStyle.value.borderColor) ||
      '#4e79a7'
    : 'transparent'

  const borderWidth = shouldHaveBorder
    ? (style.borderWidth ??
        (isMindMap.value ? MIND_MAP_GEOMETRY.borderWidth : defaultStyle.value.borderWidth) ??
        2)
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
      style.textColor ||
      (isMindMap.value ? mindMapThemeColors.value.text : defaultStyle.value.textColor) ||
      '#333333',
    fontFamily:
      style.fontFamily ||
      (isMindMap.value ? MIND_MAP_GEOMETRY.fontFamily : DIAGRAM_NODE_FONT_STACK),
    fontSize: `${
      style.fontSize ||
      defaultStyle.value.fontSize ||
      (isMindMap.value ? mindMapBranchFontSize(props.id) : MIND_MAP_GEOMETRY.fontSize)
    }px`,
    fontWeight: style.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: style.fontStyle || 'normal',
    textDecoration: style.textDecoration || 'none',
    boxShadow: shouldHaveShadow ? undefined : 'none',
  }

  const shape = nodeShape.value
  const shaped = applyNodeShapeToStyle(base, shape, borderColor, isMindMap.value)

  if (shape === 'rounded' && !style.nodeShape && !isMindMap.value) {
    shaped.borderRadius = `${style.borderRadius || 8}px`
  }

  const result: CSSProperties = { ...shaped }

  if (isMindMap.value) {
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
      result.boxShadow = shouldHaveShadow ? '0 1px 3px rgba(15, 23, 42, 0.06)' : 'none'
    }
    if (isBlankedForSheet && layoutWidth && layoutWidth > 0) {
      const widthPx = Math.max(layoutWidth, MIND_MAP_GEOMETRY.minWidth)
      result.width = `${widthPx}px`
      result.minWidth = `${widthPx}px`
    }
    if (isBlankedForSheet && layoutHeight && layoutHeight > 0) {
      result.minHeight = `${Math.max(layoutHeight, MIND_MAP_GEOMETRY.minHeight)}px`
    }
  }

  if (isTreeMap.value && props.data.style?.width != null) {
    result.width = `${props.data.style.width}px`
    result.minWidth = `${props.data.style.width}px`
    result.maxWidth = `${props.data.style.width}px`
  }
  return finalizeMindMapExportNodeStyle(result)
})

// Inline editing state
// Inline editing state
const isEditing = ref(false)

const previewStore = useMindMapSubgraphPreviewStore()
const { isGenerating: subgraphPreviewGenerating, generatingNodeId } = storeToRefs(previewStore)
const isSubgraphGenerating = computed(
  () => subgraphPreviewGenerating.value && generatingNodeId.value === props.id
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

// Branch move (mind map long-press to move branch)
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
    isMindMap.value ||
    (props.data.diagramType === 'tree_map' &&
      (props.id?.startsWith('tree-cat-') || props.id?.startsWith('tree-leaf-'))) ||
    (isBridgeMap.value && props.id?.startsWith('pair-'))
)

const isSheetPickActive = computed(() => isLearningSheetCustomPickActive())

function handleBranchMovePointerDown(event: MouseEvent): void {
  if (isSheetPickActive.value) return
  if (supportsBranchMove.value) {
    branchMove.onBranchMovePointerDown(props.id, isEditing.value, event.clientX, event.clientY)
  }
}

function handleBranchMoveTouchStart(event: TouchEvent): void {
  if (isSheetPickActive.value) return
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

useNodeDimensions(branchNodeRef, props.id, {
  onResize(w, h) {
    if (!isMindMap.value || isEditing.value) return
    if (
      diagramStore.isLearningSheet &&
      diagramStore.isNodeBlankedForLearningSheet(props.id)
    ) {
      return
    }
    diagramStore.setMindMapNodeDimensions(props.id, w, h)
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

function handleBranchNodeDoubleClick(): void {
  if (isLearningSheetCustomPickActive()) return
  if (diagramPresentationReadOnlyRef.value) return
  if ((props.data.hidden === true && diagramStore.isLearningSheet) || isEditing.value) return
  if (collabCanvas?.isNodeLockedByOther?.(props.id)) {
    notifyCollab.warning(t('collab.nodeLocked'))
    return
  }
  if (isMindMap.value) {
    diagramStore.selectNodes(props.id)
  }
  isEditing.value = true
}

function handleBranchNodeClick(event: MouseEvent): void {
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
      class="branch-node flex select-none border-solid relative"
      :class="[
        isUnderlineShape ? 'flex-col items-stretch' : 'items-center',
        contentJustifyClass,
        {
          'tree-map-node': isTreeMap,
          'mind-map-node': isMindMap && useMindMapV2Visuals,
          'mind-map-legacy-node': isMindMap && !useMindMapV2Visuals,
          'mind-map-underline-node': isUnderlineShape,
          'border-none': isBridgeMap,
          'px-4 py-2': !isMindMap || !useMindMapV2Visuals,
          'cursor-grab': !isSheetPickActive,
          'branch-node--sheet-pick': isSheetPickActive,
        },
      ]"
      :style="nodeStyle"
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

    <!-- Connection handles for horizontal layouts (mind maps, etc.) -->
    <!-- Hide handles for bridge maps (connections handled by overlay) -->
    <Handle
      v-if="!isTreeMap && !isBridgeMap"
      id="left"
      type="target"
      :position="Position.Left"
      :style="isUnderlineShape ? mindMapUnderlineHandleStyle('left') : undefined"
      class="bg-blue-400!"
    />
    <Handle
      v-if="!isTreeMap && !isBridgeMap"
      id="right"
      type="source"
      :position="Position.Right"
      :style="isUnderlineShape ? mindMapUnderlineHandleStyle('right') : undefined"
      class="bg-blue-400!"
    />
    <!-- Right target handle for mindmap left-side children (RL direction) -->
    <Handle
      v-if="
        !isTreeMap &&
        !isBridgeMap &&
        (data.diagramType === 'mindmap' || data.diagramType === 'mind_map')
      "
      id="right-target"
      type="target"
      :position="Position.Right"
      :style="isUnderlineShape ? mindMapUnderlineHandleStyle('right') : undefined"
      class="bg-blue-400!"
    />
    <!-- Left source handle for mindmap left-side branches (RL direction) -->
    <Handle
      v-if="
        !isTreeMap &&
        !isBridgeMap &&
        (data.diagramType === 'mindmap' || data.diagramType === 'mind_map')
      "
      id="left-source"
      type="source"
      :position="Position.Left"
      :style="isUnderlineShape ? mindMapUnderlineHandleStyle('left') : undefined"
      class="bg-blue-400!"
    />

    <!-- Connection handles for tree maps (vertical layout) -->
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
  </LlmPhaseRing>
</template>

<style scoped>
.branch-node.mind-map-node.mind-map-underline-node {
  min-width: unset;
  min-height: unset;
  width: fit-content;
  box-shadow: none !important;
}

.branch-node.mind-map-underline-node {
  width: fit-content;
  box-shadow: none !important;
}

.branch-node.mind-map-underline-node .mind-map-underline-text {
  width: 100%;
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

.branch-node.mind-map-node:hover:not(.border-none) {
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.1);
  border-color: #94a3b8;
}

.branch-node {
  min-width: 80px;
  min-height: 36px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  transition:
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

/* Tree map nodes: adaptive width, min-width for short labels */
.branch-node.tree-map-node {
  min-width: 80px;
}

/* Bridge map nodes (all pairs): no shadow */
.branch-node.border-none {
  box-shadow: none !important;
}

.branch-node:hover:not(.border-none) {
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.12);
  border-color: #3b82f6;
}

.branch-node:active:not(.branch-node--sheet-pick) {
  cursor: grabbing;
}

.branch-node-ring {
  width: fit-content;
  height: fit-content;
}

/* Hide handle dots visually while keeping them functional */
.branch-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
