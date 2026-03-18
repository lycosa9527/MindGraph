<script setup lang="ts">
/**
 * BranchNode - Branch/child node for mind maps and tree maps
 * Represents branches, children, or categories in hierarchical diagrams
 * Supports inline text editing on double-click
 */
import { computed, inject, ref } from 'vue'
import type { CSSProperties } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { getMindmapBranchColor } from '@/config/mindmapColors'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import type { MindGraphNodeProps } from '@/types'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

// Get theme defaults matching old StyleManager
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

// Determine if this is a child node (deeper in hierarchy)
const isChild = computed(() => props.data.nodeType === 'branch' && props.data.parentId)

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

// Check if this is a bridge map node (should be text-only, including first pair)
const isBridgeMap = computed(() => props.data.diagramType === 'bridge_map')

// Mindmap uses pill shape for branch and children nodes (matches topic)
const isMindMap = computed(
  () => props.data.diagramType === 'mindmap' || props.data.diagramType === 'mind_map'
)

const mindmapBranchColors = computed(() => {
  const index = (props.data.branchIndex as number) ?? 0
  return getMindmapBranchColor(index)
})

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

const isFirstPair = computed(() => {
  if (!isBridgeMap.value) return true
  const pairIndex = props.data.pairIndex
  return pairIndex === undefined || pairIndex === 0
})

const nodeStyle = computed((): CSSProperties => {
  // For all bridge map nodes (including first pair), remove borders, background, and shadows (text-only)
  const shouldHaveBorder = !isBridgeMap.value
  const shouldHaveBackground = !isBridgeMap.value
  const shouldHaveShadow = !isBridgeMap.value

  const bgColor = shouldHaveBackground
    ? props.data.style?.backgroundColor ||
      (isTreeMap.value && treeMapGroupColors.value
        ? treeMapGroupColors.value.fill
        : isMindMap.value
          ? mindmapBranchColors.value.fill
          : defaultStyle.value.backgroundColor) ||
      '#e3f2fd'
    : 'transparent'
  const borderColor = shouldHaveBorder
    ? props.data.style?.borderColor ||
      (isTreeMap.value && treeMapGroupColors.value
        ? treeMapGroupColors.value.border
        : isMindMap.value
          ? mindmapBranchColors.value.border
          : defaultStyle.value.borderColor) ||
      '#4e79a7'
    : 'transparent'

  const borderWidth = shouldHaveBorder
    ? (props.data.style?.borderWidth ?? (isMindMap.value ? 3 : defaultStyle.value.borderWidth) ?? 2)
    : 0
  const borderStyle = shouldHaveBorder
    ? (props.data.style?.borderStyle || 'solid')
    : 'solid'

  const base: CSSProperties = {
    backgroundColor: bgColor,
    ...(shouldHaveBorder
      ? getBorderStyleProps(borderColor, borderWidth, borderStyle, {
          backgroundColor: bgColor,
        })
      : { borderColor: 'transparent', borderWidth: '0px', borderStyle: 'none' }),
    color: props.data.style?.textColor || defaultStyle.value.textColor || '#333333',
    fontFamily: props.data.style?.fontFamily,
    fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 16}px`,
    fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    borderRadius:
      isMindMap.value || isTreeMap.value
        ? '9999px'
        : `${props.data.style?.borderRadius || 8}px`,
    boxShadow: shouldHaveShadow ? undefined : 'none',
  }
  // Tree map: use measured width from layout for center alignment (rendered must match layout)
  if (isTreeMap.value && props.data.style?.width != null) {
    base.width = `${props.data.style.width}px`
    base.minWidth = `${props.data.style.width}px`
    base.maxWidth = `${props.data.style.width}px`
  }
  return base
})

// Inline editing state
const isEditing = ref(false)

// Branch move (mind map long-press to move branch)
const branchMove = inject<{
  onBranchMovePointerDown: (
    nodeId: string,
    isEditing: boolean,
    clientX?: number,
    clientY?: number
  ) => void
  onBranchMovePointerUp: () => void
}>('branchMove', { onBranchMovePointerDown: () => {}, onBranchMovePointerUp: () => {} })

const supportsBranchMove = computed(
  () =>
    isMindMap.value ||
    (props.data.diagramType === 'tree_map' && (props.id?.startsWith('tree-cat-') || props.id?.startsWith('tree-leaf-'))) ||
    (isBridgeMap.value && props.id?.startsWith('pair-'))
)

function handleBranchMovePointerDown(event: MouseEvent): void {
  if (supportsBranchMove.value) {
    branchMove.onBranchMovePointerDown(
      props.id,
      isEditing.value,
      event.clientX,
      event.clientY
    )
  }
}

function handleBranchMovePointerUp(): void {
  if (supportsBranchMove.value) {
    branchMove.onBranchMovePointerUp()
  }
}

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
</script>

<template>
  <div
    class="branch-node flex items-center justify-center px-4 py-2 cursor-grab select-none border-solid"
    :class="{
      'tree-map-node': isTreeMap,
      'border-none': isBridgeMap,
    }"
    :style="nodeStyle"
    @mousedown.capture="handleBranchMovePointerDown"
    @mouseup.capture="handleBranchMovePointerUp"
  >
    <InlineEditableText
      :text="data.label || ''"
      :node-id="id"
      :is-editing="isEditing"
      :readonly="data.hidden === true"
      max-width="150px"
      text-align="center"
      :text-decoration="data.style?.textDecoration || 'none'"
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />

    <!-- Connection handles for horizontal layouts (mind maps, etc.) -->
    <!-- Hide handles for bridge maps (connections handled by overlay) -->
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

.branch-node:active {
  cursor: grabbing;
}

/* Hide handle dots visually while keeping them functional */
.branch-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}
</style>
