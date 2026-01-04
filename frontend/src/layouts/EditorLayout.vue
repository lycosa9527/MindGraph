<script setup lang="ts">
/**
 * Editor Layout - Full-screen editor with toolbar and canvas
 */
import { provide, ref } from 'vue'

// Provide panel visibility controls to child components
const leftPanelOpen = ref(false)
const rightPanelOpen = ref(false)

provide('leftPanelOpen', leftPanelOpen)
provide('rightPanelOpen', rightPanelOpen)

function toggleLeftPanel() {
  leftPanelOpen.value = !leftPanelOpen.value
}

function toggleRightPanel() {
  rightPanelOpen.value = !rightPanelOpen.value
}

provide('toggleLeftPanel', toggleLeftPanel)
provide('toggleRightPanel', toggleRightPanel)
</script>

<template>
  <div
    class="editor-layout h-screen w-screen overflow-hidden flex flex-col bg-gray-100 dark:bg-gray-900"
  >
    <!-- Main Content Area -->
    <main class="flex-1 relative overflow-hidden">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.editor-layout {
  --toolbar-height: 48px;
  --panel-width: 320px;
}
</style>
