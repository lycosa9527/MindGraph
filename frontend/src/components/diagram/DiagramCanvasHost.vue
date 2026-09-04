<script setup lang="ts">
/**
 * Routes to MindMapCanvasRouter (legacy / v2 / v3) or shared DiagramCanvas for other types.
 */
import { computed } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'

import DiagramCanvas from './DiagramCanvas.vue'
import MindMapCanvasRouter from './MindMapCanvasRouter.vue'

const diagramStore = useDiagramSession()

const isMindMap = computed(
  () => diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
)
</script>

<template>
  <MindMapCanvasRouter
    v-if="isMindMap"
    v-bind="$attrs"
  >
    <template
      v-for="(_, slotName) in $slots"
      #[slotName]="slotProps"
    >
      <slot
        :name="slotName"
        v-bind="slotProps ?? {}"
      />
    </template>
  </MindMapCanvasRouter>
  <DiagramCanvas
    v-else
    v-bind="$attrs"
  >
    <template
      v-for="(_, slotName) in $slots"
      #[slotName]="slotProps"
    >
      <slot
        :name="slotName"
        v-bind="slotProps ?? {}"
      />
    </template>
  </DiagramCanvas>
</template>
