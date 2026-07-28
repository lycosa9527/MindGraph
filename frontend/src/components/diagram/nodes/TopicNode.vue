<script setup lang="ts">
/**
 * TopicNode — routes mind maps to lazy legacy/v2 shells; other diagram types use TopicNodeDiagram.
 */
import { computed, defineAsyncComponent } from 'vue'

import { useMindMapCanvasVisuals } from '@/composables/mindMap/useMindMapCanvasVisuals'
import type { MindGraphNodeProps } from '@/types'

const props = defineProps<MindGraphNodeProps>()

const isMindMap = computed(
  () => props.data.diagramType === 'mindmap' || props.data.diagramType === 'mind_map'
)

const useMindMapV2 = useMindMapCanvasVisuals()

const MindMapLegacyTopicNode = defineAsyncComponent(
  () => import('./mindMap/MindMapLegacyTopicNode.vue')
)
const MindMapV2TopicNode = defineAsyncComponent(() => import('./mindMap/MindMapV2TopicNode.vue'))
const TopicNodeDiagram = defineAsyncComponent(() => import('./TopicNodeDiagram.vue'))
</script>

<template>
  <MindMapLegacyTopicNode
    v-if="isMindMap && !useMindMapV2"
    v-bind="props"
  />
  <MindMapV2TopicNode
    v-else-if="isMindMap && useMindMapV2"
    v-bind="props"
  />
  <TopicNodeDiagram
    v-else
    v-bind="props"
  />
</template>
