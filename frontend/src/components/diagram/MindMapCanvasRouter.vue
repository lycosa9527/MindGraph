<script setup lang="ts">
/**
 * Routes mind maps to legacy or v2 canvas shells.
 * V2 is eager — async canvas was the dominant library-open delay (~1–2s to first shell mount).
 * Legacy stays lazy (rare mode switch).
 * Mode comes from the injected diagram session (editor syncs UI; Showcase uses gallery policy).
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
