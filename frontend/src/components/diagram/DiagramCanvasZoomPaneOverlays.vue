<script setup lang="ts">
import type { GraphNode } from '@vue-flow/core'

import { getBranchMoveCircleStyle, getDropTargetStyle } from '@/composables/diagramCanvas'
import type { DropTarget } from '@/composables/editor/useBranchMoveDrag'
import type { useBranchMoveDrag } from '@/composables/editor/useBranchMoveDrag'

type BranchMove = ReturnType<typeof useBranchMoveDrag>

defineProps<{
  branchMove: BranchMove
  /** Returns current Vue Flow nodes (for branch-move drop target sizing). */
  getVueFlowNodes: () => GraphNode[]
  linkPreviewPath: string | null
  linkDragCursor: { x: number; y: number } | null
  linkDragTargetNodeId: string | null
  showConceptLinkPreview: boolean
  linkPreviewShowArrow: boolean
}>()
</script>

<template>
  <div
    v-if="branchMove.state.value.active && branchMove.state.value.cursorPos"
    class="branch-move-overlay pointer-events-none"
    style="position: absolute; inset: 0; z-index: 10"
  >
    <div
      class="branch-move-circle"
      :style="getBranchMoveCircleStyle(branchMove.state.value)"
    />
    <div
      v-if="branchMove.state.value.dropTarget"
      class="branch-move-drop-preview"
      :style="getDropTargetStyle(getVueFlowNodes, branchMove.state.value.dropTarget as DropTarget)"
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
