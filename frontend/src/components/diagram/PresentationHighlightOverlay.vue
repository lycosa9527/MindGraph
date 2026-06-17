<script setup lang="ts">
/**
 * PresentationHighlightOverlay - highlighter + classroom pen strokes in flow space.
 */
import { computed, onUnmounted, ref } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR } from '@/config/presentationHighlighter'
import type { PresentationHighlightStroke } from '@/types'

const props = withDefaults(
  defineProps<{
    active: boolean
    currentColor: string
    pointerSizeScale?: number
    strokeWidthRoleScale?: number
    /** Pen uses tighter sampling + smooth curves for handwriting */
    mode?: 'pen' | 'highlighter'
  }>(),
  {
    mode: 'highlighter',
  }
)

const strokes = defineModel<PresentationHighlightStroke[]>({ default: () => [] })

const { screenToFlowCoordinate, viewport: vueFlowViewport, getViewport } = useVueFlow()

const viewport = computed(() => vueFlowViewport.value ?? getViewport())

const transform = computed(
  () => `translate(${viewport.value.x}, ${viewport.value.y}) scale(${viewport.value.zoom})`
)

const isPen = computed(() => props.mode === 'pen')

function resolveStrokeTool(stroke: PresentationHighlightStroke): 'pen' | 'highlighter' {
  if (stroke.strokeTool) return stroke.strokeTool
  const role = stroke.strokeRoleScale ?? props.strokeWidthRoleScale ?? 1
  return role >= 1.2 ? 'highlighter' : 'pen'
}

function strokeWidthFlowForStroke(stroke: PresentationHighlightStroke): number {
  const z = Math.max(viewport.value.zoom, 0.08)
  const s = stroke.pointerScale ?? props.pointerSizeScale ?? 1
  const role = stroke.strokeRoleScale ?? props.strokeWidthRoleScale ?? 1
  const base = resolveStrokeTool(stroke) === 'pen' ? 2.75 : 8.5
  return (base / z) * s * role
}

const showLayer = computed(() => strokes.value.length > 0 || props.active)

const isDrawing = ref(false)
let rafId: number | null = null
const pendingPoints: { x: number; y: number }[] = []

function minScreenDistSq(
  a: { x: number; y: number },
  b: { x: number; y: number },
  zoom: number
): number {
  const dx = (a.x - b.x) * zoom
  const dy = (a.y - b.y) * zoom
  return dx * dx + dy * dy
}

function shouldAppendPoint(
  prev: { x: number; y: number },
  next: { x: number; y: number },
  zoom: number,
  pen: boolean
): boolean {
  const minPx = pen ? 0.85 : 3.5
  return minScreenDistSq(prev, next, zoom) >= minPx * minPx
}

function pointsToPath(points: { x: number; y: number }[], pen: boolean): string {
  if (points.length === 0) return ''
  if (!pen || points.length < 3) {
    let d = `M ${points[0].x} ${points[0].y}`
    for (let i = 1; i < points.length; i++) {
      d += ` L ${points[i].x} ${points[i].y}`
    }
    return d
  }

  let d = `M ${points[0].x} ${points[0].y}`
  for (let i = 1; i < points.length - 1; i++) {
    const cx = points[i].x
    const cy = points[i].y
    const nx = (points[i].x + points[i + 1].x) / 2
    const ny = (points[i].y + points[i + 1].y) / 2
    d += ` Q ${cx} ${cy} ${nx} ${ny}`
  }
  const last = points[points.length - 1]
  d += ` L ${last.x} ${last.y}`
  return d
}

function appendFlowPoint(p: { x: number; y: number }): void {
  const list = strokes.value
  if (list.length === 0) return
  const last = list[list.length - 1]
  const prev = last.points[last.points.length - 1]
  const pen = resolveStrokeTool(last) === 'pen'
  if (prev && !shouldAppendPoint(prev, p, viewport.value.zoom, pen)) return

  const nextStroke: PresentationHighlightStroke = {
    points: [...last.points, p],
    color: last.color ?? DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR,
    pointerScale: last.pointerScale,
    strokeRoleScale: last.strokeRoleScale,
    strokeTool: last.strokeTool,
  }
  const next = [...list]
  next[next.length - 1] = nextStroke
  strokes.value = next
}

function flushPendingPoints(): void {
  rafId = null
  for (const p of pendingPoints) {
    appendFlowPoint(p)
  }
  pendingPoints.length = 0
}

function queueFlowPoint(p: { x: number; y: number }): void {
  pendingPoints.push(p)
  if (rafId === null) {
    rafId = requestAnimationFrame(flushPendingPoints)
  }
}

function ingestPointerEvents(event: PointerEvent): void {
  const coalesced = event.getCoalescedEvents?.() ?? [event]
  for (const ev of coalesced) {
    queueFlowPoint(screenToFlowCoordinate({ x: ev.clientX, y: ev.clientY }))
  }
}

function onPointerDown(e: PointerEvent) {
  if (!props.active || e.button !== 0) return
  e.preventDefault()
  e.stopPropagation()
  const p = screenToFlowCoordinate({ x: e.clientX, y: e.clientY })
  isDrawing.value = true
  pendingPoints.length = 0
  const pointerScale = props.pointerSizeScale ?? 1
  const strokeRoleScale = props.strokeWidthRoleScale ?? 1
  strokes.value = [
    ...strokes.value,
    {
      points: [p],
      color: props.currentColor,
      pointerScale,
      strokeRoleScale,
      strokeTool: props.mode,
    },
  ]
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  if (!props.active || !isDrawing.value) return
  e.preventDefault()
  ingestPointerEvents(e)
}

function onPointerUp(e: PointerEvent) {
  if (!isDrawing.value) return
  isDrawing.value = false
  ingestPointerEvents(e)
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    flushPendingPoints()
  }
  try {
    ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
  } catch {
    /* already released */
  }
  const list = strokes.value
  if (list.length === 0) return
  const last = list[list.length - 1]
  if (last.points.length === 1) {
    const p = last.points[0]
    const dup: PresentationHighlightStroke = {
      points: [p, { x: p.x + 0.35, y: p.y + 0.35 }],
      color: last.color ?? DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR,
      pointerScale: last.pointerScale,
      strokeRoleScale: last.strokeRoleScale,
      strokeTool: last.strokeTool,
    }
    const next = [...list]
    next[next.length - 1] = dup
    strokes.value = next
  }
}

onUnmounted(() => {
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
  }
})
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
          :d="pointsToPath(stroke.points, resolveStrokeTool(stroke) === 'pen')"
          fill="none"
          :stroke="stroke.color ?? DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR"
          :stroke-width="strokeWidthFlowForStroke(stroke)"
          stroke-linecap="round"
          stroke-linejoin="round"
          :style="resolveStrokeTool(stroke) === 'pen' ? { paintOrder: 'stroke fill' } : undefined"
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
