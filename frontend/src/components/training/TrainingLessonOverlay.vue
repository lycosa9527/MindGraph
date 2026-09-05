<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import TrainingStepMarks from '@/components/training/TrainingStepMarks.vue'
import { liveLessonCoversMedia, liveLessonStep } from '@/composables/training/applyTrainingSnapshot'
import { visibleMarkOverlays } from '@/composables/training/trainingMarkSteps'
import { useTrainingStore } from '@/stores/training'
import { shouldSkipTrainingFollow } from '@/utils/trainingClient'

const route = useRoute()
const training = useTrainingStore()

const liveStep = computed(() =>
  liveLessonStep(training.snapshot, {
    skip: shouldSkipTrainingFollow(),
    trainingRoute: route.path.startsWith('/training'),
  })
)
const coverMedia = computed(() => liveLessonCoversMedia(liveStep.value))
const marks = computed(() => (liveStep.value ? visibleMarkOverlays(liveStep.value) : []))
const visible = computed(() => Boolean(liveStep.value && (coverMedia.value || marks.value.length)))
</script>

<template>
  <div
    v-if="visible && liveStep"
    class="lesson-overlay"
    :class="{
      'lesson-overlay--media': coverMedia,
      'lesson-overlay--marks': !coverMedia,
    }"
  >
    <img
      v-if="coverMedia && liveStep.type === 'slide' && liveStep.asset_url"
      class="lesson-overlay__media"
      :src="liveStep.asset_url"
      alt=""
    />
    <video
      v-else-if="coverMedia && liveStep.type === 'video' && liveStep.asset_url"
      class="lesson-overlay__media"
      :src="liveStep.asset_url"
      controls
    />
    <TrainingStepMarks
      :overlays="marks"
      :step="liveStep"
      selectable
      remote-roles
    />
  </div>
</template>

<style scoped>
.lesson-overlay {
  position: fixed;
  inset: 0;
}
.lesson-overlay--media {
  z-index: 40;
  background: #111827;
}
.lesson-overlay--marks {
  z-index: 4200;
  background: transparent;
  pointer-events: none;
}
.lesson-overlay__media {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
</style>
