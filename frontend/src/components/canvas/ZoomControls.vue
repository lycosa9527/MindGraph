<script setup lang="ts">
/**
 * ZoomControls - Bottom right zoom and view controls
 * Improved with Element Plus components and better styling
 */
import { computed, ref, watch } from 'vue'

import { ElButton, ElOption, ElSelect, ElTooltip } from 'element-plus'

import { Hand, Maximize2, Minus, Play, Plus, Square } from 'lucide-vue-next'

import { ZOOM } from '@/config/uiConfig'
import { useLanguage } from '@/composables'

const { isZh } = useLanguage()

const ZOOM_OPTIONS = [
  { label: '50%', value: 50 },
  { label: '75%', value: 75 },
  { label: '100%', value: 100 },
  { label: '125%', value: 125 },
] as const

const props = withDefaults(
  defineProps<{
    /** Canvas zoom (0.1-4) - when provided, display syncs with canvas */
    zoom?: number | null
    /** When true, presentation button shows exit state */
    isPresentationMode?: boolean
  }>(),
  { zoom: null, isPresentationMode: false }
)

const zoomLevel = ref(100)
const isHandToolActive = ref(false)

const displayZoom = computed(() =>
  props.zoom != null ? Math.round(props.zoom * 100) : zoomLevel.value
)

const zoomOptions = computed(() => {
  const current = displayZoom.value
  const minPct = Math.round(ZOOM.MIN * 100)
  const maxPct = Math.round(ZOOM.MAX * 100)
  const hasExact = ZOOM_OPTIONS.some((opt) => opt.value === current)
  const options: Array<{ label: string; value: number }> = [...ZOOM_OPTIONS]
  if (!hasExact && current >= minPct && current <= maxPct) {
    options.push({ label: `${current}%`, value: current })
    options.sort((a, b) => a.value - b.value)
  }
  return options
})

const zoomSelectValue = computed({
  get: () => displayZoom.value,
  set: (value: number) => {
    zoomLevel.value = value
    if (value === 100) {
      emit('fit-to-screen')
    } else {
      emit('zoom-change', value)
    }
  },
})

watch(
  () => props.zoom,
  (z) => {
    if (z != null) {
      zoomLevel.value = Math.round(z * 100)
    }
  },
  { immediate: true }
)

function handleZoomIn() {
  emit('zoom-in')
}

function handleZoomOut() {
  emit('zoom-out')
}

function handleZoomReset() {
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
  (e: 'zoom-in'): void
  (e: 'zoom-out'): void
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

      <!-- Zoom level dropdown -->
      <ElSelect
        v-model="zoomSelectValue"
        size="small"
        class="zoom-select"
        :teleported="false"
      >
        <ElOption
          v-for="opt in zoomOptions"
          :key="`zoom-${opt.value}`"
          :label="opt.label"
          :value="opt.value"
        />
      </ElSelect>

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

      <!-- Presentation mode / Exit fullscreen -->
      <ElTooltip
        :content="
          props.isPresentationMode
            ? (isZh ? '退出全屏' : 'Exit Fullscreen')
            : (isZh ? '演示模式' : 'Presentation')
        "
        placement="top"
      >
        <ElButton
          text
          size="small"
          :class="['zoom-btn', 'presentation', { active: props.isPresentationMode }]"
          @click="handlePresentation"
        >
          <Square
            v-if="props.isPresentationMode"
            class="w-4 h-4"
          />
          <Play
            v-else
            class="w-4 h-4"
          />
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

/* Zoom level dropdown */
.zoom-select {
  min-width: 72px;
  font-size: 12px;
}

:deep(.zoom-select .el-input__wrapper) {
  padding: 4px 8px;
  box-shadow: none;
  background-color: transparent;
}

:deep(.zoom-select .el-input__wrapper:hover) {
  background-color: #e5e7eb;
}

:deep(.zoom-select.is-focus .el-input__wrapper) {
  background-color: #e5e7eb;
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

:deep(.zoom-btn.presentation.active) {
  background-color: #d1fae5 !important;
  color: #047857 !important;
}

/* Dark mode */
:deep(.dark) .divider {
  background-color: #4b5563;
}

:deep(.dark .zoom-select .el-input__wrapper) {
  background-color: transparent;
}

:deep(.dark .zoom-select .el-input__wrapper:hover),
:deep(.dark .zoom-select.is-focus .el-input__wrapper) {
  background-color: #4b5563;
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

:deep(.dark .zoom-btn.presentation.active) {
  background-color: #064e3b !important;
  color: #6ee7b7 !important;
}
</style>
