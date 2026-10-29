<script setup lang="ts">
/**
 * CanvasLayout - Full-screen layout for canvas editing
 */
import { ensureMarkdownRenderer } from '@/composables/core/useMarkdown'

void ensureMarkdownRenderer()
</script>

<template>
  <div class="canvas-layout mg-visual-viewport-shell flex flex-col bg-gray-50">
    <slot />
  </div>
</template>

<style>
html:has(.canvas-layout),
html:has(.canvas-layout) body,
html:has(.canvas-layout) #app {
  height: var(--mg-vvh, 100dvh);
  max-height: var(--mg-vvh, 100dvh);
  overflow: hidden;
}
</style>
