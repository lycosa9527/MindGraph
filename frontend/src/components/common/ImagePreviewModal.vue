<script setup lang="ts">
/**
 * ImagePreviewModal - Simple modal for previewing images.
 * The wheel zooms the picture. Dragging pans it once it is larger than the frame.
 * Supports optional navigation when images array is provided.
 */
import { computed, ref, watch } from 'vue'

import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

import { Image } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import {
  type ImagePreviewTransform,
  clampPreviewPan,
  nextPreviewScale,
  zoomAboutPoint,
} from '@/utils/imagePreviewTransform'

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

const { t } = useLanguage()

const open = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

const currentIndex = ref(0)
const stageRef = ref<HTMLElement | null>(null)
const imageRef = ref<HTMLImageElement | null>(null)
const transform = ref<ImagePreviewTransform>({ scale: 1, x: 0, y: 0 })
const panning = ref(false)

let drag: { pointerId: number; x: number; y: number; originX: number; originY: number } | null =
  null

const hasNavigation = computed(() => props.images && props.images.length > 1)

const currentImage = computed(() => {
  if (props.images && props.images.length > 0) {
    const idx = Math.min(currentIndex.value, props.images.length - 1)
    return props.images[idx]
  }
  return { title: props.title, imageUrl: props.imageUrl }
})

const canGoPrev = computed(() => hasNavigation.value && currentIndex.value > 0)
const canGoNext = computed(
  () => hasNavigation.value && props.images && currentIndex.value < props.images.length - 1
)

const imageStyle = computed(() => ({
  transform: `translate(${transform.value.x}px, ${transform.value.y}px) scale(${transform.value.scale})`,
}))

function resetTransform(): void {
  transform.value = { scale: 1, x: 0, y: 0 }
  drag = null
  panning.value = false
}

function clampToStage(next: ImagePreviewTransform): ImagePreviewTransform {
  const stage = stageRef.value
  const image = imageRef.value
  if (!stage || !image) return next
  return clampPreviewPan(
    next,
    stage.clientWidth,
    stage.clientHeight,
    image.offsetWidth,
    image.offsetHeight
  )
}

function onWheel(event: WheelEvent): void {
  const stage = stageRef.value
  if (!stage) return
  const rect = stage.getBoundingClientRect()
  const cursorX = event.clientX - rect.left - rect.width / 2
  const cursorY = event.clientY - rect.top - rect.height / 2
  const nextScale = nextPreviewScale(transform.value.scale, event.deltaY, event.deltaMode)
  transform.value = clampToStage(zoomAboutPoint(transform.value, nextScale, cursorX, cursorY))
}

function onPointerDown(event: PointerEvent): void {
  if (event.button !== 0) return
  const stage = stageRef.value
  if (!stage) return
  stage.setPointerCapture(event.pointerId)
  drag = {
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    originX: transform.value.x,
    originY: transform.value.y,
  }
  panning.value = true
}

function onPointerMove(event: PointerEvent): void {
  if (!drag || drag.pointerId !== event.pointerId) return
  transform.value = clampToStage({
    scale: transform.value.scale,
    x: drag.originX + (event.clientX - drag.x),
    y: drag.originY + (event.clientY - drag.y),
  })
}

function onPointerUp(event: PointerEvent): void {
  if (!drag || drag.pointerId !== event.pointerId) return
  drag = null
  panning.value = false
}

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

watch(
  () => [props.visible, currentIndex.value, currentImage.value.imageUrl] as const,
  () => {
    resetTransform()
  }
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
  <SwissGlassDialog
    v-model="open"
    :ribbon="t('swissGlass.hero.imagePreview.ribbon')"
    ribbon-key="swissGlass.hero.imagePreview.ribbon"
    :title="t('swissGlass.hero.imagePreview.title')"
    title-key="swissGlass.hero.imagePreview.title"
    :line1="t('swissGlass.hero.imagePreview.line1')"
    line1-key="swissGlass.hero.imagePreview.line1"
    :icon="Image"
    width="80%"
    :before-close="handleClose"
    dialog-class="image-preview-modal"
    @close="emit('close')"
  >
    <p
      v-if="currentImage.title"
      class="text-sm font-medium text-stone-700 mb-2 px-4"
    >
      {{ currentImage.title }}
    </p>
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
        <el-icon
          :size="28"
          class="mg-icon-flip-rtl"
        >
          <ArrowLeft />
        </el-icon>
      </button>

      <!-- Image: key on wrapper forces full re-render when navigating to avoid stale display -->
      <div
        :key="currentImage.imageUrl"
        ref="stageRef"
        class="image-preview-stage"
        :class="{ 'image-preview-stage--panning': panning }"
        @wheel.prevent.stop="onWheel"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
      >
        <img
          ref="imageRef"
          :src="currentImage.imageUrl"
          :alt="currentImage.title"
          draggable="false"
          :style="imageStyle"
          @dragstart.prevent
        />
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
        <el-icon
          :size="28"
          class="mg-icon-flip-rtl"
        >
          <ArrowRight />
        </el-icon>
      </button>
    </div>

    <!-- Counter for gallery mode -->
    <div
      v-if="hasNavigation && props.images"
      class="text-center text-sm text-gray-500 py-2"
    >
      {{ currentIndex + 1 }} / {{ props.images.length }}
    </div>
  </SwissGlassDialog>
</template>

<style scoped>
.image-preview-stage {
  flex: 1;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  max-height: 70vh;
  margin: 0 16px 16px;
  background: #f9fafb;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.image-preview-stage--panning {
  cursor: grabbing;
}

.image-preview-stage img {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  transform-origin: center center;
  pointer-events: none;
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
