<script setup lang="ts">
import { computed } from 'vue'

import TrainingPageLiveFrame from '@/components/training/TrainingPageLiveFrame.vue'
import TrainingStepMarks from '@/components/training/TrainingStepMarks.vue'
import { useLanguage } from '@/composables'
import { markStepCount, visibleMarkOverlays } from '@/composables/training/trainingMarkSteps'
import { hasTrainingLivePreview } from '@/config/trainingPageLive'
import { trainingPageDef } from '@/config/trainingPages'
import type { TrainingCourseStep } from '@/types/training'

const props = defineProps<{
  step: TrainingCourseStep
  index: number
  compact?: boolean
  interactive?: boolean
  thumb?: string | null
}>()

const { t } = useLanguage()

const page = computed(() => trainingPageDef(props.step.page_key))
const pageLabel = computed(() =>
  page.value ? t(page.value.labelKey) : t('training.builder.upload')
)
const diagramLabel = computed(() => {
  const type = props.step.diagram_type
  if (!type || props.step.page_key !== 'canvas') return ''
  return t(`sidebar.diagramType.${type}`)
})
const hasThumb = computed(() => Boolean(props.thumb))
const hasMedia = computed(() => Boolean(props.step.asset_url))
const isVideo = computed(() => props.step.type === 'video')
const showLive = computed(() => {
  if (props.compact || hasThumb.value || hasMedia.value) return false
  return hasTrainingLivePreview(props.step.page_key)
})
const showMarks = computed(() => props.compact)
const marks = computed(() => visibleMarkOverlays(props.step, markStepCount(props.step)))
</script>

<template>
  <div
    class="slide-preview"
    :class="{ 'slide-preview--compact': compact }"
  >
    <img
      v-if="hasThumb"
      class="slide-preview__thumb"
      :src="thumb || ''"
      alt=""
    />
    <img
      v-else-if="hasMedia && !isVideo"
      class="slide-preview__media"
      :src="step.asset_url || ''"
      alt=""
    />
    <video
      v-else-if="hasMedia && isVideo && !compact"
      class="slide-preview__media"
      :src="step.asset_url || ''"
    />
    <TrainingPageLiveFrame
      v-else-if="showLive"
      :page-key="step.page_key"
      :diagram-type="step.diagram_type"
      :canvas-mode="step.mindmap_canvas_mode"
      :interactive="interactive"
    />
    <div
      v-else
      class="slide-preview__fallback"
    >
      <p>{{ pageLabel }}</p>
      <p
        v-if="diagramLabel"
        class="slide-preview__diagram"
      >
        {{ diagramLabel }}
      </p>
    </div>
    <TrainingStepMarks
      v-if="showMarks"
      :overlays="marks"
      :step="step"
    />
    <span class="slide-preview__index">{{ index + 1 }}</span>
  </div>
</template>

<style scoped>
.slide-preview {
  position: relative;
  overflow: hidden;
  border: 1px solid #e7e5e4;
  background: #fff;
  aspect-ratio: 16 / 10;
}
.slide-preview--compact {
  width: 100%;
}
.slide-preview__thumb {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #fff;
}
.slide-preview__media {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.slide-preview--compact :deep(.step-marks) {
  z-index: 1;
}
.slide-preview--compact :deep(.text-bubble) {
  border-radius: 0.4rem;
  box-shadow: none;
}
.slide-preview--compact :deep(.text-bubble__face) {
  padding: 0.08rem 0.12rem;
  font-size: 0.48rem;
}
.slide-preview--compact :deep(.text-bubble__bar),
.slide-preview--compact :deep(.text-bubble__handle) {
  display: none;
}
.slide-preview--compact :deep(.step-marks__emoji) {
  font-size: 0.7rem;
}
.slide-preview--compact :deep(.step-marks__role-handle) {
  display: none;
}
.slide-preview--compact :deep(.topics-mark) {
  min-width: 3.6rem;
  max-width: 6.4rem;
  padding: 0.12rem 0.2rem;
  font-size: 0.4rem;
  box-shadow: none;
}
.slide-preview__fallback {
  display: grid;
  height: 100%;
  place-items: center;
  background: #f8fafc;
  color: #1c1917;
  font-size: 0.85rem;
  font-weight: 650;
  text-align: center;
}
.slide-preview__diagram {
  margin: 0.2rem 0 0;
  color: #78716c;
  font-size: 0.65rem;
  font-weight: 500;
}
.slide-preview__index {
  position: absolute;
  right: 0.35rem;
  bottom: 0.3rem;
  z-index: 3;
  color: #78716c;
  font-size: 0.65rem;
  font-weight: 600;
}
</style>
