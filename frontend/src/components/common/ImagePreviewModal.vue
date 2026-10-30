<script setup lang="ts">
/**
 * ImagePreviewModal - Simple modal for previewing images.
 * The picture opens at fit width, pinned to the top when it is taller than
 * the frame. The wheel then moves through that picture; Ctrl/Cmd+wheel, or
 * the wheel once the picture already fits, zooms. Dragging pans.
 * Supports optional navigation when images array is provided.
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

import { Image } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import {
  type ImagePreviewTransform,
  clampPreviewPan,
  fitWidthTopPan,
  nextPreviewScale,
  wheelPixels,
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
const fitted = ref(false)
const userAdjusted = ref(false)

let drag: { pointerId: number; x: number; y: number; originX: number; originY: number } | null =
  null
let resizeObserver: ResizeObserver | null = null
let fitFrame = 0

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
  userAdjusted.value = false
  fitted.value = false
  transform.value = { scale: 1, x: 0, y: 0 }
  drag = null
  panning.value = false
}

/** Size is fit-width in CSS. Pan pins a taller picture to the top of the frame. */
function applyFitWidth(): void {
  if (fitted.value && userAdjusted.value) return
  const stage = stageRef.value
  const image = imageRef.value
  if (!stage || !image) return
  const next = fitWidthTopPan(image.offsetHeight, stage.clientHeight)
  if (!next) return
  transform.value = next
  fitted.value = true
}

function syncToStage(): void {
  if (!fitted.value || !userAdjusted.value) {
    applyFitWidth()
    return
  }
  transform.value = clampToStage(transform.value)
}

function observeStage(): void {
  resizeObserver?.disconnect()
  const stage = stageRef.value
  if (!stage || typeof ResizeObserver === 'undefined') return
  resizeObserver = new ResizeObserver(() => {
    syncToStage()
  })
  resizeObserver.observe(stage)
}

function scheduleFitWidth(): void {
  applyFitWidth()
  if (fitted.value) return
  cancelAnimationFrame(fitFrame)
  fitFrame = requestAnimationFrame(() => applyFitWidth())
}

function onImageLoad(): void {
  scheduleFitWidth()
}

function onImageError(): void {
  fitted.value = true
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

function imageTallerThanFrame(): boolean {
  const stage = stageRef.value
  const image = imageRef.value
  if (!stage || !image) return false
  return image.offsetHeight * transform.value.scale > stage.clientHeight + 1
}

function onWheel(event: WheelEvent): void {
  if (!fitted.value) return
  const stage = stageRef.value
  if (!stage) return
  const zoomGesture = event.ctrlKey || event.metaKey
  if (!zoomGesture && transform.value.scale === 1 && imageTallerThanFrame()) {
    userAdjusted.value = true
    const pixels = wheelPixels(event.deltaY, event.deltaMode)
    transform.value = clampToStage({
      scale: transform.value.scale,
      x: transform.value.x,
      y: transform.value.y - pixels,
    })
    return
  }
  userAdjusted.value = true
  const rect = stage.getBoundingClientRect()
  const cursorX = event.clientX - rect.left - rect.width / 2
  const cursorY = event.clientY - rect.top - rect.height / 2
  const nextScale = nextPreviewScale(transform.value.scale, event.deltaY, event.deltaMode)
  transform.value = clampToStage(zoomAboutPoint(transform.value, nextScale, cursorX, cursorY))
}

function onPointerDown(event: PointerEvent): void {
  if (!fitted.value || event.button !== 0) return
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
  if (event.clientX !== drag.x || event.clientY !== drag.y) {
    userAdjusted.value = true
  }
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
  ([visible]) => {
    resetTransform()
    if (!visible) {
      cancelAnimationFrame(fitFrame)
      resizeObserver?.disconnect()
      resizeObserver = null
      return
    }
    void nextTick(() => scheduleFitWidth())
  }
)

watch([stageRef, imageRef], () => {
  if (!props.visible) return
  observeStage()
  const image = imageRef.value
  if (image?.complete && image.naturalWidth > 0) scheduleFitWidth()
})

onBeforeUnmount(() => {
  cancelAnimationFrame(fitFrame)
  resizeObserver?.disconnect()
  resizeObserver = null
})

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
          class="image-preview-photo"
          :class="{ 'is-fitted': fitted }"
          :src="currentImage.imageUrl"
          :alt="currentImage.title"
          draggable="false"
          :style="imageStyle"
          @load="onImageLoad"
          @error="onImageError"
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
    <p class="image-preview-hint">
      <I18nText k="swissGlass.hero.imagePreview.hint" />
    </p>
  </SwissGlassDialog>
</template>

<style scoped>
.image-preview-stage {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  max-height: 70vh;
  margin: 0 16px 8px;
  background: #f9fafb;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.image-preview-stage--panning {
  cursor: grabbing;
}

.image-preview-photo {
  width: 100%;
  height: auto;
  max-width: 100%;
  max-height: none;
  min-width: 0;
  flex-shrink: 0;
  object-fit: contain;
  transform-origin: center center;
  pointer-events: none;
  visibility: hidden;
}

.image-preview-photo.is-fitted {
  visibility: visible;
}

.image-preview-hint {
  margin: 0 16px 14px;
  text-align: center;
  font-size: 12px;
  line-height: 1.45;
  color: #9ca3af;
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
