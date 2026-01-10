<script setup lang="ts">
/**
 * ZoomControls - Bottom right zoom and view controls
 * Improved with Element Plus components and better styling
 */
import { ref } from 'vue'

import { ElButton, ElTooltip } from 'element-plus'

import { Hand, Maximize2, Minus, Play, Plus } from 'lucide-vue-next'

import { useLanguage } from '@/composables'

const { isZh } = useLanguage()

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
  <div class="zoom-controls absolute right-4 bottom-4 z-20">
    <div
      class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg p-1.5 flex items-center gap-0.5"
    >
      <!-- Hand tool -->
      <ElTooltip
        :content="isZh ? '抓手工具' : 'Hand Tool'"
        placement="top"
      >
        <ElButton
          text
          size="small"
          :class="['zoom-btn', isHandToolActive ? 'active' : '']"
          @click="toggleHandTool"
        >
          <Hand class="w-4 h-4" />
        </ElButton>
      </ElTooltip>

      <div class="divider" />

      <!-- Zoom out -->
      <ElTooltip
        :content="isZh ? '缩小' : 'Zoom Out'"
        placement="top"
      >
        <ElButton
          text
          size="small"
          class="zoom-btn"
          @click="handleZoomOut"
        >
          <Minus class="w-4 h-4" />
        </ElButton>
      </ElTooltip>

      <!-- Zoom level display -->
      <div class="zoom-level">{{ zoomLevel }}%</div>

      <!-- Zoom in -->
      <ElTooltip
        :content="isZh ? '放大' : 'Zoom In'"
        placement="top"
      >
        <ElButton
          text
          size="small"
          class="zoom-btn"
          @click="handleZoomIn"
        >
          <Plus class="w-4 h-4" />
        </ElButton>
      </ElTooltip>

      <div class="divider" />

      <!-- Fit to screen -->
      <ElTooltip
        :content="isZh ? '适应画布' : 'Fit to Screen'"
        placement="top"
      >
        <ElButton
          text
          size="small"
          class="zoom-btn"
          @click="handleZoomReset"
        >
          <Maximize2 class="w-4 h-4" />
        </ElButton>
      </ElTooltip>

      <div class="divider" />

      <!-- Presentation mode -->
      <ElTooltip
        :content="isZh ? '演示模式' : 'Presentation'"
        placement="top"
      >
        <ElButton
          text
          size="small"
          class="zoom-btn presentation"
          @click="handlePresentation"
        >
          <Play class="w-4 h-4" />
        </ElButton>
      </ElTooltip>
    </div>
  </div>
</template>

<style scoped>
/* Divider between button groups */
.divider {
  height: 20px;
  width: 1px;
  background-color: #e5e7eb;
  margin: 0 4px;
}

/* Zoom level display */
.zoom-level {
  min-width: 48px;
  text-align: center;
  font-size: 12px;
  font-weight: 500;
  color: #4b5563;
  padding: 0 4px;
  user-select: none;
}

/* Button styling */
:deep(.zoom-btn) {
  padding: 6px !important;
  margin: 0 !important;
  min-height: auto !important;
  height: auto !important;
  border-radius: 6px !important;
  border: none !important;
  color: #6b7280 !important;
  transition: all 0.15s ease !important;
}

:deep(.zoom-btn:hover) {
  background-color: #e5e7eb !important;
  color: #374151 !important;
}

:deep(.zoom-btn:active) {
  background-color: #d1d5db !important;
}

/* Active hand tool state */
:deep(.zoom-btn.active) {
  background-color: #dbeafe !important;
  color: #2563eb !important;
}

:deep(.zoom-btn.active:hover) {
  background-color: #bfdbfe !important;
}

/* Presentation button - subtle accent */
:deep(.zoom-btn.presentation) {
  color: #059669 !important;
}

:deep(.zoom-btn.presentation:hover) {
  background-color: #d1fae5 !important;
  color: #047857 !important;
}

/* Dark mode */
:deep(.dark) .divider {
  background-color: #4b5563;
}

:deep(.dark) .zoom-level {
  color: #d1d5db;
}

:deep(.dark .zoom-btn) {
  color: #9ca3af !important;
}

:deep(.dark .zoom-btn:hover) {
  background-color: #4b5563 !important;
  color: #f3f4f6 !important;
}

:deep(.dark .zoom-btn:active) {
  background-color: #374151 !important;
}

:deep(.dark .zoom-btn.active) {
  background-color: #1e3a5f !important;
  color: #60a5fa !important;
}

:deep(.dark .zoom-btn.presentation) {
  color: #34d399 !important;
}

:deep(.dark .zoom-btn.presentation:hover) {
  background-color: #064e3b !important;
  color: #6ee7b7 !important;
}
</style>
