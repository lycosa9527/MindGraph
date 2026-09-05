<script setup lang="ts">
import { computed, nextTick, onUnmounted, watch } from 'vue'

import TrainingPageLiveFrame from '@/components/training/TrainingPageLiveFrame.vue'
import TrainingPlayControls from '@/components/training/TrainingPlayControls.vue'
import TrainingStepMarks from '@/components/training/TrainingStepMarks.vue'
import { useLanguage } from '@/composables'
import { applyTrainingUiTarget } from '@/composables/training/applyTrainingUiTarget'
import { isTrainingMediaStep } from '@/composables/training/trainingBuilderHibernate'
import { hasTrainingLivePreview } from '@/config/trainingPageLive'
import { visibleMarkOverlays } from '@/composables/training/trainingMarkSteps'
import type { TrainingCourseStep } from '@/types/training'

const props = defineProps<{
  step: TrainingCourseStep
  canPrev?: boolean
  canNext?: boolean
  free?: boolean
}>()

const emit = defineEmits<{
  close: []
  prev: []
  next: []
  free: []
}>()

const { t } = useLanguage()
const isMedia = computed(() => isTrainingMediaStep(props.step))
const showLive = computed(
  () => !isMedia.value && hasTrainingLivePreview(props.step.page_key)
)
const topics = computed(() => props.step.topic_options || [])
const marks = computed(() => visibleMarkOverlays(props.step))

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}

watch(
  () => [props.step.modal_key, props.step.focus_key, showLive.value] as const,
  ([modalKey, focusKey, live]) => {
    if (!live) return
    void nextTick().then(() => applyTrainingUiTarget({ modalKey, focusKey }))
  },
  { immediate: true }
)

window.addEventListener('keydown', onKey)
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div
    class="teacher-preview"
    role="dialog"
    :aria-label="t('training.builder.preview')"
  >
    <p class="teacher-preview__kicker">{{ t('training.builder.previewHint') }}</p>
    <div
      v-if="topics.length"
      class="teacher-preview__chips"
    >
      <span
        v-for="option in topics"
        :key="option.id"
        class="teacher-preview__chip"
      >{{ option.label }}</span>
    </div>
    <div class="teacher-preview__stage">
      <img
        v-if="isMedia && step.type === 'slide' && step.asset_url"
        class="teacher-preview__media"
        :src="step.asset_url"
        alt=""
      >
      <video
        v-else-if="isMedia && step.type === 'video' && step.asset_url"
        class="teacher-preview__media"
        :src="step.asset_url"
        controls
      />
      <TrainingPageLiveFrame
        v-else-if="showLive"
        :page-key="step.page_key"
        :diagram-type="step.diagram_type"
        :canvas-mode="step.mindmap_canvas_mode"
        interactive
      />
      <p
        v-else
        class="teacher-preview__empty"
      >
        {{ t('training.builder.previewEmpty') }}
      </p>
      <TrainingStepMarks
        :overlays="marks"
        :step="step"
        selectable
      />
      <TrainingPlayControls
        class="teacher-preview__pad"
        :can-prev="canPrev"
        :can-next="canNext"
        :free="free"
        @prev="emit('prev')"
        @next="emit('next')"
        @stop="emit('close')"
        @free="emit('free')"
      />
    </div>
  </div>
</template>

<style scoped>
.teacher-preview {
  position: absolute;
  inset: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  background: #111827;
}
.teacher-preview__kicker {
  flex-shrink: 0;
  margin: 0;
  padding: 0.45rem 0.85rem;
  background: #1c1917;
  color: #fafaf9;
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.04em;
}
.teacher-preview__chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.65rem 0.85rem 0;
}
.teacher-preview__chip {
  border: 1px solid #e7e5e4;
  border-radius: 999px;
  background: #fff;
  padding: 0.2rem 0.7rem;
  color: #1c1917;
  font-size: 0.8rem;
}
.teacher-preview__stage {
  position: relative;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}
.teacher-preview__media {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.teacher-preview__empty {
  display: grid;
  height: 100%;
  place-items: center;
  margin: 0;
  color: #e7e5e4;
  font-size: 0.9rem;
}
.teacher-preview__pad {
  position: absolute;
  right: 1rem;
  bottom: 1rem;
  z-index: 40;
}
</style>
