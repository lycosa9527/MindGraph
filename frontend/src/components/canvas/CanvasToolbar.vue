<script setup lang="ts">
/**
 * Canvas editing toolbar. Every live diagram type uses the ribbon tools.
 * The archived glass toolbar is not mounted, including while the diagram type is still loading.
 */
import type { MindMapRibbonTabId } from '@/canvas-ribbon/mindMapRibbonTypes'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar'

import CanvasToolbarMindMap from './CanvasToolbarMindMap.vue'
import CanvasVirtualKeyboardPanel from './CanvasVirtualKeyboardPanel.vue'

const props = withDefaults(
  defineProps<{
    /** Flatter styles inside CanvasTopBar. */
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

const { isConceptMap, virtualKeyboardOpen } = useCanvasToolbarApps()
</script>

<template>
  <div
    class="canvas-toolbar relative z-10 w-full flex justify-center"
    :class="props.embedded ? 'max-w-none' : 'max-w-[min(100vw-1rem,1200px)]'"
  >
    <div
      class="flex items-center justify-center w-full min-w-0 overflow-x-auto"
      :class="props.embedded ? 'rounded-lg p-1 bg-transparent' : 'rounded-lg p-1'"
    >
      <CanvasToolbarMindMap
        :compact="compactToolbar"
        :ribbon-tab="ribbonTab"
      />
    </div>

    <CanvasVirtualKeyboardPanel
      v-if="isConceptMap"
      v-model="virtualKeyboardOpen"
    />
  </div>
</template>
