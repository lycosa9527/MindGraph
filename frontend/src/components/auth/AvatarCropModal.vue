<script setup lang="ts">
/**
 * Circle crop for a custom avatar. Exports a 512×512 PNG with transparent corners.
 */
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { Crop } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage } from '@/composables/core/useLanguage'

const VIEW = 280
const OUTPUT = 512
const MIN_ZOOM = 1
const MAX_ZOOM = 4

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  src: string
  saving?: boolean
}>()

const emit = defineEmits<{
  confirm: [blob: Blob]
  invalid: []
}>()

const { t } = useLanguage()

const stageRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const zoom = ref(MIN_ZOOM)
const ready = ref(false)

let source: HTMLImageElement | null = null
let coverScale = 1
let offsetX = 0
let offsetY = 0
let drag: { x: number; y: number; ox: number; oy: number } | null = null

function clampOffsets(): void {
  if (!source) {
    return
  }
  const scale = coverScale * zoom.value
  const width = source.width * scale
  const height = source.height * scale
  offsetX = Math.min(0, Math.max(VIEW - width, offsetX))
  offsetY = Math.min(0, Math.max(VIEW - height, offsetY))
}

function draw(): void {
  const canvas = canvasRef.value
  if (!canvas || !source) {
    return
  }
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return
  }
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const px = Math.round(VIEW * dpr)
  if (canvas.width !== px || canvas.height !== px) {
    canvas.width = px
    canvas.height = px
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, VIEW, VIEW)
  clampOffsets()
  const scale = coverScale * zoom.value
  ctx.drawImage(source, offsetX, offsetY, source.width * scale, source.height * scale)
}

function fit(image: HTMLImageElement): void {
  source = image
  coverScale = Math.max(VIEW / image.width, VIEW / image.height)
  zoom.value = MIN_ZOOM
  const scale = coverScale
  offsetX = (VIEW - image.width * scale) / 2
  offsetY = (VIEW - image.height * scale) / 2
  ready.value = true
  draw()
}

function setZoom(nextZoom: number, anchorX: number, anchorY: number): void {
  const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, nextZoom))
  const prev = zoom.value
  if (next === prev || !source) {
    return
  }
  const ratio = next / prev
  offsetX = anchorX - (anchorX - offsetX) * ratio
  offsetY = anchorY - (anchorY - offsetY) * ratio
  zoom.value = next
  draw()
}

function onSlider(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) {
    return
  }
  setZoom(Number(target.value), VIEW / 2, VIEW / 2)
}

function onWheel(event: WheelEvent): void {
  const stage = stageRef.value
  if (!stage) {
    return
  }
  const rect = stage.getBoundingClientRect()
  const factor = event.deltaY < 0 ? 1.08 : 1 / 1.08
  setZoom(zoom.value * factor, event.clientX - rect.left, event.clientY - rect.top)
}

function onPointerDown(event: PointerEvent): void {
  const stage = stageRef.value
  if (!stage || !source) {
    return
  }
  stage.setPointerCapture(event.pointerId)
  drag = { x: event.clientX, y: event.clientY, ox: offsetX, oy: offsetY }
}

function onPointerMove(event: PointerEvent): void {
  if (!drag) {
    return
  }
  offsetX = drag.ox + (event.clientX - drag.x)
  offsetY = drag.oy + (event.clientY - drag.y)
  draw()
}

function onPointerUp(): void {
  drag = null
}

function exportPng(): Promise<Blob | null> {
  if (!source) {
    return Promise.resolve(null)
  }
  const canvas = document.createElement('canvas')
  canvas.width = OUTPUT
  canvas.height = OUTPUT
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return Promise.resolve(null)
  }
  const ratio = OUTPUT / VIEW
  ctx.beginPath()
  ctx.arc(OUTPUT / 2, OUTPUT / 2, OUTPUT / 2, 0, Math.PI * 2)
  ctx.clip()
  clampOffsets()
  const scale = coverScale * zoom.value * ratio
  ctx.drawImage(
    source,
    offsetX * ratio,
    offsetY * ratio,
    source.width * scale,
    source.height * scale
  )
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), 'image/png')
  })
}

async function confirmCrop(): Promise<void> {
  if (props.saving || !ready.value) {
    return
  }
  const blob = await exportPng()
  if (!blob) {
    emit('invalid')
    return
  }
  emit('confirm', blob)
}

function close(): void {
  if (!props.saving) {
    visible.value = false
  }
}

function loadSource(src: string): void {
  ready.value = false
  source = null
  if (!src) {
    return
  }
  const image = new Image()
  image.onload = () => {
    if (props.src === src) {
      fit(image)
    }
  }
  image.onerror = () => {
    if (props.src === src) {
      emit('invalid')
      visible.value = false
    }
  }
  image.src = src
}

watch(
  () => [visible.value, props.src] as const,
  async ([open, src]) => {
    if (!open || !src) {
      return
    }
    await nextTick()
    loadSource(src)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  source = null
})
</script>

<template>
  <SwissGlassCard
    v-model="visible"
    overlay-class="avatar-crop-overlay"
    :ribbon="t('auth.avatarCropRibbon')"
    ribbon-key="auth.avatarCropRibbon"
    :title="t('auth.avatarCropTitle')"
    title-key="auth.avatarCropTitle"
    :line1="t('auth.avatarCropLine')"
    line1-key="auth.avatarCropLine"
    :icon="Crop"
    persistent
    :show-close="!saving"
    @close="close"
  >
    <div class="avatar-crop">
      <div
        ref="stageRef"
        class="avatar-crop__stage"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @wheel.prevent="onWheel"
      >
        <canvas ref="canvasRef" />
        <div class="avatar-crop__ring" />
      </div>
      <label class="avatar-crop__zoom">
        <span>
          <I18nText k="auth.avatarCropZoom" />
        </span>
        <input
          type="range"
          :min="MIN_ZOOM"
          :max="MAX_ZOOM"
          step="0.01"
          :value="zoom"
          :disabled="!ready || saving"
          @input="onSlider"
        />
      </label>
    </div>
    <template #footer>
      <div class="swiss-glass-footer avatar-crop__footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          :disabled="saving"
          @click="close"
        >
          <I18nText k="common.cancel" />
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          :disabled="!ready || saving"
          @click="confirmCrop"
        >
          <I18nText k="common.save" />
        </button>
      </div>
    </template>
  </SwissGlassCard>
</template>

<style scoped>
.avatar-crop {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem 1.25rem 0.5rem;
}

.avatar-crop__stage {
  position: relative;
  width: 280px;
  height: 280px;
  border-radius: 12px;
  overflow: hidden;
  background: #e7e5e4;
  touch-action: none;
  cursor: grab;
}

.avatar-crop__stage:active {
  cursor: grabbing;
}

.avatar-crop__stage canvas {
  display: block;
  width: 280px;
  height: 280px;
}

.avatar-crop__ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  box-shadow: 0 0 0 999px rgb(15 23 42 / 46%);
  pointer-events: none;
}

.avatar-crop__zoom {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: min(280px, 100%);
  color: #44403c;
  font-size: 0.8125rem;
}

.avatar-crop__zoom input {
  flex: 1;
}

.avatar-crop__footer {
  justify-content: flex-end;
  width: 100%;
}
</style>

<style>
.avatar-crop-overlay {
  z-index: 4200;
}
</style>
