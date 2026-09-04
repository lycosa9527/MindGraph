<script setup lang="ts">
/**
 * Routes mind maps to classic (V1) or V2 Vue Flow.
 * V3 bubble-style chrome is swapped on CanvasPage; this router still mounts V2.
 */
import { computed, defineAsyncComponent } from 'vue'

import MindMapV2Canvas from '@/components/diagram/MindMapV2Canvas.vue'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { resolveSessionMindMapCanvasMode } from '@/utils/mindMapCanvasMode'

const diagramStore = useDiagramSession()

const effectiveMode = computed(() =>
  resolveSessionMindMapCanvasMode(diagramStore.mindMapCanvasMode)
)

const MindMapLegacyCanvas = defineAsyncComponent(() => import('./MindMapLegacyCanvas.vue'))
</script>

<template>
  <MindMapLegacyCanvas
    v-if="effectiveMode === 'legacy'"
    :key="'mindmap-legacy'"
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
  </MindMapLegacyCanvas>
  <MindMapV2Canvas
    v-else
    :key="'mindmap-v2'"
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
  </MindMapV2Canvas>
</template>
