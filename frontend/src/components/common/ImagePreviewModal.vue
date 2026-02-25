<script setup lang="ts">
/**
 * ImagePreviewModal - Simple modal for previewing images
 * Supports optional navigation when images array is provided
 */
import { computed, ref, watch } from 'vue'

import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
  title: string
  imageUrl: string
  /** Optional: when provided with length > 1, shows prev/next navigation */
  images?: Array<{ title: string; imageUrl: string }>
  /** Optional: initial index when images array is provided */
  initialIndex?: number
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

const currentIndex = ref(0)

const hasNavigation = computed(
  () => props.images && props.images.length > 1
)

const currentImage = computed(() => {
  if (props.images && props.images.length > 0) {
    const idx = Math.min(currentIndex.value, props.images.length - 1)
    return props.images[idx]
  }
  return { title: props.title, imageUrl: props.imageUrl }
})

const canGoPrev = computed(() => hasNavigation.value && currentIndex.value > 0)
const canGoNext = computed(
  () =>
    hasNavigation.value &&
    props.images &&
    currentIndex.value < props.images.length - 1
)

// Only sync currentIndex when modal opens - avoid resetting on parent re-renders
watch(
  () => props.visible,
  (visible) => {
    if (visible && props.images && props.images.length > 0) {
      const idx = Math.min(props.initialIndex ?? 0, props.images.length - 1)
      currentIndex.value = Math.max(0, idx)
    }
  },
  { immediate: true }
)

function handleClose(done?: () => void) {
  emit('close')
  if (typeof done === 'function') {
    done()
  } else {
    emit('update:visible', false)
  }
}

function goPrev() {
  if (canGoPrev.value) {
    currentIndex.value -= 1
  }
}

function goNext() {
  if (canGoNext.value) {
    currentIndex.value += 1
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="currentImage.title"
    :show-close="true"
    :close-on-click-modal="true"
    width="80%"
    :before-close="handleClose"
    class="image-preview-modal"
  >

    <div class="relative flex items-center">
      <!-- Prev button -->
      <button
        v-if="hasNavigation"
        type="button"
        class="nav-btn nav-btn-prev"
        :disabled="!canGoPrev"
        :aria-label="'Previous'"
        @click="goPrev"
      >
        <el-icon :size="28"><ArrowLeft /></el-icon>
      </button>

      <!-- Image -->
      <div class="flex-1 overflow-auto p-4 flex items-center justify-center bg-gray-50 min-h-[400px]">
        <img
          :key="currentIndex"
          :src="currentImage.imageUrl"
          :alt="currentImage.title"
          class="max-w-full max-h-[70vh] object-contain"
        >
      </div>

      <!-- Next button -->
      <button
        v-if="hasNavigation"
        type="button"
        class="nav-btn nav-btn-next"
        :disabled="!canGoNext"
        :aria-label="'Next'"
        @click="goNext"
      >
        <el-icon :size="28"><ArrowRight /></el-icon>
      </button>
    </div>

    <!-- Counter for gallery mode -->
    <div
      v-if="hasNavigation && images"
      class="text-center text-sm text-gray-500 py-2"
    >
      {{ currentIndex + 1 }} / {{ images.length }}
    </div>
  </el-dialog>
</template>

<style scoped>
.image-preview-modal :deep(.el-dialog__body) {
  padding: 0;
}

.nav-btn {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e5e7eb;
  border-radius: 50%;
  background: white;
  color: #374151;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.nav-btn:hover:not(:disabled) {
  cursor: pointer;
  border-color: #3b82f6;
  color: #3b82f6;
  background: #f8fafc;
}

.nav-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.nav-btn-prev {
  margin-left: 12px;
}

.nav-btn-next {
  margin-right: 12px;
}
</style>
