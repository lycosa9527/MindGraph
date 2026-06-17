<script setup lang="ts">
import { computed, toValue } from 'vue'

import type { GraphNode } from '@vue-flow/core'

import {
  getBranchMoveCircleStyle,
  getBranchMoveGhostStyle,
  getDropTargetStyle,
} from '@/composables/diagramCanvas'
import { getDropTargetShapeClass } from '@/composables/diagramCanvas/diagramCanvasZoomPaneStyles'
import type { DropTarget } from '@/composables/editor/useBranchMoveDrag'
import type { useBranchMoveDrag } from '@/composables/editor/useBranchMoveDrag'
import type { MindGraphNode } from '@/types/vueflow'

type BranchMove = ReturnType<typeof useBranchMoveDrag>

const props = defineProps<{
  branchMove: BranchMove
  /** Returns current Vue Flow nodes (for branch-move drop target sizing). */
  getVueFlowNodes: () => GraphNode[]
  linkPreviewPath: string | null
  linkDragCursor: { x: number; y: number } | null
  linkDragTargetNodeId: string | null
  showConceptLinkPreview: boolean
  linkPreviewShowArrow: boolean
}>()

const dragState = computed(() => toValue(props.branchMove.state))

const ghostLayoutStyle = computed(() =>
  getBranchMoveGhostStyle({
    cursorPos: dragState.value.cursorPos,
    ghost: dragState.value.draggedGhost,
  })
)

const dropTargetShapeClass = computed((): string => {
  const target = dragState.value.dropTarget
  if (!target) return ''
  const node = props.getVueFlowNodes().find((n) => n.id === target.nodeId) as
    | MindGraphNode
    | undefined
  return node ? getDropTargetShapeClass(node) : ''
})
</script>

<template>
  <div
    v-if="dragState.active && dragState.cursorPos"
    class="branch-move-overlay pointer-events-none"
    style="position: absolute; inset: 0; z-index: 1000"
  >
    <div
      v-if="dragState.draggedGhost && ghostLayoutStyle"
      class="branch-move-ghost"
      :class="[
        dragState.draggedGhost.shapeClass,
        dragState.draggedGhost.variant === 'underline'
          ? 'branch-move-ghost--underline'
          : 'branch-move-ghost--standard',
      ]"
      :style="{
        ...ghostLayoutStyle,
        backgroundColor: dragState.draggedGhost.backgroundColor,
        color: dragState.draggedGhost.textColor,
        borderColor: dragState.draggedGhost.borderColor,
        fontSize: dragState.draggedGhost.fontSize,
        fontWeight: dragState.draggedGhost.fontWeight,
        borderRadius: dragState.draggedGhost.borderRadius,
      }"
    >
      <span class="branch-move-ghost__label">{{ dragState.draggedGhost.label }}</span>
      <span
        v-if="dragState.draggedGhost.variant === 'underline'"
        class="branch-move-ghost__underline"
        :style="{ backgroundColor: dragState.draggedGhost.borderColor }"
      />
    </div>
    <div
      v-else
      class="branch-move-circle"
      :style="getBranchMoveCircleStyle(dragState)"
    />
    <div
      v-if="dragState.dropTarget"
      class="branch-move-drop-preview"
      :class="dropTargetShapeClass"
      :style="getDropTargetStyle(getVueFlowNodes, dragState.dropTarget as DropTarget)"
    />
  </div>
  <svg
    v-if="linkPreviewPath && linkDragCursor && showConceptLinkPreview"
    class="concept-map-link-preview pointer-events-none"
    style="position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; z-index: 10"
  >
    <defs>
      <marker
        id="concept-map-link-preview-arrow"
        markerWidth="10"
        markerHeight="10"
        refX="8"
        refY="5"
        orient="auto"
        markerUnits="userSpaceOnUse"
      >
        <path
          d="M0,0 L0,10 L10,5 z"
          fill="#94a3b8"
          opacity="0.6"
        />
      </marker>
    </defs>
    <path
      :d="linkPreviewPath"
      fill="none"
      stroke="#94a3b8"
      stroke-width="2"
      opacity="0.6"
      :marker-end="linkPreviewShowArrow ? 'url(#concept-map-link-preview-arrow)' : undefined"
    />
    <rect
      v-if="!linkDragTargetNodeId"
      :x="linkDragCursor.x - 40"
      :y="linkDragCursor.y - 18"
      width="80"
      height="36"
      rx="18"
      ry="18"
      class="concept-map-link-preview-pill"
      opacity="0.6"
    />
  </svg>
</template>
