<script setup lang="ts">
/**
 * Mind map legacy canvas shell — lazy-loaded; locks variant to classic curved layout.
 */
import DiagramCanvas from './DiagramCanvas.vue'
</script>

<template>
  <DiagramCanvas
    mind-map-variant="legacy"
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
