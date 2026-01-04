<script setup lang="ts">
/**
 * CanvasPage - Full canvas editor page
 * Migrated from prototype MindGraphCanvasPage
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { AIModelSelector, CanvasToolbar, CanvasTopBar, ZoomControls } from '@/components/canvas'
import { useDiagramStore } from '@/stores'

const route = useRoute()
// diagramStore reserved for future canvas functionality
const _diagramStore = useDiagramStore()

const canvasRef = ref<HTMLDivElement | null>(null)
const zoomLevel = ref(100)
const isHandToolActive = ref(false)

const chartType = computed(() => (route.query.type as string) || '复流程图')

function handleZoomChange(level: number) {
  zoomLevel.value = level
}

function handleFitToScreen() {
  zoomLevel.value = 100
}

function handleHandToolToggle(active: boolean) {
  isHandToolActive.value = active
}

function handleStartPresentation() {
  // TODO: Implement presentation mode
}

function handleModelChange(model: string) {
  // TODO: Handle AI model change
  console.log('Selected model:', model)
}

onMounted(() => {
  // Initialize canvas
  console.log('Canvas page mounted with chart type:', chartType.value)
})
</script>

<template>
  <div class="canvas-page flex flex-col h-screen bg-gray-50">
    <!-- Top navigation bar -->
    <CanvasTopBar />

    <!-- Floating toolbar -->
    <CanvasToolbar />

    <!-- Main canvas area -->
    <div class="flex-1 relative overflow-hidden pt-16">
      <div
        ref="canvasRef"
        class="absolute inset-0 flex items-center justify-center transition-transform duration-200"
        :style="{
          transform: `scale(${zoomLevel / 100})`,
          cursor: isHandToolActive ? 'grab' : 'default',
        }"
      >
        <!-- Demo diagram content -->
        <div class="relative w-[800px] h-[600px]">
          <!-- Main event node -->
          <div class="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2">
            <div
              class="w-48 h-16 bg-blue-600 text-white flex items-center justify-center rounded-lg border-2 border-blue-700 shadow-md"
            >
              <span class="font-medium">主要事件</span>
            </div>
          </div>

          <!-- Cause 1 node -->
          <div class="absolute left-1/4 top-1/3">
            <div
              class="w-40 h-14 bg-blue-100 text-blue-800 flex items-center justify-center rounded-lg border-2 border-blue-300"
            >
              <span>原因1</span>
            </div>
          </div>

          <!-- Cause 2 node -->
          <div class="absolute left-1/4 top-2/3">
            <div
              class="w-40 h-14 bg-blue-100 text-blue-800 flex items-center justify-center rounded-lg border-2 border-blue-300"
            >
              <span>原因2</span>
            </div>
          </div>

          <!-- Result 1 node -->
          <div class="absolute right-1/4 top-1/3">
            <div
              class="w-40 h-14 bg-blue-100 text-blue-800 flex items-center justify-center rounded-lg border-2 border-blue-300"
            >
              <span>结果1</span>
            </div>
          </div>

          <!-- Result 2 node -->
          <div class="absolute right-1/4 top-2/3">
            <div
              class="w-40 h-14 bg-blue-100 text-blue-800 flex items-center justify-center rounded-lg border-2 border-blue-300"
            >
              <span>结果2</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Zoom controls (bottom right) -->
    <ZoomControls
      @zoom-change="handleZoomChange"
      @fit-to-screen="handleFitToScreen"
      @hand-tool-toggle="handleHandToolToggle"
      @start-presentation="handleStartPresentation"
    />

    <!-- AI model selector (bottom center) -->
    <AIModelSelector @model-change="handleModelChange" />
  </div>
</template>
