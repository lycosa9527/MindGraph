<script setup lang="ts">
/**
 * Canvas toolbar — tabbed ribbon for every diagram type.
 * Mind-map-only tools stay gated inside CanvasToolbarMindMap.
 */
import type { MindMapRibbonTabId } from '@/canvas-ribbon/mindMapRibbonTypes'
import { canvasVirtualKeyboardOpen } from '@/composables/canvasToolbar/useCanvasVirtualKeyboardOpen'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'

import CanvasToolbarMindMap from './CanvasToolbarMindMap.vue'
import CanvasVirtualKeyboardPanel from './CanvasVirtualKeyboardPanel.vue'

const props = withDefaults(
  defineProps<{
    embedded?: boolean
    compactToolbar?: boolean
    ribbonTab?: MindMapRibbonTabId
  }>(),
  {
    embedded: false,
    compactToolbar: false,
    ribbonTab: 'edit',
  }
)

const useMindMapV2 = useMindMapV2Chrome()
</script>

<template>
  <div
    class="canvas-toolbar relative z-10 w-full flex justify-center"
    :class="props.embedded ? 'max-w-none' : 'max-w-[min(100vw-1rem,1200px)]'"
  >
    <div
      class="flex items-center justify-center w-full min-w-0 overflow-x-auto"
      :class="
        props.embedded
          ? 'rounded-lg p-1 bg-transparent'
          : 'rounded-xl shadow-lg p-1.5 border border-gray-200/80 dark:border-gray-600/80 bg-white/90 dark:bg-gray-800/90 backdrop-blur-md'
      "
    >
      <CanvasToolbarMindMap
        :compact="compactToolbar"
        :ribbon-tab="ribbonTab"
      />
    </div>

    <CanvasVirtualKeyboardPanel
      v-if="!useMindMapV2"
      v-model="canvasVirtualKeyboardOpen"
    />
  </div>
</template>
