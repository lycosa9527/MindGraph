<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import {
  presentationRectSpotlightStyle,
  presentationSpotlightBackground,
  presentationSpotlightHoleSize,
  presentationSpotlightVisualScale,
} from '@/config/presentationSpotlight'
import {
  overlayClientPercent,
  clampSpotlightScale,
  spotlightRadius,
  spotlightShape,
  translateOverlay,
} from '@/composables/training/trainingOverlayDrag'
import type { TrainingStepOverlay } from '@/types/training'

const props = defineProps<{
  overlays: TrainingStepOverlay[]
  editable?: boolean
}>()

const rootRef = ref<HTMLElement | null>(null)
const box = ref({ width: 1, height: 1 })
let observer: ResizeObserver | null = null
let dragIndex = -1
let resizing = false
let lastX = 0
let lastY = 0

const spots = computed(() =>
  props.overlays
    .map((overlay, index) => ({ overlay, index }))
    .filter((row) => row.overlay.kind === 'spotlight')
)

function measure(): void {
  const el = rootRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  box.value = { width: rect.width || 1, height: rect.height || 1 }
}

function visualScale(overlay: TrainingStepOverlay): number {
  return presentationSpotlightVisualScale(
    spotlightRadius(overlay),
    box.value.width,
    box.value.height
  )
}

function centerPx(overlay: TrainingStepOverlay): { x: number; y: number } {
  return {
    x: ((overlay.x ?? 50) / 100) * box.value.width,
    y: ((overlay.y ?? 50) / 100) * box.value.height,
  }
}

function holeSize(overlay: TrainingStepOverlay): { halfW: number; halfH: number } {
  return presentationSpotlightHoleSize(visualScale(overlay), spotlightShape(overlay))
}

function dimStyle(overlay: TrainingStepOverlay): Record<string, string> {
  const center = centerPx(overlay)
  const scale = visualScale(overlay)
  if (spotlightShape(overlay) === 'rect') {
    return presentationRectSpotlightStyle(center.x, center.y, scale)
  }
  return {
    background: presentationSpotlightBackground(center.x, center.y, scale),
  }
}

function holeStyle(overlay: TrainingStepOverlay): Record<string, string> {
  const center = centerPx(overlay)
  const { halfW, halfH } = holeSize(overlay)
  return {
    left: `${center.x - halfW}px`,
    top: `${center.y - halfH}px`,
    width: `${halfW * 2}px`,
    height: `${halfH * 2}px`,
  }
}

function handleStyle(overlay: TrainingStepOverlay): Record<string, string> {
  const center = centerPx(overlay)
  const { halfW } = holeSize(overlay)
  return {
    left: `${center.x + halfW - 6}px`,
    top: `${center.y - 6}px`,
  }
}

function startDrag(index: number, event: PointerEvent): void {
  if (!props.editable) return
  event.preventDefault()
  event.stopPropagation()
  dragIndex = index
  resizing = false
  lastX = event.clientX
  lastY = event.clientY
  const target = event.currentTarget
  if (target instanceof Element) {
    target.setPointerCapture(event.pointerId)
  }
}

function startResize(index: number, event: PointerEvent): void {
  if (!props.editable) return
  event.preventDefault()
  event.stopPropagation()
  dragIndex = index
  resizing = true
  lastX = event.clientX
  lastY = event.clientY
  const target = event.currentTarget
  if (target instanceof Element) {
    target.setPointerCapture(event.pointerId)
  }
}

function moveDrag(event: PointerEvent): void {
  if (dragIndex < 0 || !rootRef.value) return
  const overlay = props.overlays[dragIndex]
  if (!overlay || overlay.kind !== 'spotlight') return
  if (resizing) {
    const rect = rootRef.value.getBoundingClientRect()
    const center = centerPx(overlay)
    const dist = Math.hypot(event.clientX - rect.left - center.x, event.clientY - rect.top - center.y)
    const unit = presentationSpotlightHoleSize(1, spotlightShape(overlay)).halfW
    const factor = visualScale(overlay) / spotlightRadius(overlay)
    overlay.r = clampSpotlightScale(dist / unit / (factor || 1))
    return
  }
  const prev = overlayClientPercent(rootRef.value, lastX, lastY)
  const next = overlayClientPercent(rootRef.value, event.clientX, event.clientY)
  translateOverlay(overlay, next.x - prev.x, next.y - prev.y)
  lastX = event.clientX
  lastY = event.clientY
}

function endDrag(): void {
  dragIndex = -1
  resizing = false
}

onMounted(() => {
  measure()
  observer = new ResizeObserver(measure)
  if (rootRef.value) observer.observe(rootRef.value)
})

onUnmounted(() => {
  observer?.disconnect()
})
</script>

<template>
  <div
    ref="rootRef"
    class="training-spotlight"
    :class="{ 'training-spotlight--editable': editable }"
    @pointermove="moveDrag"
    @pointerup="endDrag"
    @pointercancel="endDrag"
  >
    <div
      v-for="row in spots"
      :key="row.index"
      class="training-spotlight__dim"
      :style="dimStyle(row.overlay)"
    />
    <template v-if="editable">
      <div
        v-for="row in spots"
        :key="`hit-${row.index}`"
        class="training-spotlight__hole"
        :class="{ 'is-rect': spotlightShape(row.overlay) === 'rect' }"
        :style="holeStyle(row.overlay)"
        @pointerdown="startDrag(row.index, $event)"
      />
      <div
        v-for="row in spots"
        :key="`handle-${row.index}`"
        class="training-spotlight__handle"
        :style="handleStyle(row.overlay)"
        @pointerdown="startResize(row.index, $event)"
      />
    </template>
  </div>
</template>

<style scoped>
.training-spotlight {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}
.training-spotlight__dim {
  position: absolute;
  inset: 0;
}
.training-spotlight--editable .training-spotlight__hole,
.training-spotlight--editable .training-spotlight__handle {
  pointer-events: auto;
}
.training-spotlight__hole {
  position: absolute;
  border-radius: 999px;
  cursor: grab;
}
.training-spotlight__hole.is-rect {
  border-radius: 0.35rem;
}
.training-spotlight__hole:active {
  cursor: grabbing;
}
.training-spotlight__handle {
  position: absolute;
  z-index: 1;
  width: 12px;
  height: 12px;
  border: 1px solid #1c1917;
  border-radius: 999px;
  background: #fbbf24;
  cursor: ew-resize;
}
</style>
