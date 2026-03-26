<script setup lang="ts">
/**
 * PresentationHighlightOverlay - Semi-transparent highlighter strokes in presentation mode.
 * Coordinates match LearningSheetOverlay (flow space inside viewport transform).
 */
import { computed, ref } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR } from '@/config/presentationHighlighter'
import type { PresentationHighlightStroke } from '@/types'

const props = defineProps<{
  /** When true, capture pointer events for drawing */
  active: boolean
  /** Stroke color for new paths (rgba) */
  currentColor: string
  /** Multiplier for stroke width (presentation Ctrl±) */
  pointerSizeScale?: number
}>()

const strokes = defineModel<PresentationHighlightStroke[]>({ default: () => [] })

const { screenToFlowCoordinate, viewport: vueFlowViewport, getViewport } = useVueFlow()

const viewport = computed(() => vueFlowViewport.value ?? getViewport())

const transform = computed(
  () => `translate(${viewport.value.x}, ${viewport.value.y}) scale(${viewport.value.zoom})`,
)

/** Keep apparent stroke width roughly constant on screen (flow space is scaled by zoom). */
const strokeWidthFlow = computed(() => {
  const z = viewport.value.zoom
  const s = props.pointerSizeScale ?? 1
  if (!z || z < 0.05) return 40 * s
  return (34 / z) * s
})

const showLayer = computed(() => strokes.value.length > 0 || props.active)

const isDrawing = ref(false)

function minDistSq(a: { x: number; y: number }, b: { x: number; y: number }): number {
  const dx = a.x - b.x
  const dy = a.y - b.y
  return dx * dx + dy * dy
}

const MIN_DIST = 4

function pointsToPath(points: { x: number; y: number }[]): string {
  if (points.length === 0) return ''
  let d = `M ${points[0].x} ${points[0].y}`
  for (let i = 1; i < points.length; i++) {
    d += ` L ${points[i].x} ${points[i].y}`
  }
  return d
}

function onPointerDown(e: PointerEvent) {
  if (!props.active || e.button !== 0) return
  e.preventDefault()
  e.stopPropagation()
  const p = screenToFlowCoordinate({ x: e.clientX, y: e.clientY })
  isDrawing.value = true
  strokes.value = [...strokes.value, { points: [p], color: props.currentColor }]
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  if (!props.active || !isDrawing.value) return
  e.preventDefault()
  const p = screenToFlowCoordinate({ x: e.clientX, y: e.clientY })
  const list = strokes.value
  if (list.length === 0) return
  const last = list[list.length - 1]
  const prev = last.points[last.points.length - 1]
  if (prev && minDistSq(prev, p) < MIN_DIST * MIN_DIST) return
  const nextStroke: PresentationHighlightStroke = {
    points: [...last.points, p],
    color: last.color ?? DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR,
  }
  const next = [...list]
  next[next.length - 1] = nextStroke
  strokes.value = next
}

function onPointerUp(e: PointerEvent) {
  if (!isDrawing.value) return
  isDrawing.value = false
  try {
    ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
  } catch {
    // Pointer may already be released
  }
  const list = strokes.value
  if (list.length === 0) return
  const last = list[list.length - 1]
  if (last.points.length === 1) {
    const p = last.points[0]
    const dup: PresentationHighlightStroke = {
      points: [p, { x: p.x + 0.6, y: p.y + 0.6 }],
      color: last.color ?? DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR,
    }
    const next = [...list]
    next[next.length - 1] = dup
    strokes.value = next
  }
}
</script>

<template>
  <div
    v-if="showLayer"
    class="presentation-highlight-layer absolute inset-0 w-full h-full"
    :class="props.active ? 'z-[250]' : 'z-[240] pointer-events-none'"
  >
    <svg
      class="absolute inset-0 h-full w-full overflow-visible pointer-events-none"
      aria-hidden="true"
    >
      <g :transform="transform">
        <path
          v-for="(stroke, i) in strokes"
          :key="i"
          :d="pointsToPath(stroke.points)"
          fill="none"
          :stroke="stroke.color ?? DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR"
          :stroke-width="strokeWidthFlow"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </g>
    </svg>
    <div
      v-if="props.active"
      class="absolute inset-0 touch-none"
      style="pointer-events: auto"
      @pointercancel="onPointerUp"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
    />
  </div>
</template>
