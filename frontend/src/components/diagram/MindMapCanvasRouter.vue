<script setup lang="ts">
/**
 * Lazy-loads exactly one mind map canvas shell (legacy or v2).
 * Remounts on mode switch so only the active variant's chunk is used.
 */
import { computed, defineAsyncComponent } from 'vue'

import { useFeatureFlagsStore, useUIStore } from '@/stores'
import { effectiveMindMapCanvasMode } from '@/utils/mindMapCanvasMode'

const uiStore = useUIStore()
const featureFlagsStore = useFeatureFlagsStore()

const effectiveMode = computed(() =>
  effectiveMindMapCanvasMode(
    uiStore.mindMapCanvasMode,
    featureFlagsStore.getFeatureMindmapV2Canvas()
  )
)

const MindMapLegacyCanvas = defineAsyncComponent(() => import('./MindMapLegacyCanvas.vue'))
const MindMapV2Canvas = defineAsyncComponent(() => import('./MindMapV2Canvas.vue'))
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
