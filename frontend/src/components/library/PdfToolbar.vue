<script setup lang="ts">
/**
 * PdfToolbar - Complete PDF viewer toolbar with navigation and controls
 */
import { computed } from 'vue'
import {
  ZoomIn,
  ZoomOut,
  Printer,
  RotateCw,
  Bookmark,
  MapPin,
} from 'lucide-vue-next'
import { ElButton, ElInputNumber, ElSelect, ElOption } from 'element-plus'

interface Props {
  currentPage: number
  totalPages: number
  zoom: number
  canGoPrevious: boolean
  canGoNext: boolean
  isBookmarked?: boolean
  pinMode?: boolean
}

interface Emits {
  (e: 'previous-page'): void
  (e: 'next-page'): void
  (e: 'go-to-page', page: number): void
  (e: 'zoom-in'): void
  (e: 'zoom-out'): void
  (e: 'zoom-change', zoom: number): void
  (e: 'rotate'): void
  (e: 'print'): void
  (e: 'toggle-bookmark'): void
  (e: 'toggle-pin-mode'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const pageInput = computed({
  get: () => props.currentPage,
  set: (value: number | null) => {
    if (value !== null && value >= 1 && value <= props.totalPages) {
      emit('go-to-page', value)
    }
  },
})

function handlePageInput(cur: number | undefined, prev: number | undefined) {
  if (cur !== undefined && cur !== null && cur >= 1 && cur <= props.totalPages) {
    emit('go-to-page', cur)
  }
}

const baseZoomOptions = [
  { label: '50%', value: 50 },
  { label: '75%', value: 75 },
  { label: '100%', value: 100 },
  { label: '125%', value: 125 },
  { label: '150%', value: 150 },
  { label: '200%', value: 200 },
  { label: '300%', value: 300 },
]

function zoomToPercentage(zoom: number): number {
  return Math.round(zoom * 100)
}

function percentageToZoom(percentage: number): number {
  return percentage / 100
}

const zoomOptions = computed(() => {
  const currentPercentage = zoomToPercentage(props.zoom)
  const hasExactMatch = baseZoomOptions.some((opt) => opt.value === currentPercentage)
  
  const options = [...baseZoomOptions]
  
  if (!hasExactMatch && currentPercentage >= 50 && currentPercentage <= 300) {
    options.push({
      label: `${currentPercentage}%`,
      value: currentPercentage,
    })
  }
  
  return options
})

const zoomSelectValue = computed({
  get: () => {
    return zoomToPercentage(props.zoom)
  },
  set: (value: number) => {
    emit('zoom-change', percentageToZoom(value))
  },
})


function handleZoomSelectChange(value: number) {
  emit('zoom-change', value)
}
</script>

<template>
  <div class="pdf-toolbar h-12 px-4 bg-white border-b border-stone-200 flex items-center gap-2">
    <!-- Page Number -->
    <div class="flex items-center gap-1 text-sm text-stone-600">
      <ElInputNumber
        v-model="pageInput"
        :min="1"
        :max="totalPages"
        :precision="0"
        size="small"
        class="w-16"
        @change="handlePageInput"
      />
      <span class="text-stone-500">/ {{ totalPages }}</span>
    </div>

    <div class="flex-1" />

    <!-- Zoom Controls -->
    <div class="flex items-center gap-1">
      <ElButton
        text
        size="small"
        class="toolbar-button"
        @click="emit('zoom-out')"
      >
        <ZoomOut class="w-4 h-4" />
      </ElButton>
      <ElSelect
        v-model="zoomSelectValue"
        size="small"
        class="zoom-select"
        :teleported="false"
        @change="handleZoomSelectChange"
      >
        <ElOption
          v-for="option in zoomOptions"
          :key="`zoom-${option.value}`"
          :label="option.label"
          :value="option.value"
        />
      </ElSelect>
      <ElButton
        text
        size="small"
        class="toolbar-button"
        @click="emit('zoom-in')"
      >
        <ZoomIn class="w-4 h-4" />
      </ElButton>
    </div>

    <!-- Action Controls -->
    <div class="flex items-center gap-1 border-l border-stone-200 pl-2 ml-2">
      <ElButton
        text
        size="small"
        :class="['toolbar-button', { 'is-active': pinMode }]"
        title="添加评论"
        @click="emit('toggle-pin-mode')"
      >
        <MapPin
          :class="['w-4 h-4', { 'fill-current': pinMode }]"
        />
      </ElButton>
      <ElButton
        text
        size="small"
        :class="['toolbar-button', { 'is-active': isBookmarked }]"
        title="书签"
        @click="emit('toggle-bookmark')"
      >
        <Bookmark
          :class="['w-4 h-4', { 'fill-current': isBookmarked }]"
        />
      </ElButton>
      <ElButton
        text
        size="small"
        class="toolbar-button"
        title="旋转"
        @click="emit('rotate')"
      >
        <RotateCw class="w-4 h-4" />
      </ElButton>
      <ElButton
        text
        size="small"
        class="toolbar-button"
        title="打印"
        @click="emit('print')"
      >
        <Printer class="w-4 h-4" />
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
.pdf-toolbar {
  flex-shrink: 0;
}

.toolbar-button {
  --el-button-text-color: #57534e;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #f5f5f4;
  --el-button-disabled-text-color: #d6d3d1;
}

.toolbar-button.is-active {
  --el-button-text-color: #1c1917;
  --el-button-bg-color: #f5f5f4;
  background-color: #f5f5f4;
}

.nav-button {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-text-color: #ffffff;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
  --el-button-hover-text-color: #ffffff;
  --el-button-disabled-bg-color: #e7e5e4;
  --el-button-disabled-border-color: #e7e5e4;
  --el-button-disabled-text-color: #a8a29e;
}

:deep(.el-input-number) {
  --el-input-number-control-width: 24px;
}

:deep(.el-input-number__decrease),
:deep(.el-input-number__increase) {
  width: 24px;
  height: 24px;
}

.zoom-select {
  width: 80px;
}

:deep(.zoom-select .el-input__wrapper) {
  padding: 0 8px;
  box-shadow: none;
  border: 1px solid #d6d3d1;
  border-radius: 4px;
}

:deep(.zoom-select .el-input__wrapper:hover) {
  border-color: #a8a29e;
}

:deep(.zoom-select.is-focus .el-input__wrapper) {
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px #3b82f6;
}
</style>
