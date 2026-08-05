<script setup lang="ts">
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
/**
 * MindMapLegacyBranchNode — classic mind map branch node (pill, per-branch palette).
 */
import { computed, inject, ref, toValue } from 'vue'
import type { CSSProperties } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { useLanguage, useNotifications } from '@/composables'
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
import { getMindmapBranchColor } from '@/config/mindmapColors'
import { useDiagramStore } from '@/stores/diagram'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import {
  MIND_MAP_BRANCH_MAX_TEXT_WIDTH,
  resolveMindMapBranchTextMaxWidthPx,
} from '@/utils/mindMapTextWrap'

import InlineEditableText from '../InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const diagramStore = useDiagramSession()
const isTextReadonly = computed(
  () =>
    (props.data.hidden === true && diagramStore.isLearningSheet) ||
    (diagramPresentationReadOnlyRef.value || toValue(diagramStore.isReadonly))
)
const branchNodeRef = ref<HTMLDivElement | null>(null)
const exportOutlineActive = useMindMapExportOutlineWireframeActive()

function finalizeMindMapExportNodeStyle(style: CSSProperties): CSSProperties {
  return wrapMindMapNodeStyleForExport(style, exportOutlineActive.value, {
    isMindMapV2: false,
    isUnderlineShape: false,
  })
}

const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const isChild = computed(() => props.data.nodeType === 'branch' && Boolean(props.data.parentId))

const themeNodeType = computed(() => (isChild.value ? 'child' : 'branch'))
const defaultStyle = computed(() => getNodeStyle(themeNodeType.value))

const resolvedStyle = computed(() => ({
  ...(diagramStore.data?._node_styles?.[props.id] || {}),
  ...(props.data.style || {}),
}))

const mindmapBranchColors = computed(() => {
  const index = (props.data.branchIndex as number) ?? 0
  return getMindmapBranchColor(index, 'legacy')
})

const nodeStyle = computed((): CSSProperties => {
  const style = resolvedStyle.value
  const bgColor = mindmapBranchColors.value.fill
  const borderColor = mindmapBranchColors.value.border
  const borderWidth = style.borderWidth ?? defaultStyle.value.borderWidth ?? 3
  const borderStyleVal = style.borderStyle || 'solid'

  const legacy: CSSProperties = {
    backgroundColor: bgColor,
    ...getBorderStyleProps(borderColor, borderWidth, borderStyleVal, {
      backgroundColor: bgColor,
    }),
    color: style.textColor || defaultStyle.value.textColor || '#333333',
    fontFamily: style.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${style.fontSize || defaultStyle.value.fontSize || 16}px`,
    fontWeight: style.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: style.fontStyle || 'normal',
    textDecoration: style.textDecoration || 'none',
    borderRadius: '9999px',
  }
  return finalizeMindMapExportNodeStyle(legacy)
})

const textMaxWidth = computed(() => {
  const label = ((props.data.label as string) || '').trim()
  if (!label) return `${MIND_MAP_BRANCH_MAX_TEXT_WIDTH}px`
  const fontSize = parseFloat(nodeStyle.value.fontSize as string) || 16
  const fontWeight = String(nodeStyle.value.fontWeight || 'normal')
  return `${resolveMindMapBranchTextMaxWidthPx(label, fontSize, {
    fontWeight,
    fontFamily: DIAGRAM_NODE_FONT_STACK,
  })}px`
})

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

const isSheetPickActive = computed(() => isLearningSheetCustomPickActive())

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
    if (isEditing.value) return
    if (diagramStore.isLearningSheet && diagramStore.isNodeBlankedForLearningSheet(props.id)) {
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
  if ((diagramPresentationReadOnlyRef.value || toValue(diagramStore.isReadonly))) return
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
  <div
    ref="branchNodeRef"
    class="branch-node flex select-none border-solid relative items-center justify-center mind-map-legacy-node px-4 py-2"
    :class="{
      'cursor-grab': !isSheetPickActive,
      'branch-node--sheet-pick': isSheetPickActive,
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
      auto-wrap
      render-markdown
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @close="handleEditCancel"
      @edit-start="isEditing = true"
    />

    <Handle
      id="left"
      type="target"
      :position="Position.Left"
      class="bg-blue-400!"
    />
    <Handle
      id="right"
      type="source"
      :position="Position.Right"
      class="bg-blue-400!"
    />
    <Handle
      id="right-target"
      type="target"
      :position="Position.Right"
      class="bg-blue-400!"
    />
    <Handle
      id="left-source"
      type="source"
      :position="Position.Left"
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

.branch-node:hover {
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.12);
  border-color: #3b82f6;
}

.branch-node:active:not(.branch-node--sheet-pick) {
  cursor: grabbing;
}

.branch-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
