<script setup lang="ts">
/**
 * BranchNode — routes mind maps to lazy legacy/v2 shells; other diagram types use BranchNodeDiagram.
 */
import { computed, defineAsyncComponent } from 'vue'

import { useMindMapCanvasVisuals } from '@/composables/mindMap/useMindMapCanvasVisuals'
import type { MindGraphNodeProps } from '@/types'

const props = defineProps<MindGraphNodeProps>()

const isMindMap = computed(
  () => props.data.diagramType === 'mindmap' || props.data.diagramType === 'mind_map'
)

const useMindMapV2 = useMindMapCanvasVisuals()

const MindMapLegacyBranchNode = defineAsyncComponent(
  () => import('./mindMap/MindMapLegacyBranchNode.vue')
)
const MindMapV2BranchNode = defineAsyncComponent(() => import('./mindMap/MindMapV2BranchNode.vue'))
const BranchNodeDiagram = defineAsyncComponent(() => import('./BranchNodeDiagram.vue'))
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
