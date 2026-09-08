<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import TrainingSpotlightLayer from '@/components/training/TrainingSpotlightLayer.vue'
import TrainingTextBubble from '@/components/training/TrainingTextBubble.vue'
import TrainingTopicsMark from '@/components/training/TrainingTopicsMark.vue'
import { requestTrainingTopicApply } from '@/composables/training/trainingCommands'
import {
  type ArrowHandle,
  moveArrowHandle,
  overlayClientPercent,
  translateOverlay,
} from '@/composables/training/trainingOverlayDrag'
import { stepUsesDualTopics } from '@/composables/training/trainingTopicOptions'
import {
  TRAINING_ARROW_COLORS,
  trainingArrowHex,
  trainingArrowLine,
} from '@/config/trainingMarkPalettes'
import {
  resizeRoleWidth,
  roleWidth,
  trainingRoleMarkSrc,
} from '@/config/trainingRoles'
import {
  bumpTextBubbleFont,
  resizeTextBubble,
  setTextBubbleAlign,
  setTextBubbleInk,
  setTextBubbleStroke,
  toggleTextBubbleBold,
  toggleTextBubbleItalic,
} from '@/config/trainingTextBubbles'
import type {
  TrainingCourseStep,
  TrainingStepOverlay,
  TrainingTextAlign,
  TrainingTopicOption,
} from '@/types/training'

const props = defineProps<{
  overlays: TrainingStepOverlay[]
  editable?: boolean
  selectable?: boolean
  remoteRoles?: boolean
  stillRoles?: boolean
  step?: TrainingCourseStep
}>()

const emit = defineEmits<{
  awake: []
}>()

const topicOptions = computed(() => props.step?.topic_options || [])
const dualTopics = computed(() => stepUsesDualTopics(props.step))

const rootRef = ref<HTMLElement | null>(null)
const selectedTextIndex = ref<number | null>(null)
const markScope = `ar-${Math.random().toString(36).slice(2, 10)}`
type MarkHandle = ArrowHandle | 'body' | 'role-size' | 'text-size'
let dragIndex = -1
let arrowHandle: MarkHandle = 'body'
let lastX = 0
let lastY = 0

watch(
  () => props.overlays.length,
  (length, previous) => {
    if (!props.editable || length <= (previous ?? 0)) return
    const last = length - 1
    if (props.overlays[last]?.kind === 'text') selectedTextIndex.value = last
  }
)

function onDocPointer(event: PointerEvent): void {
  const target = event.target
  if (!(target instanceof Element) || target.closest('.text-bubble')) return
  selectedTextIndex.value = null
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointer)
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocPointer)
})

function startDrag(index: number, event: PointerEvent, handle: MarkHandle = 'body'): void {
  if (!props.editable) return
  event.preventDefault()
  event.stopPropagation()
  selectedTextIndex.value = props.overlays[index]?.kind === 'text' ? index : null
  dragIndex = index
  arrowHandle = handle
  lastX = event.clientX
  lastY = event.clientY
  const capture = rootRef.value
  if (capture) capture.setPointerCapture(event.pointerId)
}

function moveDrag(event: PointerEvent): void {
  if (dragIndex < 0 || !rootRef.value) return
  const overlay = props.overlays[dragIndex]
  if (!overlay) return
  const next = overlayClientPercent(rootRef.value, event.clientX, event.clientY)
  if (overlay.kind === 'arrow' && (arrowHandle === 'start' || arrowHandle === 'end')) {
    moveArrowHandle(overlay, arrowHandle, next.x, next.y)
    return
  }
  if (overlay.kind === 'role' && arrowHandle === 'role-size') {
    resizeRoleWidth(overlay, next.x)
    return
  }
  if (overlay.kind === 'text' && arrowHandle === 'text-size') {
    resizeTextBubble(overlay, next.x, next.y)
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

function roleSrc(overlay: TrainingStepOverlay): string {
  const id = overlay.role || overlay.glyph || ''
  return trainingRoleMarkSrc(id, {
    still: props.stillRoles,
    remote: props.remoteRoles,
  })
}

function roleBox(overlay: TrainingStepOverlay): Record<string, string> {
  return {
    left: left(overlay),
    top: top(overlay),
    width: `${roleWidth(overlay)}%`,
  }
}

function left(overlay: TrainingStepOverlay): string {
  return `${overlay.x ?? 0}%`
}

function top(overlay: TrainingStepOverlay): string {
  return `${overlay.y ?? 0}%`
}

function editText(overlay: TrainingStepOverlay, text: string): void {
  overlay.text = text
  emit('awake')
}

function bumpText(overlay: TrainingStepOverlay, delta: number): void {
  bumpTextBubbleFont(overlay, delta)
  emit('awake')
}

function toggleBold(overlay: TrainingStepOverlay): void {
  toggleTextBubbleBold(overlay)
  emit('awake')
}

function toggleItalic(overlay: TrainingStepOverlay): void {
  toggleTextBubbleItalic(overlay)
  emit('awake')
}

function alignText(overlay: TrainingStepOverlay, align: TrainingTextAlign): void {
  setTextBubbleAlign(overlay, align)
  emit('awake')
}

function setInk(overlay: TrainingStepOverlay, color: string): void {
  setTextBubbleInk(overlay, color)
  emit('awake')
}

function setStroke(overlay: TrainingStepOverlay, color: string): void {
  setTextBubbleStroke(overlay, color)
  emit('awake')
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
      <TrainingTextBubble
        v-if="overlay.kind === 'text'"
        :overlay="overlay"
        :editable="editable"
        :selected="Boolean(editable && selectedTextIndex === index)"
        @select="selectedTextIndex = index"
        @edit="editText(overlay, $event)"
        @bump-font="bumpText(overlay, $event)"
        @toggle-bold="toggleBold(overlay)"
        @toggle-italic="toggleItalic(overlay)"
        @align="alignText(overlay, $event)"
        @ink="setInk(overlay, $event)"
        @stroke="setStroke(overlay, $event)"
        @drag="startDrag(index, $event)"
        @resize="startDrag(index, $event, 'text-size')"
      />
      <span
        v-else-if="overlay.kind === 'emoji'"
        class="step-marks__label step-marks__emoji"
        :style="{ left: left(overlay), top: top(overlay) }"
        @pointerdown="startDrag(index, $event)"
        >{{ overlay.glyph }}</span
      >
      <div
        v-else-if="overlay.kind === 'role'"
        class="step-marks__label step-marks__role"
        :style="roleBox(overlay)"
        @pointerdown="startDrag(index, $event)"
      >
        <img
          class="step-marks__role-img"
          :src="roleSrc(overlay)"
          alt=""
        />
        <span
          v-if="editable"
          class="step-marks__role-handle"
          @pointerdown="startDrag(index, $event, 'role-size')"
        />
      </div>
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
.step-marks__emoji {
  font-size: clamp(1.25rem, 7cqh, 2.1rem);
  line-height: 1;
}
.step-marks__role {
  max-width: none;
  line-height: 0;
}
.step-marks__role-img {
  display: block;
  width: 100%;
  height: auto;
  pointer-events: none;
  user-select: none;
}
.step-marks__role-handle {
  position: absolute;
  right: 0.05rem;
  bottom: 0.05rem;
  z-index: 3;
  width: 0.7rem;
  height: 0.7rem;
  border: 1px solid #1c1917;
  border-radius: 2px;
  background: #fafaf9;
  cursor: nwse-resize;
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
.step-marks--editable .step-marks__knob,
.step-marks--editable .step-marks__role-handle,
.step-marks--editable :deep(.text-bubble),
.step-marks--editable :deep(.text-bubble__handle) {
  pointer-events: auto;
  cursor: grab;
}
.step-marks--editable .step-marks__role-handle,
.step-marks--editable :deep(.text-bubble__handle) {
  cursor: nwse-resize;
}
.step-marks--editable :deep(.text-bubble__edit) {
  cursor: text;
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
