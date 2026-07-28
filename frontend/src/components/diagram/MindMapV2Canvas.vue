<script setup lang="ts">
/**
 * Mind map v2 canvas shell — lazy-loaded; locks variant and mounts v2-only overlays.
 */
import DiagramCanvas from './DiagramCanvas.vue'
import MindMapV2CanvasOverlays from './MindMapV2CanvasOverlays.vue'
</script>

<template>
  <DiagramCanvas
    mind-map-variant="v2"
    v-bind="$attrs"
  >
    <template #v2-canvas-overlays="overlayScope">
      <MindMapV2CanvasOverlays v-bind="overlayScope" />
    </template>
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
