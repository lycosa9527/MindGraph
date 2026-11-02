<script setup lang="ts">
import { computed, nextTick, onUnmounted, watch } from 'vue'

import TrainingDragChipTray from '@/components/training/TrainingDragChipTray.vue'
import TrainingDragHintModal from '@/components/training/TrainingDragHintModal.vue'
import TrainingPageLiveFrame from '@/components/training/TrainingPageLiveFrame.vue'
import TrainingPlayControls from '@/components/training/TrainingPlayControls.vue'
import TrainingStepMarks from '@/components/training/TrainingStepMarks.vue'
import TrainingVodPlayer from '@/components/training/TrainingVodPlayer.vue'
import { useLanguage } from '@/composables'
import type { TrainingSteerMode } from '@/composables/training/applyTrainingSnapshot'
import { applyTrainingUiTarget } from '@/composables/training/applyTrainingUiTarget'
import { isTrainingMediaStep } from '@/composables/training/trainingBuilderHibernate'
import {
  nodeVodId,
  overlaysForReadNode,
  readFocusNodeId,
} from '@/composables/training/trainingInteract'
import { visibleMarkOverlays } from '@/composables/training/trainingMarkSteps'
import { hasTrainingLivePreview } from '@/config/trainingPageLive'
import type { TrainingCourseStep } from '@/types/training'

const props = withDefaults(
  defineProps<{
    step: TrainingCourseStep
    canPrev?: boolean
    canNext?: boolean
    free?: boolean
    showMode?: boolean
  }>(),
  {
    canPrev: false,
    canNext: false,
    free: false,
    showMode: true,
  }
)

const emit = defineEmits<{
  close: []
  prev: []
  next: []
  mode: [value: TrainingSteerMode]
  resize: [size: { width: number; height: number }]
}>()

const { t } = useLanguage()
const isMedia = computed(() => isTrainingMediaStep(props.step))
const isCanvas = computed(() => props.step.page_key === 'canvas' || props.step.type === 'canvas')
const showLive = computed(() => !isMedia.value && hasTrainingLivePreview(props.step.page_key))
const topics = computed(() => props.step.topic_options || [])
const focusNodeId = computed(() => readFocusNodeId(props.step))
const marks = computed(() =>
  overlaysForReadNode(visibleMarkOverlays(props.step), focusNodeId.value)
)
const nodeVod = computed(() => nodeVodId(props.step, focusNodeId.value))
const usesDrag = computed(
  () =>
    isCanvas.value &&
    props.step.interact?.mode === 'drag' &&
    props.step.interact.sequence_saved === true &&
    (props.step.interact.blanks?.length ?? 0) > 0
)
const usesGuidedReading = computed(
  () => props.step.interact?.mode === 'read' && props.step.interact.sequence_saved === true
)

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}

watch(
  () => [props.step.modal_key, props.step.focus_key, props.step.ui_lock, showLive.value] as const,
  ([modalKey, focusKey, uiLock, live]) => {
    if (!live) return
    void nextTick().then(() =>
      applyTrainingUiTarget({
        modalKey,
        focusKey,
        uiLock: uiLock || modalKey,
        hostModals: false,
      })
    )
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
    :class="{ 'teacher-preview--canvas': isCanvas, 'teacher-preview--drag': usesDrag }"
    role="dialog"
    :aria-label="t('training.builder.preview')"
  >
    <p class="teacher-preview__kicker">
      <I18nText k="training.builder.previewHint" />
      <span
        v-if="usesGuidedReading"
        class="teacher-preview__interact"
      >
        <I18nText k="training.builder.interactPlayRead" />
      </span>
    </p>
    <div
      v-if="topics.length"
      class="teacher-preview__chips"
    >
      <span
        v-for="option in topics"
        :key="option.id"
        class="teacher-preview__chip"
        >{{ option.label }}</span
      >
    </div>
    <div class="teacher-preview__stage">
      <img
        v-if="isMedia && step.type === 'slide' && step.asset_url"
        class="teacher-preview__media"
        :src="step.asset_url"
        alt=""
      />
      <video
        v-else-if="isMedia && step.type === 'video' && step.asset_url"
        class="teacher-preview__media"
        :src="step.asset_url"
        controls
      />
      <TrainingPageLiveFrame
        v-else-if="showLive && !isCanvas"
        :page-key="step.page_key"
        :diagram-type="step.diagram_type"
        :step="step"
        interactive
        use-builder-chrome
      />
      <p
        v-else-if="!isCanvas"
        class="teacher-preview__empty"
      >
        <I18nText k="training.builder.previewEmpty" />
      </p>
      <TrainingVodPlayer
        v-if="!isCanvas && (nodeVod || step.vod_media_id)"
        class="teacher-preview__vod"
        :media-id="nodeVod || step.vod_media_id || ''"
        :autoplay="Boolean(step.vod_autoplay)"
        :width="step.vod_width"
        :height="step.vod_height"
        :step-key="step.id || 'preview'"
        :can-next="canNext"
        @resize="emit('resize', $event)"
        @next="emit('next')"
      />
      <TrainingStepMarks
        v-if="!isCanvas"
        :overlays="marks"
        :step="step"
        portaled
        remote-roles
        selectable
      />
      <TrainingDragChipTray
        v-if="isCanvas && usesDrag"
        class="teacher-preview__drag-list"
        :step="step"
      />
      <TrainingDragHintModal v-if="isCanvas && usesDrag" />
      <TrainingPlayControls
        class="teacher-preview__pad"
        :can-prev="canPrev"
        :can-next="canNext"
        :mode="free ? 'free' : 'pull'"
        :show-mode="showMode"
        @prev="emit('prev')"
        @next="emit('next')"
        @stop="emit('close')"
        @mode="emit('mode', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.teacher-preview {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  flex-direction: column;
  background: #111827;
}
.teacher-preview--canvas {
  background: transparent;
  pointer-events: none;
}
.teacher-preview--canvas .teacher-preview__kicker,
.teacher-preview--canvas .teacher-preview__pad,
.teacher-preview--canvas .teacher-preview__chips,
.teacher-preview--canvas .teacher-preview__drag-list {
  pointer-events: auto;
}
.teacher-preview__drag-list {
  position: absolute;
  top: 0.75rem;
  right: 0;
  z-index: 40;
  width: min(16rem, 42%);
  max-height: calc(100% - 5.5rem);
}
.teacher-preview__kicker {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 0.6rem;
  margin: 0;
  padding: 0.45rem 0.85rem;
  background: #1c1917;
  color: #fafaf9;
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.04em;
}
.teacher-preview--canvas .teacher-preview__kicker {
  position: absolute;
  top: 0.55rem;
  left: 50%;
  z-index: 2;
  width: max-content;
  max-width: calc(100% - 8rem);
  transform: translateX(-50%);
  border-radius: 999px;
}
.teacher-preview__interact {
  border-radius: 999px;
  background: #eef2ff;
  padding: 0.15rem 0.55rem;
  color: #4338ca;
  letter-spacing: 0;
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
.teacher-preview__vod {
  position: absolute;
  left: 0.75rem;
  bottom: 0.75rem;
  z-index: 30;
}
.teacher-preview__pad {
  position: absolute;
  right: max(1rem, env(safe-area-inset-right, 0px));
  bottom: max(1rem, env(safe-area-inset-bottom, 0px));
  z-index: 40;
  overflow: visible;
}
</style>
