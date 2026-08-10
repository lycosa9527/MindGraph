<script setup lang="ts">
/**
 * V2 mind map canvas overlays — lazy chunk paired with MindMapV2Canvas.vue.
 * Floating toolbar, learning-sheet bar, directional add, collapse toggles.
 */
import { type Ref, computed, unref } from 'vue'

import { CanvasNodeFloatingToolbar } from '@/components/canvas'
import LearningSheetFloatBar from '@/components/canvas/LearningSheetFloatBar.vue'
import type { FloatingToolbarPosition } from '@/composables/canvasToolbar/useNodeFloatingToolbarPosition'
import { useUIStore } from '@/stores'

import MindMapCollapseToggleOverlay from './MindMapCollapseToggleOverlay.vue'
import MindMapDirectionalAddOverlay from './MindMapDirectionalAddOverlay.vue'

const props = defineProps<{
  presentationDiagramEditLocked: boolean
  floatingToolbarPosition: FloatingToolbarPosition
  floatingToolbarAnchorId: string | null
  subgraphGenerating: boolean
  floatingToolbarShowAiSubgraph: boolean
  canvasContainer: Ref<HTMLElement | null> | HTMLElement | null
  presentationTeleportTarget: string | HTMLElement | undefined
  onAiSubgraphGenerate: () => void
  onNodeExplain: () => void
}>()

const uiStore = useUIStore()

const resolvedContainer = computed((): HTMLElement | null => unref(props.canvasContainer))
</script>

<template>
  <LearningSheetFloatBar
    v-if="!presentationDiagramEditLocked && !uiStore.exportWireframeOutline"
  />

  <CanvasNodeFloatingToolbar
    v-if="!presentationDiagramEditLocked"
    :position="floatingToolbarPosition"
    :node-id="floatingToolbarAnchorId"
    :ai-generating="subgraphGenerating"
    :show-ai-subgraph="floatingToolbarShowAiSubgraph"
    @ai-subgraph-generate="onAiSubgraphGenerate()"
    @node-explain="onNodeExplain()"
  />

  <MindMapDirectionalAddOverlay
    v-if="!presentationDiagramEditLocked && !uiStore.exportWireframeOutline"
    :container-ref="resolvedContainer"
    :teleport-target="presentationTeleportTarget"
  />
  <MindMapCollapseToggleOverlay
    v-if="!presentationDiagramEditLocked && !uiStore.exportWireframeOutline"
    :container-ref="resolvedContainer"
    :teleport-target="presentationTeleportTarget"
  />
</template>
