<script setup lang="ts">
/**
 * V2 mind map canvas overlays — lazy chunk paired with MindMapV2Canvas.vue.
 * Floating toolbar (incl. node explain), learning-sheet bar, directional add, collapse toggles.
 */
import { type Ref, computed, inject, unref } from 'vue'

import { CanvasNodeFloatingToolbar } from '@/components/canvas'
import LearningSheetFloatBar from '@/components/canvas/LearningSheetFloatBar.vue'
import type {
  FloatingToolbarPosition,
  FloatingToolbarSize,
} from '@/composables/canvasToolbar/useNodeFloatingToolbarPosition'
import { useUIStore } from '@/stores'

import MindMapCollapseToggleOverlay from './MindMapCollapseToggleOverlay.vue'
import MindMapDirectionalAddOverlay from './MindMapDirectionalAddOverlay.vue'

const props = defineProps<{
  presentationDiagramEditLocked: boolean
  floatingToolbarPosition: FloatingToolbarPosition
  floatingToolbarAnchorId: string | null
  subgraphGenerating: boolean
  floatingToolbarShowAiSubgraph: boolean
  /** Hide teleported node chrome while the explain bubble is open. */
  nodeExplainOpen: boolean
  canvasContainer: Ref<HTMLElement | null> | HTMLElement | null
  presentationTeleportTarget: string | HTMLElement | undefined
  onAiSubgraphGenerate: () => void
  onExplainNode: () => void
  onFloatingToolbarSizeChange: (size: FloatingToolbarSize | null) => void
}>()

const uiStore = useUIStore()

const branchMove = inject<{ state: { value: { active: boolean } } } | null>('branchMove', null)
const branchMoveActive = computed(() => branchMove?.state.value.active === true)

const resolvedContainer = computed((): HTMLElement | null => unref(props.canvasContainer))
</script>

<template>
  <LearningSheetFloatBar
    v-if="!presentationDiagramEditLocked && !uiStore.exportWireframeOutline"
  />

  <!-- Hide toolbar / add handles so they do not cover the explain bubble. -->
  <CanvasNodeFloatingToolbar
    v-if="!presentationDiagramEditLocked && !nodeExplainOpen"
    :position="floatingToolbarPosition"
    :node-id="floatingToolbarAnchorId"
    :ai-generating="subgraphGenerating"
    :show-ai-subgraph="floatingToolbarShowAiSubgraph"
    @ai-subgraph-generate="onAiSubgraphGenerate()"
    @explain-node="onExplainNode()"
    @size-change="onFloatingToolbarSizeChange($event)"
  />

  <MindMapDirectionalAddOverlay
    v-if="
      !presentationDiagramEditLocked &&
      !uiStore.exportWireframeOutline &&
      !nodeExplainOpen &&
      !branchMoveActive
    "
    :container-ref="resolvedContainer"
    :teleport-target="presentationTeleportTarget"
  />
  <MindMapCollapseToggleOverlay
    v-if="!presentationDiagramEditLocked && !uiStore.exportWireframeOutline && !branchMoveActive"
    :container-ref="resolvedContainer"
    :teleport-target="presentationTeleportTarget"
  />
</template>
