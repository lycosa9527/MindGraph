<script setup lang="ts">
/**
 * ZoomControls - Bottom right zoom and view controls
 * Migrated from prototype MindGraphCanvasPage zoom controls
 */
import { ref } from 'vue'

import { Hand, Maximize2, Minus, Play, Plus } from 'lucide-vue-next'

const zoomLevel = ref(100)
const isHandToolActive = ref(false)

function handleZoomIn() {
  zoomLevel.value = Math.min(zoomLevel.value + 10, 200)
  emit('zoom-change', zoomLevel.value)
}

function handleZoomOut() {
  zoomLevel.value = Math.max(zoomLevel.value - 10, 50)
  emit('zoom-change', zoomLevel.value)
}

function handleZoomReset() {
  zoomLevel.value = 100
  emit('zoom-change', zoomLevel.value)
  emit('fit-to-screen')
}

function toggleHandTool() {
  isHandToolActive.value = !isHandToolActive.value
  emit('hand-tool-toggle', isHandToolActive.value)
}

function handlePresentation() {
  emit('start-presentation')
}

const emit = defineEmits<{
  (e: 'zoom-change', level: number): void
  (e: 'fit-to-screen'): void
  (e: 'hand-tool-toggle', active: boolean): void
  (e: 'start-presentation'): void
}>()

defineExpose({
  zoomLevel,
  isHandToolActive,
})
</script>

<template>
  <div
    class="zoom-controls absolute right-4 bottom-4 bg-white border border-gray-200 rounded-lg shadow-md p-1 flex items-center"
  >
    <!-- Hand tool -->
    <button
      class="p-1.5 rounded-md hover:bg-gray-100 transition-colors"
      :class="isHandToolActive ? 'bg-blue-50 text-blue-600' : 'text-gray-600'"
      title="抓手工具"
      @click="toggleHandTool"
    >
      <Hand class="w-4 h-4" />
    </button>

    <div class="h-5 border-r border-gray-200 mx-1" />

    <!-- Zoom out -->
    <button
      class="p-1.5 rounded-md hover:bg-gray-100 transition-colors text-gray-600"
      title="缩小"
      @click="handleZoomOut"
    >
      <Minus class="w-4 h-4" />
    </button>

    <!-- Zoom level -->
    <span class="px-2 text-xs text-gray-600 min-w-[45px] text-center">{{ zoomLevel }}%</span>

    <!-- Zoom in -->
    <button
      class="p-1.5 rounded-md hover:bg-gray-100 transition-colors text-gray-600"
      title="放大"
      @click="handleZoomIn"
    >
      <Plus class="w-4 h-4" />
    </button>

    <div class="h-5 border-r border-gray-200 mx-1" />

    <!-- Fit to screen -->
    <button
      class="p-1.5 rounded-md hover:bg-gray-100 transition-colors text-gray-600"
      title="适应画布"
      @click="handleZoomReset"
    >
      <Maximize2 class="w-4 h-4" />
    </button>

    <div class="h-5 border-r border-gray-200 mx-1" />

    <!-- Presentation mode -->
    <button
      class="p-1.5 rounded-md hover:bg-gray-100 transition-colors text-gray-600"
      title="演示"
      @click="handlePresentation"
    >
      <Play class="w-4 h-4" />
    </button>
  </div>
</template>
