<script setup lang="ts">
/**
 * CanvasLayout - Full-screen layout for canvas editing
 */
import { ensureMarkdownRenderer } from '@/composables/core/useMarkdown'

void ensureMarkdownRenderer()
</script>

<template>
  <div class="canvas-layout h-screen w-screen flex flex-col overflow-hidden bg-gray-50">
    <slot />
  </div>
</template>
