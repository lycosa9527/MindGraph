<script setup lang="ts">
/**
 * CanvasChrome — sticky wrapper for the merged canvas top bar (header + editing toolbar in one row).
 */
</script>

<template>
  <header
    class="canvas-chrome shrink-0 sticky top-0 z-30 w-full shadow-sm"
  >
    <slot />
  </header>
</template>
