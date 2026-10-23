<script setup lang="ts">
/**
 * V2 mind map canvas overlays — lazy chunk paired with MindMapV2Canvas.vue.
 * Floating toolbar (incl. node explain), directional add, collapse toggles.
 */
import { type Ref, computed, inject, unref } from 'vue'

import { CanvasNodeFloatingToolbar } from '@/components/canvas'
import { useCanvasNodeChromeOverlayGate } from '@/composables/canvasToolbar'
import type {
  FloatingToolbarPosition,
  FloatingToolbarSize,
} from '@/composables/canvasToolbar/useNodeFloatingToolbarPosition'
import { useUIStore } from '@/stores'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'

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
const headlessExport = isMindgraphHeadlessExportSession()
const overlayBlocksNodeChrome = useCanvasNodeChromeOverlayGate()

const branchMove = inject<{ state: { value: { active: boolean } } } | null>('branchMove', null)
const branchMoveActive = computed(() => branchMove?.state.value.active === true)

const resolvedContainer = computed((): HTMLElement | null => unref(props.canvasContainer))
const hideNodeChrome = computed(
  () =>
    headlessExport ||
    props.presentationDiagramEditLocked ||
    props.nodeExplainOpen ||
    overlayBlocksNodeChrome.value
)
const hideCollapseChrome = computed(
  () => headlessExport || props.presentationDiagramEditLocked || overlayBlocksNodeChrome.value
)
</script>

<template>
  <!-- Hide body-teleported chrome so it cannot paint over brainstorm / dialogs. -->
  <CanvasNodeFloatingToolbar
    v-if="!hideNodeChrome"
    :position="floatingToolbarPosition"
    :node-id="floatingToolbarAnchorId"
    :ai-generating="subgraphGenerating"
    :show-ai-subgraph="floatingToolbarShowAiSubgraph"
    @ai-subgraph-generate="onAiSubgraphGenerate()"
    @explain-node="onExplainNode()"
    @size-change="onFloatingToolbarSizeChange($event)"
  />

  <MindMapDirectionalAddOverlay
    v-if="!hideNodeChrome && !uiStore.exportWireframeOutline && !branchMoveActive"
    :container-ref="resolvedContainer"
    :teleport-target="presentationTeleportTarget"
  />
  <MindMapCollapseToggleOverlay
    v-if="!hideCollapseChrome && !uiStore.exportWireframeOutline && !branchMoveActive"
    :container-ref="resolvedContainer"
    :teleport-target="presentationTeleportTarget"
  />
</template>
