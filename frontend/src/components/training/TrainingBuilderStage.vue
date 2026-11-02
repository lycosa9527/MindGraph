<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'

import TrainingInteractDock from '@/components/training/TrainingInteractDock.vue'
import TrainingSlidePreview from '@/components/training/TrainingSlidePreview.vue'
import TrainingStepMarks from '@/components/training/TrainingStepMarks.vue'
import TrainingVodPlayer from '@/components/training/TrainingVodPlayer.vue'
import { builderDiagramNodes } from '@/composables/training/builderDiagramBridge'
import { registerTrainingDragKnock } from '@/composables/training/trainingDragKnock'
import {
  nodeVodId,
  overlaysForReadNode,
  readFocusNodeId,
  toggleInteractBlank,
} from '@/composables/training/trainingInteract'
import { visibleMarkOverlays } from '@/composables/training/trainingMarkSteps'
import { overlayClientPercent } from '@/composables/training/trainingOverlayDrag'
import {
  isTrainingTopicsDrag,
  isTrainingTopicsDrop,
  setTrainingTopicsDragLive,
  useTrainingTopicsDragLive,
} from '@/composables/training/trainingTopicOptions'
import type { TrainingCourseStep } from '@/types/training'

const props = withDefaults(
  defineProps<{
    step: TrainingCourseStep
    index: number
    thumb?: string | null
    hibernated?: boolean
    playAudio?: boolean | null
    readonly?: boolean
    canNext?: boolean
    playing?: boolean
  }>(),
  { canNext: true, playAudio: null, playing: false }
)

const stageRef = ref<HTMLElement | null>(null)
const focusNodeId = computed(() => readFocusNodeId(props.step))
const marks = computed(() =>
  overlaysForReadNode(visibleMarkOverlays(props.step), focusNodeId.value)
)
const nodeVod = computed(() => nodeVodId(props.step, focusNodeId.value))
const topicsDragLive = useTrainingTopicsDragLive()
const showInteract = computed(() => {
  const interactMode = props.step.interact?.mode
  const canvas = props.step.page_key === 'canvas' || props.step.type === 'canvas'
  return canvas && (interactMode === 'read' || interactMode === 'drag' || interactMode === 'quiz')
})

const emit = defineEmits<{
  wake: []
  topics: [pos: { x: number; y: number }]
  resize: [size: { width: number; height: number }]
  next: []
}>()

const releaseDragKnock = registerTrainingDragKnock((nodeId) => {
  if (readInteractMode() !== 'drag') return
  const node = builderDiagramNodes.value.find((row) => row.id === nodeId)
  if (!node) return
  emit('wake')
  toggleInteractBlank(props.step, node)
})

function readInteractMode(): string | null {
  return props.step.interact?.mode ?? null
}

onUnmounted(releaseDragKnock)

function onStageClick(event: MouseEvent): void {
  const raw = event.target
  if (raw instanceof Element && raw.closest('.step-marks')) return
  emit('wake')
}

function onDragOver(event: DragEvent): void {
  if (!isTrainingTopicsDrag(event.dataTransfer)) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
}

function onDrop(event: DragEvent): void {
  if (!isTrainingTopicsDrop(event.dataTransfer) || !stageRef.value) return
  event.preventDefault()
  event.stopPropagation()
  const pos = overlayClientPercent(stageRef.value, event.clientX, event.clientY)
  setTrainingTopicsDragLive(false)
  emit('wake')
  emit('topics', pos)
}
</script>

<template>
  <div
    ref="stageRef"
    class="builder-stage"
    :class="{
      'builder-stage--hibernated': hibernated,
      'builder-stage--dock': showInteract && !playing,
      'builder-stage--play': playing,
    }"
    @click="hibernated ? onStageClick($event) : undefined"
  >
    <TrainingSlidePreview
      :step="step"
      :index="index"
      :thumb="hibernated ? thumb : null"
      :interactive="!hibernated"
      authoring
      :play-audio="playAudio"
      :can-next="canNext"
      @resize="emit('resize', $event)"
      @next="emit('next')"
    />
    <TrainingStepMarks
      :overlays="marks"
      :step="step"
      :editable="!readonly"
      :selectable="!readonly"
      @awake="emit('wake')"
    />
    <TrainingVodPlayer
      v-if="nodeVod"
      class="builder-stage__vod"
      :media-id="nodeVod"
      :step-key="`${step.id || index}:${focusNodeId}`"
      :can-next="false"
    />
    <TrainingInteractDock
      v-if="showInteract && !playing"
      :step="step"
      @awake="emit('wake')"
    />
    <div
      v-if="topicsDragLive && !readonly"
      class="builder-stage__catch"
      @dragover="onDragOver"
      @drop="onDrop"
    />
  </div>
</template>

<style scoped>
.builder-stage {
  position: relative;
  isolation: isolate;
  flex: 1;
  min-height: 22rem;
  overflow: hidden;
  border: 1px solid #e7e5e4;
  background: #fff;
}
.builder-stage__vod {
  position: absolute;
  left: 0.75rem;
  bottom: 0.75rem;
  z-index: 5;
}
.builder-stage--play {
  min-height: 0;
  border: 0;
}
.builder-stage--play :deep(.canvas-preview__zoom),
.builder-stage--play :deep(.live-shell__side),
.builder-stage--play :deep(.live-shell__expand) {
  display: none;
}
.builder-stage--hibernated {
  cursor: pointer;
}
.builder-stage--dock {
  --builder-dock-width: min(16rem, 42%);
}
.builder-stage--dock :deep(.canvas-preview__zoom) {
  right: calc(var(--builder-dock-width) + 0.75rem);
}
.builder-stage__catch {
  position: absolute;
  inset: 0;
  z-index: 5000;
}
.builder-stage :deep(.slide-preview) {
  height: 100%;
  overflow: hidden;
  aspect-ratio: auto;
}
.builder-stage :deep(.live-frame) {
  min-height: 100%;
}
</style>
