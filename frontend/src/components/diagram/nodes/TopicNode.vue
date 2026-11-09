<script setup lang="ts">
/**
 * TopicNode — routes mind maps to legacy/v2 shells; other diagram types use TopicNodeDiagram.
 * V2 and diagram shells are eager. An async shell mounts frames after its siblings,
 * so layout places the rest of the map around an unmeasured topic, then moves it.
 */
import { computed, defineAsyncComponent } from 'vue'

import MindMapV2TopicNode from '@/components/diagram/nodes/mindMap/MindMapV2TopicNode.vue'
import { useMindMapCanvasVisuals } from '@/composables/mindMap/useMindMapCanvasVisuals'
import type { MindGraphNodeProps } from '@/types'

import TopicNodeDiagram from './TopicNodeDiagram.vue'

const props = defineProps<MindGraphNodeProps>()

const isMindMap = computed(
  () => props.data.diagramType === 'mindmap' || props.data.diagramType === 'mind_map'
)

const useMindMapV2 = useMindMapCanvasVisuals()

const MindMapLegacyTopicNode = defineAsyncComponent(
  () => import('./mindMap/MindMapLegacyTopicNode.vue')
)
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
