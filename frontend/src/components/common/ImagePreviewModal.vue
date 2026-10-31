<script setup lang="ts">
/**
 * Simple image lightbox: dark backdrop, image, close, optional prev/next.
 * Fit-width + pan/zoom gestures stay; SwissGlass chrome is intentionally gone.
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { ArrowLeft, ArrowRight, Close } from '@element-plus/icons-vue'

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

function close(): void {
  emit('update:visible', false)
  emit('close')
}

function onKeydown(event: KeyboardEvent): void {
  if (!props.visible) return
  if (event.key === 'Escape') {
    event.preventDefault()
    close()
    return
  }
  if (event.key === 'ArrowLeft' && canGoPrev.value) {
    event.preventDefault()
    goPrev()
    return
  }
  if (event.key === 'ArrowRight' && canGoNext.value) {
    event.preventDefault()
    goNext()
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (visible && props.images && props.images.length > 0) {
      const idx = Math.min(props.initialIndex ?? 0, props.images.length - 1)
      currentIndex.value = Math.max(0, idx)
    }
    if (visible) {
      window.addEventListener('keydown', onKeydown)
      return
    }
    window.removeEventListener('keydown', onKeydown)
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
  window.removeEventListener('keydown', onKeydown)
  cancelAnimationFrame(fitFrame)
  resizeObserver?.disconnect()
  resizeObserver = null
})

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
  <Teleport to="body">
    <div
      v-if="visible"
      class="mm-image-lightbox"
      role="dialog"
      aria-modal="true"
      :aria-label="currentImage.title || title"
      @click.self="close"
    >
      <button
        type="button"
        class="mm-image-lightbox__close"
        :aria-label="'Close'"
        @click="close"
      >
        <el-icon :size="18"><Close /></el-icon>
      </button>

      <button
        v-if="hasNavigation"
        type="button"
        class="mm-image-lightbox__nav mm-image-lightbox__nav--prev"
        :disabled="!canGoPrev"
        :aria-label="'Previous'"
        @click="goPrev"
      >
        <el-icon
          :size="22"
          class="mg-icon-flip-rtl"
        >
          <ArrowLeft />
        </el-icon>
      </button>

      <div
        :key="currentImage.imageUrl"
        ref="stageRef"
        class="mm-image-lightbox__stage"
        :class="{ 'is-panning': panning }"
        @wheel.prevent.stop="onWheel"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @click.stop
      >
        <img
          ref="imageRef"
          class="mm-image-lightbox__photo"
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

      <button
        v-if="hasNavigation"
        type="button"
        class="mm-image-lightbox__nav mm-image-lightbox__nav--next"
        :disabled="!canGoNext"
        :aria-label="'Next'"
        @click="goNext"
      >
        <el-icon
          :size="22"
          class="mg-icon-flip-rtl"
        >
          <ArrowRight />
        </el-icon>
      </button>

      <p
        v-if="hasNavigation && props.images"
        class="mm-image-lightbox__count"
      >
        {{ currentIndex + 1 }} / {{ props.images.length }}
      </p>
    </div>
  </Teleport>
</template>

<style scoped>
.mm-image-lightbox {
  position: fixed;
  inset: 0;
  z-index: 4100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.72);
}

.mm-image-lightbox__close {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 2;
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  cursor: pointer;
}

.mm-image-lightbox__close:hover {
  background: rgba(255, 255, 255, 0.24);
}

.mm-image-lightbox__stage {
  width: min(92vw, 960px);
  max-height: min(88vh, 900px);
  min-height: 240px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.mm-image-lightbox__stage.is-panning {
  cursor: grabbing;
}

.mm-image-lightbox__photo {
  width: 100%;
  height: auto;
  max-width: 100%;
  object-fit: contain;
  transform-origin: center center;
  pointer-events: none;
  visibility: hidden;
}

.mm-image-lightbox__photo.is-fitted {
  visibility: visible;
}

.mm-image-lightbox__nav {
  position: absolute;
  top: 50%;
  z-index: 2;
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  transform: translateY(-50%);
  cursor: pointer;
}

.mm-image-lightbox__nav:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.24);
}

.mm-image-lightbox__nav:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.mm-image-lightbox__nav--prev {
  left: 16px;
}

.mm-image-lightbox__nav--next {
  right: 16px;
}

.mm-image-lightbox__count {
  position: absolute;
  bottom: 16px;
  left: 50%;
  margin: 0;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.82);
  font-size: 13px;
}
</style>
