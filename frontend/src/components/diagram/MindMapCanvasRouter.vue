<script setup lang="ts">
/**
 * Mind maps always use the new (V2) Vue Flow canvas.
 */
import MindMapV2Canvas from '@/components/diagram/MindMapV2Canvas.vue'
</script>

<template>
  <MindMapV2Canvas
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
