<script setup lang="ts">
/**
 * BranchNode — routes mind maps to legacy/v2 shells; other diagram types use BranchNodeDiagram.
 * V2 and diagram shells are eager. An async shell mounts frames after its siblings,
 * so layout places the rest of the map around unmeasured branches, then moves it.
 */
import { computed, defineAsyncComponent } from 'vue'

import MindMapV2BranchNode from '@/components/diagram/nodes/mindMap/MindMapV2BranchNode.vue'
import { useMindMapCanvasVisuals } from '@/composables/mindMap/useMindMapCanvasVisuals'
import type { MindGraphNodeProps } from '@/types'

import BranchNodeDiagram from './BranchNodeDiagram.vue'

const props = defineProps<MindGraphNodeProps>()

const isMindMap = computed(
  () => props.data.diagramType === 'mindmap' || props.data.diagramType === 'mind_map'
)

const useMindMapV2 = useMindMapCanvasVisuals()

const MindMapLegacyBranchNode = defineAsyncComponent(
  () => import('./mindMap/MindMapLegacyBranchNode.vue')
)
</script>

<template>
  <MindMapLegacyBranchNode
    v-if="isMindMap && !useMindMapV2"
    v-bind="props"
  />
  <MindMapV2BranchNode
    v-else-if="isMindMap && useMindMapV2"
    v-bind="props"
  />
  <BranchNodeDiagram
    v-else
    v-bind="props"
  />
</template>
