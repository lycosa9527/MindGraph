<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

import TrainingSpotlightLayer from '@/components/training/TrainingSpotlightLayer.vue'
import TrainingTopicsMark from '@/components/training/TrainingTopicsMark.vue'
import {
  TRAINING_ARROW_COLORS,
  trainingArrowHex,
  trainingArrowLine,
} from '@/config/trainingMarkPalettes'
import {
  moveArrowHandle,
  overlayClientPercent,
  translateOverlay,
  type ArrowHandle,
} from '@/composables/training/trainingOverlayDrag'
import { requestTrainingTopicApply } from '@/composables/training/trainingCommands'
import { stepUsesDualTopics } from '@/composables/training/trainingTopicOptions'
import type { TrainingCourseStep, TrainingStepOverlay, TrainingTopicOption } from '@/types/training'

const props = defineProps<{
  overlays: TrainingStepOverlay[]
  editable?: boolean
  selectable?: boolean
  step?: TrainingCourseStep
}>()

const emit = defineEmits<{
  awake: []
}>()

const topicOptions = computed(() => props.step?.topic_options || [])
const dualTopics = computed(() => stepUsesDualTopics(props.step))

const rootRef = ref<HTMLElement | null>(null)
const markScope = `ar-${Math.random().toString(36).slice(2, 10)}`
let dragIndex = -1
let arrowHandle: ArrowHandle | 'body' = 'body'
let lastX = 0
let lastY = 0

function startDrag(index: number, event: PointerEvent, handle: ArrowHandle | 'body' = 'body'): void {
  if (!props.editable) return
  event.preventDefault()
  event.stopPropagation()
  dragIndex = index
  arrowHandle = handle
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
  if (!overlay) return
  const next = overlayClientPercent(rootRef.value, event.clientX, event.clientY)
  if (overlay.kind === 'arrow' && arrowHandle !== 'body') {
    moveArrowHandle(overlay, arrowHandle, next.x, next.y)
    return
  }
  const prev = overlayClientPercent(rootRef.value, lastX, lastY)
  translateOverlay(overlay, next.x - prev.x, next.y - prev.y)
  lastX = event.clientX
  lastY = event.clientY
}

function endDrag(): void {
  dragIndex = -1
  arrowHandle = 'body'
}

function left(overlay: TrainingStepOverlay): string {
  return `${overlay.x ?? 0}%`
}

function top(overlay: TrainingStepOverlay): string {
  return `${overlay.y ?? 0}%`
}

async function pickTopic(overlay: TrainingStepOverlay, option: TrainingTopicOption): Promise<void> {
  if (!props.selectable) return
  overlay.text = option.id
  emit('awake')
  await nextTick()
  requestTrainingTopicApply(option)
}

function markerId(overlay: TrainingStepOverlay): string {
  return `${markScope}-${overlay.color || 'red'}`
}

function strokeWidth(overlay: TrainingStepOverlay): number {
  return trainingArrowLine(overlay.line) === 'thick' ? 2.6 : 1.4
}

function dashArray(overlay: TrainingStepOverlay): string | undefined {
  return trainingArrowLine(overlay.line) === 'dashed' ? '3.2 2.4' : undefined
}
</script>

<template>
  <div
    ref="rootRef"
    class="step-marks"
    :class="{ 'step-marks--editable': editable }"
    @pointermove="moveDrag"
    @pointerup="endDrag"
    @pointercancel="endDrag"
  >
    <TrainingSpotlightLayer
      :overlays="overlays"
      :editable="editable"
    />
    <svg
      class="step-marks__svg"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
    >
      <defs>
        <marker
          v-for="swatch in TRAINING_ARROW_COLORS"
          :id="`${markScope}-${swatch.key}`"
          :key="swatch.key"
          markerWidth="6"
          markerHeight="6"
          refX="5"
          refY="3"
          orient="auto"
        >
          <path
            d="M0,0 L6,3 L0,6 Z"
            :fill="swatch.hex"
          />
        </marker>
      </defs>
      <template
        v-for="(overlay, index) in overlays"
        :key="`arrow-${index}`"
      >
        <line
          v-if="overlay.kind === 'arrow'"
          class="step-marks__hit"
          :x1="overlay.x"
          :y1="overlay.y"
          :x2="overlay.x2"
          :y2="overlay.y2"
          :stroke="trainingArrowHex(overlay.color)"
          :stroke-width="strokeWidth(overlay)"
          :stroke-dasharray="dashArray(overlay)"
          stroke-linecap="round"
          :marker-end="`url(#${markerId(overlay)})`"
          @pointerdown="startDrag(index, $event, 'body')"
        />
      </template>
    </svg>
    <template
      v-for="(overlay, index) in overlays"
      :key="`label-${index}`"
    >
      <span
        v-if="overlay.kind === 'text'"
        class="step-marks__label step-marks__text"
        :style="{ left: left(overlay), top: top(overlay) }"
        @pointerdown="startDrag(index, $event)"
      >{{ overlay.text }}</span>
      <span
        v-else-if="overlay.kind === 'emoji'"
        class="step-marks__label step-marks__emoji"
        :style="{ left: left(overlay), top: top(overlay) }"
        @pointerdown="startDrag(index, $event)"
      >{{ overlay.glyph }}</span>
      <div
        v-else-if="overlay.kind === 'topics'"
        class="step-marks__label step-marks__topics"
        :class="{ 'is-static': !selectable }"
        :style="{ left: left(overlay), top: top(overlay) }"
        @pointerdown="startDrag(index, $event)"
      >
        <TrainingTopicsMark
          :options="topicOptions"
          :dual="dualTopics"
          :selected-id="overlay.text"
          :selectable="Boolean(selectable)"
          @pick="pickTopic(overlay, $event)"
        />
      </div>
      <template v-else-if="overlay.kind === 'arrow' && editable">
        <span
          class="step-marks__knob"
          :style="{ left: left(overlay), top: top(overlay) }"
          @pointerdown="startDrag(index, $event, 'start')"
        />
        <span
          class="step-marks__knob"
          :style="{ left: `${overlay.x2 ?? 0}%`, top: `${overlay.y2 ?? 0}%` }"
          @pointerdown="startDrag(index, $event, 'end')"
        />
      </template>
    </template>
  </div>
</template>

<style scoped>
.step-marks {
  position: absolute;
  inset: 0;
  z-index: 4200;
  container-type: size;
  pointer-events: none;
}
.step-marks__svg {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.step-marks__label {
  position: absolute;
  z-index: 2;
  max-width: 42%;
  transform: translate(-50%, -50%);
  line-height: 1.25;
  white-space: pre-wrap;
}
.step-marks__text {
  color: #1c1917;
  font-size: clamp(0.95rem, 3.4cqh, 1.35rem);
  font-weight: 600;
}
.step-marks__emoji {
  font-size: clamp(1.25rem, 7cqh, 2.1rem);
  line-height: 1;
}
.step-marks__knob {
  position: absolute;
  z-index: 3;
  width: 0.7rem;
  height: 0.7rem;
  border: 1px solid #1c1917;
  border-radius: 999px;
  background: #fafaf9;
  transform: translate(-50%, -50%);
  cursor: grab;
}
.step-marks__topics {
  pointer-events: auto;
  max-width: min(16rem, 46%);
}
.step-marks__topics.is-static {
  pointer-events: none;
}
.step-marks--editable .step-marks__hit,
.step-marks--editable .step-marks__label,
.step-marks--editable .step-marks__knob {
  pointer-events: auto;
  cursor: grab;
}
.step-marks--editable .step-marks__topics {
  cursor: grab;
}
.step-marks--editable .step-marks__hit:active,
.step-marks--editable .step-marks__label:active,
.step-marks--editable .step-marks__knob:active {
  cursor: grabbing;
}
</style>
