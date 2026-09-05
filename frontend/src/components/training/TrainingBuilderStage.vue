<script setup lang="ts">
import { computed, ref } from 'vue'

import TrainingSlidePreview from '@/components/training/TrainingSlidePreview.vue'
import TrainingStepMarks from '@/components/training/TrainingStepMarks.vue'
import { visibleMarkOverlays } from '@/composables/training/trainingMarkSteps'
import { overlayClientPercent } from '@/composables/training/trainingOverlayDrag'
import {
  isTrainingTopicsDrag,
  isTrainingTopicsDrop,
  setTrainingTopicsDragLive,
  useTrainingTopicsDragLive,
} from '@/composables/training/trainingTopicOptions'
import type { TrainingCourseStep } from '@/types/training'

const props = defineProps<{
  step: TrainingCourseStep
  index: number
  thumb?: string | null
  hibernated?: boolean
}>()

const stageRef = ref<HTMLElement | null>(null)
const marks = computed(() => visibleMarkOverlays(props.step))
const topicsDragLive = useTrainingTopicsDragLive()

const emit = defineEmits<{
  wake: []
  topics: [pos: { x: number; y: number }]
}>()

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
    :class="{ 'builder-stage--hibernated': hibernated }"
    @click="hibernated ? onStageClick($event) : undefined"
  >
    <TrainingSlidePreview
      :step="step"
      :index="index"
      :thumb="hibernated ? thumb : null"
      :interactive="!hibernated"
    />
    <TrainingStepMarks
      :overlays="marks"
      :step="step"
      editable
      selectable
      @awake="emit('wake')"
    />
    <div
      v-if="topicsDragLive"
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
.builder-stage--hibernated {
  cursor: pointer;
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
